"""Main FastAPI application with full integration"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import numpy as np
from loguru import logger

from multi_tenant.tenant_middleware import get_tenant_id  # kept for the /demo route only
from ab_testing.ab_engine import choose_model, log_ab_result
from models.risk_model import get_model, train_and_save_models
from feature_store.feature_service import get_feature_store, FEATURE_COLUMNS
from vector_store.faiss_store import get_vector_store
from messaging.kafka_service import get_kafka_producer
from monitoring.metrics import (
    record_prediction,
    record_ab_assignment,
    record_ab_outcome,
    get_metrics,
    get_metrics_content_type,
)
from mlflow_tracking.tracker import get_mlflow_tracker
from rag.explain import explain_prediction, answer_policy_question, explain_fraud_risk
from product_auth.qr_service import generate_serial, generate_qr_svg
from product_auth.scan_service import compute_scan_features
from product_auth.fraud_model import get_fraud_model, FEATURE_COLUMNS as FRAUD_FEATURE_COLUMNS
from core import db
from auth.security import (
    get_current_user,
    check_rate_limit,
    authenticate_user,
    create_access_token,
    generate_api_key,
    require_role,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SaaS AI Risk Platform...")
    db.init_db()
    get_feature_store()
    get_mlflow_tracker()
    logger.info("SaaS AI Risk Platform ready!")
    yield


app = FastAPI(
    title="SaaS AI Risk Platform",
    description="Multi-tenant ML risk prediction platform with A/B testing",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    user_id: int
    features: Optional[Dict[str, float]] = None


class PredictResponse(BaseModel):
    tenant: str
    data: Dict[str, Any]


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SimilarCustomersRequest(BaseModel):
    customer_id: int
    k: int = 5


class ABOutcomeRequest(BaseModel):
    user_id: int
    model_version: str
    outcome: str


class ExplainRequest(BaseModel):
    customer_id: int


class PolicyQuestionRequest(BaseModel):
    question: str


class RegisterProductRequest(BaseModel):
    product_name: str


class ScanRequest(BaseModel):
    serial: str
    latitude: float
    longitude: float


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/metrics")
def metrics():
    return Response(content=get_metrics(), media_type=get_metrics_content_type())


@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(username=request.username, tenant_id=user["tenant_id"], roles=user["roles"])
    return LoginResponse(access_token=token)


@app.post("/auth/api-key")
async def create_api_key(user: Dict = Depends(require_role("admin"))):
    """Generate a new API key for the caller's own tenant (admin only)."""
    api_key = generate_api_key(user["tenant_id"])
    return {"api_key": api_key, "tenant_id": user["tenant_id"]}


def _feature_vector_from_request(body: PredictRequest, tenant_id: str) -> np.ndarray:
    feature_store = get_feature_store()
    if body.features:
        defaults = {
            "recency": 10.0,
            "frequency": 5.0,
            "monetary": 1000.0,
            "account_age_days": 180,
            "num_transactions": 20,
            "avg_transaction_amount": 50.0,
            "num_disputes": 0,
            "credit_score": 700.0,
        }
        return np.array([body.features.get(col, defaults[col]) for col in FEATURE_COLUMNS])
    return feature_store.get_feature_vector(body.user_id, tenant_id)


@app.post("/predict", response_model=PredictResponse)
async def predict(body: PredictRequest, user: Dict = Depends(check_rate_limit)):
    """Make a risk prediction for a customer. A/B tests model version.
    tenant_id always comes from the authenticated principal, never a header."""
    start_time = time.time()
    tenant_id = user["tenant_id"]

    model_version = choose_model(body.user_id)
    record_ab_assignment(model_version)

    feature_vector = _feature_vector_from_request(body, tenant_id)
    model = get_model(model_version)

    try:
        result = model.predict(feature_vector)
        risk_score, risk_class = result["risk_score"], result["risk_class"]
    except Exception as e:
        logger.warning(f"Model prediction failed: {e}")
        risk_score, risk_class = 0.5, 0

    latency = time.time() - start_time
    record_prediction(model_version, tenant_id, risk_score, risk_class, latency)
    db.record_prediction(tenant_id, body.user_id, model_version, risk_score, risk_class)

    vector_store = get_vector_store(tenant_id)
    vector_store.add_customer_embedding(body.user_id, feature_vector.astype("float32"))

    get_kafka_producer().send_prediction_event(
        tenant_id=tenant_id,
        customer_id=body.user_id,
        model_version=model_version,
        risk_score=risk_score,
        risk_class=risk_class,
    )

    get_mlflow_tracker().log_ab_experiment(user_id=body.user_id, model_version=model_version, risk_score=risk_score)
    log_ab_result(body.user_id, model_version, "prediction")

    prediction = {
        "model_version": model_version,
        "risk_score": round(risk_score, 4),
        "risk_class": risk_class,
        "risk_label": "high" if risk_class == 1 else "low",
        "latency_ms": round(latency * 1000, 2),
    }
    return PredictResponse(tenant=tenant_id, data=prediction)


@app.post("/predict/batch")
async def predict_batch(user_ids: List[int], user: Dict = Depends(check_rate_limit)):
    results = []
    for user_id in user_ids:
        body = PredictRequest(user_id=user_id)
        result = await predict(body, user)
        results.append(result)
    return {"predictions": results}


@app.post("/similar-customers")
async def find_similar_customers(request: SimilarCustomersRequest, user: Dict = Depends(check_rate_limit)):
    tenant_id = user["tenant_id"]
    feature_store = get_feature_store()
    vector_store = get_vector_store(tenant_id)

    feature_vector = feature_store.get_feature_vector(request.customer_id, tenant_id)
    vector_store.add_customer_embedding(request.customer_id, feature_vector.astype("float32"))

    similar = vector_store.search_similar_customers(
        query_embedding=feature_vector.astype("float32"),
        k=request.k,
        exclude_customer_id=request.customer_id,
    )
    return {"customer_id": request.customer_id, "similar_customers": similar}


@app.post("/ab/outcome")
async def record_ab_test_outcome(request: ABOutcomeRequest, user: Dict = Depends(check_rate_limit)):
    record_ab_outcome(request.model_version, request.outcome)
    log_ab_result(request.user_id, request.model_version, request.outcome)
    get_kafka_producer().send_ab_result_event(
        user_id=request.user_id, model_version=request.model_version, outcome=request.outcome
    )
    return {"status": "recorded"}


@app.get("/ab/stats")
async def get_ab_stats(user: Dict = Depends(get_current_user)):
    import pandas as pd

    try:
        df = pd.read_csv("data/ab_results.csv", names=["user_id", "model", "outcome"])
        stats = df.groupby("model").agg(
            total=("user_id", "count"),
            conversions=("outcome", lambda x: (x == "conversion").sum()),
        )
        stats["conversion_rate"] = stats["conversions"] / stats["total"]
        return stats.to_dict("index")
    except Exception as e:
        return {"error": str(e), "message": "No A/B data available yet"}


@app.get("/predictions/recent")
async def get_recent_predictions(user: Dict = Depends(get_current_user)):
    """Recent predictions for the caller's own tenant only."""
    return {"predictions": db.get_predictions_for_tenant(user["tenant_id"], limit=50)}


@app.get("/features/{customer_id}")
async def get_customer_features(customer_id: int, user: Dict = Depends(check_rate_limit)):
    feature_store = get_feature_store()
    features = feature_store.get_features(customer_id, user["tenant_id"])
    return {"customer_id": customer_id, "features": features}


@app.post("/explain")
async def explain_customer_risk(request: ExplainRequest, user: Dict = Depends(check_rate_limit)):
    """Natural-language explanation for a customer's risk classification,
    grounded in retrieved underwriting policy (RAG). Works with or without
    an LLM configured - see rag/explain.py for the fallback behavior."""
    tenant_id = user["tenant_id"]
    feature_store = get_feature_store()
    features = feature_store.get_features(request.customer_id, tenant_id)
    feature_vector = feature_store.get_feature_vector(request.customer_id, tenant_id)

    model_version = choose_model(request.customer_id)
    model = get_model(model_version)
    prediction = model.predict(feature_vector)

    result = await explain_prediction(prediction["risk_class"], prediction["risk_score"], features)

    return {
        "customer_id": request.customer_id,
        "risk_score": round(prediction["risk_score"], 4),
        "risk_class": prediction["risk_class"],
        "model_version": model_version,
        **result,
    }


@app.post("/policy/ask")
async def ask_policy_question(request: PolicyQuestionRequest, user: Dict = Depends(check_rate_limit)):
    """General RAG Q&A over the underwriting policy knowledge base - no
    customer data involved, so it's not tenant-scoped beyond requiring auth."""
    return await answer_policy_question(request.question)


# --- Product authenticity domain --------------------------------------------
# Shares this platform's auth, tenant isolation, persistence, and RAG
# explanation pattern with the credit-risk domain above - a second
# application of the same infrastructure rather than a separate project.


@app.post("/products/register")
async def register_product(request: RegisterProductRequest, user: Dict = Depends(check_rate_limit)):
    tenant_id = user["tenant_id"]
    serial = generate_serial()
    product = db.create_product(serial, tenant_id, request.product_name)
    qr_svg = generate_qr_svg(serial, tenant_id)
    return {"product": product, "qr_svg": qr_svg}


@app.post("/scan")
async def scan_product(request: ScanRequest, user: Dict = Depends(check_rate_limit)):
    """Record a scan and return a fraud-risk assessment, grounded in
    authenticity policy via the same RAG explainer used for credit risk."""
    tenant_id = user["tenant_id"]
    product = db.get_product(request.serial)

    if not product or product["tenant_id"] != tenant_id:
        # Unregistered (or wrong-tenant) serial is itself the strongest
        # possible signal - per rag/knowledge_base/product_authenticity_policy.md
        return {
            "serial": request.serial,
            "verified": False,
            "risk_score": 1.0,
            "risk_class": 1,
            "explanation": "This serial number is not registered to this tenant. Unrecognized or mismatched serials are treated as unverified by policy.",
            "sources": [],
        }

    db.record_scan(request.serial, tenant_id, request.latitude, request.longitude)
    features = compute_scan_features(request.serial, tenant_id)
    feature_vector = np.array([features[col] for col in FRAUD_FEATURE_COLUMNS])

    model = get_fraud_model()
    prediction = model.predict(feature_vector)

    explanation = await explain_fraud_risk(prediction["risk_class"], prediction["risk_score"], features)

    get_kafka_producer().send_prediction_event(
        tenant_id=tenant_id,
        customer_id=hash(request.serial) % 1_000_000,  # scan events aren't customer-keyed; reuse the same event shape
        model_version="fraud_model",
        risk_score=prediction["risk_score"],
        risk_class=prediction["risk_class"],
    )

    return {
        "serial": request.serial,
        "verified": True,
        "product_name": product["product_name"],
        "risk_score": round(prediction["risk_score"], 4),
        "risk_class": prediction["risk_class"],
        "features": features,
        **explanation,
    }


@app.get("/products/{serial}/history")
async def get_product_scan_history(serial: str, user: Dict = Depends(check_rate_limit)):
    tenant_id = user["tenant_id"]
    product = db.get_product(serial)
    if not product or product["tenant_id"] != tenant_id:
        raise HTTPException(status_code=404, detail="Product not found for this tenant")
    return {"serial": serial, "product_name": product["product_name"], "history": db.get_scan_history(serial, tenant_id)}


@app.post("/models/train")
async def train_models(user: Dict = Depends(require_role("admin"))):
    try:
        metrics_out = train_and_save_models()
        return {"status": "Models trained and saved successfully", "metrics": metrics_out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


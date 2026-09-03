# SaaS AI Risk Platform

> A production-grade, multi-tenant ML risk prediction platform featuring A/B model testing, a real-time feature store, vector similarity search, Kafka event streaming, and full observability — all deployable with a single `docker-compose up`.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Docker Compose (Full Stack)](#docker-compose-full-stack)
- [API Reference](#api-reference)
  - [Health & Metrics](#health--metrics)
  - [Authentication](#authentication-endpoints)
  - [Predictions](#prediction-endpoints)
  - [Features](#feature-endpoints)
  - [Similar Customers](#similar-customers-endpoint)
  - [A/B Testing](#ab-testing-endpoints)
  - [Model Management](#model-management-endpoints)
- [Authentication Guide](#authentication-guide)
- [ML Models & A/B Testing](#ml-models--ab-testing)
- [Feature Store](#feature-store)
- [Vector Store & Similarity Search](#vector-store--similarity-search)
- [Event Streaming with Kafka](#event-streaming-with-kafka)
- [Monitoring & Observability](#monitoring--observability)
- [MLflow Experiment Tracking](#mlflow-experiment-tracking)
- [Streamlit Dashboard](#streamlit-dashboard)
- [Configuration](#configuration)
- [Running Tests](#running-tests)
- [Demo Credentials](#demo-credentials)
- [Production Considerations](#production-considerations)

---

## Overview

The **SaaS AI Risk Platform** is an end-to-end machine learning system built to predict customer risk in a multi-tenant SaaS environment. It is designed to handle real-world concerns: tenant isolation, rate limiting, model versioning, experiment tracking, and operational observability — while remaining easy to run locally or deploy as a container stack.

At its core, every prediction request:
1. Authenticates the caller (JWT, API key, or tenant header)
2. Routes through a deterministic A/B testing engine to select a model variant
3. Retrieves customer features from a feature store (Parquet-backed, Feast-compatible)
4. Scores the customer using a trained scikit-learn model (Random Forest or Gradient Boosting)
5. Persists the embedding in a FAISS vector index for later similarity queries
6. Publishes the event to Kafka for downstream consumers
7. Tracks the run in MLflow
8. Emits Prometheus metrics scraped by Grafana

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client / Dashboard                        │
│              (Streamlit UI  ·  REST API consumers)               │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTPS / REST
┌──────────────────────────────▼──────────────────────────────────┐
│                     FastAPI Application                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Auth Layer │  │ Multi-Tenant │  │    Rate Limiter       │   │
│  │ JWT/API Key │  │  Middleware  │  │  (per tenant+IP)      │   │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         └────────────────┴──────────────────────┘               │
│                          │                                       │
│  ┌───────────────────────▼────────────────────────────────────┐ │
│  │                  Prediction Pipeline                        │ │
│  │  A/B Engine → Feature Store → Risk Model → Vector Store    │ │
│  └───────────────────────┬────────────────────────────────────┘ │
└──────────────────────────┼──────────────────────────────────────┘
                           │
        ┌──────────────────┼───────────────────┐
        │                  │                   │
┌───────▼──────┐  ┌────────▼───────┐  ┌───────▼──────┐
│    Kafka     │  │    MLflow      │  │  Prometheus  │
│  (streaming) │  │  (tracking)    │  │  (metrics)   │
└──────────────┘  └────────────────┘  └──────┬───────┘
                                             │
                                      ┌──────▼───────┐
                                      │   Grafana    │
                                      │ (dashboards) │
                                      └──────────────┘
```

---

## Features

### Machine Learning
- **Two A/B model variants** — `model_A` (Random Forest, 100 estimators) and `model_B` (Gradient Boosting, 100 estimators) trained side-by-side
- **Deterministic A/B routing** — a user always gets the same model based on their `user_id`, ensuring consistent user experience during experiments
- **Risk scoring** — outputs a continuous probability score (0–1) and a binary risk class (`low` / `high`)
- **On-demand model training** via a protected admin API endpoint
- **Batch predictions** — score multiple customers in a single request

### Data Infrastructure
- **Feature store** — Parquet-backed feature retrieval with Feast-compatible definitions; falls back to seeded synthetic features for unknown customers
- **FAISS vector store** — L2-indexed embeddings for fast nearest-neighbour similarity search across customers; persisted to disk
- **Kafka event streaming** — publishes prediction events and A/B outcomes to dedicated topics with producer retry and graceful degradation when Kafka is unavailable

### Security & Multi-tenancy
- **Three authentication methods**: JWT bearer tokens, API keys (`X-API-Key` header), and legacy tenant-ID headers (`X-Tenant-ID`)
- **Role-based access control** — `admin` role required for model training and API key generation; `user` role for predictions
- **Per-tenant rate limiting** — in-memory sliding window limiter (100 req/min for header auth, 1 000 req/min for API key/JWT)
- **Full tenant isolation** — every response is scoped to the calling tenant

### Observability
- **Prometheus metrics** — request counts, latencies, prediction counts, risk score distributions, A/B assignment and outcome counters, feature cache hit/miss rates
- **Grafana dashboards** — pre-wired to scrape Prometheus; default credentials `admin / admin`
- **MLflow experiment tracking** — logs parameters, metrics, and model artifacts per run; queryable via the MLflow UI
- **Structured logging** — Loguru-based logging throughout all services

### Developer Experience
- **Streamlit dashboard** — a five-tab interactive UI covering risk prediction, A/B testing, similar customer search, feature inspection, and live metrics
- **Docker Compose** — single command brings up the full stack (API, Streamlit, Kafka, Zookeeper, Prometheus, Grafana, MLflow)
- **Comprehensive test suite** — pytest tests for the API, models, auth, A/B engine, feature store, and vector store
- **Auto-initialisation** — the Dockerfile generates sample data and pre-trains both models at build time

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Data Validation | Pydantic v2 |
| ML Models | scikit-learn (RandomForest, GradientBoosting) |
| Feature Store | Feast + Apache Parquet (PyArrow) |
| Vector Store | FAISS (faiss-cpu) |
| Experiment Tracking | MLflow |
| Event Streaming | Apache Kafka + Zookeeper (Confluent images) |
| Monitoring | Prometheus + Grafana |
| Authentication | PyJWT |
| Logging | Loguru |
| Dashboard | Streamlit |
| Testing | pytest + pytest-asyncio + httpx |
| Containerisation | Docker + Docker Compose |
| Runtime | Python 3.10 |

---

## Project Structure

```
saas-ai-risk-platform/
│
├── api/
│   ├── __init__.py
│   └── main.py                  # FastAPI app — all routes, startup, CORS
│
├── models/
│   ├── __init__.py
│   ├── risk_model.py            # RiskModel class, A/B variants, train/save/load
│   └── trained/                 # Persisted .pkl model files (generated at runtime)
│
├── feature_store/
│   ├── __init__.py
│   ├── feature_service.py       # FeatureStoreService — Parquet lookup + fallback
│   └── feast_repo/              # Feast feature view definitions
│
├── vector_store/
│   ├── __init__.py
│   └── faiss_store.py           # VectorStore — FAISS L2 index + disk persistence
│
├── ab_testing/
│   ├── __init__.py
│   └── ab_engine.py             # Deterministic model selection + CSV logging
│
├── auth/
│   ├── __init__.py
│   └── security.py              # JWT, API key, rate limiter, RBAC dependencies
│
├── multi_tenant/
│   ├── __init__.py
│   └── tenant_middleware.py     # Tenant extraction helpers
│
├── messaging/
│   ├── __init__.py
│   └── kafka_service.py         # KafkaEventProducer, KafkaEventConsumer
│
├── monitoring/
│   ├── __init__.py
│   └── metrics.py               # Prometheus counters, histograms, gauges
│
├── mlflow_tracking/
│   ├── __init__.py
│   └── tracker.py               # MLflowTracker — runs, params, metrics, models
│
├── streamlit_app/
│   ├── __init__.py
│   └── app.py                   # Five-tab Streamlit dashboard
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_auth.py
│   ├── test_ab_testing.py
│   ├── test_feature_store.py
│   ├── test_models.py
│   └── test_vector_store.py
│
├── data/
│   ├── customer_features.parquet  # Pre-generated customer features
│   ├── ab_results.csv             # Running A/B log
│   └── generate_features.py       # Script to regenerate sample data
│
├── Dockerfile
├── docker-compose.yml
├── prometheus.yml                 # Prometheus scrape config
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **pip** (or a virtual environment manager)
- **Docker & Docker Compose** (for the full stack)
- `jq` (optional, for parsing JSON in shell examples)

### Local Development

**1. Clone the repository**

```bash
git clone https://github.com/Ashwani4545/saas-ai-risk-platform.git
cd saas-ai-risk-platform
```

**2. Create and activate a virtual environment (recommended)**

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Generate sample customer data**

```bash
python data/generate_features.py
```

**5. Train both A/B model variants**

```bash
python -c "from models.risk_model import train_and_save_models; train_and_save_models()"
```

This saves `model_A.pkl` and `model_B.pkl` under `models/trained/`.

**6. Start the API server**

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

**7. Start the Streamlit dashboard** (in a separate terminal)

```bash
streamlit run streamlit_app/app.py
```

Dashboard available at [http://localhost:8501](http://localhost:8501).

---

### Docker Compose (Full Stack)

Bring up every service — API, Streamlit, Kafka, Prometheus, Grafana, and MLflow — with a single command:

```bash
docker-compose up -d
```

| Service | URL | Notes |
|---|---|---|
| FastAPI | http://localhost:8000 | REST API + `/docs` |
| Streamlit | http://localhost:8501 | Interactive dashboard |
| Kafka | localhost:9092 | Broker (internal: `kafka:29092`) |
| Prometheus | http://localhost:9090 | Metrics scraping |
| Grafana | http://localhost:3000 | Dashboards (`admin / admin`) |
| MLflow | http://localhost:5000 | Experiment tracking |

To view logs for a specific service:

```bash
docker-compose logs -f api
```

To stop everything:

```bash
docker-compose down
```

---

## API Reference

The full interactive documentation (Swagger UI) is served at `GET /docs` and the ReDoc version at `GET /redoc`.

### Health & Metrics

#### `GET /health`

Returns the current health status and version of the API.

```bash
curl http://localhost:8000/health
```

```json
{ "status": "ok", "version": "1.0.0" }
```

#### `GET /metrics`

Returns Prometheus-formatted metrics for scraping.

```bash
curl http://localhost:8000/metrics
```

---

### Authentication Endpoints

#### `POST /auth/login`

Exchange username and password for a JWT access token (valid for 30 minutes).

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

#### `POST /auth/api-key`

Generate a new API key scoped to the caller's tenant. Requires the `admin` role.

```bash
curl -X POST http://localhost:8000/auth/api-key \
  -H "Authorization: Bearer <jwt>"
```

```json
{ "api_key": "rsk_<random>" }
```

---

### Prediction Endpoints

#### `POST /predict`

Score a single customer. The A/B engine deterministically assigns a model version based on `user_id`. Optionally supply custom feature values; otherwise features are pulled from the feature store.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | integer | Yes | Customer identifier |
| `features` | object | No | Override feature values (see feature keys below) |

**Supported feature keys:** `recency`, `frequency`, `monetary`, `account_age_days`, `num_transactions`, `avg_transaction_amount`, `num_disputes`, `credit_score`

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key-tenant1" \
  -d '{
    "user_id": 42,
    "features": {
      "recency": 5.0,
      "frequency": 10.0,
      "monetary": 5000.0,
      "credit_score": 750.0,
      "account_age_days": 365,
      "num_transactions": 50,
      "avg_transaction_amount": 100.0,
      "num_disputes": 0
    }
  }'
```

**Response:**

```json
{
  "tenant": "tenant_1",
  "data": {
    "model_version": "model_A",
    "risk_score": 0.2341,
    "risk_class": 0,
    "risk_label": "low",
    "latency_ms": 12.5
  }
}
```

#### `POST /predict/batch`

Score multiple customers at once. Accepts a JSON array of integer user IDs.

```bash
curl -X POST http://localhost:8000/predict/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key-tenant1" \
  -d '[1, 2, 3, 4, 5]'
```

```json
{
  "predictions": [
    { "tenant": "tenant_1", "data": { "model_version": "model_B", "risk_score": 0.67, ... } },
    ...
  ]
}
```

---

### Feature Endpoints

#### `GET /features/{customer_id}`

Retrieve the stored feature vector for a given customer.

```bash
curl http://localhost:8000/features/42 \
  -H "X-API-Key: demo-api-key-tenant1"
```

```json
{
  "customer_id": 42,
  "features": {
    "recency": 7.3,
    "frequency": 5.0,
    "monetary": 1234.56,
    "account_age_days": 180,
    "num_transactions": 22,
    "avg_transaction_amount": 56.1,
    "num_disputes": 0,
    "credit_score": 710.0
  }
}
```

---

### Similar Customers Endpoint

#### `POST /similar-customers`

Use FAISS vector similarity to find customers with profiles most similar to a given customer. The query customer's embedding must first exist in the vector store (populated automatically on prediction).

```bash
curl -X POST http://localhost:8000/similar-customers \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key-tenant1" \
  -d '{"customer_id": 42, "k": 5}'
```

```json
{
  "customer_id": 42,
  "similar_customers": [
    { "customer_id": 17, "distance": 0.312, "similarity_score": 0.762 },
    { "customer_id": 88, "distance": 0.418, "similarity_score": 0.705 },
    ...
  ]
}
```

---

### A/B Testing Endpoints

#### `POST /ab/outcome`

Record a business outcome (conversion, bounce, click, purchase, etc.) against a specific model version. This data feeds into A/B statistical analysis and is published to Kafka.

```bash
curl -X POST http://localhost:8000/ab/outcome \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-api-key-tenant1" \
  -d '{"user_id": 42, "model_version": "model_A", "outcome": "conversion"}'
```

```json
{ "status": "recorded" }
```

#### `GET /ab/stats`

Retrieve aggregated A/B test statistics — total assignments and conversion rates per model variant. Requires JWT authentication.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r .access_token)

curl http://localhost:8000/ab/stats \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "model_A": { "total": 512, "conversions": 87, "conversion_rate": 0.170 },
  "model_B": { "total": 488, "conversions": 94, "conversion_rate": 0.193 }
}
```

---

### Model Management Endpoints

#### `POST /models/train`

Retrain both `model_A` and `model_B` on fresh synthetic data and persist them to disk. **Admin role required.**

```bash
curl -X POST http://localhost:8000/models/train \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

```json
{ "status": "Models trained and saved successfully" }
```

---

## Authentication Guide

The platform supports three authentication methods, checked in priority order:

### 1. JWT Bearer Token (recommended for users)

```bash
# Step 1 — obtain a token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r .access_token)

# Step 2 — use the token
curl -X POST http://localhost:8000/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1}'
```

Tokens expire after **30 minutes**. Rate limit: **1 000 requests / minute**.

### 2. API Key (recommended for services)

Two demo keys are pre-populated:

| Key | Tenant | Permissions |
|---|---|---|
| `demo-api-key-tenant1` | tenant_1 | read, predict |
| `demo-api-key-tenant2` | tenant_2 | read, predict, admin |

```bash
curl -X POST http://localhost:8000/predict \
  -H "X-API-Key: demo-api-key-tenant1" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1}'
```

Rate limit: **1 000 requests / minute**.

### 3. Tenant Header (legacy / backward-compatible)

No credentials required — just pass a tenant identifier. Useful during development.

```bash
curl -X POST http://localhost:8000/predict \
  -H "X-Tenant-ID: tenant_1" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1}'
```

Rate limit: **100 requests / minute**.

---

## ML Models & A/B Testing

### Models

| Variant | Algorithm | Estimators | Max Depth |
|---|---|---|---|
| `model_A` | Random Forest Classifier | 100 | 10 |
| `model_B` | Gradient Boosting Classifier | 100 | 5 |

Both models are trained on the same eight customer features:

| Feature | Description |
|---|---|
| `recency` | Days since last transaction |
| `frequency` | Number of interactions in period |
| `monetary` | Total spend in period ($) |
| `account_age_days` | Days since account creation |
| `num_transactions` | Lifetime transaction count |
| `avg_transaction_amount` | Mean transaction value ($) |
| `num_disputes` | Number of disputes raised |
| `credit_score` | Credit bureau score (300–850) |

Models are serialised with `pickle` to `models/trained/{version}.pkl` and loaded lazily into an in-process cache on first use.

### A/B Routing

The A/B engine uses a deterministic hash of the `user_id` to assign a model variant. This guarantees that the same customer always experiences the same model during a running experiment, preventing switching effects.

```python
# ab_testing/ab_engine.py
def choose_model(user_id: int) -> str:
    random.seed(user_id)
    return "model_A" if random.random() < 0.5 else "model_B"
```

Outcomes are appended to `data/ab_results.csv` and can be queried via `GET /ab/stats`.

---

## Feature Store

The `FeatureStoreService` reads customer features from a Parquet file (`data/customer_features.parquet`) at startup and caches the DataFrame in memory.

**Lookup behaviour:**
- If the `customer_id` is found in the Parquet file, its row is returned as a dict.
- If the customer is unknown, a seeded synthetic feature vector is generated (reproducible — same `customer_id` always yields the same fallback features).

The `feast_repo/` directory contains Feast feature view definitions for teams wishing to integrate a production-grade online feature store (e.g., Redis-backed Feast).

---

## Vector Store & Similarity Search

The platform maintains a **FAISS `IndexFlatL2`** (8-dimensional, one dimension per feature) that stores a floating-point embedding for every customer who has received a prediction.

**Key operations:**

| Operation | Method |
|---|---|
| Add embedding | `VectorStore.add_customer_embedding(customer_id, embedding)` |
| Find neighbours | `VectorStore.search_similar_customers(query, k, exclude_id)` |
| Retrieve embedding | `VectorStore.get_customer_embedding(customer_id)` |

The index and ID maps are persisted to `data/faiss_index/` on disk and reloaded on startup, so embeddings survive process restarts.

The similarity score returned to callers is `1 / (1 + L2_distance)`, giving a value between 0 and 1 where 1 means identical.

---

## Event Streaming with Kafka

All prediction and A/B outcome events are published to Kafka topics via `KafkaEventProducer`.

| Topic | Trigger | Key fields |
|---|---|---|
| `risk-predictions` | Every `POST /predict` | tenant_id, customer_id, model_version, risk_score, risk_class |
| `ab-testing-results` | Every `POST /ab/outcome` | user_id, model_version, outcome |

The producer connects lazily on first use. If Kafka is unreachable (e.g. during local development without Docker), the producer falls back to logging the event locally — the API call still succeeds.

A `KafkaEventConsumer` class is provided for building downstream consumers (e.g., a fraud alert service or a data pipeline).

**Docker Compose configuration:**

| Service | Port | Notes |
|---|---|---|
| Zookeeper | 2181 | Required by Kafka |
| Kafka | 9092 (external) / 29092 (internal) | Confluent 7.4.0 |

---

## Monitoring & Observability

### Prometheus Metrics

All metrics are exposed at `GET /metrics` in the standard Prometheus text format. Prometheus is configured to scrape the API every 15 seconds via `prometheus.yml`.

| Metric | Type | Labels | Description |
|---|---|---|---|
| `risk_platform_requests_total` | Counter | method, endpoint, tenant_id, status | Total HTTP requests |
| `risk_platform_request_latency_seconds` | Histogram | method, endpoint | End-to-end latency |
| `risk_platform_predictions_total` | Counter | model_version, tenant_id, risk_class | Predictions made |
| `risk_platform_prediction_latency_seconds` | Histogram | model_version | Model inference time |
| `risk_platform_risk_score` | Histogram | model_version, tenant_id | Risk score distribution |
| `risk_platform_ab_test_assignments_total` | Counter | model_version | A/B assignments |
| `risk_platform_ab_test_outcomes_total` | Counter | model_version, outcome | A/B recorded outcomes |
| `risk_platform_feature_fetch_latency_seconds` | Histogram | source | Feature retrieval time |
| `risk_platform_feature_cache_hits_total` | Counter | cache_type | Cache hits |
| `risk_platform_feature_cache_misses_total` | Counter | cache_type | Cache misses |

### Grafana

Grafana is pre-configured to connect to Prometheus. Access it at [http://localhost:3000](http://localhost:3000).

Default credentials: `admin / admin`

---

## MLflow Experiment Tracking

All prediction and A/B runs are logged to MLflow under the `risk_prediction` experiment.

**Logged data per run:**

| Data | Examples |
|---|---|
| Parameters | `model_version`, `tenant_id`, `user_id` |
| Metrics | `risk_score`, `risk_class`, feature values |
| Tags | `outcome` (for A/B runs) |
| Artifacts | Serialised scikit-learn models (when training) |

Access the MLflow UI at [http://localhost:5000](http://localhost:5000) when running Docker Compose.

By default, MLflow uses a local SQLite backend (`mlflow.db`). Set `MLFLOW_TRACKING_URI` to a remote tracking server for production use.

---

## Streamlit Dashboard

The dashboard at [http://localhost:8501](http://localhost:8501) provides five tabs:

| Tab | Capability |
|---|---|
| **Risk Prediction** | Single prediction with optional feature sliders; batch prediction for comma-separated user IDs |
| **A/B Testing** | Record outcomes against model versions; view aggregated conversion statistics |
| **Similar Customers** | Run a vector similarity search and view nearest-neighbour results in a table |
| **Features** | Inspect stored feature values for any customer ID with a bar chart visualisation |
| **Metrics** | View live Prometheus metric values and raw metric text |

Authentication can be switched between API Key, JWT Token (with in-dashboard login), and header-only modes from the sidebar. The sidebar also shows a live API health indicator.

---

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | `your-secret-key-change-in-production` | Secret used to sign JWT tokens. **Change before deploying.** |
| `MLFLOW_TRACKING_URI` | `sqlite:///mlflow.db` | MLflow backend store URI |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address(es) |
| `API_BASE_URL` | `http://localhost:8000` | Used by the Streamlit app to reach the API |

In Docker Compose these are set in the `environment` blocks of each service definition.

---

## Running Tests

```bash
# Run the full test suite
pytest tests/ -v

# Run a specific test module
pytest tests/test_api.py -v
pytest tests/test_auth.py -v
pytest tests/test_models.py -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html to browse coverage
```

**Test modules:**

| Module | Coverage |
|---|---|
| `test_api.py` | Health, predict, batch predict, metrics, auth, features, similar customers |
| `test_auth.py` | Login success/failure, JWT validation, API key validation |
| `test_ab_testing.py` | Deterministic routing, distribution across users |
| `test_feature_store.py` | Feature lookup, fallback generation |
| `test_models.py` | Model training, inference, save/load |
| `test_vector_store.py` | Embedding storage and similarity search |

---

## Demo Credentials

| Type | Value | Tenant | Roles |
|---|---|---|---|
| Username / Password | `admin` / `admin123` | admin | admin, user |
| Username / Password | `user1` / `user123` | tenant_1 | user |
| API Key | `demo-api-key-tenant1` | tenant_1 | read, predict |
| API Key | `demo-api-key-tenant2` | tenant_2 | read, predict, admin |

---

## Production Considerations

The following items should be addressed before deploying this platform to a production environment:

- **Change `JWT_SECRET_KEY`** to a cryptographically random value; never commit it to source control.
- **Replace in-memory stores** — the rate limiter, API key store, and user store are all held in process memory. Replace with Redis (rate limiting) and a proper database (users, API keys).
- **Harden password hashing** — the demo uses SHA-256 directly. Replace with `bcrypt` or `argon2`.
- **Kafka replication** — set `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR` to 3+ in any multi-broker deployment.
- **FAISS index rebuilds** — the current implementation appends vectors but never removes stale entries. Implement a periodic index rebuild for updated customers.
- **MLflow remote tracking** — point `MLFLOW_TRACKING_URI` at a hosted MLflow server with a proper RDBMS backend.
- **Secrets management** — use a secrets manager (AWS Secrets Manager, Vault, etc.) rather than environment variables for sensitive values.
- **CORS policy** — tighten the `allow_origins=["*"]` setting to the specific domains of your frontend.
- **TLS termination** — place an HTTPS-terminating reverse proxy (nginx, Caddy, or a cloud load balancer) in front of the API and Streamlit services.

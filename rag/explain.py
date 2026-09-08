"""Builds a natural-language explanation for a risk prediction, grounded in
retrieved underwriting policy - the RAG part of this feature.

Two paths, both real (not a mocked demo path vs a real path):
  - LLM configured: retrieved policy chunks + the actual feature values are
    put in the prompt, and the model is asked to explain the decision using
    only what's given - answering the regulatory requirement that adverse
    action reasons be specific and in plain language (see
    rag/knowledge_base/regulatory_notes.md).
  - LLM not configured (the default - no API key needed to try this
    feature): a deterministic template cites the same retrieved chunks and
    names the features that drove the score, without the generative
    rewrite. It's less fluent but factually the same grounding, and it's
    what CI runs against since it needs no secret.
"""
from typing import Dict, List

from rag.retriever import get_retriever
from rag.llm_client import generate, is_configured

FEATURE_LABELS = {
    "recency": "days since last activity",
    "frequency": "transaction frequency",
    "monetary": "total transaction value",
    "account_age_days": "account age",
    "num_transactions": "number of transactions",
    "avg_transaction_amount": "average transaction amount",
    "num_disputes": "number of disputes",
    "credit_score": "credit score",
}

SYSTEM_PROMPT = (
    "You write plain-language adverse-action explanations for a credit risk platform. "
    "You are given a risk prediction, the customer's feature values, and excerpts from the "
    "company's underwriting policy. Explain the decision in 3-4 sentences using ONLY the "
    "policy excerpts and feature values provided - do not invent policy that isn't in the "
    "excerpts, and do not use internal terms like 'feature vector' or 'probability' toward "
    "the applicant. Name the specific factors that drove the decision."
)


def _query_from_features(features: Dict[str, float]) -> str:
    """Turn feature values into a retrieval query, so retrieval reflects
    what's actually notable about this customer rather than being generic."""
    terms = []
    if features.get("credit_score", 999) < 650:
        terms.append("low credit score")
    elif features.get("credit_score", 0) > 720:
        terms.append("high credit score")
    if features.get("num_disputes", 0) >= 2:
        terms.append("multiple disputes")
    elif features.get("num_disputes", 0) == 1:
        terms.append("one dispute")
    if features.get("account_age_days", 999) < 90:
        terms.append("new account short history")
    if not terms:
        terms.append("standard low risk applicant")
    return " ".join(terms)


def _fallback_explanation(risk_class: int, features: Dict[str, float], chunks: List[dict]) -> str:
    label = "high" if risk_class == 1 else "low"
    drivers = []
    if features.get("credit_score", 999) < 650:
        drivers.append(f"a credit score of {features['credit_score']:.0f}")
    if features.get("num_disputes", 0) >= 1:
        drivers.append(f"{int(features['num_disputes'])} dispute(s) on record")
    if features.get("account_age_days", 999) < 90:
        drivers.append(f"an account only {int(features['account_age_days'])} days old")
    driver_text = ", ".join(drivers) if drivers else "a combination of the customer's overall feature profile"

    policy_refs = ", ".join(sorted({c["doc"].replace(".md", "").replace("_", " ") for c in chunks})) or "general underwriting guidelines"

    return (
        f"This customer was classified as {label} risk, primarily driven by {driver_text}. "
        f"This is consistent with company policy on {policy_refs}. "
        f"(Generated without an LLM - set ANTHROPIC_API_KEY to enable natural-language generation.)"
    )


async def explain_prediction(risk_class: int, risk_score: float, features: Dict[str, float]) -> Dict:
    query = _query_from_features(features)
    chunks = get_retriever().retrieve(query, k=3)

    llm_text = None
    if is_configured():
        feature_lines = "\n".join(f"- {FEATURE_LABELS.get(k, k)}: {v}" for k, v in features.items())
        policy_lines = "\n\n".join(f"[{c['doc']}] {c['text']}" for c in chunks)
        user_prompt = (
            f"Risk score: {risk_score:.2f} ({'high' if risk_class else 'low'} risk)\n\n"
            f"Customer features:\n{feature_lines}\n\n"
            f"Relevant policy excerpts:\n{policy_lines}"
        )
        llm_text = await generate(SYSTEM_PROMPT, user_prompt)

    explanation = llm_text or _fallback_explanation(risk_class, features, chunks)

    return {
        "explanation": explanation,
        "generated_by": "llm" if llm_text else "template_fallback",
        "sources": chunks,
    }


async def answer_policy_question(question: str) -> Dict:
    """General (non customer-specific) RAG Q&A over the policy knowledge base."""
    chunks = get_retriever().retrieve(question, k=3)

    if not chunks:
        return {
            "answer": "No matching policy content found for that question.",
            "generated_by": "none",
            "sources": [],
        }

    llm_text = None
    if is_configured():
        policy_lines = "\n\n".join(f"[{c['doc']}] {c['text']}" for c in chunks)
        system_prompt = (
            "Answer the question using ONLY the policy excerpts provided. If the excerpts don't "
            "answer it, say so rather than guessing. Keep the answer to 2-3 sentences."
        )
        llm_text = await generate(system_prompt, f"Question: {question}\n\nPolicy excerpts:\n{policy_lines}")

    if llm_text:
        answer = llm_text
    else:
        answer = "LLM not configured - showing the most relevant policy excerpts for this question:\n\n" + "\n\n".join(
            f"[{c['doc']}] {c['text']}" for c in chunks
        )

    return {
        "answer": answer,
        "generated_by": "llm" if llm_text else "template_fallback",
        "sources": chunks,
    }


# --- Product authenticity domain --------------------------------------------

FRAUD_FEATURE_LABELS = {
    "scan_count": "total number of scans",
    "unique_locations": "number of distinct scan locations",
    "max_travel_speed_kmh": "fastest implied travel speed between consecutive scans (km/h)",
    "min_seconds_between_scans": "shortest gap between two scans (seconds)",
    "scans_last_hour": "scans in the last hour",
}

FRAUD_SYSTEM_PROMPT = (
    "You write plain-language fraud-risk explanations for a product authenticity platform. "
    "You are given a risk prediction, a product's scan history features, and excerpts from the "
    "company's authenticity/fraud policy. Explain the decision in 2-4 sentences using ONLY the "
    "policy excerpts and feature values provided - do not invent policy that isn't in the "
    "excerpts. Name the specific signal(s) that drove the decision (e.g. impossible travel "
    "speed, too many scan locations) in language a non-technical consumer could understand."
)


def _fraud_query_from_features(features: Dict[str, float]) -> str:
    terms = []
    if features.get("max_travel_speed_kmh", 0) > 900:
        terms.append("impossible travel distant locations short time")
    if features.get("unique_locations", 0) > 5:
        terms.append("multiple scan locations duplicated code")
    if features.get("scans_last_hour", 0) > 3:
        terms.append("many scans in short period")
    if not terms:
        terms.append("normal verified product low risk")
    return " ".join(terms)


def _fraud_fallback_explanation(risk_class: int, features: Dict[str, float], chunks: List[dict]) -> str:
    label = "high" if risk_class == 1 else "low"
    drivers = []
    if features.get("max_travel_speed_kmh", 0) > 900:
        drivers.append(f"an implied travel speed of {features['max_travel_speed_kmh']:.0f} km/h between scans")
    if features.get("unique_locations", 0) > 5:
        drivers.append(f"{int(features['unique_locations'])} distinct scan locations")
    if features.get("scans_last_hour", 0) > 3:
        drivers.append(f"{int(features['scans_last_hour'])} scans within the last hour")
    driver_text = ", ".join(drivers) if drivers else "a scan pattern consistent with normal use"

    policy_refs = ", ".join(sorted({c["doc"].replace(".md", "").replace("_", " ") for c in chunks})) or "general authenticity guidelines"

    return (
        f"This product was classified as {label} fraud risk, primarily driven by {driver_text}. "
        f"This is consistent with company policy on {policy_refs}. "
        f"(Generated without an LLM - set ANTHROPIC_API_KEY to enable natural-language generation.)"
    )


async def explain_fraud_risk(risk_class: int, risk_score: float, features: Dict[str, float]) -> Dict:
    query = _fraud_query_from_features(features)
    chunks = get_retriever().retrieve(query, k=3)

    llm_text = None
    if is_configured():
        feature_lines = "\n".join(f"- {FRAUD_FEATURE_LABELS.get(k, k)}: {v}" for k, v in features.items())
        policy_lines = "\n\n".join(f"[{c['doc']}] {c['text']}" for c in chunks)
        user_prompt = (
            f"Risk score: {risk_score:.2f} ({'high' if risk_class else 'low'} risk)\n\n"
            f"Scan history features:\n{feature_lines}\n\n"
            f"Relevant policy excerpts:\n{policy_lines}"
        )
        llm_text = await generate(FRAUD_SYSTEM_PROMPT, user_prompt)

    explanation = llm_text or _fraud_fallback_explanation(risk_class, features, chunks)

    return {
        "explanation": explanation,
        "generated_by": "llm" if llm_text else "template_fallback",
        "sources": chunks,
    }

"""Prometheus metrics for monitoring"""
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
import time

# Request metrics
REQUEST_COUNT = Counter(
    'risk_platform_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'tenant_id', 'status']
)

REQUEST_LATENCY = Histogram(
    'risk_platform_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Prediction metrics
PREDICTIONS_COUNT = Counter(
    'risk_platform_predictions_total',
    'Total number of predictions made',
    ['model_version', 'tenant_id', 'risk_class']
)

PREDICTION_LATENCY = Histogram(
    'risk_platform_prediction_latency_seconds',
    'Prediction latency in seconds',
    ['model_version'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)

RISK_SCORE = Histogram(
    'risk_platform_risk_score',
    'Distribution of risk scores',
    ['model_version', 'tenant_id'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# A/B testing metrics
AB_TEST_ASSIGNMENTS = Counter(
    'risk_platform_ab_test_assignments_total',
    'Number of A/B test assignments',
    ['model_version']
)

AB_TEST_OUTCOMES = Counter(
    'risk_platform_ab_test_outcomes_total',
    'A/B test outcomes',
    ['model_version', 'outcome']
)

# System metrics
ACTIVE_TENANTS = Gauge(
    'risk_platform_active_tenants',
    'Number of active tenants'
)

MODEL_INFO = Info(
    'risk_platform_model',
    'Information about loaded models'
)

# Feature store metrics
FEATURE_FETCH_LATENCY = Histogram(
    'risk_platform_feature_fetch_latency_seconds',
    'Feature retrieval latency',
    ['source'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
)

FEATURE_CACHE_HITS = Counter(
    'risk_platform_feature_cache_hits_total',
    'Feature cache hits',
    ['cache_type']
)

FEATURE_CACHE_MISSES = Counter(
    'risk_platform_feature_cache_misses_total',
    'Feature cache misses',
    ['cache_type']
)


def track_request(method: str, endpoint: str):
    """Decorator to track request metrics"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=endpoint,
                    tenant_id='unknown',
                    status='success'
                ).inc()
                return result
            except Exception as e:
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=endpoint,
                    tenant_id='unknown',
                    status='error'
                ).inc()
                raise
            finally:
                REQUEST_LATENCY.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(time.time() - start_time)
        return wrapper
    return decorator


def record_prediction(
    model_version: str,
    tenant_id: str,
    risk_score: float,
    risk_class: int,
    latency: float
):
    """Record prediction metrics"""
    PREDICTIONS_COUNT.labels(
        model_version=model_version,
        tenant_id=tenant_id,
        risk_class=str(risk_class)
    ).inc()
    
    PREDICTION_LATENCY.labels(
        model_version=model_version
    ).observe(latency)
    
    RISK_SCORE.labels(
        model_version=model_version,
        tenant_id=tenant_id
    ).observe(risk_score)


def record_ab_assignment(model_version: str):
    """Record A/B test assignment"""
    AB_TEST_ASSIGNMENTS.labels(model_version=model_version).inc()


def record_ab_outcome(model_version: str, outcome: str):
    """Record A/B test outcome"""
    AB_TEST_OUTCOMES.labels(
        model_version=model_version,
        outcome=outcome
    ).inc()


def get_metrics():
    """Get current metrics in Prometheus format"""
    return generate_latest()


def get_metrics_content_type():
    """Get content type for metrics response"""
    return CONTENT_TYPE_LATEST

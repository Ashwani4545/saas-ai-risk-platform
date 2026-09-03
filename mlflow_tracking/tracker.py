"""MLflow integration for experiment tracking and model registry"""
import mlflow
from mlflow.tracking import MlflowClient
import numpy as np
from typing import Optional, Dict, Any
from loguru import logger
import os

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
EXPERIMENT_NAME = "risk_prediction"


class MLflowTracker:
    """MLflow integration for experiment tracking"""
    
    def __init__(self, tracking_uri: str = None, experiment_name: str = None):
        self.tracking_uri = tracking_uri or MLFLOW_TRACKING_URI
        self.experiment_name = experiment_name or EXPERIMENT_NAME
        self._initialized = False
        self._client: Optional[MlflowClient] = None
    
    def _initialize(self):
        """Initialize MLflow connection"""
        if self._initialized:
            return
        
        try:
            mlflow.set_tracking_uri(self.tracking_uri)
            
            # Create experiment if it doesn't exist
            experiment = mlflow.get_experiment_by_name(self.experiment_name)
            if experiment is None:
                mlflow.create_experiment(self.experiment_name)
            
            mlflow.set_experiment(self.experiment_name)
            self._client = MlflowClient()
            self._initialized = True
            logger.info(f"MLflow initialized with tracking URI: {self.tracking_uri}")
            
        except Exception as e:
            logger.warning(f"Could not initialize MLflow: {e}")
            self._initialized = False
    
    def start_run(self, run_name: str = None, tags: Dict[str, str] = None) -> Optional[str]:
        """Start a new MLflow run"""
        self._initialize()
        if not self._initialized:
            return None
        
        try:
            run = mlflow.start_run(run_name=run_name, tags=tags)
            return run.info.run_id
        except Exception as e:
            logger.error(f"Failed to start MLflow run: {e}")
            return None
    
    def end_run(self):
        """End the current MLflow run"""
        try:
            mlflow.end_run()
        except Exception as e:
            logger.error(f"Failed to end MLflow run: {e}")
    
    def log_params(self, params: Dict[str, Any]):
        """Log parameters to current run"""
        self._initialize()
        if not self._initialized:
            return
        
        try:
            mlflow.log_params(params)
        except Exception as e:
            logger.error(f"Failed to log params: {e}")
    
    def log_metrics(self, metrics: Dict[str, float], step: int = None):
        """Log metrics to current run"""
        self._initialize()
        if not self._initialized:
            return
        
        try:
            mlflow.log_metrics(metrics, step=step)
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")
    
    def log_model(self, model, model_name: str, signature=None):
        """Log model artifact"""
        self._initialize()
        if not self._initialized:
            return
        
        try:
            mlflow.sklearn.log_model(
                model, 
                model_name,
                signature=signature,
                registered_model_name=model_name
            )
            logger.info(f"Logged model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to log model: {e}")
    
    def log_prediction(
        self,
        model_version: str,
        features: Dict[str, float],
        risk_score: float,
        risk_class: int,
        tenant_id: str
    ):
        """Log a single prediction for tracking"""
        self._initialize()
        if not self._initialized:
            return
        
        try:
            with mlflow.start_run(run_name=f"prediction_{tenant_id}", nested=True):
                mlflow.log_params({
                    'model_version': model_version,
                    'tenant_id': tenant_id
                })
                mlflow.log_metrics({
                    'risk_score': risk_score,
                    'risk_class': float(risk_class)
                })
                # Log features as metrics for analysis
                for name, value in features.items():
                    mlflow.log_metric(f"feature_{name}", float(value))
        except Exception as e:
            logger.debug(f"Failed to log prediction: {e}")
    
    def log_ab_experiment(
        self,
        user_id: int,
        model_version: str,
        risk_score: float,
        outcome: str = None
    ):
        """Log A/B test experiment data"""
        self._initialize()
        if not self._initialized:
            return
        
        try:
            with mlflow.start_run(run_name=f"ab_test_{model_version}", nested=True):
                mlflow.log_params({
                    'user_id': str(user_id),
                    'model_version': model_version
                })
                mlflow.log_metrics({
                    'risk_score': risk_score
                })
                if outcome:
                    mlflow.set_tag('outcome', outcome)
        except Exception as e:
            logger.debug(f"Failed to log A/B experiment: {e}")
    
    def get_best_model(self, metric: str = "accuracy") -> Optional[str]:
        """Get the best model version based on a metric"""
        self._initialize()
        if not self._initialized:
            return None
        
        try:
            runs = mlflow.search_runs(
                experiment_names=[self.experiment_name],
                order_by=[f"metrics.{metric} DESC"],
                max_results=1
            )
            if len(runs) > 0:
                return runs.iloc[0]['run_id']
            return None
        except Exception as e:
            logger.error(f"Failed to get best model: {e}")
            return None


# Singleton instance
_tracker: Optional[MLflowTracker] = None

def get_mlflow_tracker() -> MLflowTracker:
    """Get MLflow tracker singleton"""
    global _tracker
    if _tracker is None:
        _tracker = MLflowTracker()
    return _tracker


def track_training_run(
    model_version: str,
    params: Dict[str, Any],
    metrics: Dict[str, float],
    model=None
):
    """Convenience function to track a training run"""
    tracker = get_mlflow_tracker()
    tracker.start_run(run_name=f"train_{model_version}")
    tracker.log_params(params)
    tracker.log_metrics(metrics)
    if model:
        tracker.log_model(model, model_version)
    tracker.end_run()

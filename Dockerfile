FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data models/trained

# Generate sample data and train models
RUN python -c "from data.generate_features import save_features; save_features()" || true
RUN python -c "from models.risk_model import train_and_save_models; train_and_save_models()" || true
RUN python -c "from core import db; db.init_db()" || true
RUN python -c "from product_auth.data_generator import generate_and_persist_scan_data; generate_and_persist_scan_data()" || true
RUN python -c "from product_auth.fraud_model import train_and_save_fraud_model; train_and_save_fraud_model()" || true

# Expose ports
EXPOSE 8000
EXPOSE 8501

# Default command (API server)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

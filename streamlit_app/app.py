"""Enhanced Streamlit Dashboard for SaaS AI Risk Platform"""
import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="SaaS AI Risk Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("🎯 SaaS AI Risk Dashboard")

# Sidebar for authentication
with st.sidebar:
    st.header("🔐 Authentication")
    
    st.caption("Every request below is authenticated - there's no tenant-by-header option anymore, since that used to let any caller impersonate any tenant.")
    auth_method = st.radio("Auth Method", ["API Key", "JWT Token"])
    
    if auth_method == "API Key":
        api_key = st.text_input("API Key", value="demo-api-key-tenant1", type="password")
        headers = {"X-API-Key": api_key}
    else:
        with st.expander("Login", expanded="token" not in st.session_state):
            username = st.text_input("Username", value="admin")
            password = st.text_input("Password", value="admin123", type="password")
            if st.button("Login"):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/auth/login",
                        json={"username": username, "password": password}
                    )
                    if response.status_code == 200:
                        st.session_state.token = response.json()["access_token"]
                        st.success("Logged in successfully!")
                    else:
                        st.error("Login failed")
                except Exception as e:
                    st.error(f"Connection error: {e}")
        
        token = st.session_state.get("token", "")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    st.divider()
    st.header("📡 API Status")
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health.status_code == 200:
            st.success(f"✅ API Online - v{health.json().get('version', 'unknown')}")
        else:
            st.error("❌ API Error")
    except:
        st.error("❌ API Offline")

# Main tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎲 Risk Prediction", 
    "📊 A/B Testing", 
    "🔍 Similar Customers",
    "📈 Features",
    "📉 Metrics"
])

# Tab 1: Risk Prediction
with tab1:
    st.header("Risk Prediction")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Single Prediction")
        user_id = st.number_input("Customer ID", min_value=1, value=1, step=1)
        
        use_custom_features = st.checkbox("Use Custom Features")
        
        features = None
        if use_custom_features:
            with st.expander("Custom Features", expanded=True):
                features = {
                    "recency": st.slider("Recency (days)", 0.0, 100.0, 10.0),
                    "frequency": st.slider("Frequency", 1.0, 50.0, 5.0),
                    "monetary": st.slider("Monetary ($)", 0.0, 10000.0, 1000.0),
                    "account_age_days": st.slider("Account Age (days)", 30, 1000, 180),
                    "num_transactions": st.slider("Transactions", 0, 100, 20),
                    "avg_transaction_amount": st.slider("Avg Transaction ($)", 0.0, 500.0, 50.0),
                    "num_disputes": st.slider("Disputes", 0, 10, 0),
                    "credit_score": st.slider("Credit Score", 300, 850, 700)
                }
        
        if st.button("🔮 Predict Risk", type="primary"):
            try:
                payload = {"user_id": user_id}
                if features:
                    payload["features"] = features
                
                response = requests.post(
                    f"{API_BASE_URL}/predict",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data["data"]
                    
                    st.success(f"Tenant: {data['tenant']}")
                    
                    # Display results
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    
                    with metric_col1:
                        st.metric("Risk Score", f"{result['risk_score']:.2%}")
                    with metric_col2:
                        risk_color = "🔴" if result['risk_class'] == 1 else "🟢"
                        st.metric("Risk Level", f"{risk_color} {result['risk_label'].upper()}")
                    with metric_col3:
                        st.metric("Model", result['model_version'])
                    
                    st.info(f"Latency: {result['latency_ms']}ms")
                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Request failed: {e}")
    
    with col2:
        st.subheader("Batch Prediction")
        batch_input = st.text_area(
            "Customer IDs (comma-separated)",
            value="1, 2, 3, 4, 5"
        )
        
        if st.button("📦 Batch Predict"):
            try:
                user_ids = [int(x.strip()) for x in batch_input.split(",")]
                
                response = requests.post(
                    f"{API_BASE_URL}/predict/batch",
                    json=user_ids,
                    headers=headers
                )
                
                if response.status_code == 200:
                    results = response.json()["predictions"]
                    
                    df = pd.DataFrame([
                        {
                            "Customer ID": cid,
                            "Risk Score": r["data"]["risk_score"],
                            "Risk Class": r["data"]["risk_label"],
                            "Model": r["data"]["model_version"]
                        }
                        for cid, r in zip(user_ids, results)
                    ])
                    
                    st.dataframe(df)
                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Request failed: {e}")

# Tab 2: A/B Testing
with tab2:
    st.header("A/B Testing Dashboard")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Record Outcome")
        outcome_user_id = st.number_input("User ID", min_value=1, value=1, key="ab_user")
        model_version = st.selectbox("Model Version", ["model_A", "model_B"])
        outcome = st.selectbox("Outcome", ["conversion", "bounce", "click", "purchase"])
        
        if st.button("📝 Record Outcome"):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/ab/outcome",
                    json={
                        "user_id": outcome_user_id,
                        "model_version": model_version,
                        "outcome": outcome
                    },
                    headers=headers
                )
                if response.status_code == 200:
                    st.success("Outcome recorded!")
                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Request failed: {e}")
    
    with col2:
        st.subheader("A/B Statistics")
        if st.button("📊 Refresh Stats"):
            try:
                response = requests.get(
                    f"{API_BASE_URL}/ab/stats",
                    headers=headers
                )
                if response.status_code == 200:
                    stats = response.json()
                    if "error" in stats:
                        st.warning(stats["message"])
                    else:
                        st.json(stats)
                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Request failed: {e}")

# Tab 3: Similar Customers
with tab3:
    st.header("Similar Customer Search")
    
    search_customer_id = st.number_input("Customer ID", min_value=1, value=1, key="similar")
    k_neighbors = st.slider("Number of Similar Customers", 1, 20, 5)
    
    if st.button("🔍 Find Similar"):
        try:
            response = requests.post(
                f"{API_BASE_URL}/similar-customers",
                json={"customer_id": search_customer_id, "k": k_neighbors},
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                st.subheader(f"Customers similar to #{result['customer_id']}")
                
                if result["similar_customers"]:
                    df = pd.DataFrame(result["similar_customers"])
                    st.dataframe(df)
                else:
                    st.info("No similar customers found. Make some predictions first to populate the vector store.")
            else:
                st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")

# Tab 4: Features
with tab4:
    st.header("Customer Features")
    
    feature_customer_id = st.number_input("Customer ID", min_value=1, value=1, key="features")
    
    if st.button("📋 Get Features"):
        try:
            response = requests.get(
                f"{API_BASE_URL}/features/{feature_customer_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                st.subheader(f"Features for Customer #{result['customer_id']}")
                
                features_df = pd.DataFrame([result["features"]])
                st.dataframe(features_df.T.rename(columns={0: "Value"}))
                
                # Visualize features
                st.bar_chart(pd.Series(result["features"]))
            else:
                st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")

# Tab 5: Metrics
with tab5:
    st.header("Platform Metrics")
    
    if st.button("🔄 Refresh Metrics"):
        try:
            response = requests.get(f"{API_BASE_URL}/metrics")
            if response.status_code == 200:
                metrics_text = response.text
                
                # Parse some key metrics
                lines = metrics_text.split("\n")
                metrics_data = []
                
                for line in lines:
                    if line and not line.startswith("#"):
                        parts = line.split(" ")
                        if len(parts) >= 2:
                            metrics_data.append({
                                "metric": parts[0],
                                "value": parts[1]
                            })
                
                if metrics_data:
                    df = pd.DataFrame(metrics_data[:20])  # Show first 20
                    st.dataframe(df)
                
                with st.expander("Raw Metrics"):
                    st.code(metrics_text)
            else:
                st.error("Could not fetch metrics")
        except Exception as e:
            st.error(f"Request failed: {e}")

# Footer
st.divider()
st.caption(f"SaaS AI Risk Platform Dashboard | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

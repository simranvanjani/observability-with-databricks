"""🤖 AI Gateway — govern serving endpoints (usage tracking, inference tables,
rate limits, guardrails)."""
import streamlit as st

from lib import ai_gateway


def render():
    st.header("🤖 AI Gateway")
    st.caption("Add governance to a model-serving endpoint: usage tracking, "
               "inference-table logging, rate limits, and PII guardrails.")

    endpoints = ai_gateway.list_endpoints()
    if isinstance(endpoints, dict) and "error" in endpoints:
        st.warning(f"Could not list endpoints: {endpoints['error']}")
        names = []
    else:
        names = [e["name"] for e in endpoints]
        st.dataframe(endpoints, use_container_width=True, hide_index=True)

    endpoint = st.selectbox("Endpoint", names) if names else st.text_input("Endpoint name")
    calls = st.slider("Rate limit (calls/minute)", 10, 1000, 100, step=10)
    catalog = st.text_input("Inference-table catalog", "main")
    schema = st.text_input("Inference-table schema", "cost_demo")
    block_pii = st.checkbox("Block PII on input", value=True)

    if endpoint:
        st.json(ai_gateway.preview_gateway(endpoint, calls, catalog, schema, block_pii))
        if st.checkbox("I reviewed the config") and st.button("✅ Apply AI Gateway config"):
            st.success(str(ai_gateway.apply_gateway(endpoint, calls, catalog, schema, block_pii)))

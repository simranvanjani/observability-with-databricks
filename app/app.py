"""Observability Setup Center — a Databricks App.

A one-stop UI where a customer assesses their cost/governance posture and applies
tagging, budgets, policies, AI Gateway config, and governed tags — every write
following Assess -> Preview -> Apply, acting as the logged-in operator (OBO).
"""
import streamlit as st

from views import overview, tags, budgets_policies, ai_gateway, data_gov

st.set_page_config(page_title="Observability Setup Center", page_icon="🛰️", layout="wide")

TABS = {
    "📊 Overview": overview.render,
    "🏷️ Tags": tags.render,
    "💰 Budgets, Alerts & Policies": budgets_policies.render,
    "🤖 AI Gateway": ai_gateway.render,
    "🔒 Data Governance": data_gov.render,
}

st.sidebar.title("🛰️ Observability Setup Center")
st.sidebar.caption("Assess → Preview → Apply. Writes act as **you** (your permissions).")
choice = st.sidebar.radio("Go to", list(TABS.keys()), label_visibility="collapsed")

st.sidebar.divider()
st.sidebar.number_input("Lookback (days)", min_value=7, max_value=365, value=30, key="lookback_days")
st.sidebar.text_input("Primary tag key", value="cost_center", key="tag_key")
st.sidebar.info("All costs are **list price** (system.billing.list_prices); actual "
                "invoice varies by contract.")

try:
    TABS[choice]()
except Exception as e:  # keep the app alive; show actionable errors
    st.error(f"Something went wrong in this view:\n\n```\n{e}\n```")
    st.caption("Common causes: system schemas not enabled, missing warehouse id, "
               "or the operator lacks the required grant/role.")

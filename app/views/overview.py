"""📊 Overview — Governance-Hub-style single pane across Cost / Tags / AI / Data."""
import streamlit as st

from lib import assess


def render():
    st.header("📊 Overview")
    st.caption("Mirrors the native **Governance Hub** (Cost · Tags · AI · Data). "
               "Open the account console → Governance Hub for the built-in version.")
    days = st.session_state.get("lookback_days", 30)
    tag_key = st.session_state.get("tag_key", "cost_center")

    # ---- Cost pillar ----
    st.subheader("💵 Cost")
    head = assess.spend_headline(days)
    if not head.empty:
        r = head.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Spend (last {days}d)", f"${r.get('list_cost_usd', 0):,.0f}")
        c2.metric("Spend (MTD)", f"${r.get('mtd_cost_usd', 0) or 0:,.0f}")
        c3.metric("Avg daily", f"${r.get('avg_daily_usd', 0) or 0:,.0f}")

    cov = assess.tagging_coverage(tag_key, days)
    if not cov.empty:
        total = cov["list_cost_usd"].sum()
        tagged = cov.loc[cov["status"] == "tagged", "list_cost_usd"].sum()
        pct = (tagged / total * 100) if total else 0
        st.metric(f"Tagging coverage ({tag_key})", f"{pct:,.0f}%")
        st.progress(min(pct / 100, 1.0))

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Spend by product")
        st.bar_chart(assess.spend_by_product(days).set_index("product"))
    with c2:
        st.caption(f"Spend by {tag_key}")
        st.bar_chart(assess.spend_by_tag(tag_key, days).set_index("tag_value"))

    # ---- AI pillar ----
    st.subheader("🤖 AI")
    ai = assess.ai_spend(days)
    if ai.empty:
        st.caption("No model-serving usage found in the window.")
    else:
        st.bar_chart(ai.set_index("product"))

    # ---- Data pillar ----
    st.subheader("🔒 Data")
    st.caption("Recent audit activity (governance signal — who did what)")
    st.dataframe(assess.recent_audit(days=7, limit=100), use_container_width=True, hide_index=True)

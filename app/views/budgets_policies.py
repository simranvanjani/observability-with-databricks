"""💰 Budgets, Alerts & Policies — budget policies, account budgets, cluster
policy, and the natural-language alert builder over system tables."""
import streamlit as st

from lib import budgets, policies, nl_alerts


def render():
    st.header("💰 Budgets, Alerts & Policies")
    t_alert, t_policy, t_budget, t_cluster = st.tabs(
        ["🗣️ NL Alert Builder", "Serverless budget policy", "Account budget", "Cluster policy"])

    # ---------- Natural-language alert builder ----------
    with t_alert:
        st.caption("Describe the alert in plain English. It's translated to SQL over "
                   "system tables, shown for review, then created as a Databricks SQL Alert.")
        example = "alert me when finance's monthly serverless spend passes $5,000"
        nl = st.text_area("Describe your alert", placeholder=example)
        if st.button("🧠 Generate", disabled=not nl):
            with st.spinner("Asking the model…"):
                try:
                    st.session_state["_alert_spec"] = nl_alerts.generate(nl)
                except Exception as e:
                    st.error(f"Could not generate a safe alert: {e}")

        spec = st.session_state.get("_alert_spec")
        if spec:
            st.markdown(f"**{spec['title']}** — {spec.get('explanation','')}")
            st.code(spec["sql"], language="sql")
            st.write(f"Trigger when `{spec['value_column']}` **{spec['op']}** `{spec['threshold']}`")
            recipients = st.text_input("Alert recipients (comma-separated emails)")
            if st.checkbox("I reviewed the generated SQL") and st.button("✅ Create alert"):
                res = nl_alerts.create_alert(
                    spec, [r.strip() for r in recipients.split(",") if r.strip()])
                st.success(res)

    # ---------- Serverless budget policy ----------
    with t_policy:
        st.caption("Attach custom tags to serverless usage (jobs/SQL/serving).")
        name = st.text_input("Policy name", "finance-serverless")
        cc = st.text_input("cost_center", "1001", key="bp_cc")
        team = st.text_input("team", "data-eng", key="bp_team")
        tags = {k: v for k, v in {"cost_center": cc, "team": team}.items() if v}
        st.json(budgets.preview_budget_policy(name, tags))
        if st.button("✅ Create budget policy"):
            st.success(str(budgets.create_budget_policy(name, tags)))
        st.divider()
        st.caption("Existing budget policies")
        st.write(budgets.list_budget_policies())

    # ---------- Account budget ----------
    with t_budget:
        st.caption("Account budgets + alert thresholds (requires account admin).")
        name = st.text_input("Budget name", "monthly-finance", key="b_name")
        amount = st.number_input("Monthly amount (USD)", value=5000.0, step=500.0)
        thresholds = st.multiselect("Alert thresholds (%)", [50, 75, 90, 100], default=[75, 90, 100])
        recips = st.text_input("Recipients", "finops@example.com")
        st.json(budgets.preview_budget(name, amount, thresholds,
                                       [r.strip() for r in recips.split(",")], None))
        st.info("Create in Account Console → Usage → Budgets (or the Budgets API).")

    # ---------- Cluster policy ----------
    with t_cluster:
        st.caption("Enforce required tags + cost guardrails on all-purpose/job compute.")
        pname = st.text_input("Policy name", "cost-guardrails")
        allow = st.text_input("Allowed teams (comma-separated)", "data-eng,ds,bi")
        max_workers = st.slider("Max workers", 1, 64, 8)
        max_term = st.slider("Max autotermination (min)", 10, 240, 60)
        definition = policies.build_definition(
            {"cost_center": "^[0-9]{4}$"}, [t.strip() for t in allow.split(",") if t.strip()],
            max_workers, max_term)
        st.json(definition)
        if st.button("✅ Apply cluster policy"):
            st.success(policies.apply_policy(pname, definition))

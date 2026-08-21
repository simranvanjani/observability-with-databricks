"""🏷️ Tags — governed-tag taxonomy + apply tags to clusters/jobs/warehouses."""
import streamlit as st

from lib import tagging, governed_tags


def render():
    st.header("🏷️ Tags")
    tab_apply, tab_governed = st.tabs(["Apply tags to compute", "Governed tags (UC assets)"])

    # ---------- Apply tags to compute ----------
    with tab_apply:
        st.caption("Set a tag taxonomy, pick assets, preview the diff, then apply. "
                   "Serverless has no cluster to tag → use budget policies instead.")

        st.markdown("**1. Desired tags**")
        cc = st.text_input("cost_center", "")
        team = st.text_input("team", "")
        env = st.selectbox("environment", ["", "prod", "dev", "test"])
        desired = {k: v for k, v in {"cost_center": cc, "team": team, "environment": env}.items() if v}

        if st.button("🔍 Load assets & compute plan", disabled=not desired):
            st.session_state["_assets"] = tagging.list_assets()

        assets = st.session_state.get("_assets")
        if assets:
            st.markdown("**2. Select assets**")
            labels = {f"{a.asset_type}: {a.asset_name}": a.asset_id for a in assets}
            picked = st.multiselect("Assets", list(labels.keys()))
            selected_ids = {labels[p] for p in picked}
            changes = tagging.plan(assets, desired, selected_ids)

            st.markdown("**3. Preview diff**")
            if not changes:
                st.info("No changes for the current selection.")
            else:
                st.dataframe(
                    [{"asset": f"{c.asset_type}: {c.asset_name}",
                      "current": c.current, "new": c.new, "changes": c.diff} for c in changes],
                    use_container_width=True)
                if st.checkbox("I reviewed the diff above") and st.button("✅ Apply tags"):
                    results = tagging.apply(changes)
                    st.dataframe(results, use_container_width=True, hide_index=True)

    # ---------- Governed tags ----------
    with tab_governed:
        st.caption("Assign governed tags to Unity Catalog securables. Allowed-value "
                   "*policies* are defined account-side (Settings → Governed tags).")
        stype = st.selectbox("Securable type", ["CATALOG", "SCHEMA", "TABLE"])
        full_name = st.text_input("Full name (e.g. main.finance.transactions)")
        key = st.text_input("Tag key", "data_domain")
        value = st.text_input("Tag value", "finance")
        if full_name:
            st.code(governed_tags.preview_assign(stype, full_name, key, value)["sql"], language="sql")
            if st.button("✅ Assign governed tag"):
                st.success(governed_tags.assign_tag(stype, full_name, key, value))

        st.divider()
        st.caption("Current UC tag assignments")
        st.dataframe(governed_tags.list_governed_tags(), use_container_width=True)

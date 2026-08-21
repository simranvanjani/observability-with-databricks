"""🔒 Data Governance — access/grants summary, data classification, and
Lakehouse Monitoring for data quality."""
import streamlit as st

from lib import assess
from lib.auth import get_workspace_client


def render():
    st.header("🔒 Data Governance")
    t_access, t_class, t_quality = st.tabs(
        ["Access & grants", "Data classification", "Data quality (monitoring)"])

    # ---------- Access summary ----------
    with t_access:
        st.caption("Who has which privileges across Unity Catalog securables.")
        st.dataframe(assess.access_summary(limit=300), use_container_width=True, hide_index=True)

    # ---------- Data classification ----------
    with t_class:
        st.caption("Automatic sensitive-data detection classifies columns (e.g. PII). "
                   "Enable it per-metastore, then results surface in Catalog Explorer.")
        st.markdown(
            "- Enable: **Catalog → Settings → Data classification** (or the classification API).\n"
            "- Once scanned, classified columns carry system tags you can filter in the "
            "**Tags** view and the Governance Hub.")
        st.info("Classification enablement is a metastore-admin setting; this app links "
                "you there rather than toggling it silently.")

    # ---------- Data quality ----------
    with t_quality:
        st.caption("Create a Lakehouse Monitor to track data-quality metrics on a table.")
        table = st.text_input("Fully-qualified table (catalog.schema.table)")
        schedule = st.selectbox("Profile type", ["Snapshot", "TimeSeries"])
        if table and st.button("✅ Create quality monitor"):
            try:
                w = get_workspace_client()
                from databricks.sdk.service.catalog import (
                    MonitorSnapshot, MonitorTimeSeries)
                kwargs = {"table_name": table,
                          "assets_dir": f"/Workspace/Shared/monitors/{table.replace('.', '_')}",
                          "output_schema_name": table.rsplit(".", 1)[0]}
                if schedule == "Snapshot":
                    monitor = w.quality_monitors.create(snapshot=MonitorSnapshot(), **kwargs)
                else:
                    monitor = w.quality_monitors.create(
                        time_series=MonitorTimeSeries(timestamp_col="event_time",
                                                      granularities=["1 day"]), **kwargs)
                st.success(f"Created monitor for {table}")
            except Exception as e:
                st.error(f"Could not create monitor: {e}")

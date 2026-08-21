# Databricks notebook source
# MAGIC %md
# MAGIC # 🚦 START HERE — Cost, Tagging & Governance STS Demo
# MAGIC
# MAGIC This bundle walks a customer through **cost management, tagging, budgets, dashboards, and AI governance** on Databricks — built primarily for **Azure Databricks** but written **cloud-agnostic** on top of `system.*` tables.
# MAGIC
# MAGIC Every topic follows the same rhythm:
# MAGIC
# MAGIC > **📖 Concept** (what & why) → **🛠️ Implementation guide** (how) → **▶️ Example** (runnable cell)
# MAGIC
# MAGIC ## Session map
# MAGIC | Notebook | Session | Covers |
# MAGIC |---|---|---|
# MAGIC | `01_Cost_Setup_Tagging` | **Session 1 — Cost Setup & Tagging** | Cost model & DBUs, tagging taxonomy, tag clusters/jobs/warehouses, find untagged spend, enforce tags via cluster policies |
# MAGIC | `02_Budgets_Dashboards` | **Session 2 — Budgets, Alerts & Dashboards** | Budget policies & budgets, alert thresholds, billing/usage/audit views, deploy the prebuilt cost dashboard |
# MAGIC | `03_Progress_AI_Gateway` | **Session 3 — Progress Check-In & AI Gateway** | Progress checklist, Mosaic AI Gateway (usage tracking, rate limits, inference tables, cost attribution) |
# MAGIC
# MAGIC > 🎤 **How to drive this in the room:** run `00_START_HERE` once at the top of Session 1 to set the widgets and confirm prereqs. The three session notebooks then "just run."

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Prerequisites
# MAGIC
# MAGIC | Requirement | Why | How to check |
# MAGIC |---|---|---|
# MAGIC | **Unity Catalog** enabled | System tables live in the `system` catalog | `SHOW CATALOGS` includes `system` |
# MAGIC | **System schemas enabled** | `billing`, `access`, `compute`, `lakeflow`, `serving` | See enablement cell below |
# MAGIC | **Account admin** (for budgets) | Budgets & budget policies are account-level | Account console access |
# MAGIC | **A SQL warehouse** | To run the `%sql` cells | Set the widget below |
# MAGIC | **Reader access to `system.billing`** | Cost queries | Permissions probe below |
# MAGIC
# MAGIC > ☁️ **Azure note:** system tables are identical across clouds. Where cost is shown in currency we use `system.billing.list_prices` (list price, USD). Azure "resource tags" on the workspace are separate from **Databricks custom tags** — this demo uses Databricks custom tags, which is what flows into `system.billing.usage.custom_tags`.

# COMMAND ----------

# Widgets — set these once; every session notebook reads the same widget names.
dbutils.widgets.text("catalog", "main", "Target catalog (for demo views)")
dbutils.widgets.text("schema", "cost_demo", "Target schema (for demo views)")
dbutils.widgets.text("tag_key", "cost_center", "Primary tag key to analyze")
dbutils.widgets.text("lookback_days", "30", "Lookback window (days)")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
tag_key = dbutils.widgets.get("tag_key")
lookback_days = dbutils.widgets.get("lookback_days")

print(f"catalog={catalog}  schema={schema}  tag_key={tag_key}  lookback_days={lookback_days}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Confirm which system schemas are enabled
# MAGIC
# MAGIC 🛠️ **Implementation guide:** system schemas are enabled per-metastore by an account admin. `billing` and `access` are on by default in most workspaces; `compute`, `lakeflow`, and `serving` may need enabling.
# MAGIC
# MAGIC To enable one (account admin, via the Databricks CLI / REST):
# MAGIC ```bash
# MAGIC # List schemas and their state
# MAGIC databricks unity-catalog metastores current
# MAGIC # Enable a schema (e.g. compute) via the System Schemas API
# MAGIC # PUT /api/2.0/unity-catalog/metastores/{metastore_id}/systemschemas/compute
# MAGIC ```

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ Which system schemas exist / are readable?
# MAGIC SHOW SCHEMAS IN system;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Permissions probe — can we read billing?
# MAGIC If the next cell returns a row count, you're good. If it errors on permissions, ask an account admin to `GRANT SELECT ON SCHEMA system.billing`.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS usage_rows_last_7_days
# MAGIC FROM system.billing.usage
# MAGIC WHERE usage_date >= current_date() - INTERVAL 7 DAYS;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Packaging & install (for sharing this bundle)
# MAGIC
# MAGIC **Easiest one-click install for the customer — build a `.dbc` archive once:**
# MAGIC 1. In *any* workspace, **Workspace → Import** each `.py` file into a single folder (or import the whole folder).
# MAGIC 2. Right-click the folder → **Export → DBC Archive**. Databricks generates `observability-cost-sts-demo.dbc`.
# MAGIC 3. The customer imports that one `.dbc` via **Workspace → Import → File** — it expands into the full folder in one action.
# MAGIC
# MAGIC **Alternative (versioned):** put these `.py` files in a Git repo, then in the customer workspace **Workspace → Add → Git folder** and paste the URL.
# MAGIC
# MAGIC > ✅ You now have widgets set and prereqs confirmed. Open **`01_Cost_Setup_Tagging`** to begin Session 1.

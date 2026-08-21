# Databricks notebook source
# MAGIC %md
# MAGIC # 💰 Session 1 — Cost Setup & Tagging
# MAGIC
# MAGIC **Goals:** understand the Databricks cost model, agree a tagging taxonomy, apply tags across clusters / jobs / warehouses / serverless, find untagged spend, and enforce tags with cluster policies.
# MAGIC
# MAGIC Run `00_START_HERE` first — this notebook reads the same widgets (`catalog`, `schema`, `tag_key`, `lookback_days`).

# COMMAND ----------

dbutils.widgets.text("tag_key", "cost_center", "Primary tag key to analyze")
dbutils.widgets.text("lookback_days", "30", "Lookback window (days)")
tag_key = dbutils.widgets.get("tag_key")
lookback_days = int(dbutils.widgets.get("lookback_days"))
print(f"Analyzing tag_key='{tag_key}' over last {lookback_days} days")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.1 The Databricks cost model
# MAGIC
# MAGIC ### 📖 Concept
# MAGIC - You are billed in **DBUs** (Databricks Units) — a usage metric that varies by compute type (all-purpose, jobs, SQL, serverless, model serving).
# MAGIC - **`system.billing.usage`** is the source of truth: one row per usage record, with DBU quantity, SKU, compute metadata, and a **`custom_tags`** map.
# MAGIC - `usage` gives you **DBUs**; to get **currency** you join **`system.billing.list_prices`** (list price — good for showing relative cost; actual invoice may differ by contract).
# MAGIC - Cost attribution = *tags on usage* + *pricing*. No tags → no attribution. That's why Session 1 is about tagging.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ Example: where is the money going, by product (SKU family), last N days?
# MAGIC SELECT
# MAGIC   billing_origin_product              AS product,
# MAGIC   round(sum(usage_quantity), 1)        AS dbus
# MAGIC FROM system.billing.usage
# MAGIC WHERE usage_date >= current_date() - INTERVAL :lookback DAYS
# MAGIC GROUP BY billing_origin_product
# MAGIC ORDER BY dbus DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🛠️ Turn DBUs into $ — join list prices
# MAGIC `list_prices` is slowly-changing (has `price_start_time` / `price_end_time`). Join on SKU **and** the price active at usage time.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ Example: estimated list cost ($) by product, last N days
# MAGIC SELECT
# MAGIC   u.billing_origin_product                                   AS product,
# MAGIC   round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS list_cost_usd
# MAGIC FROM system.billing.usage u
# MAGIC JOIN system.billing.list_prices lp
# MAGIC   ON u.sku_name = lp.sku_name
# MAGIC  AND u.usage_end_time >= lp.price_start_time
# MAGIC  AND (u.usage_end_time < lp.price_end_time OR lp.price_end_time IS NULL)
# MAGIC WHERE u.usage_date >= current_date() - INTERVAL :lookback DAYS
# MAGIC GROUP BY u.billing_origin_product
# MAGIC ORDER BY list_cost_usd DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.2 A tagging taxonomy
# MAGIC
# MAGIC ### 📖 Concept
# MAGIC Agree a **small, mandatory** set of tag keys up front. Fewer keys, consistently applied, beats many keys applied sometimes.
# MAGIC
# MAGIC | Tag key | Example values | Answers |
# MAGIC |---|---|---|
# MAGIC | `cost_center` | `1001`, `mktg-analytics` | Who pays? (chargeback) |
# MAGIC | `team` | `data-eng`, `ds`, `bi` | Who owns it? |
# MAGIC | `project` | `churn-model`, `finance-etl` | What's it for? |
# MAGIC | `environment` | `prod`, `dev`, `test` | Prod vs. experimentation |
# MAGIC
# MAGIC ### 🛠️ Where tags come from (all land in `usage.custom_tags`)
# MAGIC | Compute | Where you set tags |
# MAGIC |---|---|
# MAGIC | All-purpose / Jobs clusters | Cluster **Tags** (UI), or `custom_tags` in cluster JSON / policy |
# MAGIC | SQL warehouses | Warehouse **Tags** in warehouse settings |
# MAGIC | **Serverless** (jobs, SQL, model serving) | **Budget Policies** (Session 2) — serverless has no cluster to tag, so tags are attached via a policy |
# MAGIC | Jobs | Job-level tags propagate to the job's compute |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🛠️ Implementation guide — tag a cluster / job / warehouse
# MAGIC
# MAGIC **Cluster JSON** (Compute → your cluster → JSON, or via API):
# MAGIC ```json
# MAGIC {
# MAGIC   "cluster_name": "data-eng-etl",
# MAGIC   "custom_tags": { "cost_center": "1001", "team": "data-eng", "environment": "prod" }
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC **Job** (job settings → Edit → Tags), or in Jobs API `tags`:
# MAGIC ```json
# MAGIC { "tags": { "cost_center": "1001", "project": "finance-etl", "environment": "prod" } }
# MAGIC ```
# MAGIC
# MAGIC **SQL warehouse** — SQL Warehouses → Edit → **Tags**.
# MAGIC
# MAGIC > The example below shows tagging a cluster programmatically via the SDK (safe to read; edit the cluster_id to run for real).

# COMMAND ----------

# ▶️ Example: apply/patch tags on an existing cluster via the Databricks SDK.
# (Left non-destructive — fill in a real cluster_id and remove the guard to run.)
from databricks.sdk import WorkspaceClient

CLUSTER_ID = ""  # <-- set to a real cluster_id to run
DESIRED_TAGS = {"cost_center": "1001", "team": "data-eng", "environment": "prod"}

if CLUSTER_ID:
    w = WorkspaceClient()
    current = w.clusters.get(CLUSTER_ID)
    merged = {**(current.custom_tags or {}), **DESIRED_TAGS}
    w.clusters.edit(cluster_id=CLUSTER_ID, spark_version=current.spark_version,
                    node_type_id=current.node_type_id, num_workers=current.num_workers or 0,
                    custom_tags=merged)
    print("Applied tags:", merged)
else:
    print("Set CLUSTER_ID to apply tags. Showing intended tags:", DESIRED_TAGS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.3 Find untagged spend (the money you can't attribute)
# MAGIC
# MAGIC ### 📖 Concept
# MAGIC The fastest way to make the case for tagging is to **quantify what's untagged**. This is the headline chart for the customer.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ Example: tagged vs untagged list cost for the primary tag key
# MAGIC SELECT
# MAGIC   CASE WHEN u.custom_tags[:tag_key] IS NULL OR u.custom_tags[:tag_key] = ''
# MAGIC        THEN '❌ untagged' ELSE '✅ tagged' END           AS tag_status,
# MAGIC   round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS list_cost_usd
# MAGIC FROM system.billing.usage u
# MAGIC JOIN system.billing.list_prices lp
# MAGIC   ON u.sku_name = lp.sku_name
# MAGIC  AND u.usage_end_time >= lp.price_start_time
# MAGIC  AND (u.usage_end_time < lp.price_end_time OR lp.price_end_time IS NULL)
# MAGIC WHERE u.usage_date >= current_date() - INTERVAL :lookback DAYS
# MAGIC GROUP BY tag_status
# MAGIC ORDER BY list_cost_usd DESC

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ Example: cost by the primary tag value (chargeback view)
# MAGIC SELECT
# MAGIC   coalesce(u.custom_tags[:tag_key], '(untagged)')          AS tag_value,
# MAGIC   round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS list_cost_usd
# MAGIC FROM system.billing.usage u
# MAGIC JOIN system.billing.list_prices lp
# MAGIC   ON u.sku_name = lp.sku_name
# MAGIC  AND u.usage_end_time >= lp.price_start_time
# MAGIC  AND (u.usage_end_time < lp.price_end_time OR lp.price_end_time IS NULL)
# MAGIC WHERE u.usage_date >= current_date() - INTERVAL :lookback DAYS
# MAGIC GROUP BY tag_value
# MAGIC ORDER BY list_cost_usd DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.4 Enforce tags & usage policies with **cluster policies**
# MAGIC
# MAGIC ### 📖 Concept
# MAGIC Tagging only sticks if it's **enforced**. A **cluster policy** can *require* tag values, cap cluster size, force autotermination, and restrict node types — so cost governance is applied at creation time, not audited after the fact.
# MAGIC
# MAGIC ### 🛠️ Implementation guide — example policy
# MAGIC Compute → **Policies** → Create policy → paste a definition like this:
# MAGIC ```json
# MAGIC {
# MAGIC   "custom_tags.cost_center": { "type": "regex", "pattern": "^[0-9]{4}$", "hidden": false },
# MAGIC   "custom_tags.team":        { "type": "allowlist", "values": ["data-eng","ds","bi"] },
# MAGIC   "autotermination_minutes": { "type": "range", "maxValue": 60, "defaultValue": 30 },
# MAGIC   "num_workers":             { "type": "range", "maxValue": 8 },
# MAGIC   "spark_version":           { "type": "regex", "pattern": ".*-lts-.*" }
# MAGIC }
# MAGIC ```
# MAGIC This forces every cluster created under the policy to carry a valid `cost_center` and an approved `team`, auto-terminate within an hour, and stay within a size cap.

# COMMAND ----------

# ▶️ Example: create the enforcing cluster policy via the SDK (idempotent-ish; edits if name exists).
from databricks.sdk import WorkspaceClient
import json

CREATE_POLICY = False  # flip to True to actually create it
policy_name = "sts-demo-cost-guardrails"
definition = {
    "custom_tags.cost_center": {"type": "regex", "pattern": "^[0-9]{4}$", "hidden": False},
    "custom_tags.team":        {"type": "allowlist", "values": ["data-eng", "ds", "bi"]},
    "autotermination_minutes": {"type": "range", "maxValue": 60, "defaultValue": 30},
    "num_workers":             {"type": "range", "maxValue": 8},
}

if CREATE_POLICY:
    w = WorkspaceClient()
    existing = {p.name: p for p in w.cluster_policies.list()}
    if policy_name in existing:
        w.cluster_policies.edit(policy_id=existing[policy_name].policy_id,
                                name=policy_name, definition=json.dumps(definition))
        print("Updated policy:", policy_name)
    else:
        w.cluster_policies.create(name=policy_name, definition=json.dumps(definition))
        print("Created policy:", policy_name)
else:
    print("Set CREATE_POLICY=True to create. Policy definition:\n", json.dumps(definition, indent=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.5 DB Demos & Governance Hub
# MAGIC
# MAGIC - **DB Demos** — install the FinOps / system-tables demos directly into the workspace:
# MAGIC   ```python
# MAGIC   %pip install dbdemos
# MAGIC   import dbdemos; dbdemos.install('billing-forecast')     # cost forecasting on system.billing
# MAGIC   ```
# MAGIC - **Governance Hub / Catalog Explorer** — use **Catalog → system** to browse the billing/access tables, and the **Account Console → Usage** page for the built-in spend view.
# MAGIC
# MAGIC ## 📝 Homework (before Session 2)
# MAGIC 1. Agree the mandatory tag keys (recommend: `cost_center`, `team`, `environment`).
# MAGIC 2. Apply the cluster policy above to all-purpose compute; require tags on jobs.
# MAGIC 3. Tag existing SQL warehouses.
# MAGIC 4. Re-run **1.3** — target: untagged spend trending toward zero.
# MAGIC
# MAGIC ➡️ Next: **`02_Budgets_Dashboards`**

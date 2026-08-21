# Databricks notebook source
# MAGIC %md
# MAGIC # 📊 Session 2 — Budgets, Alerts & Dashboards
# MAGIC
# MAGIC **Goals:** configure budget policies + budgets with alert thresholds, enforce usage policies, build reusable **billing / usage / audit views** in Unity Catalog, and deploy a **prebuilt cost dashboard**.
# MAGIC
# MAGIC Reads widgets from `00_START_HERE` (`catalog`, `schema`, `tag_key`, `lookback_days`).

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Target catalog")
dbutils.widgets.text("schema", "cost_demo", "Target schema")
dbutils.widgets.text("lookback_days", "30", "Lookback window (days)")
catalog = dbutils.widgets.get("catalog")
schema  = dbutils.widgets.get("schema")
lookback_days = int(dbutils.widgets.get("lookback_days"))
spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
print(f"Views will be created in {catalog}.{schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2.1 Budgets, budget policies & alerts
# MAGIC
# MAGIC ### 📖 Concept
# MAGIC Two related account-level features:
# MAGIC - **Budgets** — set a spend threshold over a period and get **email alerts** at % thresholds (e.g. 50/75/90/100%). Purely for monitoring/alerting.
# MAGIC - **Budget policies** — the way you **attach tags to serverless usage**. Serverless (jobs, SQL, model serving) has no cluster to tag, so you create a *budget policy* carrying `custom_tags` and assign it to serverless workloads. Those tags then appear in `system.billing.usage.custom_tags` — closing the attribution gap from Session 1.
# MAGIC
# MAGIC ### 🛠️ Implementation guide
# MAGIC - **Budgets:** *Account Console → Usage → Budgets → Create budget*. Set period, amount, filters (by tag/workspace/SKU), and alert recipients + thresholds.
# MAGIC - **Budget policies:** *Account Console → Settings → Budget policies* (or Workspace **Settings → Compute → Budget policies**). Define `custom_tags`, then assign the policy to serverless jobs / SQL / notebooks. Users must be granted access to the policy.
# MAGIC
# MAGIC > ☁️ **Azure note:** budgets & budget policies are managed in the Databricks **Account Console**, independent of Azure Cost Management. For an all-up Azure bill view you'd also look at Azure Cost Management, but attribution *within* Databricks comes from these policies + tags.

# COMMAND ----------

# MAGIC %md
# MAGIC ### ▶️ Example — "budget alert" as a SQL query you can schedule
# MAGIC Even without the console budget, you can replicate threshold alerting with a scheduled query + **Databricks SQL Alert**. This cell computes month-to-date list cost vs. a target; wire it to a SQL Alert to email when it crosses the threshold.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Month-to-date list cost vs. a monthly target (edit :monthly_target_usd).
# MAGIC WITH mtd AS (
# MAGIC   SELECT round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS mtd_cost_usd
# MAGIC   FROM system.billing.usage u
# MAGIC   JOIN system.billing.list_prices lp
# MAGIC     ON u.sku_name = lp.sku_name
# MAGIC    AND u.usage_end_time >= lp.price_start_time
# MAGIC    AND (u.usage_end_time < lp.price_end_time OR lp.price_end_time IS NULL)
# MAGIC   WHERE u.usage_date >= date_trunc('MONTH', current_date())
# MAGIC )
# MAGIC SELECT mtd_cost_usd,
# MAGIC        :monthly_target_usd                             AS target_usd,
# MAGIC        round(100 * mtd_cost_usd / :monthly_target_usd, 1) AS pct_of_budget,
# MAGIC        CASE WHEN mtd_cost_usd >= :monthly_target_usd THEN '🔴 OVER'
# MAGIC             WHEN mtd_cost_usd >= 0.9 * :monthly_target_usd THEN '🟠 90%+'
# MAGIC             WHEN mtd_cost_usd >= 0.75 * :monthly_target_usd THEN '🟡 75%+'
# MAGIC             ELSE '🟢 OK' END                            AS status
# MAGIC FROM mtd

# COMMAND ----------

# MAGIC %md
# MAGIC > 🛠️ **Wire the alert:** save the query above (with a real `monthly_target_usd`) → **Create Alert** → trigger when `pct_of_budget >= 90` → add recipients. This is the DBSQL-native equivalent of a budget alert, useful when you want alerting on a *custom* slice (per team/project).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2.2 Billing / usage / audit views in Unity Catalog
# MAGIC
# MAGIC ### 📖 Concept
# MAGIC Wrap the raw system tables in **clean, priced, tag-exploded views** so dashboards and analysts don't re-derive the price join every time. We create three views:
# MAGIC - `v_usage_priced` — usage with list $ and key tags exploded to columns
# MAGIC - `v_cost_daily` — daily $ rollup by product / tag (dashboard-ready)
# MAGIC - `v_audit_activity` — audit events for governance (who did what)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ View 1: priced usage with tags exploded to columns
# MAGIC CREATE OR REPLACE VIEW ${catalog}.${schema}.v_usage_priced AS
# MAGIC SELECT
# MAGIC   u.usage_date,
# MAGIC   u.workspace_id,
# MAGIC   u.billing_origin_product                      AS product,
# MAGIC   u.sku_name,
# MAGIC   u.usage_quantity                              AS dbus,
# MAGIC   u.usage_quantity * lp.pricing.effective_list.default AS list_cost_usd,
# MAGIC   u.custom_tags['cost_center']                  AS cost_center,
# MAGIC   u.custom_tags['team']                         AS team,
# MAGIC   u.custom_tags['project']                      AS project,
# MAGIC   u.custom_tags['environment']                  AS environment,
# MAGIC   u.usage_metadata.job_id                       AS job_id,
# MAGIC   u.usage_metadata.cluster_id                   AS cluster_id,
# MAGIC   u.usage_metadata.warehouse_id                 AS warehouse_id
# MAGIC FROM system.billing.usage u
# MAGIC JOIN system.billing.list_prices lp
# MAGIC   ON u.sku_name = lp.sku_name
# MAGIC  AND u.usage_end_time >= lp.price_start_time
# MAGIC  AND (u.usage_end_time < lp.price_end_time OR lp.price_end_time IS NULL);

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ View 2: daily cost rollup (dashboard-ready)
# MAGIC CREATE OR REPLACE VIEW ${catalog}.${schema}.v_cost_daily AS
# MAGIC SELECT usage_date, product,
# MAGIC        coalesce(cost_center, '(untagged)') AS cost_center,
# MAGIC        coalesce(team, '(untagged)')        AS team,
# MAGIC        coalesce(environment, '(untagged)') AS environment,
# MAGIC        round(sum(dbus), 2)          AS dbus,
# MAGIC        round(sum(list_cost_usd), 2) AS list_cost_usd
# MAGIC FROM ${catalog}.${schema}.v_usage_priced
# MAGIC GROUP BY usage_date, product, cost_center, team, environment;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ View 3: audit activity (governance / who-did-what)
# MAGIC CREATE OR REPLACE VIEW ${catalog}.${schema}.v_audit_activity AS
# MAGIC SELECT
# MAGIC   event_time,
# MAGIC   user_identity.email   AS user_email,
# MAGIC   service_name,
# MAGIC   action_name,
# MAGIC   request_params,
# MAGIC   source_ip_address
# MAGIC FROM system.access.audit
# MAGIC WHERE event_date >= current_date() - INTERVAL 30 DAYS;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ Sanity check the daily cost view
# MAGIC SELECT * FROM ${catalog}.${schema}.v_cost_daily
# MAGIC ORDER BY usage_date DESC, list_cost_usd DESC
# MAGIC LIMIT 20;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2.3 Deploy a prebuilt cost dashboard
# MAGIC
# MAGIC ### 📖 Concept
# MAGIC Databricks ships an **Account Usage AI/BI dashboard** template built on `system.billing`. You can deploy it in seconds and point it at the views above.
# MAGIC
# MAGIC ### 🛠️ Three ways to get a dashboard in front of the customer
# MAGIC 1. **Account Console → Usage** — zero-build, built-in spend charts (great for the first "wow").
# MAGIC 2. **`dbdemos` FinOps dashboard** — `import dbdemos; dbdemos.install('billing-forecast')` installs an AI/BI dashboard + cost-forecast model on `system.billing`.
# MAGIC 3. **Build a mini AI/BI dashboard on `v_cost_daily`** — *Dashboards → Create* → add a line chart (list_cost_usd by usage_date), a bar chart (cost by team), and the tagged-vs-untagged counter. Because it sits on our view, tags are already exploded.
# MAGIC
# MAGIC > 💾 To ship a dashboard *with* this bundle, export it as a `.lvdash.json` (Dashboard → ⋮ → Export) and import it in the customer workspace via *Dashboards → Import*.

# COMMAND ----------

# ▶️ Example: install the dbdemos FinOps/billing dashboard (uncomment to run).
# %pip install dbdemos
# import dbdemos
# dbdemos.install('billing-forecast')
print("Uncomment the lines above to install the dbdemos FinOps dashboard + forecast model.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Homework (before Session 3)
# MAGIC 1. Create a console **budget** with 75/90/100% alerts to the FinOps DL.
# MAGIC 2. Create **budget policies** for serverless jobs/SQL so serverless usage carries tags.
# MAGIC 3. Deploy one dashboard (Account Usage or the mini AI/BI on `v_cost_daily`).
# MAGIC 4. Confirm `v_usage_priced` shows tags for serverless workloads (proves the budget policy worked).
# MAGIC
# MAGIC ➡️ Next: **`03_Progress_AI_Gateway`**

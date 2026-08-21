# Databricks notebook source
# MAGIC %md
# MAGIC # 🤖 Session 3 — Progress Check-In & Mosaic AI Gateway
# MAGIC
# MAGIC **Goals:** review progress against Sessions 1–2, close open items, then govern **AI/model-serving cost & usage** with **Mosaic AI Gateway** — usage tracking, rate limits, payload/inference logging, and cost attribution that ties back to the tagging story.

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Target catalog")
dbutils.widgets.text("schema", "cost_demo", "Target schema")
catalog = dbutils.widgets.get("catalog")
schema  = dbutils.widgets.get("schema")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3.1 Progress check-in
# MAGIC
# MAGIC ### 📖 Use this as the live agenda
# MAGIC | Area | Target state | ✅ / ⚠️ / ❌ | Owner | Notes |
# MAGIC |---|---|---|---|---|
# MAGIC | Tagging taxonomy agreed | `cost_center`, `team`, `environment` mandatory | | | |
# MAGIC | Cluster policy enforcing tags | Applied to all-purpose + jobs | | | |
# MAGIC | Warehouses tagged | All SQL warehouses | | | |
# MAGIC | Serverless budget policies | Serverless usage carries tags | | | |
# MAGIC | Untagged spend | Trending → 0 | | | |
# MAGIC | Budget + alerts | 75/90/100% to FinOps DL | | | |
# MAGIC | Cost views | `v_usage_priced` / `v_cost_daily` live | | | |
# MAGIC | Dashboard | Deployed & shared | | | |

# COMMAND ----------

# MAGIC %sql
# MAGIC -- ▶️ Progress metric: untagged % over time (should be falling week over week)
# MAGIC SELECT date_trunc('WEEK', usage_date) AS week,
# MAGIC        round(100 * sum(CASE WHEN cost_center = '(untagged)' THEN list_cost_usd ELSE 0 END)
# MAGIC              / nullif(sum(list_cost_usd),0), 1) AS pct_untagged
# MAGIC FROM ${catalog}.${schema}.v_cost_daily
# MAGIC GROUP BY week ORDER BY week;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3.2 Mosaic AI Gateway — govern AI cost & usage
# MAGIC
# MAGIC ### 📖 Concept
# MAGIC As teams adopt GenAI, model-serving spend becomes a new, fast-growing cost line. **Mosaic AI Gateway** puts a governance layer in front of model serving endpoints (both Databricks-hosted foundation models and **external models** like Azure OpenAI). It gives you:
# MAGIC - **Usage tracking** — request/token counts per endpoint, logged to system tables.
# MAGIC - **Payload / inference logging** — request & response captured to an **inference table** for audit and quality.
# MAGIC - **Rate limits** — per-endpoint or per-user caps (QPM / tokens) to prevent runaway cost.
# MAGIC - **Guardrails** — PII/safety filtering on prompts and responses.
# MAGIC - **Cost attribution** — serving usage lands in `system.billing.usage` and `system.serving.*`, so the same tag story from Session 1 extends to AI.
# MAGIC
# MAGIC > ☁️ **Azure note:** a common pattern is fronting **Azure OpenAI** as an *external model* endpoint. AI Gateway then centralizes rate limits, logging, and usage tracking across all AI traffic regardless of provider — one governance point, one cost view.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🛠️ Implementation guide — create a governed external-model endpoint
# MAGIC *Serving → Create serving endpoint → External model*, or via API/SDK. Attach an **AI Gateway** config with usage tracking, an inference table, and rate limits. Example payload:
# MAGIC ```json
# MAGIC {
# MAGIC   "name": "azure-openai-gpt4o-governed",
# MAGIC   "config": {
# MAGIC     "served_entities": [{
# MAGIC       "external_model": {
# MAGIC         "name": "gpt-4o", "provider": "openai", "task": "llm/v1/chat",
# MAGIC         "openai_config": { "openai_api_type": "azure",
# MAGIC           "openai_api_base": "https://<resource>.openai.azure.com",
# MAGIC           "openai_deployment_name": "gpt-4o",
# MAGIC           "openai_api_key": "{{secrets/ai/azure_openai_key}}" }
# MAGIC       }
# MAGIC     }]
# MAGIC   },
# MAGIC   "ai_gateway": {
# MAGIC     "usage_tracking_config": { "enabled": true },
# MAGIC     "inference_table_config": { "enabled": true,
# MAGIC       "catalog_name": "main", "schema_name": "cost_demo", "table_name_prefix": "aigw" },
# MAGIC     "rate_limits": [{ "calls": 100, "renewal_period": "minute" }],
# MAGIC     "guardrails": { "input": { "pii": { "behavior": "BLOCK" } } }
# MAGIC   }
# MAGIC }
# MAGIC ```

# COMMAND ----------

# ▶️ Example: create the governed endpoint via the SDK (guarded — set CREATE=True to run).
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput, ServedEntityInput, ExternalModel, OpenAiConfig,
    AiGatewayConfig, AiGatewayUsageTrackingConfig, AiGatewayInferenceTableConfig,
    AiGatewayRateLimit,
)

CREATE = False
if CREATE:
    w = WorkspaceClient()
    w.serving_endpoints.create(
        name="azure-openai-gpt4o-governed",
        config=EndpointCoreConfigInput(served_entities=[ServedEntityInput(
            external_model=ExternalModel(
                name="gpt-4o", provider="openai", task="llm/v1/chat",
                openai_config=OpenAiConfig(
                    openai_api_type="azure",
                    openai_api_base="https://<resource>.openai.azure.com",
                    openai_deployment_name="gpt-4o",
                    openai_api_key="{{secrets/ai/azure_openai_key}}")))]),
        ai_gateway=AiGatewayConfig(
            usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
            inference_table_config=AiGatewayInferenceTableConfig(
                enabled=True, catalog_name=catalog, schema_name=schema, table_name_prefix="aigw"),
            rate_limits=[AiGatewayRateLimit(calls=100, renewal_period="minute")]))
    print("Created governed endpoint.")
else:
    print("Set CREATE=True to create the governed AI Gateway endpoint.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### ▶️ Example — AI serving cost & usage attribution
# MAGIC Model-serving usage is billable and shows up in `system.billing.usage` under serving products. The query below reuses the priced view (from Session 2) to isolate AI/serving spend by team.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- AI / model-serving spend by team (extends the tagging story to GenAI)
# MAGIC SELECT team, product,
# MAGIC        round(sum(list_cost_usd), 2) AS list_cost_usd
# MAGIC FROM ${catalog}.${schema}.v_usage_priced
# MAGIC WHERE lower(product) LIKE '%serving%' OR lower(product) LIKE '%model%' OR lower(product) LIKE '%gpu%'
# MAGIC GROUP BY team, product
# MAGIC ORDER BY list_cost_usd DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Endpoint-level usage from the serving system table (token/request tracking).
# MAGIC -- Requires the `serving` system schema; comment out if not enabled.
# MAGIC SELECT * FROM system.serving.endpoint_usage
# MAGIC ORDER BY 1 DESC
# MAGIC LIMIT 20;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Wrap-up & next steps
# MAGIC - Cost is now **attributable** (tags), **enforced** (policies), **monitored** (budgets + alerts), **visible** (views + dashboard), and **extended to AI** (AI Gateway).
# MAGIC - Suggested follow-ups: chargeback reports per `cost_center`; anomaly alerts on `v_cost_daily`; AI Gateway rate limits per team; quarterly tag-hygiene review.

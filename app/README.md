# Observability Setup Center (Databricks App)

A one-stop Streamlit app where a customer **assesses** their cost/governance posture and **applies** setup — tagging, budgets, policies, AI Gateway, and governed tags — with every write following **Assess → Preview → Apply**.

## Why it's safe
- **On-behalf-of auth:** writes act as the **logged-in operator**, respecting their own Unity Catalog / workspace permissions. The app is never a privilege-escalation path.
- **Preview before apply:** every write shows a diff/plan and requires an explicit confirm.
- **NL alerts are constrained:** the natural-language builder may only emit read-only `SELECT`s over allow-listed system tables, and the generated SQL is shown to a human before any alert is created.

## Tabs
| Tab | Does |
|---|---|
| 📊 Overview | Governance-Hub-style single pane (Cost · Tags · AI · Data) |
| 🏷️ Tags | Apply a tag taxonomy to clusters/jobs/warehouses; assign governed tags to UC assets |
| 💰 Budgets, Alerts & Policies | Serverless budget policies, account budgets, cluster policy, **NL Alert Builder** |
| 🤖 AI Gateway | Usage tracking, inference tables, rate limits, PII guardrails on serving endpoints |
| 🔒 Data Governance | Access/grants summary, data classification, Lakehouse Monitoring |

## Structure
```
app/
  app.py            entry + sidebar nav
  app.yaml          Databricks App config
  requirements.txt
  lib/              pure logic + SDK/SQL calls (assess, tagging, budgets, policies,
                    ai_gateway, governed_tags, nl_alerts, auth)
  views/            one Streamlit render() per tab
tests/              unit tests for pure logic (no workspace needed)
```

## Run locally
```bash
pip install -r app/requirements.txt
export DATABRICKS_HOST=...        # workspace URL
export DATABRICKS_TOKEN=...       # or a configured CLI profile
export DATABRICKS_WAREHOUSE_ID=...# SQL warehouse for system.* reads
cd app && streamlit run app.py
```

## Deploy as a Databricks App (recommended, GA on Azure)
```bash
databricks sync app "/Workspace/Users/<you>/observability-setup-center"
databricks apps deploy observability-setup-center \
  --source-code-path "/Workspace/Users/<you>/observability-setup-center"
```
Grant the app **user authorization** so writes run as the operator, and set
`DATABRICKS_WAREHOUSE_ID` in the app's env.

## Test
```bash
pip install pytest && pytest tests/
```

> Costs are **list price** (`system.billing.list_prices`); actual invoice varies by contract.

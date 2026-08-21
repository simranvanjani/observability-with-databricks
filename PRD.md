# PRD — Observability Setup Center

**Status:** Draft · **Owner:** Simran Vanjani (Databricks Scale SE) · **Last updated:** 2026-08-21
**Type:** Field accelerator / demo app (Databricks App, Streamlit)

---

## 1. Summary
The **Observability Setup Center** is a Databricks App that lets a customer stand up cost-management and governance observability in one guided place, instead of stitching together the account console, cluster UI, jobs UI, SQL alerts, and serving config by hand. It **assesses** current posture from system tables, then **applies** the setup — tagging, budgets, policies, AI Gateway governance, and governed tags — with a preview-and-confirm step on every change. A natural-language alert builder lets users describe alerts in plain English and have them created safely against system tables.

It is the "do it" accelerator that pairs with the "learn how" notebooks in this repo.

## 2. Problem
Cost and governance observability on Databricks is powerful but **spread across many surfaces**: tags live on clusters/jobs/warehouses, serverless attribution needs budget policies, alerts live in DBSQL, budgets in the account console, AI cost in serving + AI Gateway, and data governance in Unity Catalog. Customers in an enablement session (STS) can *understand* each piece but leave without an easy, repeatable way to **apply** it across their estate. The result: low tagging coverage, unattributed spend, and no early-warning alerts.

## 3. Goals & non-goals
**Goals**
- Cut time-to-value: go from "no tagging strategy" to "enforced tags + budgets + alerts" within a session.
- Make cost **attributable** (tags), **enforced** (policies), **monitored** (budgets/alerts), **visible** (single pane), and **extended to AI** (AI Gateway).
- Be **safe to run in a customer workspace** — no silent bulk writes.
- Be **repeatable** across customers (a field accelerator, not a one-off).

**Non-goals**
- Not a replacement for the native **Governance Hub** — it mirrors and complements it.
- Not a billing/invoicing system (uses **list price**, not contract/actual).
- Not a cross-cloud cost aggregator (e.g., it does not read Azure Cost Management).
- Not a BI tool — it deep-links to dashboards rather than replacing them.

## 4. Users & personas
| Persona | Need |
|---|---|
| **Platform / FinOps admin** | Apply tagging, budgets, and policies across the estate; see coverage gaps |
| **Data team lead** | Attribute their team's spend; set alerts on their slice |
| **Databricks SE (operator/demo driver)** | Show the value live and leave behind a working setup |

Auth model reflects this: the app acts **on behalf of the logged-in operator**, so it can only do what that person is already allowed to do.

## 5. Scope — features
Each write follows **Assess → Preview → Apply** (show a diff/plan, require explicit confirm).

| Tab | Feature | Reads | Writes |
|---|---|---|---|
| 📊 **Overview** | Governance-Hub-style single pane across Cost · Tags · AI · Data; deep-link to native Hub | system.billing, system.access | — |
| 🏷️ **Tags** | Apply tag taxonomy to clusters/jobs/warehouses with diff preview; assign governed tags to UC securables | SDK asset lists, UC tag assignments | cluster/job/warehouse tags, `ALTER … SET TAGS` |
| 💰 **Budgets, Alerts & Policies** | Serverless **budget policies**, account **budgets** + thresholds, governance **cluster policy**, and the **NL Alert Builder** | budgets/policies lists | budget policy, cluster policy, SQL alert |
| 🤖 **AI Gateway** | Enable usage tracking, inference tables, rate limits, PII guardrails on serving endpoints | serving endpoints | AI Gateway config |
| 🔒 **Data Governance** | Access/grants summary, data-classification enablement guidance, Lakehouse Monitoring quality monitor | information_schema, system.access | quality monitor |

### 5a. Natural-language alert builder (headline feature)
1. Operator describes an alert in plain English (*"alert when finance's monthly serverless spend passes $5k"*).
2. A Databricks-hosted foundation model translates it to a **read-only SELECT over allow-listed system tables** + a threshold spec, returned as strict JSON.
3. The generated SQL + threshold are **shown for review**.
4. On confirm, the app creates a **Databricks SQL Alert** with recipients.

**Safety:** only `system.billing.usage`, `system.access.audit`, `system.billing.list_prices` may be referenced; write keywords (INSERT/UPDATE/DELETE/ALTER/DROP/…) are rejected; a human always reviews the SQL before creation.

## 6. Key user flows
- **Assess → tag:** Open Overview → see tagging coverage % and untagged spend → go to Tags → set taxonomy → select assets → preview diff → apply.
- **Close serverless gap:** Budgets & Policies → create a budget policy carrying tags → serverless usage becomes attributable.
- **NL alert:** Budgets & Policies → describe alert → review SQL → create.
- **Govern AI:** AI Gateway → pick endpoint → enable tracking/inference table/rate limit → apply.

## 7. Technical design
- **Platform:** Streamlit Databricks App (GA on Azure). `app.yaml` runs `streamlit run app.py`.
- **Reads:** SQL warehouse via `databricks-sql-connector` over `system.*`.
- **Writes:** Databricks SDK (`WorkspaceClient`).
- **Auth:** on-behalf-of user token (`X-Forwarded-Access-Token`) when user authorization is enabled; falls back to the app service principal for local dev.
- **Structure:** `lib/` (pure logic + SDK/SQL calls, independently testable) and `views/` (one `render()` per tab). Pure plan/diff and NL-SQL validation are unit-tested with no workspace dependency.

## 8. Security & privacy
- Operator-scoped writes (no privilege escalation).
- Preview-before-apply on every mutation; per-asset success/failure reporting (never silently half-done).
- NL builder constrained to read-only, allow-listed tables with human review.
- All cost shown as **list price** with an explicit caveat.

## 9. Success metrics
- **Tagging coverage %** rises (untagged spend → 0) after a session.
- Time from "empty" to "budgets + alerts + enforced tags" (target: within one working session).
- # of budget policies / alerts / policies created via the app.
- Reuse across customer engagements (accelerator adoption).

## 10. Risks & mitigations
| Risk | Mitigation |
|---|---|
| App SP/operator lacks permissions | OBO auth + clear per-action "which grant/role is missing" errors |
| SDK call signatures drift across versions | Pin versions in `requirements.txt`; smoke-test against a live workspace before demos |
| NL builder generates wrong/unsafe SQL | Allow-list tables, reject writes, mandatory human review |
| Confusion vs. native Governance Hub | Position as complement; Overview deep-links to the Hub |

## 11. Roadmap / phasing
- **P1 (MVP):** Overview + Tags (coverage dashboard + one-click tagging).
- **P2:** Budgets, Alerts & Policies (incl. NL Alert Builder).
- **P3:** AI Gateway + Data Governance.

## 12. Open questions
- Should the app also materialize the reusable UC cost views (currently left in notebook 02)?
- Account-level budgets: create via API in-app, or keep as a deep-link to the console?
- Which foundation model to standardize on for the NL builder across customer workspaces?

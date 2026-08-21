# Observability / Cost STS Demo

A runnable Databricks notebook bundle for a 3-session cost-management, tagging, budgets, and AI-governance STS. Built for **Azure Databricks**, written **cloud-agnostic** on `system.*` tables. Runs against **real system tables** in the customer workspace.

## Contents
| File | Session |
|---|---|
| `00_START_HERE.py` | Prereqs, system-schema check, widgets, permissions probe, packaging |
| `01_Cost_Setup_Tagging.py` | Session 1 — cost model, tagging taxonomy, tag clusters/jobs/warehouses, untagged-spend analysis, enforcing cluster policy |
| `02_Budgets_Dashboards.py` | Session 2 — budgets/policies/alerts, billing/usage/audit UC views, prebuilt dashboards |
| `03_Progress_AI_Gateway.py` | Session 3 — progress check-in, Mosaic AI Gateway governance & AI cost attribution |

Each topic: **📖 Concept → 🛠️ Implementation guide → ▶️ Runnable example.**

## App: Observability Setup Center
`app/` is a **Streamlit Databricks App** — a one-stop UI where a customer assesses posture and applies setup (tagging, budgets, policies, AI Gateway, governed tags), every write following **Assess → Preview → Apply**. It includes a **natural-language alert builder**: describe an alert in plain English and it's translated to SQL over system tables, shown for review, then created as a Databricks SQL Alert. See [`app/README.md`](app/README.md). The notebooks are the "under the hood" teaching companion.

## Prerequisites
- Unity Catalog + `system` schemas enabled (`billing`, `access`, `compute`, `lakeflow`, `serving`)
- A SQL warehouse; `SELECT` on `system.billing`
- Account admin for budgets/budget policies

## Install
**Easiest (one-click .dbc):** import the `.py` files into a folder in any workspace → right-click folder → **Export → DBC Archive** → give the customer that `.dbc` to import in one action.

**Versioned:** put this folder in a Git repo → customer does **Workspace → Add → Git folder**.

Run `00_START_HERE` first to set widgets (`catalog`, `schema`, `tag_key`, `lookback_days`) — the session notebooks read them.

## Notes
- Currency is **list price** via `system.billing.list_prices` (relative cost; actual invoice varies by contract).
- Destructive/create actions (cluster tags, policies, endpoints) are **guarded behind flags** so the notebooks are safe to run/present as-is.

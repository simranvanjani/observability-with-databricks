"""Natural-language alert builder.

Flow (Assess -> Preview -> Apply):
  1. Operator describes an alert in plain English.
  2. ``generate`` calls a Databricks-hosted foundation model (through the serving
     endpoint / AI Gateway) to translate it into a SQL query over system tables
     plus a threshold spec. Output is constrained to strict JSON.
  3. The UI shows the generated SQL + threshold for review (never runs blind).
  4. ``create_alert`` saves the query and a Databricks SQL Alert on confirm.

Only the two allow-listed system tables below may be referenced, and the model
is instructed to emit read-only SELECTs. The generated SQL is still shown to a
human before anything is created.
"""
from __future__ import annotations

import json
import re

ALLOWED_TABLES = ("system.billing.usage", "system.access.audit", "system.billing.list_prices")

_DEFAULT_MODEL = "databricks-meta-llama-3-3-70b-instruct"

_SYSTEM_PROMPT = f"""You translate a plain-English monitoring request into a Databricks SQL alert.
Return STRICT JSON only, no prose, matching:
{{
  "title": "<short alert name>",
  "sql": "<one read-only SELECT over system tables>",
  "value_column": "<the numeric column the alert compares>",
  "op": "GREATER_THAN|LESS_THAN|EQUAL",
  "threshold": <number>,
  "explanation": "<one sentence: what this alerts on>"
}}
Rules:
- Only reference these tables: {', '.join(ALLOWED_TABLES)}.
- SELECT only. Never write INSERT/UPDATE/DELETE/ALTER/DROP/CREATE/MERGE.
- For cost, join list_prices and use usage_quantity * lp.pricing.effective_list.default.
- The query must return exactly one row with the value_column as a number.
"""

_FORBIDDEN = re.compile(r"\b(insert|update|delete|alter|drop|create|merge|grant|revoke)\b", re.I)


def generate(nl_request: str, model: str = _DEFAULT_MODEL) -> dict:
    """Return the parsed alert spec. Raises ValueError if the SQL is unsafe."""
    from .auth import get_workspace_client
    w = get_workspace_client()
    resp = w.serving_endpoints.query(
        name=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": nl_request},
        ],
        temperature=0.0,
    )
    content = resp.choices[0].message.content
    spec = json.loads(_extract_json(content))
    _validate(spec)
    return spec


def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Model did not return JSON:\n{text}")
    return text[start : end + 1]


def _validate(spec: dict) -> None:
    sql = spec.get("sql", "")
    if _FORBIDDEN.search(sql):
        raise ValueError(f"Refusing non-read-only SQL:\n{sql}")
    if not any(t in sql for t in ALLOWED_TABLES):
        raise ValueError("Generated SQL does not reference an allow-listed system table.")
    for field in ("title", "sql", "value_column", "op", "threshold"):
        if field not in spec:
            raise ValueError(f"Missing field '{field}' in generated spec.")


def create_alert(spec: dict, recipients: list[str] | None = None):
    """Save the query + create a Databricks SQL Alert on the configured warehouse."""
    from .auth import get_workspace_client, get_warehouse_id
    w = get_workspace_client()
    warehouse_id = get_warehouse_id()
    if not warehouse_id:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID must be set to create alerts.")

    from databricks.sdk.service.sql import (
        CreateQueryRequestQuery, AlertOperand, AlertOperandColumn, AlertOperandValue,
        AlertCondition, AlertConditionOperand, CreateAlertRequestAlert, ComparisonOperator,
    )

    query = w.queries.create(query=CreateQueryRequestQuery(
        display_name=spec["title"], warehouse_id=warehouse_id, query_text=spec["sql"]))

    op_map = {"GREATER_THAN": ComparisonOperator.GREATER_THAN,
              "LESS_THAN": ComparisonOperator.LESS_THAN,
              "EQUAL": ComparisonOperator.EQUAL}
    condition = AlertCondition(
        op=op_map.get(spec["op"], ComparisonOperator.GREATER_THAN),
        operand=AlertConditionOperand(column=AlertOperandColumn(name=spec["value_column"])),
        threshold=AlertOperandValue(double_value=float(spec["threshold"])),
    )
    alert = w.alerts.create(alert=CreateAlertRequestAlert(
        display_name=spec["title"], query_id=query.id, condition=condition))
    return {"query_id": query.id, "alert_id": alert.id, "title": spec["title"]}

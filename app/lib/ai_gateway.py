"""Mosaic AI Gateway governance for model serving endpoints.

Enable usage tracking, inference-table logging, rate limits, and guardrails on
existing or new serving endpoints so AI cost & usage are attributable.
"""
from __future__ import annotations

from .auth import get_workspace_client


def list_endpoints():
    w = get_workspace_client()
    try:
        return [{"name": e.name, "state": str(e.state)} for e in w.serving_endpoints.list()]
    except Exception as e:
        return {"error": str(e)}


def preview_gateway(endpoint: str, calls_per_min: int, catalog: str, schema: str,
                    block_pii: bool) -> dict:
    return {
        "action": "configure AI Gateway",
        "endpoint": endpoint,
        "usage_tracking": True,
        "inference_table": f"{catalog}.{schema}.aigw_*",
        "rate_limit": f"{calls_per_min} calls/minute",
        "guardrails": {"input_pii": "BLOCK" if block_pii else "off"},
    }


def apply_gateway(endpoint: str, calls_per_min: int, catalog: str, schema: str,
                  block_pii: bool):
    w = get_workspace_client()
    from databricks.sdk.service.serving import (
        AiGatewayConfig, AiGatewayUsageTrackingConfig, AiGatewayInferenceTableConfig,
        AiGatewayRateLimit, AiGatewayGuardrails, AiGatewayGuardrailParameters,
        AiGatewayGuardrailPiiBehavior,
    )
    guardrails = None
    if block_pii:
        guardrails = AiGatewayGuardrails(
            input=AiGatewayGuardrailParameters(
                pii=AiGatewayGuardrailPiiBehavior(behavior="BLOCK")))
    return w.serving_endpoints.put_ai_gateway(
        name=endpoint,
        usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
        inference_table_config=AiGatewayInferenceTableConfig(
            enabled=True, catalog_name=catalog, schema_name=schema, table_name_prefix="aigw"),
        rate_limits=[AiGatewayRateLimit(calls=calls_per_min, renewal_period="minute")],
        guardrails=guardrails,
    )

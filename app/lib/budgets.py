"""Budget policies (serverless tag attribution) and account budgets + alerts.

Budget policies attach custom_tags to serverless usage (jobs, SQL, serving),
closing the attribution gap for compute that has no cluster to tag.
Budgets + alert thresholds are account-level; require an account admin.
"""
from __future__ import annotations

from .auth import get_workspace_client


def list_budget_policies():
    w = get_workspace_client()
    try:
        return list(w.budget_policy.list())
    except Exception as e:
        return {"error": str(e)}


def create_budget_policy(name: str, tags: dict[str, str]):
    """Create a serverless budget policy carrying the given custom_tags."""
    w = get_workspace_client()
    from databricks.sdk.service.billing import BudgetPolicy, CustomPolicyTag
    policy = BudgetPolicy(
        policy_name=name,
        custom_tags=[CustomPolicyTag(key=k, value=v) for k, v in tags.items()],
    )
    return w.budget_policy.create(policy=policy)


def preview_budget_policy(name: str, tags: dict[str, str]) -> dict:
    """Non-mutating preview of what create_budget_policy will do."""
    return {"action": "create budget policy", "name": name, "custom_tags": tags}


# --- account budgets + alert thresholds (account admin) --------------------
def preview_budget(name: str, amount_usd: float, thresholds_pct: list[int],
                   recipients: list[str], filter_tag: tuple[str, str] | None) -> dict:
    return {
        "action": "create budget",
        "name": name,
        "amount_usd": amount_usd,
        "alert_thresholds_pct": thresholds_pct,
        "recipients": recipients,
        "filter_tag": filter_tag,
        "note": "Budgets are account-level; requires account admin. Managed via the "
                "Account Console -> Usage -> Budgets, or the Budgets API.",
    }

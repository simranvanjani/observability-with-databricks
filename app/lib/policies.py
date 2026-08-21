"""Governance cluster policy — enforce required tags + cost guardrails."""
from __future__ import annotations

import json


def build_definition(required_tag_regex: dict[str, str],
                     team_allowlist: list[str],
                     max_workers: int = 8,
                     max_autotermination_min: int = 60) -> dict:
    """Pure builder for a cost-guardrail policy definition."""
    definition: dict = {}
    for key, pattern in required_tag_regex.items():
        definition[f"custom_tags.{key}"] = {"type": "regex", "pattern": pattern, "hidden": False}
    if team_allowlist:
        definition["custom_tags.team"] = {"type": "allowlist", "values": team_allowlist}
    definition["autotermination_minutes"] = {"type": "range", "maxValue": max_autotermination_min,
                                              "defaultValue": min(30, max_autotermination_min)}
    definition["num_workers"] = {"type": "range", "maxValue": max_workers}
    return definition


def apply_policy(name: str, definition: dict):
    """Create or update the named cluster policy."""
    from .auth import get_workspace_client
    w = get_workspace_client()
    existing = {p.name: p for p in w.cluster_policies.list()}
    payload = json.dumps(definition)
    if name in existing:
        w.cluster_policies.edit(policy_id=existing[name].policy_id, name=name, definition=payload)
        return {"action": "updated", "name": name}
    w.cluster_policies.create(name=name, definition=payload)
    return {"action": "created", "name": name}

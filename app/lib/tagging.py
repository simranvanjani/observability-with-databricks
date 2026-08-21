"""Tagging engine — list compute assets, compute a diff plan, apply on confirm.

Follows the Assess -> Preview -> Apply contract:
  * ``list_assets``  reads current tags
  * ``plan``         pure function: (assets, desired tags, selection) -> change rows
  * ``apply``        executes the plan via the SDK; returns per-asset results

Serverless has no cluster to tag; the UI routes that to budget policies instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TagChange:
    asset_type: str          # "cluster" | "job" | "warehouse"
    asset_id: str
    asset_name: str
    current: dict = field(default_factory=dict)
    new: dict = field(default_factory=dict)

    @property
    def diff(self) -> dict:
        return {k: v for k, v in self.new.items() if self.current.get(k) != v}


# --------------------------------------------------------------------------
def list_assets() -> list[TagChange]:
    """Return current tags for all-purpose/job clusters, jobs, and warehouses."""
    from .auth import get_workspace_client
    w = get_workspace_client()
    out: list[TagChange] = []

    for c in w.clusters.list():
        out.append(TagChange("cluster", c.cluster_id, c.cluster_name or c.cluster_id,
                             current=dict(c.custom_tags or {})))
    for j in w.jobs.list():
        settings = j.settings
        out.append(TagChange("job", str(j.job_id), (settings.name if settings else "") or str(j.job_id),
                             current=dict(settings.tags or {}) if settings else {}))
    for wh in w.warehouses.list():
        cur = {t.key: t.value for t in (wh.tags.custom_tags if wh.tags else [])} if wh.tags else {}
        out.append(TagChange("warehouse", wh.id, wh.name or wh.id, current=cur))
    return out


def plan(assets: list[TagChange], desired: dict[str, str],
         selected_ids: set[str]) -> list[TagChange]:
    """Pure: build the set of changes for the selected assets. No side effects."""
    changes = []
    for a in assets:
        if a.asset_id not in selected_ids:
            continue
        merged = {**a.current, **desired}
        change = TagChange(a.asset_type, a.asset_id, a.asset_name, current=a.current, new=merged)
        if change.diff:                       # only include assets that actually change
            changes.append(change)
    return changes


def apply(changes: list[TagChange]) -> list[dict]:
    """Execute the plan. Returns [{asset, ok, error}] — never raises mid-batch."""
    from .auth import get_workspace_client
    w = get_workspace_client()
    results = []
    for ch in changes:
        try:
            if ch.asset_type == "cluster":
                cur = w.clusters.get(ch.asset_id)
                w.clusters.edit(
                    cluster_id=ch.asset_id, spark_version=cur.spark_version,
                    node_type_id=cur.node_type_id, num_workers=cur.num_workers or 0,
                    custom_tags=ch.new)
            elif ch.asset_type == "job":
                from databricks.sdk.service.jobs import JobSettings
                cur = w.jobs.get(int(ch.asset_id))
                new_settings = cur.settings
                new_settings.tags = ch.new
                w.jobs.reset(job_id=int(ch.asset_id), new_settings=new_settings)
            elif ch.asset_type == "warehouse":
                from databricks.sdk.service.sql import EndpointTags, EndpointTagPair
                cur = w.warehouses.get(ch.asset_id)
                w.warehouses.edit(
                    id=ch.asset_id, name=cur.name, cluster_size=cur.cluster_size,
                    tags=EndpointTags(custom_tags=[EndpointTagPair(key=k, value=v)
                                                   for k, v in ch.new.items()]))
            results.append({"asset": f"{ch.asset_type}:{ch.asset_name}", "ok": True, "error": None})
        except Exception as e:  # surface, don't abort the batch
            results.append({"asset": f"{ch.asset_type}:{ch.asset_name}", "ok": False, "error": str(e)})
    return results

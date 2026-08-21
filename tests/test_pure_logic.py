"""Unit tests for the pure (no-workspace) logic: tag diff/plan, policy builder,
and NL-alert SQL validation. These import only the light modules, so they run
without Streamlit, the SDK client, or a live workspace."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from lib import tagging, policies, nl_alerts  # noqa: E402


# ---- tagging.plan / diff --------------------------------------------------
def test_plan_only_includes_changed_selected_assets():
    assets = [
        tagging.TagChange("cluster", "c1", "etl", current={"team": "data-eng"}),
        tagging.TagChange("cluster", "c2", "ml", current={"cost_center": "1001"}),
    ]
    desired = {"cost_center": "1001"}
    # select both; c2 already has cost_center=1001 so it should NOT appear
    changes = tagging.plan(assets, desired, {"c1", "c2"})
    ids = {c.asset_id for c in changes}
    assert ids == {"c1"}
    assert changes[0].new == {"team": "data-eng", "cost_center": "1001"}


def test_plan_respects_selection():
    assets = [tagging.TagChange("job", "j1", "nightly", current={})]
    changes = tagging.plan(assets, {"team": "ds"}, selected_ids=set())
    assert changes == []


# ---- policies.build_definition -------------------------------------------
def test_policy_enforces_tags_and_limits():
    d = policies.build_definition({"cost_center": "^[0-9]{4}$"}, ["data-eng", "ds"],
                                  max_workers=4, max_autotermination_min=45)
    assert d["custom_tags.cost_center"]["type"] == "regex"
    assert d["custom_tags.team"]["values"] == ["data-eng", "ds"]
    assert d["num_workers"]["maxValue"] == 4
    assert d["autotermination_minutes"]["maxValue"] == 45


# ---- nl_alerts validation -------------------------------------------------
def test_rejects_non_readonly_sql():
    spec = {"title": "x", "sql": "DELETE FROM system.billing.usage",
            "value_column": "c", "op": "GREATER_THAN", "threshold": 1}
    try:
        nl_alerts._validate(spec)
        assert False, "should have rejected write SQL"
    except ValueError:
        pass


def test_rejects_non_allowlisted_table():
    spec = {"title": "x", "sql": "SELECT count(*) c FROM main.secret.t",
            "value_column": "c", "op": "GREATER_THAN", "threshold": 1}
    try:
        nl_alerts._validate(spec)
        assert False, "should have rejected non-allowlisted table"
    except ValueError:
        pass


def test_accepts_valid_billing_alert():
    spec = {"title": "spend", "value_column": "list_cost_usd", "op": "GREATER_THAN",
            "threshold": 5000,
            "sql": "SELECT sum(usage_quantity) list_cost_usd FROM system.billing.usage"}
    nl_alerts._validate(spec)  # should not raise

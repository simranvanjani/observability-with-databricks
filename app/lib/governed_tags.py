"""Governed tags: define account tag policies (allowed values) and assign
tags to Unity Catalog securables (catalogs / schemas / tables).
"""
from __future__ import annotations

from .auth import get_workspace_client, run_sql


def assign_tag(securable_type: str, full_name: str, key: str, value: str):
    """ALTER <securable> SET TAGS — assign a tag to a UC object.

    securable_type: 'CATALOG' | 'SCHEMA' | 'TABLE'
    """
    st = securable_type.upper()
    run_sql(f"ALTER {st} {full_name} SET TAGS ('{key}' = '{value}')")
    return {"action": "assigned tag", "securable": f"{st} {full_name}", "tag": {key: value}}


def preview_assign(securable_type: str, full_name: str, key: str, value: str) -> dict:
    return {"action": "assign tag", "securable": f"{securable_type.upper()} {full_name}",
            "tag": {key: value},
            "sql": f"ALTER {securable_type.upper()} {full_name} SET TAGS ('{key}' = '{value}')"}


def list_governed_tags():
    """Account governed-tag policies (allowed key/values).

    Governed tag *policies* are defined at the account level (Settings ->
    Governed tags, or the Tag Policies API). This surfaces current UC tag
    assignments as a proxy where the policies API is unavailable.
    """
    try:
        return run_sql(
            """
            SELECT catalog_name, schema_name, table_name, tag_name, tag_value
            FROM system.information_schema.table_tags
            LIMIT 500
            """
        )
    except Exception as e:
        return {"error": str(e)}

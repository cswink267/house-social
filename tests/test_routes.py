"""Every public handler in the dashboard API is a route."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_public_handler_keeps_its_route():
    tree = ast.parse((ROOT / "dashboard" / "plugin_api.py").read_text(encoding="utf-8"))
    bare = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and not node.name.startswith("_")
        and not any(
            isinstance(item, ast.Call) and getattr(item.func, "attr", "") in {"get", "post", "put", "patch", "delete"}
            for item in node.decorator_list
        )
    ]
    assert bare == []

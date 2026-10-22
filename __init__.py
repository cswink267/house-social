"""Agent tools for the house social roster. The dashboard is the composer."""

from __future__ import annotations

import json


def register(ctx) -> None:
    from .store import create_piece, load, roster

    def handle_roster(_params, **kwargs):
        del kwargs
        return json.dumps({"posting": False, "brands": roster(load())})

    def handle_draft(params, **kwargs):
        del kwargs
        try:
            piece = create_piece(load(), params.get("brand_id", ""), params.get("idea", ""))
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        return json.dumps({"ok": True, "posted": False, "piece": piece})

    ctx.register_tool(
        name="house_social_roster",
        toolset="house_social",
        schema={
            "name": "house_social_roster",
            "description": "List house brands and whether Facebook, Instagram, and Threads handles are known. Does not post.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=handle_roster,
    )
    ctx.register_tool(
        name="house_social_draft",
        toolset="house_social",
        schema={
            "name": "house_social_draft",
            "description": "Save a house-social draft from one idea, shaped separately for Facebook, Instagram, and Threads. Does not publish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_id": {"type": "string", "description": "Roster id, such as misfit-mindset or jamhaul."},
                    "idea": {"type": "string", "description": "The idea in the author's words."},
                },
                "required": ["brand_id", "idea"],
            },
        },
        handler=handle_draft,
    )

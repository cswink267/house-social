"""Agent tools for the house social roster.

The agent can draft a piece in its own words, give it a time, see the queue,
and post. How far it may go is the brand's mode on the Brief: fully
autonomous schedules and posts without a person; the other modes send the
piece for review first. Posting also needs House settings and the brand to
have posting turned on.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def register(ctx) -> None:
    # The modules import each other by plain name, as the dashboard loads them.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from store import create_piece, load, roster, update_piece

    def answer(work):
        try:
            return json.dumps({"ok": True, **work()})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    def handle_roster(_params, **kwargs):
        del kwargs
        from publish import posting_view

        state = load()
        return json.dumps({"posting": posting_view(state)["on"], "brands": roster(state)})

    def handle_draft(params, **kwargs):
        del kwargs

        def work():
            piece = create_piece(
                load(),
                params.get("brand_id", ""),
                params.get("idea", ""),
                pillar=params.get("pillar", "") or "",
                format_name=params.get("format", "") or "",
            )
            written = {
                platform: {"body": str(params[platform])}
                for platform in ("facebook", "instagram", "threads")
                if params.get(platform)
            }
            if written:
                piece = update_piece(load(), piece["id"], variants=written)
            return {"posted": False, "piece": piece}

        return answer(work)

    def handle_queue(params, **kwargs):
        del kwargs
        from queue_desk import queue_for

        def work():
            view = queue_for(load(), params.get("brand_id", ""))
            keep = ("id", "status", "label", "idea", "date", "time", "failure", "problems", "published", "can_post_now", "placeholder")
            return {"live": view["live"], "items": [{key: item.get(key) for key in keep} for item in view["items"]]}

        return answer(work)

    def handle_schedule(params, **kwargs):
        del kwargs
        from modes import agent_schedule

        return answer(lambda: agent_schedule(load(), params.get("piece_id", ""), params.get("scheduled_for", "")))

    def handle_post_now(params, **kwargs):
        del kwargs
        from publish import publish_piece

        return answer(lambda: publish_piece(load(), params.get("piece_id", ""), immediate=True))

    def handle_post_due(_params, **kwargs):
        del kwargs
        from publish import tick

        def work():
            result = tick()
            if result is None:
                raise RuntimeError("Another run is posting right now. Try again in a minute.")
            return result

        return answer(work)

    def handle_posting(params, **kwargs):
        del kwargs
        from publish import posting_view

        return answer(lambda: posting_view(load(), params.get("brand_id", "") or ""))

    brand = {"type": "string", "description": "Roster id, such as misfit-mindset or jamhaul."}
    piece = {"type": "string", "description": "The piece id from house_social_draft or house_social_queue."}
    tools = [
        (
            "house_social_roster",
            "List house brands, whether Facebook, Instagram, and Threads are known, and whether posting is on.",
            {"type": "object", "properties": {}},
            handle_roster,
        ),
        (
            "house_social_draft",
            "Save a draft for one brand. Give the idea, and optionally the exact words for facebook, instagram, and threads. "
            "The three must differ. Instagram hashtags go in the words only when the brand allows. Saving does not post.",
            {
                "type": "object",
                "properties": {
                    "brand_id": brand,
                    "idea": {"type": "string", "description": "The idea in the author's words."},
                    "facebook": {"type": "string", "description": "Facebook post, up to 5000 characters."},
                    "instagram": {"type": "string", "description": "Instagram caption, up to 2200 characters. Instagram also needs an image."},
                    "threads": {"type": "string", "description": "Threads post, up to 500 characters."},
                    "pillar": {"type": "string", "description": "A pillar id from the brand, if one fits."},
                    "format": {"type": "string", "description": "feed, quote-image, carousel, reel, story, thread, or text."},
                },
                "required": ["brand_id", "idea"],
            },
            handle_draft,
        ),
        (
            "house_social_queue",
            "List a brand's pieces with their status, time, problems, and links to what already posted.",
            {"type": "object", "properties": {"brand_id": brand}, "required": ["brand_id"]},
            handle_queue,
        ),
        (
            "house_social_schedule",
            "Give a piece a time. Under fully autonomous the piece is approved and scheduled, and posts then. "
            "Under manual or approval it is sent for review and scheduled once a person approves it.",
            {
                "type": "object",
                "properties": {
                    "piece_id": piece,
                    "scheduled_for": {"type": "string", "description": "ISO-8601 time with a timezone, such as 2026-10-27T09:00:00-04:00."},
                },
                "required": ["piece_id", "scheduled_for"],
            },
            handle_schedule,
        ),
        (
            "house_social_post_now",
            "Post an approved piece right away to every connected platform that has words for it. This is public.",
            {"type": "object", "properties": {"piece_id": piece}, "required": ["piece_id"]},
            handle_post_now,
        ),
        (
            "house_social_post_due",
            "Post every scheduled piece whose time has come. The dashboard also does this once a minute.",
            {"type": "object", "properties": {}},
            handle_post_due,
        ),
        (
            "house_social_posting",
            "Whether posting is on for the house and for one brand, and which accounts can post.",
            {"type": "object", "properties": {"brand_id": brand}},
            handle_posting,
        ),
    ]
    for name, description, parameters, handler in tools:
        ctx.register_tool(
            name=name,
            toolset="house_social",
            schema={"name": name, "description": description, "parameters": parameters},
            handler=handler,
        )

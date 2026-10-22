# House Social

A [Hermes](https://github.com/NousResearch/hermes-agent) dashboard plugin for the Misfit House brands. It reads Facebook, Instagram, and Threads, keeps a local draft queue, and learns from engagement that was actually returned.

It does not publish. Nothing in this module sends a post.

Studio (`studio.misfitmindset.com`) still owns the weekly posts, the peak posts, and the now posts. This module does not generate those.

## What you get

Each brand has the same desks.

| Desk | What it holds |
| --- | --- |
| Brief | Audience, voice line, guards, pillars, and the public handles. |
| Voice | Tone, personality, do and don't, visual notes, banned lines, required lines, and an example. Create can score a draft against that guide. |
| Pages | The Meta app id, the page or account id, and a token. The token is written to a vault. The saved record stores the vault name. |
| Ideas | A board or a list of sparks, competitor notes, trends, and questions. Tag them, set a priority, and turn one into a draft. A link is only a link. The board does not fetch it. |
| Approval | Draft, then needs review, then approved, then scheduled. One approver, or up to four names in order. Comments, the last two versions side by side, and notices on this desk. Nothing is mailed and nothing is sent. |
| Composer | The creation hub. Facebook, Instagram, and Threads each get a preview, a character count, a first comment, and media from the library. Hashtags are suggested from the brand and the draft. The assistant can rewrite, shorten, expand, vary, hook, or caption an image, and the brand voice guide is the rule. |
| Library | Images, video, carousels, templates, logos, and copy blocks. Tags, search, folders, and version history. Use on a piece or a live post, and the card shows the engagements that use actually earned. |
| Calendar | Month, week, and day. Planned, drafted, ready, scheduled, and published. Drag a piece onto a day. Filter by platform, format, pillar, or campaign. |
| Queue | What is going out. Drafts stay on the making side. Pending approval, scheduled, and failed are the pipeline. Bulk actions move pieces. A suggested hour appears only when past performance shows a real gap. Platform rules block a schedule that is not allowed. Nothing is sent. |
| Campaigns | A named effort with a kind, a goal, dates, the pieces, and the assets. Progress is how much of that work is in the campaign. Performance is what those pieces have already earned. |
| Analytics | Reach, engagement, saves, shares, follower change, top posts, and format performance for 7, 28, or 90 days, or the whole history. This window sits beside the one before it. A campaign is compared with the other posts only when both sides have three and the gap is real. A missing number stays missing. |
| Hashtags | Saved sets of up to five tags. Performance of tags that posts actually used. Notes for a topic, a sound, or a format. A tag or a format is only called ahead when the gap is real. |
| Learning | A comparison is kept only when both sides have at least three posts and the gap is real. An impression count of zero is never turned into a rate. |

Facebook and Instagram are one Meta app. A Page token can name the linked Instagram professional account, and that account is read with the same token. Threads is a separate login on `graph.threads.net`. The Facebook token cannot read it. The username often matches Instagram. The id does not.

## Install

Clone this repository into the Hermes plugins directory:

```bash
git clone https://github.com/cswink267/house-social.git ~/.hermes/plugins/house-social
```

Add `house-social` to `plugins.enabled` in `~/.hermes/config.yaml`. Restart the Hermes dashboard so the new Python routes load. Restart the gateway only when you also want the `house_social_roster` and `house_social_draft` tools. Those tools list brands and save a draft. They do not post.

The web tab is `House Social`. The desktop pane lists the roster. Both talk to `/api/plugins/house-social/`.

State is not in this repository. Drafts, connections, and pull results live in `~/.hermes/plugin-data/house-social/state.json`. Override that with `HOUSE_SOCIAL_STATE`. Library files live in a sibling `assets` directory. Override that with `HOUSE_SOCIAL_ASSETS`. Neither directory belongs in git.

The assistant calls a local OpenAI-compatible endpoint. `HOUSE_SOCIAL_AI_URL` defaults to `http://127.0.0.1:11434/v1/chat/completions`. `HOUSE_SOCIAL_AI_MODEL` defaults to `qwen3.5:9b`. Captions use `HOUSE_SOCIAL_VISION_MODEL`, default `moondream`. No key lives in this repository. If the endpoint is down, the composer says the assistant is offline.

## Tokens

Paste a token once, in the Pages desk. The plugin runs `vault set` and stores `vault:house-social.<brand>.<platform>.token` on the connection. The token is not a field in `state.json`. Saving the connection again without a token keeps the old vault name.

There is no token, app secret, or page token in this repository. `brands.py` may include a public handle or a public page id. That is not a credential.

If a pull fails, the error text is stored with `access_token` redacted.

## Optional ledger

Before a brand has a live pull, Josie Blackthorn can read a directory of daily Facebook JSON files. Point at it with `HOUSE_SOCIAL_LEDGER`. Each file is named `YYYY-MM-DD.json` and may contain:

- `posts[]` with `id`, `message`, `created_time_iso`, `local_hour`, `reactions`, `comments`, `shares`, `total`, `permalink`
- `insights` with daily rows of `date` and `value` for the usual Page metrics (`page_posts_impressions_organic`, `page_post_engagements`, and the reaction, follow, and view metrics)

A missing directory is an empty ledger. After a successful pull, the live posts replace that window. The ledger path belongs in the environment of the dashboard process, not in this git.

## Brand rules that already exist

Seeds are only rules that were already written down. A saved voice guide replaces those fields for that brand. Empty brands stay empty until someone writes them.

- Misfit Mindset speaks to you, validates before it reframes, and refuses the cheerful lines in its banned list.
- Josie Blackthorn's Facebook draft is a quote card. It cannot be marked ready until the image is ready. JamHaul does not go on her page.
- JamHaul's Facebook draft must include `jamhaul.com` and a question mark. JamHaul copy is refused on the other brands.
- A piece cannot be marked ready while the Facebook, Instagram, and Threads bodies are the same text.

`planned` holds a day without passing those gates. `ready` and `scheduled` do not.

## Layout

```
plugin.yaml              plugin name and version
__init__.py              roster and draft tools
brands.py                brands, pillars, desks
adapt.py                 one idea, three different drafts
assist.py                voice-bound rewrites, variations, hooks, and captions
queue_desk.py            the publishing queue, still local
campaigns.py             named efforts, goals, and dates
ideas.py                 sparks, notes, and the draft they become
approval.py              review steps, comments, and notices on the desk
hashtags.py              saved sets and the tags posts used
voice.py                 guides and the voice checklist
library.py               assets, versions, and use
store.py                 state, connections, calendar, pulls
learn.py                 performance and lessons
meta.py                  Graph reads for Facebook, Instagram, and Threads
dashboard/manifest.json  tab registration
dashboard/plugin_api.py  HTTP routes
dashboard/dist/          the dashboard UI
desktop/plugin.js        the desktop roster pane
tests/                   pytest
```

## Tests

```bash
python -m pytest tests
```

The tests use fake tokens and fake ids. One test fails if a credential-shaped string or a private machine path shows up in the tree.

## Times

Dates you drop on the calendar are America/New_York. A date with no clock lands at noon. Moving a piece that already has a clock keeps that clock and changes the day.

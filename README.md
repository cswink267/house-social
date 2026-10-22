# House Social

A [Hermes](https://github.com/NousResearch/hermes-agent) dashboard plugin for the Misfit House brands. It reads Facebook, Instagram, and Threads, keeps a local draft queue, and learns from engagement that was actually returned.

It does not publish. Nothing in this module sends a post.

Studio (`studio.misfitmindset.com`) still owns the weekly posts, the peak posts, and the now posts. This module does not generate those.

## What you get

Each brand has the same desks.

| Desk | What it holds |
| --- | --- |
| Brief | Audience, voice line, guards, pillars, and the public handles. |
| Voice | Tone, personality, formality, humor, point of view, do and don't, visual notes, banned lines, preferred lines, required lines, and competitor notes. Pillars keep the angles you write. On-brand and off-brand examples can be written, pasted, or taken from posts when the gap is real. Create scores a draft and can ask for a rewrite. Each save keeps a version. |
| Pages | The Meta app id, the page or account id, and a token. The token is written to a vault. The saved record stores the vault name. |
| Ideas | A board or a list of sparks, competitor notes, trends, questions, and comments. One click makes a draft and opens the composer. A pattern line appears only when the posts already show it. An idea is archived as ahead only when its draft has a post at least 3× the others. Suggest uses the voice, the pillars, those posts, and the trend notes you saved. |
| Approval | Draft, then needs review, then approved, then scheduled. One approver, or up to four names in order. Comments, the last two versions side by side, and notices on this desk. Nothing is mailed and nothing is sent. |
| Composer | The creation hub. Start from a subject, an idea, an image, or a post that is at least 3× the others. Facebook, Instagram, and Threads each get a preview and a count. The assistant stays inside the brand voice. A variation shows the historical pattern it matches, and only when that pattern is clear. Improve this draft asks for a rewrite from those misses. What the posts say lists similar posts with the engagements they earned. Hold a day on the calendar, or save the words to the library. Nothing is sent. |
| Library | Images, video, carousels, templates, logos, and copy blocks. Hooks, CTAs, hashtags, and bios insert into the composer. Tags, search, folders, and versions. Mean engagement and last used come from the uses that have numbers. A version or a topic is called ahead only when both sides have three uses and the gap is real. Image tags come from tags this brand already uses, or from the vision model when it answers. |
| Calendar | Month, week, and day. Drag a piece onto a day. Color by status, pillar, campaign, or platform. The next 7 days name any pillar that has nothing planned. A suggested day or hour appears only when that pattern is clear. An idea or a library block can be held on the chosen day. A recurrence holds the same words on that weekday for up to 8 weeks. Nothing is sent. |
| Queue | Draft, needs approval, approved, scheduled, on the record, or failed. On the record is a post already tied to the draft, with its engagements. Bulk actions still move pieces. A format hour is used when that format is clearly ahead; otherwise the brand hour, and only when the gap is real. A slot warning names an hour that has underperformed for that format. The pace line counts what is scheduled and does not apply a Meta rate limit. Nothing is sent. |
| Campaigns | A named effort with a kind, a goal, dates, the pieces, and the assets. Clone copies the shape and leaves the pieces where they are. A kind is ahead of the others only when both sides have three posts and the gap is real. A closed campaign can keep that lesson: the post's words go to the voice, and the comparison goes to the ideas board. Nothing is sent. |
| Analytics | Reach, impressions, engagements, a rate only when impressions exist, saves, shares, comments, clicks, video completion, and follower change. 7, 28, or 90 days, or the whole history. Patterns for hour, day, format, pillar, hook, length, and assisted drafts appear only when both sides have three posts and the gap is real. A goal is the percent you set, measured against the stretch before it. Paste a CSV of old posts. A row counts when it has a date and an engagement count. |
| Hashtags | Saved sets of up to five tags. Performance of tags that posts actually used. Notes for a topic, a sound, or a format. A tag or a format is only called ahead when the gap is real. |
| Inbox | A short list of comments, mentions, and messages the page token can read. Questions and messages sit at the top. A suggested reply follows the brand voice and stays a draft. |
| Reports | A week or a month for this brand. Key numbers, top posts, and a note you write. Download markdown or JSON. A missing number stays missing. The file does not include a token. |
| Learning | A comparison is kept only when both sides have at least three posts and the gap is real. An impression count of zero is never turned into a rate. |

Facebook and Instagram are one Meta app. A Page token can name the linked Instagram professional account, and that account is read with the same token. Threads is a separate login on `graph.threads.net`. The Facebook token cannot read it. The username often matches Instagram. The id does not.

A pasted CSV on the voice desk teaches that desk. A row with a date and an engagement count is also in Analytics. A row without a date stays out of the windows. A pattern still needs three posts on both sides and a real gap.

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
inbox.py                 comments, mentions, and reply drafts
reports.py               weekly and monthly reports, markdown and JSON |
voice.py                 the brand profile, the checklist, and lessons from posts
library.py               assets, versions, and use
store.py                 state, connections, calendar, pulls
learn.py                 performance and lessons
analytics_desk.py        patterns, goals, and imported history
calendar_desk.py         gaps, slots, and the mix for the next 7 days
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

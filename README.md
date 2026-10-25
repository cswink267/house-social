# House Social

A [Hermes](https://github.com/NousResearch/hermes-agent) dashboard plugin for the Misfit House brands. It reads Facebook, Instagram, and Threads, keeps a local draft queue, and learns from engagement that was actually returned.

It posts to Facebook, Instagram, and Threads once posting is switched on, for the house in House settings and for each brand on its Accounts desk. Both switches start off. The brand's mode decides how much a person signs off: manual and approval need someone to approve every post; fully autonomous lets the agent schedule and post what it writes.

Studio (`studio.misfitmindset.com`) still owns the weekly posts, the peak posts, the quote cards, and the now posts. Misfit Mindset can read that queue, those cards, and the used quotes. This module does not generate them and does not write back.

## What you get

Each brand has the same desks.

| Desk | What it holds |
| --- | --- |
| Brief | Health first: the mode, the last ingest, the posts with numbers, and the channels. Then the audience, voice line, guards, pillars, website, and public handles. The mode, a pause, content mix targets, pace limits, mail settings, and the activity log sit below. Misfit Mindset also shows the last read from Studio. Removing a brand is at the bottom and asks for its name. |
| Voice | Tone, personality, formality, humor, point of view, do and don't, visual notes, banned lines, preferred lines, required lines, and competitor notes. Pillars keep the angles you write. On-brand and off-brand examples can be written, pasted, or taken from posts when the gap is real. Create scores a draft and can ask for a rewrite. Each save keeps a version. |
| Accounts | Connect with Facebook or Connect with Threads signs in through the house app. Back on the desk you pick this brand's Page and Instagram account, or confirm its Threads account. The tokens go to the vault. Change, disconnect, or paste a token by hand. Posting is switched on here for this brand. Check posting proves each account can post and leaves nothing visible. A test post is real and public, and Facebook and Threads tests can be deleted from the desk. |
| Ideas | A board or a list of sparks, competitor notes, trends, questions, and comments. One click makes a draft and opens the composer. A pattern line appears only when the posts already show it. An idea is archived as ahead only when its draft has a post at least 3× the others. Suggest uses the voice, the pillars, those posts, and the trend notes you saved. |
| Approval | Draft, then needs review, then approved, then scheduled. One name is a single step. Extra names are optional and go in order. Comments, the lines that changed between versions, and a trail that stays after a notice is marked read. An approved piece that already has a future time is scheduled at once. With approval email on, each step's approver gets the post by email and replies APPROVE or CHANGES; the link in the email opens the piece here. |
| Composer | The creation hub. Start from a subject, an idea, an image, or a post that is at least 3× the others. Facebook, Instagram, and Threads each get a preview and a count. The assistant stays inside the brand voice. A variation shows the historical pattern it matches, and only when that pattern is clear. Improve this draft asks for a rewrite from those misses. What the posts say lists similar posts with the engagements they earned. Hold a day on the calendar, or save the words to the library. Saving does not post. |
| Library | Images, video, carousels, templates, logos, and copy blocks. Hooks, CTAs, hashtags, and bios insert into the composer. Tags, search, folders, and versions. Mean engagement and last used come from the uses that have numbers. A version or a topic is called ahead only when both sides have three uses and the gap is real. Image tags come from tags this brand already uses, or from the vision model when it answers. |
| Series | A structure you can open again with a new topic. Pause holds it. Fill uses a pillar this brand already has and does not save a draft. A shape is suggested only when it is already ahead. Stats wait for three uses with numbers. A later drop is a note, and the series stays. It does not move to another brand. Nothing is sent. |
| Feedback | Used, better, worse, off-brand, or irrelevant on a composer, idea, hashtag, or series suggestion. Memory shows the counts. Delete restores the earlier mark. Nothing is sent. |
| Across | Off until two brands are included from Brief. Format, hour, and content counts only, and only when the gap is real. No caption crosses. Accept on the composer does not change the draft. |
| Modes | Manual, approval, or fully autonomous, chosen on Brief. Manual starts nothing. Approval drafts one piece and does not schedule it until you approve. Fully autonomous, once confirmed, lets the agent approve and schedule what it writes, inside the pace limits; it posts at its time while posting is on. A piece the desk drafts by itself is a placeholder and never posts until someone writes it. |
| Support | Health on Brief, a filterable log, preview that does not schedule, a hard mix hold, a pause, and a redacted export. Mail settings are stored. Nothing is sent. |
| Map | Overview, post, formats, and audience. Only stored numbers. A missing reach stays blank. A thin format says it is thin. Nothing is sent. |
| Notes | Brief can let Josie append a real gap to the todo. Off until that check is on. Two a day. Nothing already written is deleted. |
| Calendar | Month, week, and day. Drag a piece onto a day. Color by status, pillar, campaign, or platform. The next 7 days name any pillar that has nothing planned. A suggested day or hour appears only when that pattern is clear. An idea or a library block can be held on the chosen day. A recurrence holds the same words on that weekday for up to 8 weeks. A scheduled piece posts at its time while posting is on. |
| Queue | Draft, needs approval, approved, scheduled, posted, on the record, or failed. Posted links to each platform it went out on. Post now sends an approved piece at once, after a confirm. A failed platform can be retried without posting the others twice. On the record is a pulled post tied to the draft, with its engagements. Bulk actions still move pieces. A format hour is used when that format is clearly ahead; otherwise the brand hour, and only when the gap is real. A slot warning names an hour that has underperformed for that format. The pace line counts what is scheduled and does not apply a Meta rate limit. |
| Campaigns | A named effort with a kind, a goal, dates, the pieces, and the assets. Clone copies the shape and leaves the pieces where they are. A kind is ahead of the others only when both sides have three posts and the gap is real. A closed campaign can keep that lesson: the post's words go to the voice, and the comparison goes to the ideas board. Nothing is sent. |
| Analytics | Reach, impressions, engagements, a rate only when impressions exist, saves, shares, comments, clicks, video completion, and follower change. 7, 28, or 90 days, or the whole history. Patterns for hour, day, format, pillar, hook, length, and assisted drafts appear only when both sides have three posts and the gap is real. A goal is the percent you set, measured against the stretch before it. Paste a CSV of old posts. A row counts when it has a date and an engagement count. |
| Ingest | Map a paste, CSV, JSON, or Excel file onto caption, date, and counts. A missing number stays missing. A row already imported is skipped. |
| Memory | The patterns the posts already showed, with the count and the dates. Pin, lower, or delete one. A deleted pattern stays deleted until it is restored. Reset leaves the posts. Export is markdown or JSON. |
| Range | On the Composer. Wide until a pattern is already clear. Low, medium, or high after that. The closest posts keep their real engagements. A grade waits for a real count and shows up on Memory. Hide it for one brand or every brand. |
| Hashtags | Saved sets of up to five tags, optionally for a pillar or a campaign. A tag or a whole set is ahead only when this brand's posts show the gap. Suggestions skip banned words and anything that is not ahead. Notes stay notes. A note is in the niche when it uses a pillar or tag word from this brand. Nothing here is a popularity chart. |
| Inbox | A short list of comments, mentions, and messages the page token can read. Questions and messages sit at the top. A comment is flagged when it sits on a post that is at least 3× the others. Keep as an idea stores that comment. Keep this reply in the voice stores the reply you wrote, not the audience's words. A suggested reply stays a draft. Nothing is sent. |
| Reports | A week or a month for this brand. Key numbers, top posts, what is clear, the goal if one is set, and a next-period line only when a pattern is already clear. Write the insight asks the assistant to use that brief. If it adds a percent the brief does not have, the line is refused. Download markdown or JSON, or copy the report id. The id is for this desk. It is not a public link. Nothing is mailed. A missing number stays missing. |
| Learning | A comparison is kept only when both sides have at least three posts and the gap is real. An impression count of zero is never turned into a rate. |

Facebook and Instagram are one Meta app. A Page token can name the linked Instagram professional account, and that account is read with the same token. Threads is a separate login on `graph.threads.net`. The Facebook token cannot read it. The username often matches Instagram. The id does not.

A pasted CSV on the voice desk teaches that desk. A row with a date and an engagement count is also in Analytics. A row without a date stays out of the windows. A pattern still needs three posts on both sides and a real gap.

## Install

Clone this repository into the Hermes plugins directory:

```bash
git clone https://github.com/cswink267/house-social.git ~/.hermes/plugins/house-social
```

Add `house-social` to `plugins.enabled` in `~/.hermes/config.yaml`. Restart the Hermes dashboard so the new Python routes load. Restart the gateway when you also want the agent tools:

| Tool | What it does |
| --- | --- |
| `house_social_roster` | Brands, their channels, and whether posting is on. |
| `house_social_draft` | Save a draft, optionally with the exact Facebook, Instagram, and Threads words. Saving does not post. |
| `house_social_queue` | A brand's pieces, their status and time, and links to what posted. |
| `house_social_schedule` | Give a piece a time. Fully autonomous approves and schedules it; manual and approval send it for review first. |
| `house_social_post_now` | Post an approved piece right away. |
| `house_social_post_due` | Post every scheduled piece whose time has come. |
| `house_social_posting` | Whether posting is on, and which accounts can post. |

A Hermes cron job that calls `house_social_draft` and `house_social_schedule` each morning is how a fully autonomous brand runs on its own.

The web tab is `House Social`. The desktop pane lists the roster. Both talk to `/api/plugins/house-social/`.

The rail on the left picks the brand and the desk, and the tab remembers both. Every save says what happened. The tab follows the Hermes theme, light or dark. On a narrow screen the rail becomes two selects.

State is not in this repository. Drafts, connections, and pull results live in `~/.hermes/plugin-data/house-social/state.json`. Override that with `HOUSE_SOCIAL_STATE`. Library files live in a sibling `assets` directory. Override that with `HOUSE_SOCIAL_ASSETS`. Neither directory belongs in git.

The assistant calls a local OpenAI-compatible endpoint. `HOUSE_SOCIAL_AI_URL` defaults to `http://127.0.0.1:11434/v1/chat/completions`. `HOUSE_SOCIAL_AI_MODEL` defaults to `qwen3.5:9b`. Captions use `HOUSE_SOCIAL_VISION_MODEL`, default `moondream`. `HOUSE_SOCIAL_AI_TIMEOUT` sets how long a call may take, in seconds; the default is 60, and a deployment whose model needs longer can raise it instead of reading "offline". No key lives in this repository. If the endpoint is down, the composer says the assistant is offline.

## Connecting accounts

The Meta app and the Threads app are set once for the whole house. Each brand then signs in through them.

1. Open **House settings** under the brand picker. Add the Meta app id and secret, and the Threads app id and secret. Each secret goes to the vault as `house-social.meta.app_secret` or `house-social.threads.app_secret`. Only the ids stay in `state.json`.
2. Copy the sign-in address shown there. Add it to the Meta app under Facebook Login, Settings, Valid OAuth Redirect URIs. Add it to the Threads app under the Threads use case, Settings, Redirect Callback URLs. Open the dashboard at that same address when you connect.
3. On a brand's **Accounts** desk, press **Connect with Facebook**. Facebook asks which Pages to share. Back on the desk, pick the brand's Page and its Instagram account. A Page named like the brand, or already on the brand, is picked for you.
4. Press **Connect with Threads** and sign in as the brand's Threads account. Confirm it on the desk.

The sign-in asks only to read: Pages, their posts and insights, Instagram media, insights, comments, and messages, and Threads posts, replies, and insights. Nothing asks to publish. While a Meta app is in development mode, only people with a role on the app can sign in. That covers your own Pages.

The Page token comes from a long-lived sign-in and does not expire. The Instagram account reads with the token of the Page it is linked to. A Threads token lasts 60 days. The desk warns two weeks ahead, the rail marks the desk a week ahead, and connecting again renews it.

While you pick, the tokens wait in the dashboard's memory for up to 20 minutes. Only the chosen ones are written, with `vault set`, to `vault:house-social.<brand>.<platform>.token`. `state.json` keeps the vault name, never the token. A sign-in that is not finished in 30 minutes expires. Disconnect forgets the connection; the vault entry stays until you remove it there.

**Paste a token instead**, on the same desk, still saves a hand-made token. Saving it again without a token keeps the old vault name.

## Posting

Turn on **Let the desk post** in House settings, then **Post from** the brand on its Accounts desk. Press **Check posting** first: Facebook makes a hidden post and deletes it, and Instagram and Threads read their daily posting allowance. A connection made before posting, or before comment replies, needs **Change** once, so the sign-in grants posting (`pages_manage_posts`, `instagram_content_publish`, `threads_content_publish`) and replying (`pages_manage_engagement`, `instagram_manage_comments`, `threads_manage_replies`).

While the dashboard runs, it checks once a minute and posts each scheduled piece whose time has come. A piece posts only when it is approved, it is not the desk's placeholder, it passes the brand rules, the brand is not paused, and both switches are on. A piece more than six hours past its time does not post late; it is marked failed and waits for a new time. Two runs never post the same piece: a lock file beside `state.json` and a claim on the piece keep them apart.

Facebook takes text or one image. Instagram needs one image; a text piece skips Instagram. Threads takes text or one image. Instagram and Threads fetch an image from a public address, so the desk uses the image the Facebook post just made, or uploads it to the Page unpublished, to get one. Video and carousel posts are not posted by the desk yet. Instagram hashtags are added to the caption when it posts.

Set `HOUSE_SOCIAL_WORKER=0` to keep the dashboard from posting on its own; the agent tool and the House settings button still post what is due.

## Approval email

Approval email goes through [AgentMail](https://agentmail.to) or [Resend](https://resend.com). Set it up in House settings:

- **AgentMail** sends from an inbox, such as `approvals@agentmail.to`, and reads the replies from it.
- **Resend** sends from an address on a domain you verified there. Resend cannot hand replies back here, so put the AgentMail inbox in **Replies go to** if you want replies read; otherwise approvers use the link in the email.

Each API key goes to the vault as `house-social.agentmail.api_key` or `house-social.resend.api_key`. Then add each approver's email next to their name under **Review steps** on a brand's Approval desk.

When a piece goes for review, or moves to the next step, that step's approver gets the three versions, the time, and a link that opens the piece on the Approval desk. The subject carries a code such as `HS-K7QX2M`. Once a minute the desk reads new mail in the AgentMail inbox. A reply counts only when it comes from that step's approver and its first line starts with APPROVE, or CHANGES followed by what to change. Anything else is left with a notice on the Approval desk saying why. An approved piece with a future time is scheduled, and posts then while posting is on. Quiet hours on the Brief hold the mail until they end.

Replies are read rather than pushed by webhook: the Hermes dashboard only answers requests that carry its session, so a mail service cannot call it directly. Reading the inbox once a minute gets the same answer without opening a public endpoint.

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
connect.py               sign-in through the house apps, and the account picker
publish.py               posting, the once-a-minute run, checks, and test posts
approval_mail.py         approval email through AgentMail or Resend, and reading replies
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

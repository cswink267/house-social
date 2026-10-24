# Later — do not start

Chris, Oct 22 2026. These are extras. The order is locked. One at a time, when he asks. Do not pull the next one forward. Do not delete an item. Mark it complete when it is done.

Item 1, item 2, and item 3 are complete. The rest are not started.

Ingest history, then make the knowledge visible and correctable, then apply it while writing, then capture reusable formats and explicit feedback, then, only if he still wants it, look across brands.

A missing number stays missing. Nothing is sent. Tokens stay in the vault. A comparison still needs three on both sides and a real gap. Do not invent a percent, a popularity score, or a confidence number the posts did not earn.

## 1. Historical Content Ingest Center

**Status: complete.** The Ingest desk maps a paste, CSV, JSON, or Excel file, keeps a missing count missing, skips a row already imported, and writes the first lines from the posts that were actually dated. Recent posts are not weighted. Each dated post counts once.

Highest priority extra. A dedicated flow for pulling in past content and metrics so the brand starts with a real baseline instead of learning only from new posts.

This is the on-ramp. Voice refinements, prediction, formats, and ideas should use this history instead of a generic pattern. Without it the rest of the learning loop is slow.

Implementation notes:
- Add a new desk or a clear entry point under Analytics (or a dedicated Ingest desk) that walks the user through upload.
- Accept CSV, Excel (xlsx), JSON, or common platform export shapes (Instagram, LinkedIn, X, TikTok, Facebook). Provide a manual bulk-paste fallback that parses tab- or comma-separated text.
- Field mapping UI: user maps columns to known fields (caption/body, created date, platform, likes/reactions, comments, shares, saves, impressions, reach, video views, permalink, etc.). Save the mapping per brand so later uploads of the same shape are faster.
- Cleaning step before save: deduplicate by permalink or by (date + first 80 chars of body), normalize dates to America/New_York noon when no clock is present, leave missing metrics as missing (never invent zero), flag incomplete rows but still allow the user to import the rest.
- After a successful import, run an analysis pass that only reports patterns where both sides have at least three posts and a real gap. Group by performance band (top / middle / bottom) only when the counts support it.
- Generate a First Insights report that lists only what the imported posts actually support: content types that appear, hooks that appear more than once among the stronger posts, times and days that show a gap, pillars already visible in the data, and voice notes only where the text supports them. The report names the count behind every line.
- Store an audit record with each import: timestamp, number of rows accepted, number skipped, mapping used, and source filename (not a full path). Partial imports can be resumed by re-uploading and matching on permalink or body hash.
- Weight more recent posts higher only when the dates are real and the user has not disabled it. Do not invent a confidence level; always say “based on N posts.”
- Raw imported posts live in the same store as live pulls so Analytics, Voice, and Learning can see them. An imported row without a date stays out of time windows.

## 2. Memory / Context Panel

**Status: complete.** The Memory desk lists the patterns the posts already showed, with the count and the dates. A thin line says it is thin. Pin, lower, and delete stick. A deleted pattern stays deleted until it is restored. Reset clears those corrections and leaves the posts. Export is markdown or JSON, with tokens, vault names, and machine paths stripped. Composer and Calendar open it from “Why this recommendation?”

A transparent view of what is currently held for the brand, so it can be understood, trusted, and corrected.

User corrections are the signal. The panel is the control surface. It does not get to hide a pattern that was deleted.

Implementation notes:
- New desk (or a panel reachable from every desk) that reads from the existing learn.py / store patterns.
- Summary sections: preferred hooks, formats, posting times/days, pillars, engagement by content type, common CTAs, voice patterns. Every line names the exact count it came from and the date range of the posts.
- When the count is thin (fewer than three on a side), the line says it is thin. Do not convert thin data into a confidence score or a percent.
- Editable controls: promote (pin as preferred), demote (lower priority), or delete a learned pattern. A deleted pattern must stay deleted even if new posts would have recreated it, until the user restores it.
- Timeline view of changes: what was added, removed, or edited after an import or after a post that was actually ahead. Store the before/after for each change.
- From the Composer or Calendar, a “Why this recommendation?” link opens the Memory panel scrolled to the pattern that produced the suggestion.
- Reset action that clears learned patterns and corrections but leaves the raw posts and metrics untouched.
- Export of the current memory state as markdown or JSON. The export is redacted: no token, no vault name, no machine path.
- All corrections are written to the same state store so other desks see them immediately.

## 3. Performance Prediction Score

**Status: complete.** The Composer shows a wide, low, medium, or high range. It narrows only when a pattern already clears the three-post gap. A thin window stays wide and names the post count. The closest posts show their real engagements. A grade is written only after a real engagement count arrives, and it shows up on Memory. Hide is per brand or for every brand. Nothing is sent.

A visible range on a draft that reflects similarity to this brand's past posts. Build it only after the history exists.

Implementation notes:
- In the Composer, after the draft has a body and (optionally) media, compute a simple range: Low / Medium / High, or a wide band. Never a precise 0–100 that the data cannot support.
- The breakdown lists only factors that actually matched or missed against historical patterns that already meet the three-post rule (hook style, format, topic/pillar, length band, media type, CTA presence).
- When history is thin, the UI says the range is wide and shows the post count. Do not invent a tighter number.
- Show the three (or fewer) past posts the draft is most similar to, with their real engagement numbers. If fewer than three exist, say so.
- After a post is published and real metrics arrive, record whether the prediction was directionally correct (higher than brand average, about average, lower). Surface that accuracy record in the Memory panel. Do not grade a post that still has no metrics.
- Optional “optimize for higher score” button suggests one small change drawn from a pattern that is already clear. If nothing is clear, the button stays quiet.
- User can hide the score per brand or globally. Hidden state is stored with the brand.
- Similarity is computed locally from the stored posts; no external call is required for the score itself.

## 4. Content Series / Formats Library

**Status: not started.**

Proven structures that can be reused with a new topic.

Implementation notes:
- Store formats in the existing library or a new formats collection tied to the brand.
- Auto-suggest a format only when the posts already show the same structure repeating and both sides of any comparison have three posts with a real gap. Examples of shape (not requirements): myth vs reality, before/after, three mistakes, day-in-the-life, customer story, short tip + CTA.
- Manual create form: name, structure (section order or slide outline), typical hook pattern, media note, and links to example posts that already exist.
- Stats per format (average engagement, best instance, use count) appear only when the uses have real numbers and meet the three-post rule.
- One-click apply: select format + enter a new topic → Composer opens with the structure pre-filled and voice constraints applied. The original example posts stay linked for reference.
- Tagging and search so formats are findable. Tags can be pillars or free text.
- Suggest retiring or refreshing a format only when its later uses are actually behind the earlier ones, with three on both sides and a real gap. The suggestion is a notice, not an automatic delete.
- Formats can be linked from Ideas and from the Calendar so a user can plan a series deliberately.
- A format is never applied to a different brand.

## 5. Feedback Buttons

**Status: not started.**

Explicit signals on suggestions, so judgment is not only the eventual post performance.

Implementation notes:
- On every AI-generated suggestion in the Composer, Ideas, Hashtags, and Formats: buttons for Used, Better, Worse, Off-brand, Irrelevant. Optional short note field.
- Store the feedback against the suggestion type, the brand, the topic/pillar if known, and the format if one was used. Include the timestamp and the user (if multi-user later).
- Memory panel shows the totals as counts (“Off-brand: 7”). Never turn the counts into a score.
- When explicit feedback conflicts with a pure performance pattern, the feedback wins until the user corrects it. A corrected feedback entry replaces the old one.
- Past feedback is reviewable and editable in the Memory panel. Deleting feedback restores the previous state.
- Feedback is local state. It does not leave the machine and is not sent anywhere.

## 6. Cross-Brand Insights

**Status: not started.**

Optional. Last. Only after one brand's loop is solid.

Implementation notes:
- Separate, clearly labeled view that is off by default.
- Aggregated only. No voice line, no specific hook, no message text, and no asset ever crosses from one brand to another.
- Comparisons (content type, time of day, format) appear only when both sides have at least three posts and the gap is real. Do not invent an “X%”.
- Opt-in per brand. Turning it off for a brand removes that brand from all cross-brand views immediately.
- If a cross-brand observation is ever offered in the Composer, it is labeled “cross-brand” and requires an explicit accept. It is never auto-applied.
- Do not build this while a single brand’s history, memory, and corrections are still unfinished.

Do not build this while a single brand's history, memory, and corrections are still unfinished.

## 7. Operating Modes

**Status: not started.**

Three modes for how Hermes acts on a brand. The user chooses the mode per brand. The mode is stored with the brand and can be changed at any time. Nothing is sent until the mode and the approval rules allow it. Tokens stay in the vault.

### 1. Manual

Self-explanatory. The user does every step.

How it works:
- The user creates ideas, drafts, and schedules everything by hand.
- The Composer, Calendar, Queue, and Approval desks work exactly as they do today.
- Hermes may suggest (voice check, similar past posts, format ideas) but never creates, schedules, or advances a piece without an explicit user action.
- No email is sent. No background job runs for this brand.

Why:
- Full control. Useful while the brand voice is still being established or when the user wants to stay hands-on.
- Safe default. New brands start here.

Implementation notes:
- Mode selector on the Brief or Pages desk (or a small settings area).
- When Manual is selected, hide or disable any “run autonomously” controls.
- Existing approval flow remains available if the user wants a second person to review, but Hermes itself does not initiate work.

### 2. Autonomous with approval

Hermes performs the content work on its own, then asks the user to approve or reject each piece by email before anything is scheduled or published.

How it works:
- On a schedule the user sets (or on demand), Hermes generates ideas, drafts, and proposed calendar slots for the brand, staying inside the voice guide and any learned patterns that already meet the three-post rule.
- It does not schedule or mark anything ready.
- It sends one email (via agent.to or the configured mail path) that lists every piece waiting for approval.
- The email contains the draft text, platform previews, proposed day/time, and simple Approve / Reject links or buttons for each piece.
- When the user clicks Approve, Hermes moves that piece to scheduled (or to the Approval desk if a human approver is still required).
- When the user clicks Reject, Hermes discards or archives the piece and records the rejection as feedback.
- If the user does not respond, the piece stays unscheduled. Nothing is sent.

Why:
- Lets Hermes do the repetitive creation work while the user keeps final control.
- Builds a record of what the user accepts and rejects, which later feeds Fully Autonomous mode.
- Uses email so the user can approve from anywhere without opening the dashboard.

Implementation notes:
- New mode flag on the brand.
- Background job (or Hermes session) that generates a batch only when the mode is Autonomous-with-approval and the last batch has been resolved or expired.
- Email template that is plain and factual. Each piece gets its own Approve and Reject action. Actions are single-use and tied to the piece id.
- Incoming approval/rejection is handled by a small endpoint or by Hermes reading the reply; the result is written to the same store the dashboard uses.
- Each Approve/Reject link is single-use, expires after a configurable window (default 7 days), and is tied to the piece id and a random token stored only in the vault or in memory. The email never contains a long-lived secret.
- If the user edits the piece in the dashboard after the email is sent, the email actions are invalidated and a new email is required. The activity log records the invalidation.
- Rejection is stored as explicit feedback (Off-brand or Irrelevant, with the optional note the user can add). The note field in the email is optional and limited in length.
- The email never contains a token, a vault name, or a machine path.
- The user can still open the dashboard and approve or reject the same pieces there; both paths stay in sync. The first action wins; the second is refused with a clear message.
- If the mail path is down, the batch stays unscheduled, a notice appears on the Brief desk, and Hermes retries on the next run. It does not fall back to scheduling.
- Concurrent batches are not started while an earlier batch still has unresolved pieces.

### 3. Fully Autonomous

After the user has used Autonomous-with-approval long enough to trust the results, they can switch the brand to Fully Autonomous. Hermes creates, schedules, and (when a publisher is attached) publishes without waiting for per-piece approval.

How it works:
- Hermes runs on the schedule the user set.
- It generates content that stays inside the voice guide and the patterns that have already been accepted.
- It schedules pieces directly.
- It still writes an audit log of what it created and why (the pattern or pillar it matched).
- The user can still open the dashboard, edit, unschedule, or switch the brand back to a stricter mode at any time.
- A simple confidence or “still learning” notice appears if the recent acceptance rate in mode 2 was low; the user must explicitly confirm before the switch.

Why:
- Removes the last manual step once the user is confident.
- The learning loop from mode 2 (approvals and rejections) is what makes this mode safe.
- The user remains able to intervene; autonomy is a setting, not a lock.

Implementation notes:
- Mode switch requires an explicit confirmation that names the recent approval rate (only if the numbers exist; otherwise it says the history is thin).
- Hermes still respects hard guards (JamHaul never on Josie’s page, quote-image requirement, etc.).
- Every autonomous action is logged with the piece id, the pattern it matched, and the timestamp.
- The user can set a maximum number of posts per day or per week; Hermes stops when the limit is reached.
- Switching back to Manual or Autonomous-with-approval takes effect immediately; already-scheduled pieces stay scheduled unless the user removes them.
- Nothing in this mode bypasses the “three posts and a real gap” rule for any learned recommendation.
- Generation prompt construction: Hermes assembles the voice guide, active pillars, any locked series, content-mix targets, recent rejections, and the three-post patterns. It does not add instructions that are not already in those sources.
- Diversity: if the last N scheduled pieces used the same format or pillar, Hermes prefers a different one that still meets the rules. If no alternative exists, it proceeds and logs the repetition.
- Failure handling: if generation fails or the publisher (when attached) returns an error, the piece is marked failed, the activity log records the error (redacted), and Hermes does not retry the same piece automatically in the same run.
- The user can set a “review window” even in Fully Autonomous (for example, hold new pieces for 2 hours). During the window the pieces appear in the Queue as scheduled-but-held and can still be edited or removed.

The three modes are progressive. Manual is the starting point. Autonomous-with-approval builds the trust and the feedback data. Fully Autonomous is available only after that data exists and the user chooses it. A brand can move between modes at any time. Nothing is sent until the active mode and the approval rules allow it.

## 8. Additional features that support the modes and the learning loop

**Status: not started.**

These are optional. None of them are started. They can be built after the three modes exist, or alongside them when they make a mode safer or clearer. A missing number stays missing. Nothing is sent until the active mode and the approval rules allow it. Tokens stay in the vault. A comparison still needs three on both sides and a real gap.

### Mode-specific activity log

A filterable log per brand that shows what Hermes did or proposed under the current mode.

How it works:
- Every generation, email, approval, rejection, schedule, hold, or mode switch is written as a line.
- The line names the piece (if any), the action, the mode at the time, and the timestamp.
- The user can filter by mode, by action, or by date range.
- The log is readable from the Brief desk or from a small panel on every desk.

Why:
- Makes the progression from Manual to Autonomous-with-approval to Fully Autonomous visible.
- Gives the user a single place to audit what changed when they switched modes.
- Supports later exports and confidence checks.

Implementation notes:
- Store the log in the same state as the pieces. Do not invent a confidence score; show the raw counts.
- Keep the log redacted: no token, no vault name, no machine path.
- The log is append-only. A user can clear it, but the clear is itself logged.
- Each entry stores: timestamp, brand id, mode, action, piece id (if any), short reason (pattern id or “user”), and outcome.
- The log is queryable by the Brand health summary and by the exportable decision record.
- Retention: the log keeps at least the last 90 days or 1 000 entries, whichever is larger. Older entries can be archived to a downloadable file; they are not silently dropped.

### Approval email preferences

Per-brand settings for the emails sent in Autonomous-with-approval mode.

How it works:
- The user chooses digest (one email per day or per batch) or immediate.
- Quiet hours can be set; emails wait until the quiet period ends.
- The user can choose a short preview plus a link, or the full draft text in the email.
- Approve and Reject actions remain available either way.

Why:
- The email is the main control surface in mode 2. Tuning it reduces noise and increases the chance the user reviews.
- Different brands may need different cadences.

Implementation notes:
- Preferences are stored with the brand.
- The email never contains a token or a machine path.
- If the mail path is unavailable, the pieces stay unscheduled and a notice appears on the Brief desk.

### Teach-from-rejection shortcut

When a user rejects a piece (from email or dashboard), offer a one-click way to turn the rejection into a lasting rule.

How it works:
- After Reject, the user can choose: add a banned phrase, demote a format, add a voice note, or just discard.
- The choice is written immediately to the voice guide or the formats library.
- The rejection is also stored as explicit feedback.

Why:
- Rejections are the highest-quality signal. Making them immediately actionable tightens the learning loop faster than waiting for post performance.
- Reduces the chance the same mistake is repeated in the next autonomous batch.

Implementation notes:
- The shortcut is available on both the email action and the dashboard.
- A deleted or demoted pattern stays deleted until the user restores it (same rule as the Memory panel).
- The action is logged in the mode-specific activity log.

### Content mix guardrails

User-set targets for pillars or formats so Hermes does not over-optimize for engagement.

How it works:
- The user sets soft targets (for example, “at least two educational posts per week” or “no more than one promotional post per week”).
- In Autonomous modes, Hermes warns or holds a piece that would break a target.
- The warning names the target and the current count for the window. It does not invent a percent.

Why:
- Prevents the system from drifting toward whatever has historically performed well at the expense of brand balance.
- Gives the user a lever that is clearer than editing the voice guide.

Implementation notes:
- Targets are stored with the brand.
- A hold is not a rejection; the user can still approve the piece.
- The three-post rule still applies to any learned recommendation that influences the mix.
- Evaluation window is the current calendar week (America/New_York) unless the user sets a different window.
- A piece that would break a hard target is held and appears in the Queue with the reason. A soft target only produces a warning.
- The user can override a hold; the override is logged.

### Dry-run / preview week

Generate a full week of proposed content under the current mode without scheduling or emailing.

How it works:
- The user clicks “Preview next week.”
- Hermes generates the same batch it would generate in the active mode and shows the pieces in the Calendar and Queue marked as preview.
- Nothing is emailed. Nothing is scheduled.
- The user can promote a preview piece to a real draft, discard it, or discard the whole preview.

Why:
- Lets the user inspect what Autonomous-with-approval or Fully Autonomous would actually produce before turning it on or leaving it on.
- Safe way to test voice and format changes.

Implementation notes:
- Preview pieces are stored separately or flagged so they cannot be scheduled by accident.
- The preview respects the same guards and the three-post rule as a real run.
- A preview can be re-run; the previous preview is replaced.
- Preview pieces are visually distinct (dashed border or “Preview” chip) and cannot be moved to scheduled by drag-and-drop. Promotion to a real draft is an explicit action.
- A dry-run does not send email and does not count against daily/weekly post limits.
- If the user switches mode while a preview exists, the preview is kept but marked stale; the user must re-run it.

### Brand health summary on Brief

A compact card on the Brief desk that shows whether the brand is ready for a more autonomous mode.

How it works:
- Shows the current mode.
- Shows the date of the last successful ingest (or “none”).
- Shows the number of posts the learning is based on.
- Shows the recent approval rate from mode 2 if that mode has been used and the numbers exist; otherwise it says the history is thin.
- Lists any hard guards that are active for the brand.

Why:
- Gives a single place to decide whether to move from Manual to Autonomous-with-approval or from Autonomous-with-approval to Fully Autonomous.
- Surfaces missing history before the user expects the system to act.

Implementation notes:
- The card reads only from data that already exists. It does not invent a confidence score.
- It links to the Ingest desk if no history is present and to the activity log if mode 2 has been used.

### Recurring series planner

Extend the Formats Library so a user can lock a repeating structure and let Hermes fill the topics.

How it works:
- The user defines a series (for example, “Monday tip, Wednesday story”) and links it to a format.
- In Autonomous modes, Hermes proposes topics that fit the locked structure and the voice guide.
- The user can still edit or reject any instance.

Why:
- Many brands succeed by repeating a small number of strong formats. This makes that deliberate instead of accidental.
- Reduces blank-page decisions once the structure is trusted.

Implementation notes:
- A series is stored with the brand and can be paused.
- Hermes does not invent a new format; it only fills topics inside formats the user has already saved or that already meet the three-post rule.
- The series respects content-mix guardrails if they are set.

### Cross-post adaptation rules

Explicit, per-brand rules for how a piece should differ across Facebook, Instagram, and Threads.

How it works:
- The user sets rules such as maximum length, whether a first comment is required, whether a quote image is required, or which hashtag set to prefer.
- In Autonomous modes, Hermes applies the rules when it creates the three variants.
- The rules are visible on the Voice or Composer desk.

Why:
- The system already creates three variants. Making the adaptation rules editable reduces off-brand output once Hermes acts on its own.
- Hard guards (quote-image on Josie, jamhaul.com on JamHaul, etc.) remain non-negotiable.

Implementation notes:
- Rules are stored with the brand.
- A rule that conflicts with a hard guard is refused.
- The Composer still shows the three previews so the user can override.

### Pause / vacation mode

A temporary override that freezes generation and scheduling for a date range without changing the underlying mode.

How it works:
- The user sets a start and end date.
- During that window, Hermes does not generate, email, or schedule for the brand.
- Already-scheduled pieces stay scheduled unless the user removes them.
- When the window ends, the previous mode resumes.

Why:
- Practical for real use. The user should not have to switch to Manual and remember to switch back.
- Keeps the learning and approval history intact.

Implementation notes:
- The pause is stored with the brand and is visible on the Brief health card.
- A pause does not delete drafts or history.
- The activity log records the start and end of the pause.

### Exportable decision record

A markdown or JSON export of every autonomous decision for a date range.

How it works:
- The user chooses a date range and downloads a file.
- The file lists each piece, the mode, the action taken, the pattern or pillar matched (if any), and the final status.
- The export is redacted.

Why:
- Useful for the user’s own review or for an agency client.
- Makes the audit trail portable.

Implementation notes:
- The export reads from the mode-specific activity log.
- No token, vault name, or machine path is included.
- The export can be re-run; it does not change state.

### Layout and clarity options

Small UI changes that make the modes and the learning state easier to see.

- Collapsible group headers in the desk list (Setup / Create / Plan / Review / Learn) so the sidebar stays scannable as desks are added.
- A persistent “current mode” indicator in the header of every desk.
- Empty-state hints that name the next useful action (“No history yet — start with Ingest” or “Mode is Manual — switch to Autonomous with approval when you are ready”).
- On the Brief desk, the health summary card is the first thing shown.

Why:
- The three modes and the learning loop are only useful if the user can see the current state without hunting.
- These changes do not alter behavior; they only surface what already exists.

Implementation notes:
- Group headers read the `group` field already added to the section list.
- The mode indicator reads the brand’s current mode.
- Empty-state text stays factual and does not invent a next step the data does not support.

These additions are progressive. The activity log, teach-from-rejection, dry-run, and brand health summary most directly support the three modes. The rest can follow. A brand can use any of them while remaining in Manual mode; none of them force a piece to be sent.

## 9. Graphical Engagement Map

**Status: not started.**

A set of detailed, visual dashboards that surface the engagement metrics Facebook, Instagram, and Threads actually return. These are display-only. They do not invent rates, confidence scores, or demographics the platforms did not supply. A missing number stays missing. Nothing is sent from these views.

The four views below match the mockups. They can be built as tabs or sub-views inside the existing Analytics desk, or as a dedicated Engagement Map desk. All numbers come from stored posts and insights; no external estimation.

### Brand overview — cross-platform engagement map

A single screen that shows daily engagement trends and summary cards for all three platforms.

What it shows:
- Multi-line chart of daily total engagements (or the closest available engagement count) for Facebook, Instagram, and Threads over a selectable window (7 / 28 / 90 days).
- Three summary cards:
  - Facebook: Reach, Engagements, Reactions, Comments, Shares, Link clicks (and any other fields the pull returned).
  - Instagram: Reach, Likes, Comments, Saves, Shares, Reel plays (and average watch time when present).
  - Threads: Views, Likes, Replies, Reposts.
- A follower-change row showing net change for each platform when the data exists.
- Small sparklines or percent-change indicators only when both the current and prior windows have real numbers.

Why:
- Gives an at-a-glance picture of how the three platforms are moving together.
- Makes gaps obvious (a platform with no recent data simply shows “no numbers in this window”).

Implementation notes:
- Reads from the same post and insight store used by Analytics.
- Colors stay consistent (Facebook warm, Instagram teal, Threads gold, or the existing palette).
- If a metric was not returned by the platform, the cell is omitted or shows “—”. Do not substitute zero.

### Deep post-level breakdown

A focused view of one post with its full engagement composition and early performance curve.

What it shows:
- Post preview (caption excerpt, platform badges, publish time).
- Donut or stacked breakdown of total engagements into Reactions/Likes, Comments/Replies, Shares/Reposts, Saves, Clicks (only the types that exist for that post).
- Horizontal bars of engagement rate or raw engagements by hour for the first 48 hours, when hourly data exists.
- Three-column metric grid repeating the platform-specific numbers for that post.
- Cumulative engagements line from publish time to 48 hours (or to the latest available point).

Why:
- Lets the user see exactly why a post performed the way it did.
- Supports the “similar past posts” and prediction features by making the composition visible.

Implementation notes:
- Opened from any post list (Analytics, Queue, Calendar).
- Hourly breakdown appears only when the stored data contains it; otherwise the section is hidden.
- All percentages are calculated only from the numbers present on that post.

### Content-type and format performance map

A view organized by format (feed, quote-image, carousel, reel, story, thread, text) with a time heatmap.

What it shows:
- Row of format cards with average engagements (and a tiny distribution) for the selected window. A format appears only when it has posts.
- Heatmap of average engagements by day-of-week and hour, using only posts that have a local hour.
- Side-by-side bars of average reach and average engagements by format, split by platform where the data exists.
- Top posts table (platform, format, truncated caption, engagements, saves/shares, engagement rate when reach exists, posted time).

Why:
- Makes the “which formats work” question visual instead of a list of numbers.
- Feeds the Formats Library and the recurring series planner with evidence.

Implementation notes:
- Averages are shown only when a format has at least three posts in the window; otherwise the card says the count is thin.
- The heatmap uses America/New_York local hour already stored on posts.
- Engagement rate column appears only for rows that have both engagements and reach/impressions.

### Audience and growth view

Follower trends and the engagement-quality metrics the platforms return.

What it shows:
- Area or line chart of follower count (or net change) over 90 days for each platform that has the data.
- Simple rate displays for engagement rate, save rate, and reply rate, each calculated only when the denominator exists, with a comparison to the prior period when both sides have numbers.
- Cards for profile visits, follows from content, and unfollows when those fields were returned.
- Optional top cities or age bands only if the platform actually supplied them for this brand; otherwise the panel is omitted.
- Table of organic reach vs engaged users by platform.

Why:
- Separates “how many people saw it” from “how many people did something.”
- Gives a clean place to watch follower trajectory without mixing it into post-level numbers.

Implementation notes:
- Every rate names its numerator and denominator in a tooltip or caption.
- If a demographic panel has no data, it is not rendered.
- Export of the current view (markdown or CSV of the visible numbers) is allowed; the export stays redacted.

These four views are display-only. They consume the same stored metrics the rest of Analytics already uses. They do not create posts, send email, or change mode. A missing metric stays missing. Build them after the historical ingest and the basic Analytics desk are solid, so the charts have real posts to draw from.

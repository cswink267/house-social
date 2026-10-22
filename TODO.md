# Later — do not start

Chris, Oct 22 2026. These are extras. None of them are started. The order is locked. One at a time, when he asks. Do not pull the next one forward.

Ingest history, then make the knowledge visible and correctable, then apply it while writing, then capture reusable formats and explicit feedback, then, only if he still wants it, look across brands.

A missing number stays missing. Nothing is sent. Tokens stay in the vault. A comparison still needs three on both sides and a real gap. Do not invent a percent, a popularity score, or a confidence number the posts did not earn.

## 1. Historical Content Ingest Center

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

Explicit signals on suggestions, so judgment is not only the eventual post performance.

Implementation notes:
- On every AI-generated suggestion in the Composer, Ideas, Hashtags, and Formats: buttons for Used, Better, Worse, Off-brand, Irrelevant. Optional short note field.
- Store the feedback against the suggestion type, the brand, the topic/pillar if known, and the format if one was used. Include the timestamp and the user (if multi-user later).
- Memory panel shows the totals as counts (“Off-brand: 7”). Never turn the counts into a score.
- When explicit feedback conflicts with a pure performance pattern, the feedback wins until the user corrects it. A corrected feedback entry replaces the old one.
- Past feedback is reviewable and editable in the Memory panel. Deleting feedback restores the previous state.
- Feedback is local state. It does not leave the machine and is not sent anywhere.

## 6. Cross-Brand Insights

Optional. Last. Only after one brand's loop is solid.

Implementation notes:
- Separate, clearly labeled view that is off by default.
- Aggregated only. No voice line, no specific hook, no message text, and no asset ever crosses from one brand to another.
- Comparisons (content type, time of day, format) appear only when both sides have at least three posts and the gap is real. Do not invent an “X%”.
- Opt-in per brand. Turning it off for a brand removes that brand from all cross-brand views immediately.
- If a cross-brand observation is ever offered in the Composer, it is labeled “cross-brand” and requires an explicit accept. It is never auto-applied.
- Do not build this while a single brand’s history, memory, and corrections are still unfinished.

Do not build this while a single brand's history, memory, and corrections are still unfinished.

(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const React = SDK.React;
  const { useCallback, useEffect, useMemo, useRef, useState } = SDK.hooks;
  const h = React.createElement;
  const PLATFORMS = [["facebook", "Facebook"], ["instagram", "Instagram"], ["threads", "Threads"]];
  const FORMATS = ["feed", "quote-image", "carousel", "reel", "story", "thread", "text"];

  function messageOf(error) {
    if (!error) return "";
    const detail = error.detail || error.message || String(error);
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }

  // A titled block inside a desk. Collapsible ones use <details>, so the
  // keyboard and screen readers get the disclosure behavior for free.
  function Section(props) {
    const head = h("div", { className: "hs-section-head" },
      h("div", { className: "hs-section-titles" },
        h("h3", { className: "hs-h3" }, props.title),
        props.note ? h("p", { className: "hs-note" }, props.note) : null),
      props.actions ? h("div", { className: "hs-row hs-section-actions" }, props.actions) : null);
    const body = h("div", { className: "hs-section-body" }, props.children);
    if (props.collapsible) {
      return h("details", { className: "hs-section is-collapsible", open: !!props.open },
        h("summary", null, head), body);
    }
    return h("section", { className: "hs-section" }, head, body);
  }

  // One choice out of a few, such as month, week, or day.
  function Segmented(props) {
    return h("div", { className: "hs-seg", role: "group", "aria-label": props.label },
      props.options.map(function (pair) {
        const on = props.value === pair[0];
        return h("button", {
          key: pair[0], type: "button",
          className: "hs-seg-item" + (on ? " is-on" : ""),
          "aria-pressed": on,
          onClick: function () { props.onChange(pair[0]); },
        }, pair[1]);
      }));
  }

  function Stat(props) {
    return h("div", { className: "hs-stat" },
      h("div", { className: "hs-stat-label" }, props.label),
      h("div", { className: "hs-stat-value" + (props.missing ? " is-missing" : "") }, props.value),
      props.note ? h("div", { className: "hs-stat-note" }, props.note) : null);
  }

  // The words above, the control below, and an optional hint under it.
  function field(label, control, hint) {
    return h("label", { className: "hs-note" }, label, control, hint ? h("span", { className: "hs-hint" }, hint) : null);
  }

  function Empty(props) {
    return h("div", { className: "hs-empty" }, props.children);
  }

  function BarChart(props) {
    const points = props.points || [];
    if (!points.length) return h("p", { className: "hs-note" }, props.empty || "No engagement data yet.");
    const width = 640;
    const height = 150;
    const max = Math.max.apply(null, points.map(function (point) { return point.value || 0; }).concat([1]));
    const gap = width / points.length;
    return h("div", null,
      h("div", { className: "hs-name" }, props.label),
      h("svg", { className: "hs-chart", viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": props.label },
        points.map(function (point, index) {
          const barHeight = Math.max(2, ((point.value || 0) / max) * (height - 28));
          return h("rect", {
            key: point.id,
            x: index * gap + 1,
            y: height - 16 - barHeight,
            width: Math.max(2, gap - 3),
            height: barHeight,
            className: "hs-bar" + (props.selected === point.id ? " is-on" : ""),
            onClick: function () { props.onPick(point); },
          }, h("title", null, (point.label || point.id) + " · " + (point.value || 0)));
        })),
      h("select", {
        className: "hs-field",
        value: props.selected || "",
        onChange: function (event) {
          const point = points.find(function (item) { return item.id === event.target.value; });
          if (point) props.onPick(point);
        },
      },
        h("option", { value: "" }, "Choose a bar"),
        points.map(function (point) {
          return h("option", { key: point.id, value: point.id }, (point.label || point.id) + " · " + (point.value || 0));
        })),
    );
  }

  const BASE = "/api/plugins/house-social";
  const JSON_HEADERS = { "Content-Type": "application/json" };

  function api(method, path, body) {
    const init = { method: method };
    if (body !== undefined) {
      init.headers = JSON_HEADERS;
      init.body = JSON.stringify(body);
    }
    return SDK.fetchJSON(BASE + path, init);
  }

  function brandPath(brandId, rest) {
    return "/brands/" + encodeURIComponent(brandId) + (rest || "");
  }

  function recall(key) {
    try { return window.localStorage.getItem("house-social:" + key) || ""; }
    catch (err) { return ""; }
  }

  function remember(key, value) {
    try { window.localStorage.setItem("house-social:" + key, value); }
    catch (err) { /* private mode or blocked storage: the desk still works */ }
  }

  function slugOf(name) {
    return String(name || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/g, "");
  }

  const DESK_NOTES = {
    brief: "Who this brand speaks to, the rules it keeps, and how far the desk may act on its own.",
    voice: "The memory of this brand. Composer checks a draft against it. A suggestion is saved only when you accept it, and only when the posts actually show the gap.",
    pages: "Connect the Meta app for each platform, then pull what already went out. Tokens go to the vault, not to the saved state.",
    ideas: "Sparks, competitor notes, trends, questions, and comments. Make this a draft opens it in the composer. A pattern line appears only when the posts already show one. Nothing here is a predicted score.",
    create: "One idea becomes a Facebook, Instagram, and Threads version. The assistant stays inside the brand voice.",
    library: "Images, video, carousels, templates, logos, and copy for this brand. A new save of the words or the file keeps the older version. Files stay beside the desk, not in git.",
    series: "A structure you can reuse with a new topic. Pause holds it. Fill uses a pillar this brand already has and does not save a draft. A shape is suggested only when it is already ahead, and stats wait for three uses with numbers. A series stays on this brand.",
    calendar: "Month, week, or day. Drag a piece onto a day to hold it, or into the tray to take it off. A pillar or campaign filter hides published posts, because a live post is not tagged with either.",
    campaigns: "A campaign holds the posts, the assets, the goal, and the dates. Clone keeps the shape and leaves the pieces. A kind is ahead only when both sides have three posts and the gap is real.",
    approval: "Draft, then needs review, then approved, then scheduled. One name is a single step; extra names are optional and go in order. The trail stays after a notice is marked read. Nothing is mailed.",
    queue: "Draft, needs approval, approved, scheduled, on the record, or failed. On the record means a post is already tied to the draft, with its engagements.",
    performance: "Numbers for this brand only. A missing pull stays missing. Nothing here is a rate unless the count exists.",
    map: "Display only. A missing number stays blank. A format with fewer than three posts says it is thin.",
    ingest: "Paste rows or choose a CSV, JSON, or Excel file. Map the columns, then import. A missing number stays missing, and a row already here is skipped.",
    memory: "The patterns the posts already showed. A thin count stays thin. A deleted pattern stays off the recommendations until you restore it. Reset clears the corrections; the posts stay.",
    hashtags: "Five tags in a set, for a pillar or a campaign. A tag is suggested only when this brand's posts already show it ahead. Notes are filtered by this brand's own words; they are not a popularity chart.",
    inbox: "Recent comments, mentions, and messages. A comment is flagged when its post is at least 3× the others. Keep this reply in the voice stores the reply, not their words.",
    reports: "A week or a month, set against the period before it. A next-period line appears only when a pattern is already clear. The report id is for this desk, not a public link. Nothing is mailed.",
    across: "Off until at least two brands are included from Brief. Counts only: no caption, hook, voice line, or asset crosses.",
    learning: "Standing rules stay on the Brief. A lesson here is only what the numbers support, and a comparison waits for three observations.",
  };

  const SUPPORT_DONE = {
    preview: "Preview ready. Nothing was scheduled.",
    discard: "Preview discarded.",
    export: "Export ready below.",
    clear: "Log cleared.",
    promote: "Draft made from the preview.",
    pause: "Pause saved.",
    mail: "Mail settings saved.",
    ban: "Phrase banned.",
  };

  const MODE_DONE = {
    set: "Mode saved.",
    prepare: "Batch prepared. Nothing is scheduled until you approve.",
    run: "Ran once. Nothing is sent.",
    approve: "Approved.",
    reject: "Rejected.",
  };

  function deskBadges(studio) {
    const out = {};
    if (!studio) return out;
    const pending = ((studio.approval && studio.approval.pieces) || []).filter(function (item) { return item.status === "pending"; }).length;
    const notices = ((studio.approval && studio.approval.notices) || []).length;
    if (pending || notices) out.approval = { n: pending || notices, tone: "warn", label: pending ? pending + " waiting for review" : notices + " unread notices" };
    const attention = ((studio.inbox && studio.inbox.items) || []).filter(function (item) { return item.needs_attention; }).length;
    if (attention) out.inbox = { n: attention, tone: "warn", label: attention + " need attention" };
    const failed = ((studio.queue && studio.queue.items) || []).filter(function (item) { return item.status === "failed"; }).length;
    if (failed) out.queue = { n: failed, tone: "danger", label: failed + " failed" };
    return out;
  }

  function channelLine(brand) {
    const known = (brand.channels || []).filter(function (channel) { return channel.known; });
    if (!known.length) return "No channels yet";
    return known.map(function (channel) {
      const pair = PLATFORMS.find(function (item) { return item[0] === channel.platform; });
      return pair ? pair[1] : channel.platform;
    }).join(" · ");
  }

  function Toasts(props) {
    return h("div", { className: "hs-toasts", role: "status", "aria-live": "polite" },
      props.items.map(function (item) {
        return h("div", { key: item.id, className: "hs-toast is-" + item.kind, role: item.kind === "error" ? "alert" : null },
          h("span", { className: "hs-toast-text" }, item.text),
          h("button", { type: "button", className: "hs-toast-close", "aria-label": "Dismiss", onClick: function () { props.onDismiss(item.id); } }, "×"));
      }));
  }

  function DeskNav(props) {
    return h("nav", { className: "hs-nav", "aria-label": "Desks" },
      props.groups.map(function (group) {
        const closed = !!props.closed[group.name];
        const holdsCurrent = group.items.some(function (item) { return item.id === props.section; });
        return h("div", { key: group.name, className: "hs-nav-group" },
          h("button", {
            type: "button", className: "hs-nav-label", "aria-expanded": !closed,
            onClick: function () { props.onToggle(group.name); },
          }, h("span", { className: "hs-chevron", "aria-hidden": "true" }, closed ? "▸" : "▾"), group.name),
          closed && !holdsCurrent ? null : h("div", { className: "hs-nav-items" },
            group.items.filter(function (item) { return !closed || item.id === props.section; }).map(function (item) {
              const badge = props.badges[item.id];
              return h("button", {
                key: item.id, type: "button",
                className: "hs-nav-item" + (props.section === item.id ? " is-on" : ""),
                "aria-current": props.section === item.id ? "page" : null,
                onClick: function () { props.onPick(item.id); },
              }, h("span", null, item.label),
                badge ? h("span", { className: "hs-count is-" + badge.tone, title: badge.label, "aria-label": badge.label }, badge.n) : null);
            })));
      }));
  }

  function AddBrand(props) {
    const [form, setForm] = useState({ name: "", id: "", site: "", voice: "" });
    const [touched, setTouched] = useState(false);
    const id = touched ? form.id : slugOf(form.name);
    function setField(field, value) {
      setForm(function (current) { return Object.assign({}, current, { [field]: value }); });
    }
    return h("form", {
      className: "hs-panel",
      onSubmit: function (event) {
        event.preventDefault();
        props.onAdd({ id: id, name: form.name.trim(), site: form.site.trim(), voice: form.voice.trim() });
      },
    },
      h("div", { className: "hs-panel-head" },
        h("h2", { className: "hs-h2" }, "Add a brand"),
        h("p", { className: "hs-note" }, "A new brand starts empty. Its voice, pillars, and pages are written on its own desks.")),
      h("div", { className: "hs-grid-2" },
        h("label", { className: "hs-note" }, "Name",
          h("input", { className: "hs-field", value: form.name, autoFocus: true, placeholder: "Misfit Mindset", onChange: function (event) { setField("name", event.target.value); } })),
        h("label", { className: "hs-note" }, "Id",
          h("input", {
            className: "hs-field", value: id, placeholder: "misfit-mindset",
            onChange: function (event) { setTouched(true); setField("id", event.target.value); },
          }),
          h("span", { className: "hs-hint" }, "Lowercase words joined by hyphens. It cannot change later.")),
        h("label", { className: "hs-note" }, "Website",
          h("input", { className: "hs-field", value: form.site, placeholder: "https://", onChange: function (event) { setField("site", event.target.value); } })),
        h("label", { className: "hs-note" }, "Voice, in a line",
          h("input", { className: "hs-field", value: form.voice, placeholder: "Who it speaks to and how", onChange: function (event) { setField("voice", event.target.value); } }))),
      h("div", { className: "hs-row" },
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !form.name.trim() || !id }, "Add brand"),
        h("button", { type: "button", className: "hs-tab", onClick: props.onCancel }, "Cancel")));
  }

  function HouseSocial() {
    const [brands, setBrands] = useState([]);
    const [pieces, setPieces] = useState([]);
    const [studio, setStudio] = useState(null);
    const [brandId, setBrandId] = useState(function () { return recall("brand"); });
    const [section, setSection] = useState(function () { return recall("section") || "brief"; });
    const [memoryFocus, setMemoryFocus] = useState("");
    const [closedGroups, setClosedGroups] = useState(function () {
      try { return JSON.parse(recall("closed") || "{}"); } catch (err) { return {}; }
    });
    const [idea, setIdea] = useState("");
    const [pillar, setPillar] = useState("");
    const [format, setFormat] = useState("quote-image");
    const [hypothesis, setHypothesis] = useState("");
    const [activeId, setActiveId] = useState("");
    const [handles, setHandles] = useState({});
    const [pickedDay, setPickedDay] = useState("");
    const [pickedPost, setPickedPost] = useState("");
    const [pickedHour, setPickedHour] = useState("");
    const [toasts, setToasts] = useState([]);
    const [busy, setBusy] = useState(false);
    const [loaded, setLoaded] = useState(false);
    const [adding, setAdding] = useState(false);
    const [voiceCheck, setVoiceCheck] = useState(null);
    const [library, setLibrary] = useState({ assets: [], folders: [], tags: [] });
    const [limits, setLimits] = useState({ facebook: 5000, instagram: 2200, threads: 500 });
    const [cardLimit, setCardLimit] = useState(240);
    const [assist, setAssist] = useState(null);
    const [draftRead, setDraftRead] = useState(null);
    const [assistTarget, setAssistTarget] = useState("idea");
    const brandRef = useRef(brandId);
    // Edits typed into a draft and not saved yet, by piece, platform, and field.
    // A refresh keeps them, so attaching an image does not wipe the words.
    const unsaved = useRef({});
    const [dirty, setDirty] = useState({});
    const settled = useRef("");
    const ticket = useRef(0);
    brandRef.current = brandId;

    const brand = useMemo(function () {
      return brands.find(function (item) { return item.id === brandId; }) || null;
    }, [brands, brandId]);
    const active = useMemo(function () {
      return pieces.find(function (item) { return item.id === activeId; }) || null;
    }, [pieces, activeId]);

    function withUnsaved(list) {
      return list.map(function (piece) {
        const edits = unsaved.current[piece.id];
        if (!edits) return piece;
        const variants = Object.assign({}, piece.variants);
        Object.keys(edits).forEach(function (platform) {
          variants[platform] = Object.assign({}, variants[platform], edits[platform]);
        });
        return Object.assign({}, piece, { variants: variants });
      });
    }

    function forget(id) {
      delete unsaved.current[id];
      setDirty(function (current) {
        const next = Object.assign({}, current);
        delete next[id];
        return next;
      });
    }

    function dismiss(id) {
      setToasts(function (current) { return current.filter(function (item) { return item.id !== id; }); });
    }

    function notify(text, kind) {
      if (!text) return;
      const id = String(Date.now()) + Math.random().toString(16).slice(2);
      const tone = kind || "ok";
      setToasts(function (current) {
        return current.filter(function (item) { return !(tone === "error" && item.kind === "error"); })
          .concat([{ id: id, text: text, kind: tone }]).slice(-3);
      });
      if (tone !== "error") window.setTimeout(function () { dismiss(id); }, 3200);
    }

    const refresh = useCallback(async function () {
      const mine = ++ticket.current;
      const wanted = brandRef.current;
      const first = await Promise.all([api("GET", "/roster"), api("GET", "/pieces")]);
      const roster = first[0] || {};
      const list = roster.brands || [];
      const id = list.some(function (item) { return item.id === wanted; }) ? wanted : (list[0] ? list[0].id : "");
      const desk = id ? await Promise.all([api("GET", brandPath(id, "/studio")), api("GET", brandPath(id, "/library"))]) : [null, null];
      if (mine !== ticket.current) return null;
      setBrands(list);
      setLimits(roster.limits || { facebook: 5000, instagram: 2200, threads: 500 });
      setCardLimit(roster.card_limit || 240);
      setPieces(withUnsaved((first[1] && first[1].pieces) || []));
      setStudio(desk[0]);
      setLibrary(desk[1] || { assets: [], folders: [], tags: [] });
      setLoaded(true);
      if (id !== wanted) {
        settled.current = id;
        setBrandId(id);
      }
      return desk[0];
    }, []);

    useEffect(function () {
      if (brandId) remember("brand", brandId);
      if (settled.current && settled.current === brandId) {
        settled.current = "";
        return;
      }
      refresh().catch(function (err) { notify(messageOf(err), "error"); setLoaded(true); });
    }, [brandId]);

    useEffect(function () { remember("section", section); }, [section]);
    useEffect(function () { remember("closed", JSON.stringify(closedGroups)); }, [closedGroups]);

    useEffect(function () {
      if (!brand) return;
      const next = {};
      (brand.channels || []).forEach(function (channel) { next[channel.platform] = channel.handle || ""; });
      setHandles(next);
      setFormat(brand.preferred_format || "feed");
      setPillar("");
    }, [brand]);

    async function run(action) {
      setBusy(true);
      setToasts(function (current) { return current.filter(function (item) { return item.kind !== "error"; }); });
      try { return await action(); }
      catch (err) { notify(messageOf(err), "error"); return null; }
      finally { setBusy(false); }
    }

    // A request that does not change what the desk shows.
    function ask(method, path, body) {
      return run(function () { return api(method, path, body); });
    }

    // A request that changes state: reload the desk, then say what happened.
    async function act(method, path, body, done) {
      const saved = await ask(method, path, body);
      if (!saved) return saved;
      await refresh().catch(function (err) { notify(messageOf(err), "error"); });
      if (done) notify(typeof done === "function" ? done(saved) : done);
      return saved;
    }

    function on(path) { return brandPath(brand.id, path); }

    function openPiece(id) {
      setActiveId(id);
      setSection("create");
    }

    async function shapeIdea() {
      const piece = await ask("POST", "/pieces", { brand_id: brand.id, idea: idea, pillar: pillar, format: format, hypothesis: hypothesis });
      if (!piece) return;
      setActiveId(piece.id);
      setIdea("");
      setHypothesis("");
      await refresh();
      notify("Three versions are ready below.");
    }

    async function checkVoice() {
      const fields = { idea: idea };
      if (active && active.brand_id === brand.id && active.variants) {
        PLATFORMS.forEach(function (pair) {
          fields[pair[0]] = (active.variants[pair[0]] || {}).body || "";
        });
      }
      const report = await ask("POST", on("/voice-check"), fields);
      if (report) setVoiceCheck(report);
    }

    function assistText() {
      if (assistTarget === "idea") return idea;
      const variant = active && active.variants ? active.variants[assistTarget] || {} : {};
      return variant.body || idea;
    }

    async function readDraft(text) {
      const report = await ask("POST", on("/draft-read"), {
        text: text == null ? assistText() : text,
        format: format,
        pillar: pillar,
        piece_id: active && active.brand_id === brand.id ? active.id : "",
        has_media: Boolean(active && active.asset_ids && active.asset_ids.length),
      });
      if (report) setDraftRead(report);
      return report;
    }

    function sendFeedback(body) {
      return act("POST", on("/feedback"), body || {}, body && body.action === "delete" ? "Mark removed." : "Noted.");
    }

    async function askAssist(action, misses) {
      const fields = { action: action, text: action === "draft" ? idea : assistText() };
      if (active && active.brand_id === brand.id) fields.piece_id = active.id;
      if (misses && misses.length) fields.misses = misses;
      if (action === "remix") {
        const reading = draftRead && draftRead.remix && draftRead.remix.ready ? draftRead : await readDraft(assistText());
        if (!reading || !reading.remix || !reading.remix.ready) {
          notify((reading && reading.remix && reading.remix.detail) || "No post is at least 3× the others, so there is nothing to remix.", "error");
          return;
        }
        fields.text = reading.remix.preview;
      }
      if (action === "caption") {
        const ids = (active && active.asset_ids) || [];
        const image = ((library && library.assets) || []).find(function (asset) {
          return ids.indexOf(asset.id) >= 0 && asset.mime && asset.mime.indexOf("image/") === 0;
        });
        if (!image) {
          notify("Attach an image from the library before asking for a caption.", "error");
          return;
        }
        fields.asset_id = image.id;
      }
      const report = await ask("POST", on("/assist"), fields);
      if (report) setAssist(report);
    }

    async function improveDraft() {
      const reading = await readDraft(assistText());
      if (reading && reading.misses && reading.misses.length) askAssist("rewrite", reading.misses);
      else if (reading) notify("This draft does not miss anything the posts have shown.");
    }

    function applyAssist(text) {
      if (assist && assist.action === "comment" && active && assistTarget !== "idea") {
        editVariant(assistTarget, "first_comment", text);
        setAssist(null);
        return;
      }
      if (assistTarget === "idea" || !active) setIdea(text);
      else editVariant(assistTarget, "body", text);
      setAssist(null);
    }

    function applyHashtag(tag) {
      if (!active) return;
      const variant = (active.variants && active.variants.instagram) || {};
      const tags = (variant.hashtags || []).slice();
      if (tags.map(function (item) { return item.toLowerCase(); }).indexOf(tag.toLowerCase()) < 0) tags.push(tag);
      editVariant("instagram", "hashtags", tags.slice(0, 5));
    }

    function saveChannels() {
      const body = {};
      PLATFORMS.forEach(function (pair) {
        const existing = (brand.channels || []).find(function (channel) { return channel.platform === pair[0]; }) || {};
        body[pair[0]] = { handle: handles[pair[0]] || "", external_id: existing.external_id || "" };
      });
      return act("PUT", on("/channels"), body, "Handles saved.");
    }

    function editVariant(platform, field, value) {
      const edits = unsaved.current[activeId] || {};
      edits[platform] = Object.assign({}, edits[platform], { [field]: value });
      unsaved.current[activeId] = edits;
      setDirty(function (current) { return current[activeId] ? current : Object.assign({}, current, { [activeId]: true }); });
      setPieces(function (current) {
        return current.map(function (piece) {
          if (piece.id !== activeId) return piece;
          const variants = Object.assign({}, piece.variants);
          variants[platform] = Object.assign({}, variants[platform], { [field]: value });
          return Object.assign({}, piece, { variants: variants });
        });
      });
    }

    function savePiece(extra) {
      if (!active) return null;
      const variants = {};
      PLATFORMS.forEach(function (pair) {
        const variant = active.variants[pair[0]] || {};
        variants[pair[0]] = { body: variant.body || "", hashtags: variant.hashtags || [], image_ready: !!variant.image_ready, first_comment: variant.first_comment || "" };
      });
      const status = extra && extra.status;
      const done = status === "ready" ? "Marked ready." : status === "planned" ? "Marked planned." : status === "scheduled" ? "Scheduled. Nothing is sent." : "Draft saved.";
      const id = active.id;
      const sent = unsaved.current[id];
      delete unsaved.current[id];
      return act("PATCH", "/pieces/" + id, Object.assign({ variants: variants }, extra || {}), done).then(function (saved) {
        if (saved) forget(id);
        else if (sent && !unsaved.current[id]) unsaved.current[id] = sent;
        return saved;
      });
    }

    async function runQueue(action, ids) {
      const saved = await act("POST", on("/queue"), { ids: ids, action: action });
      if (!saved) return;
      const bad = (saved.results || []).filter(function (item) { return !item.ok; });
      const good = (saved.results || []).length - bad.length;
      if (bad.length) {
        const reasons = bad.map(function (item) { return item.error; }).filter(function (text, index, list) { return text && list.indexOf(text) === index; });
        notify((bad.length === 1 ? "1 piece did not move." : bad.length + " pieces did not move.") + (reasons.length ? " " + reasons.join(" ") : ""), "error");
      }
      if (good) notify(good + (good === 1 ? " piece moved." : " pieces moved."));
    }

    function placePiece(id, date) {
      return act("PATCH", "/pieces/" + id, { scheduled_for: date }, date ? "Held on " + date + "." : "Taken off its day.");
    }

    function planPiece(body) {
      return act("POST", "/pieces", Object.assign({ brand_id: brand.id, status: "planned" }, body), "Held on the calendar.");
    }

    function saveAsset(body) {
      return act("POST", on("/assets"), body, "Saved to the library.");
    }

    function useAsset(id, body) {
      return act("POST", "/assets/" + id + "/use", body, body && body.piece_id ? "Attached to the draft." : "Use recorded.");
    }

    async function removePiece(id) {
      const done = await act("DELETE", "/pieces/" + id, undefined, "Draft deleted.");
      if (done) forget(id);
      if (done && activeId === id) setActiveId("");
    }

    async function addBrand(body) {
      const created = await ask("POST", "/brands", body);
      if (!created) return;
      setAdding(false);
      setSection("brief");
      setBrandId(created.id);
      notify(created.name + " is on the roster.");
    }

    async function removeBrand(id) {
      const gone = brands.find(function (item) { return item.id === id; });
      const done = await ask("DELETE", "/brands/" + encodeURIComponent(id));
      if (!done) return;
      const rest = brands.filter(function (item) { return item.id !== id; });
      setBrandId(rest[0] ? rest[0].id : "");
      notify((gone ? gone.name : "The brand") + " was removed.");
    }

    async function applySeries(seriesId, topic) {
      const saved = await act("POST", on("/series/" + encodeURIComponent(seriesId) + "/apply"), { topic: topic });
      if (!saved) return;
      setIdea(saved.idea || topic);
      setActiveId(saved.piece_id || "");
      setSection("create");
    }

    function pickBrand(id) {
      setBrandId(id);
      setAdding(false);
      setPickedDay("");
      setPickedPost("");
      setPickedHour("");
      setAssist(null);
      setDraftRead(null);
      setVoiceCheck(null);
    }

    function pickSection(id) {
      setSection(id);
      setAdding(false);
    }

    function explain(patternId) {
      setMemoryFocus(patternId || "");
      setSection("memory");
    }

    const sections = (brand && brand.sections) || [];
    const current = sections.find(function (item) { return item.id === section; }) || sections[0] || null;
    const desk = current ? current.id : "";
    const groups = [];
    sections.forEach(function (item) {
      const name = item.group || "Desk";
      let found = groups.find(function (group) { return group.name === name; });
      if (!found) {
        found = { name: name, items: [] };
        groups.push(found);
      }
      found.items.push(item);
    });
    const ready = !!(studio && brand && (!studio.brand || studio.brand.id === brand.id));
    const badges = deskBadges(ready ? studio : null);
    const mode = studio && studio.modes;

    function renderDesk() {
      switch (desk) {
        case "brief": return h(Brief, {
          key: brand.id,
          brand: brand, handles: handles, setHandles: setHandles, busy: busy, onSave: saveChannels, studio: studio,
          onSaveSite: function (site) { return act("POST", on("/site"), { site: site }, "Website saved."); },
          onCross: function (enabled) { return act("POST", on("/cross"), { enabled: enabled }, enabled ? "Included in cross-brand." : "Left out of cross-brand."); },
          onTodoNotes: function (enabled) { return act("POST", on("/todo-notes"), { enabled: enabled, scope: "global" }, enabled ? "Todo notes are on." : "Todo notes are off."); },
          onSupport: function (body) { return act("POST", on("/support"), body || {}, SUPPORT_DONE[(body || {}).action] || "Saved."); },
          onMode: function (body) { return act("POST", on("/mode"), body || {}, MODE_DONE[(body || {}).action] || "Saved."); },
          onPull: function () { return act("POST", on("/studio-read"), undefined, "Read from Studio."); },
          onRemove: function () { return removeBrand(brand.id); },
          onGo: pickSection,
        });
        case "voice": return h(VoiceGuide, {
          brand: brand, studio: studio, busy: busy,
          onSave: function (body) { return act("POST", on("/voice"), body, "Voice saved. A version was kept."); },
          onImport: function (body) { return act("POST", on("/voice/import"), body, "Posts added to the voice desk."); },
          onAccept: function (id) { return act("POST", on("/voice/accept"), { id: id }, "Suggestion accepted."); },
          onRestore: function (id) { return act("POST", on("/voice/restore"), { id: id }, "Version restored."); },
        });
        case "pages": return h(Pages, {
          brand: brand, studio: studio, busy: busy,
          onSave: function (body) { return act("POST", "/connections", Object.assign({ brand_id: brand.id }, body), "Connection saved. The token went to the vault."); },
          onPull: function () { return act("POST", on("/pull"), undefined, function (pulled) { return (pulled && pulled.count != null ? pulled.count + " posts pulled." : "Pulled."); }); },
        });
        case "ideas": return h(IdeasBoard, {
          studio: studio, busy: busy,
          onSave: function (body) { return act("POST", on("/ideas"), body, "Idea saved."); },
          onDraft: async function (id) {
            const saved = await act("POST", "/ideas/" + id + "/draft");
            if (saved && saved.piece_id) openPiece(saved.piece_id);
          },
          onSuggest: function () { return ask("POST", on("/ideas/suggest")); },
          onKeep: function (postId) { return act("POST", on("/ideas/shapes/" + encodeURIComponent(postId)), undefined, "Shape kept."); },
          onFeedback: sendFeedback,
          onApplySeries: applySeries,
        });
        case "create": return h(CreatePanel, {
          cross: studio && studio.cross,
          onAcceptCross: function (key) { return act("POST", on("/cross"), { accept: true, key: key }, "Accepted. The draft did not change."); },
          brand: brand, idea: idea, setIdea: setIdea, pillar: pillar, setPillar: setPillar,
          format: format, setFormat: setFormat, hypothesis: hypothesis, setHypothesis: setHypothesis,
          busy: busy, onShape: shapeIdea, onCheck: checkVoice, voiceCheck: voiceCheck, active: active, pieces: pieces, onEdit: editVariant,
          dirty: !!(active && dirty[active.id]),
          onSave: savePiece, onDelete: removePiece, onOpen: function (piece) { setActiveId(piece.id); },
          onClose: function () { setActiveId(""); },
          library: library,
          onInsert: function (asset) {
            if (!asset || typeof asset === "string") {
              const text = String(asset || "");
              setIdea(function (value) { return value ? value + "\n\n" + text : text; });
              return;
            }
            if (asset.role === "hashtags") {
              const tags = String(asset.body || "").split(/[#,\s]+/).filter(Boolean).slice(0, 5);
              if (active) editVariant("instagram", "hashtags", tags);
              return;
            }
            const text = String(asset.body || "");
            if (!text) return;
            if (assistTarget === "idea" || !active) {
              setIdea(function (value) { return value ? value + "\n\n" + text : text; });
              return;
            }
            const variant = (active.variants && active.variants[assistTarget]) || {};
            editVariant(assistTarget, "body", variant.body ? variant.body + "\n\n" + text : text);
          },
          onAttach: function (assetId) {
            if (active && active.brand_id === brand.id) useAsset(assetId, { piece_id: active.id });
          },
          limits: limits, cardLimit: cardLimit,
          assist: assist, assistTarget: assistTarget, setAssistTarget: setAssistTarget,
          assistReady: !!assistText().trim(),
          onAssist: askAssist, onApply: applyAssist, onHashtag: applyHashtag,
          onDismissAssist: function () { setAssist(null); },
          onRead: function () { readDraft(assistText()); },
          onImprove: improveDraft,
          onWhy: explain,
          onFeedback: sendFeedback,
          onUseChange: function (line) {
            const text = String(line || "").trim();
            if (!text) return;
            setIdea(function (value) { return value ? value + "\n\n" + text : text; });
          },
          onHideRange: async function (hidden, scope) {
            const saved = await ask("POST", on("/prediction-hide"), { hidden: hidden, scope: scope });
            if (saved) await readDraft(assistText());
          },
          draftRead: draftRead,
          onHold: function (date) {
            if (active && active.brand_id === brand.id) placePiece(active.id, date);
            else if (idea.trim()) planPiece({ idea: idea, scheduled_for: date, pillar: pillar, format: format });
          },
          onSaveCopy: function () {
            const text = assistText().trim();
            if (!text) return;
            saveAsset({ kind: "copy", role: "copy", name: text.slice(0, 48), body: text, tags: [] });
          },
          onQueue: function (id) { runQueue("pending", [id]); },
        });
        case "library": return h(Library, {
          library: library,
          series: studio && studio.series,
          busy: busy,
          onApplySeries: applySeries,
          piece: active && active.brand_id === brand.id ? active : null,
          posts: (studio && studio.feed) || [],
          onSave: saveAsset,
          onRevise: function (id, body) { return act("PATCH", "/assets/" + id, body, body && body.restore ? "Version restored." : "Asset saved."); },
          onUse: useAsset,
          onTags: function (id) { return act("POST", "/assets/" + encodeURIComponent(id) + "/tags", undefined, "Tags read."); },
          onFail: function (text) { notify(text, "error"); },
        });
        case "series": return h(SeriesDesk, {
          studio: studio, busy: busy,
          onFeedback: sendFeedback,
          onSave: function (body) { return act("POST", on("/series"), body, "Series saved."); },
          onKeep: function (shape) { return act("POST", on("/series/keep"), { shape: shape }, "Kept as a series."); },
          onApply: applySeries,
          onPause: function (id, paused) { return act("POST", on("/support"), { action: "series", id: id, paused: paused }, paused ? "Series paused." : "Series resumed."); },
          onFill: function (id) { return ask("POST", on("/support"), { action: "fill", id: id }); },
        });
        case "calendar": return h(Calendar, {
          onWhy: explain,
          brand: brand,
          calendar: studio && studio.calendar,
          ideas: studio && studio.ideas,
          library: library,
          busy: busy,
          onOpen: function (item) { openPiece(item.id); },
          onMove: placePiece,
          onPlan: planPiece,
          onRecur: function (body) { return act("POST", on("/recurrences"), body, "Recurrence saved."); },
          onApply: function (id) { return act("POST", "/recurrences/" + encodeURIComponent(id) + "/apply", undefined, "Those days are held."); },
        });
        case "queue": return h(QueueDesk, {
          studio: studio, busy: busy,
          onOpen: openPiece,
          onBulk: runQueue,
          onPull: function () { return act("POST", on("/studio-read"), undefined, "Read from Studio."); },
        });
        case "approval": return h(ApprovalDesk, {
          studio: studio, busy: busy,
          onOpen: openPiece,
          onSteps: function (steps) { return act("POST", on("/approval-steps"), { steps: steps }, "Steps saved."); },
          onReview: function (id) { return act("POST", "/pieces/" + id + "/review", undefined, "Sent for review."); },
          onDecide: function (id, body) { return act("POST", "/pieces/" + id + "/decision", body, body.decision === "approved" ? "Approved." : "Changes asked for."); },
          onComment: function (id, body) { return act("POST", "/pieces/" + id + "/comments", body, "Comment added."); },
          onRead: function (id) { return act("POST", "/notices/" + id + "/read"); },
        });
        case "campaigns": return h(CampaignsDesk, {
          studio: studio,
          pieces: pieces.filter(function (piece) { return piece.brand_id === brand.id; }),
          library: library,
          busy: busy,
          onOpen: openPiece,
          onSave: function (body) { return act("POST", on("/campaigns"), body, "Campaign saved."); },
          onAttach: function (id, body) { return act("POST", "/campaigns/" + id + "/attach", body, "Added to the campaign."); },
          onClone: function (id) { return act("POST", "/campaigns/" + encodeURIComponent(id) + "/clone", undefined, "Campaign cloned."); },
          onKeep: function (id) { return act("POST", "/campaigns/" + encodeURIComponent(id) + "/retrospective", undefined, "Lesson kept."); },
        });
        case "map": return h(MapDesk, { studio: studio });
        case "performance": return h(Performance, {
          brand: brand, studio: studio, busy: busy, pickedDay: pickedDay, pickedPost: pickedPost, pickedHour: pickedHour,
          onDay: function (point) { setPickedDay(point.id); },
          onPost: function (point) { setPickedPost(point.id); },
          onHour: function (point) { setPickedHour(point.id); },
          onRecorded: function (body) { return act("POST", "/stats", Object.assign({ brand_id: brand.id }, body), "Result saved."); },
          onHistory: function (csv) { return act("POST", on("/history"), { csv: csv }, "History imported."); },
          onGoal: function (body) { return act("POST", on("/goals"), body, "Goal saved."); },
        });
        case "ingest": return h(IngestDesk, {
          studio: studio, busy: busy,
          onPreview: function (body) { return ask("POST", on("/ingest/preview"), body); },
          onCommit: function (body) { return act("POST", on("/ingest"), body, function (saved) { return saved.accepted + " rows imported."; }); },
        });
        case "memory": return h(MemoryDesk, {
          studio: studio, busy: busy, focus: memoryFocus,
          onSync: function () { return act("POST", on("/memory"), { action: "sync" }); },
          onCorrect: function (action, patternId) { return act("POST", on("/memory"), { action: action, pattern_id: patternId || "" }, action === "reset" ? "Corrections cleared." : "Pattern updated."); },
          onFeedback: sendFeedback,
          onExport: function (kind) { return ask("GET", on("/memory/export?kind=" + encodeURIComponent(kind))); },
        });
        case "hashtags": return h(HashtagDesk, {
          studio: studio,
          piece: active && active.brand_id === brand.id ? active : null,
          busy: busy,
          onFeedback: sendFeedback,
          onSaveSet: function (body) { return act("POST", on("/hashtag-sets"), body, "Set saved."); },
          onApply: function (setId) {
            if (!active || active.brand_id !== brand.id) return null;
            return act("POST", "/hashtag-sets/" + setId + "/apply", { piece_id: active.id }, "Tags added to the draft.");
          },
          onUse: function (pieceId, pillarId) { return act("POST", on("/hashtags/use"), { piece_id: pieceId, pillar: pillarId || "" }, "Tags added to the draft."); },
          onTrend: function (body) { return act("POST", on("/trends"), body, "Note saved."); },
        });
        case "inbox": return h(InboxDesk, {
          studio: studio, busy: busy,
          onRefresh: function () { return act("POST", on("/inbox"), undefined, "Inbox refreshed."); },
          onReply: function (id, body) { return act("POST", "/inbox/" + encodeURIComponent(id) + "/reply", body, body && body.dismissed ? "Dismissed." : "Reply draft saved. Nothing is sent."); },
          onSuggest: function (id) { return act("POST", "/inbox/" + encodeURIComponent(id) + "/suggest"); },
          onIdea: function (id) { return act("POST", "/inbox/" + encodeURIComponent(id) + "/idea", undefined, "Kept as an idea."); },
          onVoice: function (id, reply) { return act("POST", "/inbox/" + encodeURIComponent(id) + "/voice", { reply: reply || "" }, "Reply kept in the voice."); },
        });
        case "reports": return h(ReportsDesk, {
          studio: studio, busy: busy,
          onGenerate: function (period, note) { return act("POST", on("/reports"), { period: period, note: note }, "Report ready."); },
          onInsight: function (id) { return act("POST", "/reports/" + encodeURIComponent(id) + "/insight", undefined, "Insight written."); },
        });
        case "across": return h(AcrossDesk, {
          studio: studio, busy: busy,
          onAccept: function (key) { return act("POST", on("/cross"), { accept: true, key: key }, "Accepted."); },
        });
        case "learning": return h(Learning, { studio: studio });
        default: return null;
      }
    }

    return h("div", { className: "hs-page" },
      h("header", { className: "hs-header" },
        h("div", null,
          h("h1", { className: "hs-title" }, "House Social"),
          h("p", { className: "hs-lede" }, "One desk for each brand: the brief, the drafts, the calendar, and what the numbers are allowed to teach.")),
        h("div", { className: "hs-header-tags" },
          mode ? h("button", {
            type: "button", className: "hs-badge is-mode",
            title: "Change the mode on the Brief",
            onClick: function () { pickSection("brief"); },
          }, h("span", { className: "hs-dot-live", "aria-hidden": "true" }), (mode.label || "Manual") + " mode") : null,
          h("span", { className: "hs-badge", title: "No post leaves this desk until a publisher is attached." }, "Local only · nothing is sent"))),
      h("div", { className: "hs-shell" },
        h("aside", { className: "hs-rail" },
          h("div", { className: "hs-switch" },
            h("label", { className: "hs-rail-label", htmlFor: "hs-brand" }, "Brand"),
            h("select", {
              id: "hs-brand", className: "hs-field hs-brand-pick",
              value: brand ? brand.id : "",
              onChange: function (event) { pickBrand(event.target.value); },
            }, brands.map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); })),
            brand ? h("div", { className: "hs-channels" },
              PLATFORMS.map(function (pair) {
                const channel = (brand.channels || []).find(function (item) { return item.platform === pair[0]; }) || {};
                return h("span", {
                  key: pair[0], className: "hs-channel" + (channel.known ? " is-known" : ""),
                  title: pair[1] + (channel.known ? " · " + (channel.handle || "known") : " · not set"),
                }, pair[1]);
              })) : null,
            h("button", { type: "button", className: "hs-link-button", onClick: function () { setAdding(!adding); } }, adding ? "Close" : "+ Add a brand")),
          h(DeskNav, {
            groups: groups, section: desk, badges: badges, closed: closedGroups,
            onPick: pickSection,
            onToggle: function (name) {
              setClosedGroups(function (value) { return Object.assign({}, value, { [name]: !value[name] }); });
            },
          }),
          h("label", { className: "hs-rail-label hs-desk-pick-label", htmlFor: "hs-desk" }, "Desk"),
          h("select", {
            id: "hs-desk", className: "hs-field hs-desk-pick", value: desk,
            onChange: function (event) { pickSection(event.target.value); },
          }, groups.map(function (group) {
            return h("optgroup", { key: group.name, label: group.name },
              group.items.map(function (item) {
                const badge = badges[item.id];
                return h("option", { key: item.id, value: item.id }, item.label + (badge ? " (" + badge.n + ")" : ""));
              }));
          }))),
        h("main", { className: "hs-desk", "aria-busy": busy ? "true" : "false" },
          busy ? h("div", { className: "hs-progress", "aria-hidden": "true" }) : null,
          adding ? h(AddBrand, { busy: busy, onAdd: addBrand, onCancel: function () { setAdding(false); } })
            : !loaded ? h("p", { className: "hs-note hs-loading" }, "Loading the desk…")
              : !brand ? h("div", { className: "hs-empty" }, "No brand on the roster yet. Add one to start.")
                : h("div", { className: "hs-desk-body", key: brand.id + ":" + desk },
                  h("div", { className: "hs-desk-head" },
                    h("h2", { className: "hs-desk-title" }, current ? current.label : ""),
                    DESK_NOTES[desk] ? h("p", { className: "hs-desk-note" }, DESK_NOTES[desk]) : null),
                  ready ? renderDesk() : h("p", { className: "hs-note hs-loading" }, "Loading the desk…")))),
      h(Toasts, { items: toasts, onDismiss: dismiss }),
    );
  }

  function linesOf(value) {
    return String(value || "").split("\n").map(function (line) { return line.trim(); }).filter(Boolean);
  }

  function VoiceGuide(props) {
    const guide = (props.studio && props.studio.voice) || {};
    const desk = (props.studio && props.studio.voice_desk) || { versions: [], lessons: { suggestions: [], detail: "" }, imports: 0 };
    const lessons = desk.lessons || { suggestions: [], detail: "", ready: false };
    const stamp = [
      guide.tone, guide.personality, guide.formality, guide.humor, guide.point_of_view, guide.visual, guide.differentiation,
      (guide.dos || []).join("|"), (guide.donts || []).join("|"),
      (guide.banned || []).join("|"), (guide.preferred || []).join("|"), (guide.required || []).join("|"),
      guide.second_person ? "1" : "0",
      JSON.stringify(guide.pillars || []),
      JSON.stringify(guide.examples || []),
    ].join("\n");
    const [form, setForm] = useState(null);
    const [manual, setManual] = useState({ text: "", engagements: "", kind: "on", title: "" });
    useEffect(function () {
      const angles = {};
      (guide.pillars || []).forEach(function (pillar) { angles[pillar.id] = (pillar.angles || []).join("\n"); });
      setForm({
        tone: guide.tone || "",
        personality: guide.personality || "",
        formality: guide.formality || "",
        humor: guide.humor || "",
        point_of_view: guide.point_of_view || "",
        visual: guide.visual || "",
        differentiation: guide.differentiation || "",
        dos: (guide.dos || []).join("\n"),
        donts: (guide.donts || []).join("\n"),
        banned: (guide.banned || []).join("\n"),
        preferred: (guide.preferred || []).join("\n"),
        required: (guide.required || []).join("\n"),
        second_person: !!guide.second_person,
        angles: angles,
        examples: guide.examples || [],
        exampleTitle: "",
        exampleText: "",
      });
    }, [props.brand && props.brand.id, stamp]);
    if (!form) return null;
    function setField(field, value) {
      setForm(function (current) { return Object.assign({}, current, { [field]: value }); });
    }
    function save(event) {
      event.preventDefault();
      props.onSave({
        tone: form.tone,
        personality: form.personality,
        formality: form.formality,
        humor: form.humor,
        point_of_view: form.point_of_view,
        visual: form.visual,
        differentiation: form.differentiation,
        dos: linesOf(form.dos),
        donts: linesOf(form.donts),
        banned: linesOf(form.banned),
        preferred: linesOf(form.preferred),
        required: linesOf(form.required),
        second_person: form.second_person,
        pillars: (guide.pillars || []).map(function (pillar) {
          return { id: pillar.id, name: pillar.name, angles: linesOf(form.angles[pillar.id] || "") };
        }),
        examples: form.examples || [],
      });
    }
    function addExample(kind) {
      const text = form.exampleText.trim();
      if (!text) return;
      setField("examples", (form.examples || []).concat([{ title: form.exampleTitle, text: text, kind: kind, source: "written" }]));
      setField("exampleTitle", "");
      setField("exampleText", "");
    }
    return h("div", { className: "hs-main" },
      h("form", { onSubmit: save },
        h("label", { className: "hs-note" }, "Tone", h("textarea", { className: "hs-area", value: form.tone, onChange: function (event) { setField("tone", event.target.value); } })),
        h("label", { className: "hs-note" }, "Personality", h("textarea", { className: "hs-area hs-short", value: form.personality, onChange: function (event) { setField("personality", event.target.value); } })),
        h("label", { className: "hs-note" }, "Formality",
          h("select", { className: "hs-field", value: form.formality, onChange: function (event) { setField("formality", event.target.value); } },
            h("option", { value: "" }, "Not set"),
            h("option", { value: "casual" }, "Casual"),
            h("option", { value: "plain" }, "Plain"),
            h("option", { value: "formal" }, "Formal"))),
        h("label", { className: "hs-note" }, "Humor", h("input", { className: "hs-field", value: form.humor, placeholder: "Dry, none, warm", onChange: function (event) { setField("humor", event.target.value); } })),
        h("label", { className: "hs-note" }, "Point of view", h("input", { className: "hs-field", value: form.point_of_view, placeholder: "Second person, her scene, the product", onChange: function (event) { setField("point_of_view", event.target.value); } })),
        h("label", { className: "hs-note" }, "Do", h("textarea", { className: "hs-area hs-short", placeholder: "One rule a line", value: form.dos, onChange: function (event) { setField("dos", event.target.value); } })),
        h("label", { className: "hs-note" }, "Don't", h("textarea", { className: "hs-area hs-short", placeholder: "One rule a line", value: form.donts, onChange: function (event) { setField("donts", event.target.value); } })),
        h("label", { className: "hs-note" }, "Visual", h("textarea", { className: "hs-area hs-short", value: form.visual, onChange: function (event) { setField("visual", event.target.value); } })),
        h("label", { className: "hs-note" }, "Banned words and phrases", h("textarea", { className: "hs-area hs-short", placeholder: "One phrase a line", value: form.banned, onChange: function (event) { setField("banned", event.target.value); } })),
        h("label", { className: "hs-note" }, "Preferred language", h("textarea", { className: "hs-area hs-short", placeholder: "One phrase a line. A long draft should use one of them.", value: form.preferred, onChange: function (event) { setField("preferred", event.target.value); } })),
        h("label", { className: "hs-note" }, "Required in the draft", h("textarea", { className: "hs-area hs-short", placeholder: "One phrase a line. Use ? for a question mark.", value: form.required, onChange: function (event) { setField("required", event.target.value); } })),
        h("label", { className: "hs-note" }, "Competitor differentiation", h("textarea", { className: "hs-area hs-short", placeholder: "What this brand refuses to sound like", value: form.differentiation, onChange: function (event) { setField("differentiation", event.target.value); } })),
        h("label", { className: "hs-note" }, h("input", { type: "checkbox", checked: form.second_person, onChange: function (event) { setField("second_person", event.target.checked); } }), " Require you"),
        h("div", { className: "hs-name" }, "Pillars and angles"),
        (guide.pillars || []).length ? (guide.pillars || []).map(function (pillar) {
          const known = ((props.brand && props.brand.pillars) || []).find(function (item) { return item.id === pillar.id; });
          return h("label", { key: pillar.id, className: "hs-note" },
            pillar.name + (known && known.note ? " — " + known.note : ""),
            h("textarea", {
              className: "hs-area hs-short",
              placeholder: "One angle a line, up to three",
              value: (form.angles && form.angles[pillar.id]) || "",
              onChange: function (event) {
                const value = event.target.value;
                setForm(function (current) {
                  return Object.assign({}, current, { angles: Object.assign({}, current.angles, { [pillar.id]: value }) });
                });
              },
            }));
        }) : h("p", { className: "hs-note" }, "No themes on this brand yet."),
        h("div", { className: "hs-name" }, "On-brand and off-brand"),
        (form.examples || []).map(function (example, index) {
          return h("div", { key: example.kind + example.text + index, className: "hs-pillar" },
            h("div", { className: "hs-name" }, (example.kind === "off" ? "Off-brand" : "On-brand") + " · " + (example.source || "written") + (example.title ? " · " + example.title : "")),
            h("p", { className: "hs-note" }, example.text),
            h("button", {
              type: "button", className: "hs-tab",
              onClick: function () {
                setField("examples", (form.examples || []).filter(function (_item, itemIndex) { return itemIndex !== index; }));
              },
            }, "Remove"));
        }),
        h("label", { className: "hs-note" }, "Example title", h("input", { className: "hs-field", value: form.exampleTitle, onChange: function (event) { setField("exampleTitle", event.target.value); } })),
        h("label", { className: "hs-note" }, "Example text", h("textarea", { className: "hs-area hs-short", value: form.exampleText, onChange: function (event) { setField("exampleText", event.target.value); } })),
        h("div", { className: "hs-row" },
          h("button", { type: "button", className: "hs-tab", onClick: function () { addExample("on"); } }, "Add on-brand"),
          h("button", { type: "button", className: "hs-tab", onClick: function () { addExample("off"); } }, "Add off-brand"),
          h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Save voice"))),
      h("div", { className: "hs-name" }, "What the posts suggest"),
      h("p", { className: "hs-note" }, "Save the profile before you accept a suggestion. " + (lessons.detail || "Pull the page, or paste posts below.")),
      (lessons.suggestions || []).map(function (item) {
        return h("div", { key: item.id, className: "hs-pillar" },
          h("p", { className: "hs-voice" }, item.detail),
          item.example ? h("p", { className: "hs-note" }, item.example.text) : null,
          h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onAccept(item.id); } }, "Accept"));
      }),
      h("div", { className: "hs-name" }, "Teach it from old posts"),
      h("p", { className: "hs-note" }, (desk.imports || 0) + " pasted posts sit on this desk. A row with a date and an engagement count is also in Analytics. A row without a date stays out of the windows."),
      h("label", { className: "hs-note" }, "CSV",
        h("input", {
          className: "hs-field", type: "file", accept: ".csv,text/csv",
          onChange: function (event) {
            const file = event.target.files && event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function () { props.onImport({ csv: String(reader.result || "") }); };
            reader.readAsText(file);
          },
        })),
      h("label", { className: "hs-note" }, "One post", h("textarea", { className: "hs-area hs-short", placeholder: "Paste one post", value: manual.text, onChange: function (event) { setManual(Object.assign({}, manual, { text: event.target.value })); } })),
      h("div", { className: "hs-row" },
        h("input", { className: "hs-field", placeholder: "Engagements, if you know them", value: manual.engagements, onChange: function (event) { setManual(Object.assign({}, manual, { engagements: event.target.value })); } }),
        h("select", { className: "hs-field", value: manual.kind, onChange: function (event) { setManual(Object.assign({}, manual, { kind: event.target.value })); } },
          h("option", { value: "on" }, "On-brand example"),
          h("option", { value: "off" }, "Off-brand example"),
          h("option", { value: "" }, "Numbers only")),
        h("button", {
          type: "button", className: "hs-button", disabled: props.busy || !manual.text.trim(),
          onClick: function () { props.onImport({ text: manual.text, engagements: manual.engagements, kind: manual.kind, title: manual.title }); },
        }, "Add post")),
      h("div", { className: "hs-name" }, "Versions"),
      (desk.versions || []).length ? (desk.versions || []).map(function (version) {
        return h("div", { key: version.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, version.note || "saved"),
          h("p", { className: "hs-note" }, (version.at || "") + (version.tone ? " — " + version.tone : "")),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onRestore(version.id); } }, "Restore"));
      }) : h("p", { className: "hs-note" }, "No saved version yet. The guide on screen is the one in use."),
    );
  }

  function Pages(props) {
    const connections = (props.studio && props.studio.connections) || [];
    const pull = (props.studio && props.studio.pull) || {};
    const feed = (props.studio && props.studio.feed) || [];
    const [form, setForm] = useState({ platform: "facebook", external_id: "", app_id: "", token: "" });
    function setField(field, value) {
      setForm(function (current) { return Object.assign({}, current, { [field]: value }); });
    }
    async function submit(event) {
      event.preventDefault();
      const saved = await props.onSave({
        platform: form.platform,
        external_id: form.external_id,
        app_id: form.app_id,
        token: form.token,
      });
      if (saved) setField("token", "");
    }
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-callout" },
        "Studio still writes the week. Facebook and Instagram are one Meta app. Save the Page, then Pull. The Page names its Instagram account, and that account uses the same token. Threads is a separate login. The username often matches Instagram. The id does not, and the Facebook token cannot read it."),
      connections.length ? connections.map(function (item) {
        return h("div", { key: item.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, item.platform + (item.username ? " · @" + item.username : "") + " · " + item.external_id),
          h("p", { className: "hs-note" }, "App " + item.app_id + (item.via === "facebook" ? " · found on the Facebook Page" : "") + " · " + item.token_vault));
      }) : h("p", { className: "hs-note" }, "No Meta app on this brand yet."),
      h("form", { onSubmit: submit },
        h("div", { className: "hs-cols" },
          h("select", { className: "hs-field", value: form.platform, onChange: function (event) { setField("platform", event.target.value); } },
            PLATFORMS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); })),
          h("input", { className: "hs-field", placeholder: "page or account id", value: form.external_id, onChange: function (event) { setField("external_id", event.target.value); } }),
          h("input", { className: "hs-field", placeholder: "Meta app id", value: form.app_id, onChange: function (event) { setField("app_id", event.target.value); } }),
          h("input", { className: "hs-field", type: "password", placeholder: "page or user token", value: form.token, autoComplete: "off", onChange: function (event) { setField("token", event.target.value); } })),
        h("div", { className: "hs-row" },
          h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Save app"),
          h("button", { type: "button", className: "hs-button", disabled: props.busy || !connections.length, onClick: props.onPull }, "Pull posts"))),
      pull.pulled_at ? h("p", { className: "hs-note" }, pull.count + " posts · " + pull.pulled_at) : null,
      (pull.errors || []).map(function (item) { return h("p", { key: item, className: "hs-error" }, item); }),
      h("div", { className: "hs-name" }, "On the page"),
      feed.length ? feed.map(function (item) {
        return h("div", { key: (item.platform || "") + item.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, (item.platform || "") + " · " + (item.engagements || 0) + " engagements"),
          h("p", { className: "hs-note" }, item.preview || "Untitled"),
          item.permalink ? h("a", { href: item.permalink, target: "_blank", rel: "noopener noreferrer" }, "Open") : null);
      }) : h("p", { className: "hs-note" }, "Pull the page to see what already went out."),
    );
  }


  function StudioRead(props) {
    const read = props.read || {};
    if (!read.linked) return null;
    const learning = read.learning || {};
    const week = read.week || {};
    const hasWeek = (week.posts || []).length || (week.peaks || []).length;
    return h(Section, {
      title: "Studio",
      note: "Read from Studio. Nothing is written back, and this desk does not send that queue.",
      actions: [
        read.url ? h("a", { key: "open", href: read.url, target: "_blank", rel: "noopener noreferrer" }, "Open Studio") : null,
        read.cards_url ? h("a", { key: "cards", href: read.cards_url, target: "_blank", rel: "noopener noreferrer" }, "Quote cards") : null,
        h("button", { key: "pull", type: "button", className: "hs-tab", disabled: props.busy, onClick: props.onPull }, "Pull from Studio"),
      ],
    },
      h("p", { className: "hs-note" }, learning.detail || "Nothing has been read from Studio yet."),
      (learning.days || []).length ? h("p", { className: "hs-note" }, (learning.days || []).join(" · ")) : null,
      h("div", { className: "hs-name" }, "Studio queue"),
      (read.queue || []).length ? h("ul", { className: "hs-list" }, (read.queue || []).map(function (job, index) {
        return h("li", { key: String(job.id || index) + (job.platform || ""), className: "hs-note" },
          [job.when, job.day, job.platform, job.status, job.caption].filter(Boolean).join(" · "));
      })) : h("p", { className: "hs-note" }, "Nothing is waiting in Studio's publish queue."),
      hasWeek ? h("div", { className: "hs-stack" },
        h("div", { className: "hs-name" }, "This week" + (week.arc ? " · " + week.arc : "")),
        (week.posts || []).map(function (post, index) {
          return h("p", { key: "p" + index, className: "hs-note" }, [post.day, post.title, post.quote_card].filter(Boolean).join(" · "));
        }),
        (week.peaks || []).map(function (post, index) {
          return h("p", { key: "k" + index, className: "hs-voice" }, ["Peak", post.when, post.title, post.quote_card].filter(Boolean).join(" · "));
        })) : null,
      (read.cards || []).length ? h("div", { className: "hs-stack" },
        h("div", { className: "hs-name" }, "Quote cards"),
        read.cards.map(function (card, index) { return h("p", { key: index, className: "hs-voice" }, card); })) : null,
      (read.tracks || []).length ? h("p", { className: "hs-note" }, "Tracks: " + read.tracks.map(function (track) {
        return track.artist + " — " + track.title;
      }).join(" · ")) : null);
  }

  const MODE_CHOICES = [
    ["manual", "Manual", "You do every step. Nothing starts on its own."],
    ["approval", "Autonomous with approval", "Drafts a batch for you. Nothing is scheduled until you approve it."],
    ["auto", "Fully autonomous", "Schedules one piece at a time once you confirm the switch. Nothing is sent."],
  ];

  const LOG_FILTERS = [
    ["all", "Everything"], ["manual", "Manual mode"], ["approval", "Approval mode"], ["auto", "Autonomous mode"],
    ["prepare", "Batches prepared"], ["approve", "Approvals"], ["reject", "Rejections"], ["pause", "Pauses"], ["clear", "Clears"],
  ];

  function ModePanel(props) {
    const mode = props.mode || { mode: "manual", label: "Manual", rate: "", notice: "", batch: null, log: [], can_prepare: false, can_run: false };
    const now = mode.mode || "manual";
    const [pick, setPick] = useState(now);
    const [teach, setTeach] = useState("");
    const choice = MODE_CHOICES.find(function (item) { return item[0] === pick; }) || MODE_CHOICES[0];
    const batch = mode.batch;
    const rows = (batch && batch.pieces) || [];
    const undecided = rows.filter(function (item) { return !item.decision && item.status; });
    return h("div", { className: "hs-stack" },
      h("div", { className: "hs-choices", role: "radiogroup", "aria-label": "Mode" },
        MODE_CHOICES.map(function (item) {
          const on = pick === item[0];
          return h("label", { key: item[0], className: "hs-choice" + (on ? " is-on" : "") },
            h("input", { type: "radio", name: "hs-mode", value: item[0], checked: on, onChange: function () { setPick(item[0]); } }),
            h("span", { className: "hs-choice-body" },
              h("span", { className: "hs-choice-title" }, item[1], now === item[0] ? h("span", { className: "hs-tag" }, "Current") : null),
              h("span", { className: "hs-note" }, item[2])));
        })),
      mode.rate ? h("p", { className: "hs-note" }, mode.rate) : null,
      mode.notice ? h("p", { className: "hs-warn" }, mode.notice) : null,
      pick !== now ? h("div", { className: "hs-confirm" },
        pick === "auto" ? h("p", { className: "hs-warn" }, "Fully autonomous can schedule without asking each time. Nothing is sent, and you can switch back whenever you like.") : null,
        h("div", { className: "hs-row" },
          h("button", {
            type: "button", className: "hs-button", disabled: props.busy,
            onClick: function () { props.onMode({ action: "set", mode: pick, confirm: pick === "auto" }); },
          }, pick === "auto" ? "Confirm the switch" : "Switch to " + choice[1].toLowerCase()),
          h("button", { type: "button", className: "hs-tab", onClick: function () { setPick(now); } }, "Keep " + (mode.label || "Manual").toLowerCase()))) : null,
      mode.can_prepare || mode.can_run ? h("div", { className: "hs-row" },
        mode.can_prepare ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onMode({ action: "prepare" }); } }, "Prepare a batch") : null,
        mode.can_run ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onMode({ action: "run" }); } }, "Run once")
          : null) : null,
      rows.length ? h("div", { className: "hs-stack" },
        h("div", { className: "hs-name" }, "Latest batch"),
        h("ul", { className: "hs-rows" }, rows.map(function (item) {
          return h("li", { key: item.piece_id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" },
              h("div", null, item.idea),
              h("div", { className: "hs-meta" }, [item.status, item.decision, item.posted ? "sent" : ""].filter(Boolean).join(" · "))),
            !item.decision && item.status ? h("div", { className: "hs-row" },
              h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onMode({ action: "approve", piece_id: item.piece_id }); } }, "Approve"),
              h("button", {
                type: "button", className: "hs-tab", disabled: props.busy,
                onClick: function () { props.onMode({ action: "reject", piece_id: item.piece_id, teach: teach.trim() ? "banned" : "discard", phrase: teach.trim() }); },
              }, teach.trim() ? "Reject and ban" : "Reject")) : null);
        })),
        undecided.length ? field("When you reject, also ban this phrase",
          h("input", { className: "hs-field", value: teach, placeholder: "Optional. The phrase goes on the voice guide's banned list.", onChange: function (event) { setTeach(event.target.value); } })) : null) : null);
  }

  function LimitsForm(props) {
    const limits = props.limits || {};
    const [form, setForm] = useState({
      per_day: limits.per_day ? String(limits.per_day) : "",
      per_week: limits.per_week ? String(limits.per_week) : "",
      hold_hours: limits.hold_hours ? String(limits.hold_hours) : "",
    });
    function setField(name, value) {
      setForm(function (current) { return Object.assign({}, current, { [name]: value.replace(/[^0-9]/g, "") }); });
    }
    return h("form", {
      className: "hs-stack",
      onSubmit: function (event) {
        event.preventDefault();
        props.onMode({ action: "limits", per_day: form.per_day, per_week: form.per_week, hold_hours: form.hold_hours });
      },
    },
      h("div", { className: "hs-grid-3" },
        field("Most scheduled a day", h("input", { className: "hs-field", inputMode: "numeric", value: form.per_day, placeholder: "No limit", onChange: function (event) { setField("per_day", event.target.value); } })),
        field("Most scheduled a week", h("input", { className: "hs-field", inputMode: "numeric", value: form.per_week, placeholder: "No limit", onChange: function (event) { setField("per_week", event.target.value); } })),
        field("Hold before scheduling", h("input", { className: "hs-field", inputMode: "numeric", value: form.hold_hours, placeholder: "0 hours", onChange: function (event) { setField("hold_hours", event.target.value); } }), "Hours, up to 48.")),
      h("div", { className: "hs-row" }, h("button", { type: "submit", className: "hs-tab", disabled: props.busy }, "Save limits")));
  }

  function PausePanel(props) {
    const pause = props.pause || {};
    const [start, setStart] = useState(pause.start || "");
    const [end, setEnd] = useState(pause.end || "");
    const today = todayET();
    const active = pause.start && pause.end && pause.start <= today && today <= pause.end;
    return h("form", {
      className: "hs-stack",
      onSubmit: function (event) {
        event.preventDefault();
        props.onSupport({ action: "pause", start: start, end: end });
      },
    },
      pause.start ? h("p", { className: active ? "hs-warn" : "hs-note" },
        (active ? "Paused now, " : "A pause is set, ") + pause.start + " to " + pause.end + ". New work stops; what is already scheduled stays.") : null,
      h("div", { className: "hs-grid-3" },
        field("From", h("input", { className: "hs-field", type: "date", value: start, onChange: function (event) { setStart(event.target.value); } })),
        field("Through", h("input", { className: "hs-field", type: "date", value: end, min: start || undefined, onChange: function (event) { setEnd(event.target.value); } }))),
      h("div", { className: "hs-row" },
        h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !start || !end }, "Save pause"),
        pause.start ? h("button", {
          type: "button", className: "hs-tab", disabled: props.busy,
          onClick: function () { setStart(""); setEnd(""); props.onSupport({ action: "pause", start: "", end: "" }); },
        }, "Clear pause") : null));
  }

  function MixPanel(props) {
    const rows = props.mix || [];
    const pillars = props.pillars || [];
    const [kind, setKind] = useState("pillar");
    const [name, setName] = useState("");
    const [count, setCount] = useState("2");
    const names = kind === "pillar"
      ? pillars.map(function (item) { return [item.id, item.name]; })
      : FORMATS.map(function (item) { return [item, item]; });
    const picked = names.some(function (item) { return item[0] === name; }) ? name : (names[0] ? names[0][0] : "");
    function labelOf(row) {
      if (row.kind === "pillar") {
        const found = pillars.find(function (item) { return item.id === row.name; });
        return found ? found.name : row.name;
      }
      return row.name;
    }
    return h("div", { className: "hs-stack" },
      rows.length ? h("ul", { className: "hs-rows" }, rows.map(function (row) {
        const words = (row.bound === "least" ? "At least " : "No more than ") + row.count + " " + labelOf(row) + " a week";
        return h("li", { key: row.kind + row.name + row.bound, className: "hs-list-row" },
          h("div", { className: "hs-list-main" },
            h("div", null, words),
            h("div", { className: "hs-meta" }, row.hard && row.bound === "most" ? "Hard: a piece that would go over is held." : "Recorded. It does not hold a piece.")),
          h("button", {
            type: "button", className: "hs-tab", disabled: props.busy,
            onClick: function () { props.onSupport({ action: "mix", kind: row.kind, name: row.name, bound: row.bound, remove: true }); },
          }, "Remove"));
      })) : h("p", { className: "hs-note" }, "No mix target yet."),
      h("form", {
        className: "hs-inline-form",
        onSubmit: function (event) {
          event.preventDefault();
          props.onSupport({ action: "mix", kind: kind, name: picked, bound: "most", count: count, hard: true });
        },
      },
        h("span", { className: "hs-note" }, "Hold any piece that would put more than"),
        h("input", { className: "hs-field hs-w-xs", inputMode: "numeric", "aria-label": "Count", value: count, onChange: function (event) { setCount(event.target.value.replace(/[^0-9]/g, "")); } }),
        h("select", { className: "hs-field hs-w-sm", "aria-label": "Kind", value: kind, onChange: function (event) { setKind(event.target.value); setName(""); } },
          h("option", { value: "pillar" }, "pillar"),
          h("option", { value: "format" }, "format")),
        h("select", { className: "hs-field hs-w-md", "aria-label": kind === "pillar" ? "Pillar" : "Format", value: picked, onChange: function (event) { setName(event.target.value); } },
          names.map(function (item) { return h("option", { key: item[0], value: item[0] }, item[1]); })),
        h("span", { className: "hs-note" }, "pieces in one week."),
        h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !picked || count === "" }, "Add target")));
  }

  function hourLabel(hour) {
    const value = Number(hour) || 0;
    const suffix = value < 12 ? "am" : "pm";
    const twelve = value % 12 === 0 ? 12 : value % 12;
    return twelve + suffix;
  }

  function MailPanel(props) {
    const mail = props.mail || {};
    const [form, setForm] = useState({
      cadence: mail.cadence || "immediate",
      body: mail.body || "short",
      quiet_start: String(mail.quiet_start || 0),
      quiet_end: String(mail.quiet_end || 0),
    });
    function setField(name, value) {
      setForm(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    const hours = Array.from({ length: 24 }, function (_, index) { return index; });
    return h("form", {
      className: "hs-stack",
      onSubmit: function (event) {
        event.preventDefault();
        props.onSupport({ action: "mail", cadence: form.cadence, body: form.body, quiet_start: Number(form.quiet_start), quiet_end: Number(form.quiet_end) });
      },
    },
      h("div", { className: "hs-grid-4" },
        field("When", h("select", { className: "hs-field", value: form.cadence, onChange: function (event) { setField("cadence", event.target.value); } },
          h("option", { value: "immediate" }, "Right away"),
          h("option", { value: "digest" }, "In a digest"))),
        field("Body", h("select", { className: "hs-field", value: form.body, onChange: function (event) { setField("body", event.target.value); } },
          h("option", { value: "short" }, "Short"),
          h("option", { value: "full" }, "Full"))),
        field("Quiet from", h("select", { className: "hs-field", value: form.quiet_start, onChange: function (event) { setField("quiet_start", event.target.value); } },
          hours.map(function (hour) { return h("option", { key: hour, value: String(hour) }, hourLabel(hour)); }))),
        field("Quiet until", h("select", { className: "hs-field", value: form.quiet_end, onChange: function (event) { setField("quiet_end", event.target.value); } },
          hours.map(function (hour) { return h("option", { key: hour, value: String(hour) }, hourLabel(hour)); })))),
      h("p", { className: "hs-hint" }, form.quiet_start === form.quiet_end ? "Same start and end means no quiet hours." : "Eastern time."),
      h("div", { className: "hs-row" }, h("button", { type: "submit", className: "hs-tab", disabled: props.busy }, "Save mail settings")));
  }

  function ActivityPanel(props) {
    const support = props.support || { previews: [] };
    const [exportText, setExportText] = useState("");
    const [filter, setFilter] = useState("all");
    const [copied, setCopied] = useState(false);
    const [more, setMore] = useState(false);
    const rows = (props.log || []).filter(function (item) { return filter === "all" || item.mode === filter || item.action === filter; });
    const shown = more ? rows : rows.slice(0, 8);
    const previews = support.previews || [];
    return h("div", { className: "hs-stack" },
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onSupport({ action: "preview" }); } }, "Preview next week"),
        previews.length ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onSupport({ action: "discard" }); } }, "Discard preview") : null),
      previews.length ? h("ul", { className: "hs-rows" }, previews.slice(0, 7).map(function (item) {
        return h("li", { key: item.id, className: "hs-list-row" },
          h("div", { className: "hs-list-main" },
            h("div", null, item.date + (item.stale ? " · stale" : "")),
            h("div", { className: "hs-meta" }, item.idea)),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy || item.stale, onClick: function () { props.onSupport({ action: "promote", id: item.id }); } }, "Make a draft"));
      })) : null,
      h("div", { className: "hs-row hs-spread" },
        field("Show", h("select", { className: "hs-field", value: filter, onChange: function (event) { setFilter(event.target.value); } },
          LOG_FILTERS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); }))),
        h("div", { className: "hs-row" },
          h("button", {
            type: "button", className: "hs-tab", disabled: props.busy,
            onClick: async function () {
              const saved = await props.onSupport({ action: "export", kind: "markdown" });
              if (saved && saved.body) { setExportText(saved.body); setCopied(false); }
            },
          }, "Export decisions"),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy || !(props.log || []).length, onClick: function () { props.onSupport({ action: "clear" }); } }, "Clear log"))),
      shown.length ? h("ul", { className: "hs-rows hs-log" }, shown.map(function (item, index) {
        return h("li", { key: index, className: "hs-log-row" },
          h("span", { className: "hs-meta hs-log-at" }, String(item.at || "").replace("T", " ").slice(0, 16)),
          h("span", null, [item.action, item.outcome].filter(Boolean).join(" · ")),
          item.mode ? h("span", { className: "hs-tag" }, item.mode) : null);
      })) : h("p", { className: "hs-note" }, filter === "all" ? "Nothing logged yet." : "Nothing logged for this filter."),
      rows.length > 8 ? h("button", { type: "button", className: "hs-link-button", onClick: function () { setMore(!more); } }, more ? "Show fewer" : "Show all " + rows.length) : null,
      exportText ? h("div", { className: "hs-stack" },
        h("textarea", { className: "hs-area hs-mono", readOnly: true, value: exportText, "aria-label": "Exported decisions" }),
        h("div", { className: "hs-row" },
          h("button", {
            type: "button", className: "hs-tab",
            onClick: function () {
              if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(exportText).then(function () { setCopied(true); });
            },
          }, copied ? "Copied" : "Copy"),
          h("button", { type: "button", className: "hs-tab", onClick: function () { downloadText("decisions.md", exportText, "text/markdown"); } }, "Download"),
          h("button", { type: "button", className: "hs-link-button", onClick: function () { setExportText(""); } }, "Close"))) : null);
  }

  function ProfileForm(props) {
    const brand = props.brand;
    const saved = { site: brand.site || "" };
    PLATFORMS.forEach(function (pair) {
      const channel = (brand.channels || []).find(function (item) { return item.platform === pair[0]; }) || {};
      saved[pair[0]] = channel.handle || "";
    });
    const [site, setSite] = useState(saved.site);
    const siteChanged = site.trim() !== saved.site;
    const handlesChanged = PLATFORMS.some(function (pair) { return (props.handles[pair[0]] || "") !== saved[pair[0]]; });
    const link = /^https?:\/\//.test(site.trim()) ? site.trim() : "";
    return h("form", {
      className: "hs-stack",
      onSubmit: async function (event) {
        event.preventDefault();
        if (siteChanged) await props.onSaveSite(site.trim());
        if (handlesChanged) await props.onSave();
      },
    },
      field("Website", h("input", { className: "hs-field", value: site, placeholder: "https://", onChange: function (event) { setSite(event.target.value); } }),
        link ? h("a", { href: link, target: "_blank", rel: "noopener noreferrer" }, "Open " + link.replace(/^https?:\/\//, "")) : null),
      h("div", { className: "hs-grid-3" }, PLATFORMS.map(function (pair) {
        return h("label", { key: pair[0], className: "hs-note" }, pair[1] + " handle",
          h("input", {
            className: "hs-field",
            value: props.handles[pair[0]] || "",
            placeholder: "Not set",
            onChange: function (event) {
              const value = event.target.value;
              props.setHandles(function (current) { return Object.assign({}, current, { [pair[0]]: value }); });
            },
          }));
      })),
      h("div", { className: "hs-row" },
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || (!siteChanged && !handlesChanged) }, "Save profile"),
        siteChanged || handlesChanged ? h("span", { className: "hs-hint" }, "Unsaved changes") : null));
  }

  function Brief(props) {
    const brand = props.brand;
    const studio = props.studio || {};
    const support = studio.support || {};
    const health = support.health;
    const mode = studio.modes || {};
    return h("div", { className: "hs-main" },
      health ? h("div", { className: "hs-stack" },
        h("div", { className: "hs-stats" },
          h(Stat, { label: "Mode", value: mode.label || "Manual" }),
          h(Stat, { label: "Last ingest", value: health.ingest === "none" ? "None yet" : health.ingest, missing: health.ingest === "none" }),
          h(Stat, { label: "Posts with numbers", value: String(health.posts || 0) }),
          h(Stat, { label: "Channels", value: (brand.channels || []).filter(function (item) { return item.known; }).length + " of 3", note: channelLine(brand) })),
        health.hint ? h("button", { type: "button", className: "hs-link-button", onClick: function () { props.onGo("ingest"); } }, "No history yet. Open Ingest →") : null) : null,
      h(Section, { title: "Who it speaks to" },
        brand.audience ? h("p", { className: "hs-voice hs-lead" }, brand.audience) : null,
        brand.voice ? h("p", { className: "hs-voice" }, brand.voice) : null,
        !brand.audience && !brand.voice ? h("p", { className: "hs-note" }, "No audience or voice line yet. Write them on the Voice desk.") : null,
        (brand.guards || []).length ? h("div", { className: "hs-stack" },
          h("div", { className: "hs-name" }, "Guards"),
          h("ul", { className: "hs-guard" }, brand.guards.map(function (guard) { return h("li", { key: guard }, guard); }))) : null,
        (brand.pillars || []).length ? h("div", { className: "hs-stack" },
          h("div", { className: "hs-name" }, "Pillars"),
          h("div", { className: "hs-pillars" }, (brand.pillars || []).map(function (item) {
            return h("div", { key: item.id, className: "hs-pillar" },
              h("div", { className: "hs-name" }, item.name),
              item.note ? h("p", { className: "hs-note" }, item.note) : null);
          }))) : null),
      h(StudioRead, { read: studio.studio_read, busy: props.busy, onPull: props.onPull }),
      h(Section, { title: "Profile", note: "Public handles and the website. A handle is not a credential; tokens are saved on the Pages desk." },
        h(ProfileForm, { brand: brand, handles: props.handles, setHandles: props.setHandles, busy: props.busy, onSave: props.onSave, onSaveSite: props.onSaveSite })),
      h(Section, { title: "How far the desk acts", note: "The mode decides what starts without you. Nothing is sent in any mode." },
        h(ModePanel, { mode: studio.modes, busy: props.busy, onMode: props.onMode })),
      h(Section, { title: "Pause", note: "Stops new work for a stretch of days without changing the mode.", collapsible: true, open: !!(support.pause && support.pause.start) },
        h(PausePanel, { pause: support.pause, busy: props.busy, onSupport: props.onSupport })),
      h(Section, { title: "Guardrails", note: "Limits on what autonomous modes may schedule.", collapsible: true, open: !!((support.mix || []).length) },
        h("div", { className: "hs-name" }, "Content mix"),
        h(MixPanel, { mix: support.mix, pillars: brand.pillars, busy: props.busy, onSupport: props.onSupport }),
        h("div", { className: "hs-name" }, "Pace"),
        h(LimitsForm, { limits: mode.limits, busy: props.busy, onMode: props.onMode })),
      h(Section, { title: "Mail", note: "Stored for when a mail path exists. Nothing is mailed today.", collapsible: true },
        h(MailPanel, { mail: support.mail, busy: props.busy, onSupport: props.onSupport })),
      h(Section, { title: "Activity", note: "What each mode did, a preview of next week that does not schedule, and a redacted export.", collapsible: true },
        h(ActivityPanel, { support: support, log: mode.log, busy: props.busy, onSupport: props.onSupport })),
      h(Section, { title: "Sharing" },
        h("label", { className: "hs-note" },
          h("input", {
            type: "checkbox",
            checked: !!brand.cross_enabled,
            disabled: props.busy,
            onChange: function (event) { if (props.onCross) props.onCross(event.target.checked); },
          }),
          h("span", null, h("span", { className: "hs-check-title" }, "Include this brand in cross-brand"), " It stays off until you check it. Only the counts are compared.")),
        h("label", { className: "hs-note" },
          h("input", {
            type: "checkbox",
            checked: !!(studio.todo_notes && studio.todo_notes.global),
            disabled: props.busy,
            onChange: function (event) { if (props.onTodoNotes) props.onTodoNotes(event.target.checked); },
          }),
          h("span", null, h("span", { className: "hs-check-title" }, "Let Josie add to the todo"), " Off until this is checked. Two notes a day. Nothing already written is deleted."))),
      brand.removable ? h(RemoveBrand, { brand: brand, busy: props.busy, onRemove: props.onRemove }) : null,
    );
  }

  function RemoveBrand(props) {
    const [open, setOpen] = useState(false);
    const [typed, setTyped] = useState("");
    const name = props.brand.name;
    if (!open) {
      return h("div", { className: "hs-danger-zone" },
        h("div", null,
          h("div", { className: "hs-name" }, "Remove this brand"),
          h("p", { className: "hs-note" }, "Takes " + name + " off the roster and deletes everything stored for it.")),
        h("button", { type: "button", className: "hs-tab is-danger", onClick: function () { setOpen(true); } }, "Remove brand…"));
    }
    return h("form", {
      className: "hs-danger-zone is-open",
      onSubmit: function (event) {
        event.preventDefault();
        if (typed.trim() === name) props.onRemove();
      },
    },
      h("div", { className: "hs-name" }, "Remove " + name + "?"),
      h("p", { className: "hs-note" }, "This deletes its drafts, recorded numbers, page connections, library, campaigns, ideas, series, inbox, reports, imported history, voice guide, and mode settings. It cannot be undone. Tokens in the vault are not touched."),
      h("label", { className: "hs-note" }, "Type " + name + " to confirm",
        h("input", { className: "hs-field", value: typed, autoFocus: true, autoComplete: "off", onChange: function (event) { setTyped(event.target.value); } })),
      h("div", { className: "hs-row" },
        h("button", { type: "submit", className: "hs-button is-danger", disabled: props.busy || typed.trim() !== name }, "Remove " + name),
        h("button", { type: "button", className: "hs-tab", onClick: function () { setOpen(false); setTyped(""); } }, "Cancel")));
  }

  const ASSIST_ACTIONS = [
    ["draft", "Draft", "Write a first draft from the idea"],
    ["rewrite", "Rewrite", "Rewrite inside the voice"],
    ["shorten", "Shorten", "Say it in fewer words"],
    ["expand", "Expand", "Add a line or two"],
    ["variations", "Variations", "Three other ways to say it"],
    ["hooks", "Hooks", "Opening lines"],
    ["caption", "Caption", "A caption for the attached image"],
    ["comment", "First comment", "A first comment for the post"],
    ["hashtags", "Hashtags", "Tags this brand already uses"],
    ["remix", "Remix", "Rework the post that is at least 3× the others"],
  ];

  function VoiceScore(props) {
    const report = props.report || { label: "", fields: [] };
    const missed = (report.fields || []).some(function (field) {
      return (field.checks || []).some(function (check) { return !check.ok; });
    });
    return h("div", { className: "hs-stack" },
      h("div", { className: "hs-name" }, report.label || "Voice"),
      (report.fields || []).map(function (field) {
        return h("div", { key: field.field, className: "hs-stack hs-gap-xs" },
          h("div", { className: "hs-overline" }, field.field),
          h("ul", { className: "hs-checks" }, (field.checks || []).map(function (check) {
            return h("li", { key: field.field + check.id, className: check.ok ? "is-ok" : "is-bad" },
              h("span", { className: "hs-check-mark", "aria-hidden": "true" }, check.ok ? "✓" : "✕"),
              h("span", { className: "hs-sr" }, check.ok ? "Passes: " : "Misses: "),
              check.label);
          })));
      }),
      missed ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: props.onRewrite }, "Suggest a rewrite from the misses") : null);
  }

  const VERDICTS = [["used", "Used"], ["better", "Better"], ["worse", "Worse"], ["off-brand", "Off-brand"], ["irrelevant", "Irrelevant"]];

  function FeedbackButtons(props) {
    const [note, setNote] = useState("");
    const [noting, setNoting] = useState(false);
    const [marked, setMarked] = useState("");
    if (!props.onFeedback || !props.target) return null;
    return h("div", { className: "hs-feedback" },
      h("span", { className: "hs-meta" }, marked ? "Marked " + marked + "." : "Rate it"),
      h("div", { className: "hs-row hs-gap-xs", role: "group", "aria-label": "Rate this suggestion" },
        VERDICTS.map(function (pair) {
          return h("button", {
            key: pair[0], type: "button", className: "hs-chip-button" + (marked === pair[0] ? " is-on" : ""), disabled: props.busy,
            "aria-pressed": marked === pair[0],
            onClick: async function () {
              const saved = await props.onFeedback({ kind: props.kind, target: props.target, verdict: pair[0], note: note, pillar: props.pillar || "", format: props.format || "" });
              if (saved) setMarked(pair[0]);
            },
          }, pair[1]);
        }),
        noting ? h("input", { className: "hs-field hs-w-md hs-field-sm", value: note, placeholder: "Why, in a few words", "aria-label": "Note with the rating", onChange: function (event) { setNote(event.target.value); } })
          : h("button", { type: "button", className: "hs-link-button", onClick: function () { setNoting(true); } }, "Add a note")));
  }

  function AssistResults(props) {
    const assist = props.assist;
    const hashtags = assist.action === "hashtags";
    const target = props.target === "idea" ? "the idea" : (PLATFORMS.find(function (pair) { return pair[0] === props.target; }) || [0, "the draft"])[1];
    const verb = hashtags ? "Add to Instagram" : assist.action === "comment" && props.target !== "idea" ? "Use as first comment" : "Use in " + target;
    return h("div", { className: "hs-stack" },
      h("div", { className: "hs-row hs-spread" },
        h("div", { className: "hs-name" }, assist.source === "brand" ? "Hashtags from this brand" : "Held to the voice guide"),
        h("button", { type: "button", className: "hs-link-button", onClick: props.onDismiss }, "Clear")),
      h("ul", { className: "hs-options" }, assist.options.map(function (option, index) {
        const lines = (option.reading && option.reading.lines) || [];
        return h("li", { key: index, className: "hs-option" },
          h("div", { className: "hs-option-text" }, hashtags ? "#" + option.text : option.text),
          option.voice && option.voice.total ? h("div", { className: "hs-meta" }, "Voice checks: " + option.voice.passed + " of " + option.voice.total) : null,
          lines.length ? lines.map(function (line, lineIndex) { return h("p", { key: lineIndex, className: "hs-note" }, line); })
            : option.reading ? h("p", { className: "hs-note" }, "No historical pattern matches this line.") : null,
          h("div", { className: "hs-row hs-spread" },
            h("button", {
              type: "button", className: "hs-tab", disabled: hashtags && !props.hasDraft,
              onClick: function () {
                if (hashtags) props.onHashtag(option.text);
                else props.onApply(option.text);
              },
            }, verb),
            h(FeedbackButtons, { kind: "composer", target: option.text, busy: props.busy, pillar: props.pillar, format: props.format, onFeedback: props.onFeedback })));
      })));
  }

  function DraftRead(props) {
    const read = props.read;
    const range = read.range;
    return h("div", { className: "hs-stack" },
      [read.hook, read.cta].filter(Boolean).map(function (line, index) { return h("p", { key: index, className: "hs-note" }, line); }),
      read.improve ? h("p", { className: "hs-voice" }, read.improve) : null,
      range ? h("div", { className: "hs-pillar" },
        h("div", { className: "hs-name" }, range.hidden ? "Range hidden" : "Range · " + (range.band || "wide")),
        h("p", { className: "hs-note" }, range.detail),
        (range.factors || []).length ? h("ul", { className: "hs-checks" }, (range.factors || []).map(function (factor) {
          return h("li", { key: factor.id, className: factor.matched ? "is-ok" : "is-bad" },
            h("span", { className: "hs-check-mark", "aria-hidden": "true" }, factor.matched ? "✓" : "✕"),
            factor.title + (factor.matched ? " matches." : " misses."));
        })) : null,
        (range.similar || []).map(function (item) {
          return h("p", { key: "near-" + item.id, className: "hs-note" }, h("strong", null, item.engagements), " engagements · " + item.preview);
        }),
        h("div", { className: "hs-row" },
          range.change ? h("button", {
            type: "button", className: "hs-tab", disabled: props.busy,
            onClick: function () { if (props.onUseChange) props.onUseChange(range.change); },
          }, "Try one change") : null,
          h("button", { type: "button", className: "hs-link-button", disabled: props.busy, onClick: function () { props.onHideRange(!range.hidden, "brand"); } }, range.hidden ? "Show the range" : "Hide the range"),
          h("button", { type: "button", className: "hs-link-button", disabled: props.busy, onClick: function () { props.onHideRange(!range.hidden, "all"); } }, range.hidden ? "Show it on every brand" : "Hide it on every brand"))) : null,
      (read.pattern_ids || []).length ? h("button", {
        type: "button", className: "hs-link-button",
        onClick: function () { if (props.onWhy) props.onWhy(read.pattern_ids[0]); },
      }, "Why this recommendation? →") : null,
      h("div", { className: "hs-name" }, "Similar past posts"),
      (read.similar || []).length ? h("ul", { className: "hs-rows" }, (read.similar || []).map(function (item) {
        return h("li", { key: item.id, className: "hs-list-row" },
          h("div", { className: "hs-list-main" },
            h("div", null, item.preview),
            h("div", { className: "hs-meta" }, item.engagements + " engagements" + (item.ahead ? " · ahead of the others" : ""))));
      })) : h("p", { className: "hs-note" }, "No saved post shares words with this draft."));
  }

  function CreatePanel(props) {
    const brand = props.brand;
    const mine = props.pieces.filter(function (piece) { return piece.brand_id === brand.id; });
    const [holdDay, setHoldDay] = useState("");
    const offer = props.cross && props.cross.offer;
    const active = props.active && props.active.brand_id === brand.id ? props.active : null;
    const targets = [["idea", "Idea"]].concat(active ? PLATFORMS : []);
    const target = active || props.assistTarget === "idea" ? props.assistTarget || "idea" : "idea";
    const words = ((props.library && props.library.assets) || []).filter(function (asset) {
      return asset.kind === "copy" || asset.kind === "template";
    }).slice(0, 8);
    const hasIdea = !!props.idea.trim();
    return h("div", { className: "hs-main" },
      offer ? h("div", { className: "hs-callout hs-row hs-spread" },
        h("span", null, h("strong", null, "Cross-brand: "), offer.detail),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { if (props.onAcceptCross) props.onAcceptCross(offer.key); } }, "Accept")) : null,
      h(Section, {
        title: active ? "Start another idea" : "Idea",
        note: active ? null : "Write it the way you would say it. Three versions come back, one for each platform.",
      },
        h("div", { className: "hs-grid-3" },
          field("Pillar", h("select", { className: "hs-field", value: props.pillar, onChange: function (event) { props.setPillar(event.target.value); } },
            h("option", { value: "" }, "Any pillar"),
            (brand.pillars || []).map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); }))),
          field("Format", h("select", { className: "hs-field", value: props.format, onChange: function (event) { props.setFormat(event.target.value); } },
            FORMATS.map(function (item) { return h("option", { key: item, value: item }, item); }))),
          field("Hypothesis", h("input", {
            className: "hs-field", value: props.hypothesis, placeholder: "Optional, if this is an experiment",
            onChange: function (event) { props.setHypothesis(event.target.value); },
          }))),
        field("The idea", h("textarea", {
          className: "hs-area" + (active ? " hs-short" : ""), value: props.idea, placeholder: "The idea, in your words.",
          onChange: function (event) { props.setIdea(event.target.value); },
        })),
        h("div", { className: "hs-row" },
          h("button", { type: "button", className: "hs-button", disabled: props.busy || !hasIdea, onClick: props.onShape }, "Create three versions"),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy || (!hasIdea && !active), onClick: props.onCheck }, "Check voice"),
          !active ? h("span", { className: "hs-row hs-gap-xs hs-push" },
            h("input", { className: "hs-field hs-w-md", type: "date", value: holdDay, "aria-label": "Day to hold the idea", onChange: function (event) { setHoldDay(event.target.value); } }),
            h("button", { type: "button", className: "hs-tab", disabled: props.busy || !holdDay || !hasIdea, onClick: function () { props.onHold(holdDay); } }, "Hold on this day")) : null)),
      active ? h(PieceEditor, {
        key: active.id,
        piece: active, brand: brand, busy: props.busy, limits: props.limits, cardLimit: props.cardLimit, dirty: props.dirty,
        library: props.library, onAttach: props.onAttach, onQueue: props.onQueue, onHold: props.onHold, onClose: props.onClose,
        onEdit: props.onEdit, onSave: props.onSave, onDelete: function () { props.onDelete(active.id); },
      }) : null,
      h(Section, { title: "Assistant", note: "Stays inside the brand voice. Nothing is applied until you choose an option." },
        h("div", { className: "hs-row" },
          h("span", { className: "hs-note" }, "Work on"),
          h(Segmented, { label: "Work on", value: target, options: targets, onChange: props.setAssistTarget }),
          !active ? h("span", { className: "hs-hint" }, "Open or create a draft to work on a platform version.") : null),
        !props.assistReady ? h("p", { className: "hs-hint" }, target === "idea" ? "Write the idea above first, or pick a platform that has words in it." : "This version is empty. Write a line first, or work on the idea.") : null,
        h("div", { className: "hs-row hs-gap-sm" },
          ASSIST_ACTIONS.map(function (pair) {
            const needsWords = pair[0] !== "remix" && pair[0] !== "hashtags" && pair[0] !== "caption";
            return h("button", {
              key: pair[0], type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy || (needsWords && !props.assistReady), title: pair[2],
              onClick: function () { props.onAssist(pair[0]); },
            }, pair[1]);
          })),
        h("div", { className: "hs-row" },
          h("button", { type: "button", className: "hs-tab", disabled: props.busy || !props.assistReady, onClick: props.onImprove }, "Improve from what the posts show"),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy || !props.assistReady, onClick: props.onRead }, "Find similar past posts"),
          h("button", { type: "button", className: "hs-link-button", disabled: props.busy || !props.assistReady, onClick: props.onSaveCopy }, "Save this text to the library")),
        words.length ? h("div", { className: "hs-stack hs-gap-xs" },
          h("div", { className: "hs-overline" }, "Insert from the library"),
          props.pillar ? h("p", { className: "hs-note" }, provenLine(props.library.assets, props.pillar)) : null,
          h("div", { className: "hs-row hs-gap-xs" }, words.map(function (asset) {
            return h("button", {
              key: asset.id, type: "button", className: "hs-chip-button", title: asset.body || asset.name,
              onClick: function () { if (props.onInsert) props.onInsert(asset); },
            }, (asset.role || "copy") + " · " + asset.name);
          }))) : null,
        props.assist && (props.assist.options || []).length ? h(AssistResults, {
          assist: props.assist, target: target, busy: props.busy, pillar: props.pillar, format: props.format, hasDraft: !!active,
          onApply: props.onApply, onHashtag: props.onHashtag, onFeedback: props.onFeedback, onDismiss: props.onDismissAssist,
        }) : null),
      props.voiceCheck || props.draftRead ? h(Section, { title: "What the posts say" },
        props.voiceCheck ? h(VoiceScore, {
          report: props.voiceCheck,
          busy: props.busy,
          onRewrite: function () {
            const misses = [];
            (props.voiceCheck.fields || []).forEach(function (item) {
              (item.checks || []).forEach(function (check) {
                if (!check.ok) misses.push(item.field + ": " + check.label);
              });
            });
            props.onAssist("rewrite", misses);
          },
        }) : null,
        props.draftRead ? h(DraftRead, {
          read: props.draftRead, busy: props.busy, onUseChange: props.onUseChange, onHideRange: props.onHideRange, onWhy: props.onWhy,
        }) : null) : null,
      h(Section, { title: "Drafts for " + brand.name, note: mine.length ? null : "No drafts yet. Create three versions above." },
        mine.length ? h("ul", { className: "hs-rows" }, mine.map(function (piece) {
          const on = active && piece.id === active.id;
          return h("li", { key: piece.id },
            h("button", {
              type: "button", className: "hs-row-button" + (on ? " is-on" : ""), "aria-current": on ? "true" : null,
              onClick: function () { props.onOpen(piece); },
            },
              h("span", { className: "hs-status is-" + (piece.status || "draft") }, piece.status || "draft"),
              h("span", { className: "hs-row-text" }, piece.idea),
              piece.format ? h("span", { className: "hs-meta" }, piece.format) : null));
        })) : null),
    );
  }

  const MEDIA_KINDS = ["image", "logo", "carousel", "video"];

  function platformLimit(brand, platform, limits, cardLimit) {
    if (brand && brand.id === "josie-blackthorn" && platform === "facebook") return cardLimit || 240;
    return (limits && limits[platform]) || 500;
  }

  function PieceEditor(props) {
    const piece = props.piece;
    const brand = props.brand || {};
    const [when, setWhen] = useState("");
    const [day, setDay] = useState(String(piece.scheduled_for || "").slice(0, 10));
    const [deleting, setDeleting] = useState(false);
    const assets = (props.library && props.library.assets) || [];
    const attached = assets.filter(function (asset) { return (piece.asset_ids || []).indexOf(asset.id) >= 0; });
    const loose = assets.filter(function (asset) {
      return MEDIA_KINDS.indexOf(asset.kind) >= 0 && (piece.asset_ids || []).indexOf(asset.id) < 0;
    });
    const [comments, setComments] = useState({});
    const josie = brand.id === "josie-blackthorn";
    return h("section", { className: "hs-section hs-editor", "aria-label": "Draft" },
      h("div", { className: "hs-section-head" },
        h("div", { className: "hs-section-titles" },
          h("div", { className: "hs-row hs-gap-sm" },
            h("span", { className: "hs-status is-" + (piece.status || "draft") }, piece.status || "draft"),
            piece.format ? h("span", { className: "hs-meta" }, piece.format) : null,
            piece.scheduled_for ? h("span", { className: "hs-meta" }, "· " + String(piece.scheduled_for).replace("T", " ").slice(0, 16)) : null,
            props.dirty ? h("span", { className: "hs-tag is-warn" }, "Unsaved changes") : null),
          h("h3", { className: "hs-h3" }, piece.idea)),
        h("div", { className: "hs-row" },
          h("button", { type: "button", className: "hs-button", disabled: props.busy || !props.dirty, onClick: function () { props.onSave(); } }, props.dirty ? "Save edits" : "Saved"),
          h("button", { type: "button", className: "hs-link-button", onClick: props.onClose }, "Close"))),
      h("div", { className: "hs-previews" }, PLATFORMS.map(function (pair) {
        const variant = (piece.variants && piece.variants[pair[0]]) || { body: "", hashtags: [], note: "", first_comment: "" };
        const limit = platformLimit(brand, pair[0], props.limits, props.cardLimit);
        const count = (variant.body || "").length;
        const commentCount = (variant.first_comment || "").length;
        const over = count > limit;
        return h("div", { key: pair[0], className: "hs-preview" },
          h("div", { className: "hs-row hs-spread" },
            h("div", { className: "hs-name" }, pair[1]),
            h("span", { className: "hs-counter" + (over ? " is-over" : count > limit * 0.9 ? " is-near" : ""), "aria-live": "polite" }, count + " / " + limit)),
          variant.note ? h("p", { className: "hs-note" }, variant.note) : null,
          h("textarea", {
            className: "hs-area", value: variant.body || "", "aria-label": pair[1] + " post",
            "aria-invalid": over ? "true" : null,
            onChange: function (event) { props.onEdit(pair[0], "body", event.target.value); },
          }),
          pair[0] === "instagram" ? field("Hashtags", h("input", {
            className: "hs-field", value: (variant.hashtags || []).join(" "), placeholder: "Kept out of the caption",
            onChange: function (event) { props.onEdit(pair[0], "hashtags", event.target.value.split(/\s+/).filter(Boolean)); },
          })) : null,
          variant.first_comment || comments[pair[0]] ? field("First comment", h("textarea", {
            className: "hs-area hs-short", value: variant.first_comment || "", placeholder: "Not part of the post.",
            autoFocus: !variant.first_comment && comments[pair[0]] === "new",
            onChange: function (event) { props.onEdit(pair[0], "first_comment", event.target.value); },
          }), commentCount ? h("span", { className: commentCount > 1000 ? "hs-bad" : "" }, commentCount + " / 1000") : null)
            : h("button", {
              type: "button", className: "hs-link-button",
              onClick: function () { setComments(function (current) { return Object.assign({}, current, { [pair[0]]: "new" }); }); },
            }, "+ Add a first comment"),
          variant.needs_image ? h("label", { className: "hs-note" },
            h("input", { type: "checkbox", checked: !!variant.image_ready, onChange: function (event) { props.onEdit(pair[0], "image_ready", event.target.checked); } }),
            h("span", null, "The quote image is ready")) : null);
      })),
      h("p", { className: "hs-hint" }, "Hashtags stay out of the Instagram caption. Threads stops at 500 characters." + (josie ? " Josie's Facebook card stops at 240." : "")),
      h("div", { className: "hs-stack" },
        h("div", { className: "hs-overline" }, "Media"),
        attached.length ? h("div", { className: "hs-media" }, attached.map(function (asset) {
          const image = asset.mime && asset.mime.indexOf("image/") === 0;
          return h("figure", { key: asset.id, className: "hs-media-item" },
            image ? h("img", { className: "hs-thumb", alt: asset.name, src: assetUrl(asset.id) }) : h("div", { className: "hs-thumb hs-thumb-empty" }, asset.kind),
            h("figcaption", { className: "hs-meta" }, asset.name));
        })) : h("p", { className: "hs-note" }, "No media on this draft yet."),
        loose.length ? h("select", {
          className: "hs-field hs-w-lg",
          value: "",
          "aria-label": "Attach from the library",
          onChange: function (event) {
            if (event.target.value && props.onAttach) props.onAttach(event.target.value);
            event.target.value = "";
          },
        }, h("option", { value: "" }, "Attach from the library…"),
          loose.map(function (asset) { return h("option", { key: asset.id, value: asset.id }, asset.kind + " · " + asset.name); })) : null),
      field("Campaign", h("input", {
        className: "hs-field hs-w-lg",
        defaultValue: piece.campaign || "",
        placeholder: "Optional",
        onBlur: function (event) {
          const value = event.target.value.trim();
          if (value !== (piece.campaign || "")) props.onSave({ campaign: value });
        },
      }), "Saved when you leave the field."),
      h("div", { className: "hs-actions" },
        h("div", { className: "hs-action-group" },
          h("div", { className: "hs-overline" }, "Move it along"),
          h("div", { className: "hs-row" },
            props.onQueue ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onQueue(piece.id); } }, "Send for approval") : null,
            h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onSave({ status: "ready" }); } }, "Mark ready"),
            h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onSave({ status: "planned" }); } }, "Mark planned"))),
        h("div", { className: "hs-action-group" },
          h("div", { className: "hs-overline" }, "Hold a day"),
          h("div", { className: "hs-row hs-gap-xs" },
            h("input", { className: "hs-field hs-w-md", type: "date", value: day, "aria-label": "Day to hold", onChange: function (event) { setDay(event.target.value); } }),
            h("button", { type: "button", className: "hs-tab", disabled: props.busy || !day, onClick: function () { props.onHold(day); } }, "Hold"))),
        h("div", { className: "hs-action-group" },
          h("div", { className: "hs-overline" }, "Schedule"),
          h("div", { className: "hs-row hs-gap-xs" },
            h("input", { className: "hs-field hs-w-lg", type: "datetime-local", value: when, "aria-label": "Schedule for", onChange: function (event) { setWhen(event.target.value); } }),
            h("button", { type: "button", className: "hs-tab", disabled: props.busy || !when, onClick: function () { props.onSave({ status: "scheduled", scheduled_for: new Date(when).toISOString() }); } }, "Schedule")))),
      h("div", { className: "hs-row hs-spread hs-editor-foot" },
        h("span", { className: "hs-hint" }, "Scheduling holds the time on the calendar. Nothing is sent."),
        deleting ? h("div", { className: "hs-row hs-gap-xs" },
          h("span", { className: "hs-note" }, "Delete this draft?"),
          h("button", { type: "button", className: "hs-button is-danger", disabled: props.busy, onClick: props.onDelete }, "Delete"),
          h("button", { type: "button", className: "hs-tab", onClick: function () { setDeleting(false); } }, "Keep it"))
          : h("button", { type: "button", className: "hs-tab is-danger", disabled: props.busy, onClick: function () { setDeleting(true); } }, "Delete draft…")));
  }

  // Categorical colors that read on both light and dark themes.
  const LANE_COLORS = { planned: "#8a9bb0", draft: "#c9a227", ready: "#4f9cf0", scheduled: "#3fb68b", published: "#a77de0" };
  const PILLAR_COLORS = ["#e07a5f", "#3d9be9", "#59b88a", "#d9a441", "#b07cd8", "#e05f9a"];
  const CAMPAIGN_COLORS = ["#d9a441", "#59b88a", "#3d9be9", "#e07a5f", "#b07cd8", "#e05f9a"];
  const PLATFORM_COLORS = { facebook: "#4c8df6", instagram: "#e0569b", threads: "#9aa5b1" };
  const NO_COLOR = "#7d838a";
  const LANES = [["planned", "Planned"], ["draft", "Drafted"], ["ready", "Ready"], ["scheduled", "Scheduled"], ["published", "Published"]];
  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  function Dialog(props) {
    const box = useRef(null);
    const close = useRef(props.onClose);
    close.current = props.onClose;
    useEffect(function () {
      const before = document.activeElement;
      const node = box.current;
      const first = node && node.querySelector("input, select, textarea, button:not(.hs-dialog-x)");
      if (first) first.focus();
      function onKey(event) {
        if (event.key === "Escape") { event.stopPropagation(); close.current(); return; }
        if (event.key !== "Tab" || !node) return;
        const stops = Array.from(node.querySelectorAll("input, select, textarea, button, a[href]")).filter(function (item) { return !item.disabled; });
        if (!stops.length) return;
        const head = stops[0];
        const tail = stops[stops.length - 1];
        if (event.shiftKey && document.activeElement === head) { event.preventDefault(); tail.focus(); }
        else if (!event.shiftKey && document.activeElement === tail) { event.preventDefault(); head.focus(); }
      }
      document.addEventListener("keydown", onKey, true);
      return function () {
        document.removeEventListener("keydown", onKey, true);
        if (before && before.focus) before.focus();
      };
    }, []);
    return h("div", { className: "hs-overlay", onMouseDown: function (event) { if (event.target === event.currentTarget) props.onClose(); } },
      h("div", { ref: box, className: "hs-dialog", role: "dialog", "aria-modal": "true", "aria-labelledby": "hs-dialog-title" },
        h("div", { className: "hs-row hs-spread" },
          h("h2", { id: "hs-dialog-title", className: "hs-h2" }, props.title),
          h("button", { type: "button", className: "hs-toast-close hs-dialog-x", "aria-label": "Close", onClick: props.onClose }, "×")),
        props.children));
  }

  function todayET() {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
    }).format(new Date());
  }

  function shiftDate(iso, days) {
    const parts = iso.split("-").map(Number);
    const utc = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] + days));
    const month = String(utc.getUTCMonth() + 1).padStart(2, "0");
    const day = String(utc.getUTCDate()).padStart(2, "0");
    return utc.getUTCFullYear() + "-" + month + "-" + day;
  }

  function shiftMonth(iso, delta) {
    const parts = iso.split("-").map(Number);
    const utc = new Date(Date.UTC(parts[0], parts[1] - 1 + delta, 1));
    const month = String(utc.getUTCMonth() + 1).padStart(2, "0");
    return utc.getUTCFullYear() + "-" + month + "-01";
  }

  function weekdayIndex(iso) {
    const parts = iso.split("-").map(Number);
    return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])).getUTCDay();
  }

  function utcDate(iso) {
    const parts = iso.split("-").map(Number);
    return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] || 1));
  }

  function monthLabel(iso) {
    return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" }).format(utcDate(iso));
  }

  function dayLabel(iso, options) {
    return new Intl.DateTimeFormat("en-US", Object.assign({ timeZone: "UTC" }, options)).format(utcDate(iso));
  }

  function rangeLabel(view, cursor) {
    if (view === "month") return monthLabel(cursor);
    if (view === "day") return dayLabel(cursor, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    const start = shiftDate(cursor, -weekdayIndex(cursor));
    const end = shiftDate(start, 6);
    const sameMonth = start.slice(0, 7) === end.slice(0, 7);
    return dayLabel(start, { month: "short", day: "numeric" }) + " – " + dayLabel(end, sameMonth ? { day: "numeric" } : { month: "short", day: "numeric" }) + ", " + end.slice(0, 4);
  }

  function gridDates(view, cursor) {
    if (view === "day") return [cursor];
    if (view === "week") {
      const start = shiftDate(cursor, -weekdayIndex(cursor));
      return [0, 1, 2, 3, 4, 5, 6].map(function (index) { return shiftDate(start, index); });
    }
    const first = cursor.slice(0, 7) + "-01";
    const start = shiftDate(first, -weekdayIndex(first));
    return Array.from({ length: 42 }, function (_, index) { return shiftDate(start, index); });
  }

  function entryVisible(item, filters) {
    const platforms = item.platforms || [];
    if (filters.platform !== "all") {
      if (item.kind === "published" && platforms[0] !== filters.platform) return false;
      if (item.kind === "piece" && platforms.length && platforms.indexOf(filters.platform) < 0) return false;
    }
    if (filters.format !== "all" && (item.format || "") !== filters.format) return false;
    if (filters.pillar !== "all") {
      if (item.kind === "published") return false;
      if ((item.pillar || "") !== filters.pillar) return false;
    }
    if (filters.campaign === "all") return true;
    if (item.kind === "published") return false;
    if (filters.campaign === "(none)") return !item.campaign;
    return item.campaign === filters.campaign;
  }

  function chipColor(item, colorBy, pillars, campaigns) {
    if (colorBy === "pillar") {
      const index = (pillars || []).findIndex(function (pillar) { return pillar.id === item.pillar; });
      return index < 0 ? NO_COLOR : PILLAR_COLORS[index % PILLAR_COLORS.length];
    }
    if (colorBy === "campaign") {
      const index = (campaigns || []).indexOf(item.campaign);
      return index < 0 ? NO_COLOR : CAMPAIGN_COLORS[index % CAMPAIGN_COLORS.length];
    }
    if (colorBy === "platform") return PLATFORM_COLORS[(item.platforms || [])[0]] || NO_COLOR;
    return LANE_COLORS[item.status] || LANE_COLORS.draft;
  }

  function legendFor(colorBy, pillars, campaigns, counts) {
    if (colorBy === "pillar") {
      return (pillars || []).map(function (pillar, index) { return [PILLAR_COLORS[index % PILLAR_COLORS.length], pillar.name]; }).concat([[NO_COLOR, "No pillar"]]);
    }
    if (colorBy === "campaign") {
      return (campaigns || []).map(function (name, index) { return [CAMPAIGN_COLORS[index % CAMPAIGN_COLORS.length], name]; }).concat([[NO_COLOR, "No campaign"]]);
    }
    if (colorBy === "platform") return PLATFORMS.map(function (pair) { return [PLATFORM_COLORS[pair[0]], pair[1]]; });
    return LANES.map(function (pair) { return [LANE_COLORS[pair[0]], pair[1] + " " + (counts[pair[0]] || 0)]; });
  }

  function laneCounts(items, dates) {
    const lanes = { planned: 0, draft: 0, ready: 0, scheduled: 0, published: 0 };
    const inView = items.filter(function (item) { return dates.indexOf(item.date) >= 0; });
    inView.forEach(function (item) {
      const lane = Object.prototype.hasOwnProperty.call(lanes, item.status) ? item.status : "draft";
      lanes[lane] += 1;
    });
    lanes.open = dates.filter(function (day) { return !inView.some(function (item) { return item.date === day; }); }).length;
    return lanes;
  }

  function PlanDialog(props) {
    const brand = props.brand;
    const [idea, setIdea] = useState("");
    const [pillar, setPillar] = useState(props.pillar || "");
    const [format, setFormat] = useState(brand.preferred_format || "feed");
    const [campaign, setCampaign] = useState("");
    const [date, setDate] = useState(props.date);
    const ideas = ((props.ideas && props.ideas.ideas) || []).filter(function (item) { return item.status !== "drafted"; }).slice(0, 4);
    const copies = ((props.library && props.library.assets) || []).filter(function (asset) { return asset.kind === "copy" || asset.kind === "template"; }).slice(0, 4);
    return h(Dialog, { title: "Hold " + (date ? dayLabel(date, { weekday: "long", month: "long", day: "numeric" }) : "a day"), onClose: props.onClose },
      h("form", {
        className: "hs-stack",
        onSubmit: async function (event) {
          event.preventDefault();
          if (!idea.trim() || !date) return;
          const saved = await props.onPlan({ idea: idea.trim(), campaign: campaign.trim(), pillar: pillar, format: format, scheduled_for: date });
          if (saved) props.onClose();
        },
      },
        field("The idea for this day", h("textarea", { className: "hs-area hs-short", value: idea, placeholder: "A line is enough. It is held as planned.", onChange: function (event) { setIdea(event.target.value); } })),
        ideas.length || copies.length ? h("div", { className: "hs-stack hs-gap-xs" },
          h("div", { className: "hs-overline" }, "Or start from"),
          h("div", { className: "hs-row hs-gap-xs" },
            ideas.map(function (item) {
              return h("button", { key: item.id, type: "button", className: "hs-chip-button", title: item.text, onClick: function () { setIdea(item.text || ""); } }, "Idea · " + (item.text || "").slice(0, 40));
            }),
            copies.map(function (asset) {
              return h("button", { key: asset.id, type: "button", className: "hs-chip-button", title: asset.body || asset.name, onClick: function () { setIdea(asset.body || asset.name); } }, "Library · " + asset.name);
            }))) : null,
        h("div", { className: "hs-grid-2" },
          field("Day", h("input", { className: "hs-field", type: "date", value: date, onChange: function (event) { setDate(event.target.value); } })),
          field("Pillar", h("select", { className: "hs-field", value: pillar, onChange: function (event) { setPillar(event.target.value); } },
            h("option", { value: "" }, "Any pillar"),
            (brand.pillars || []).map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); }))),
          field("Format", h("select", { className: "hs-field", value: format, onChange: function (event) { setFormat(event.target.value); } },
            FORMATS.map(function (item) { return h("option", { key: item, value: item }, item); }))),
          field("Campaign", h("input", { className: "hs-field", value: campaign, placeholder: "Optional", onChange: function (event) { setCampaign(event.target.value); } }))),
        h("div", { className: "hs-row" },
          h("button", { type: "submit", className: "hs-button", disabled: props.busy || !idea.trim() || !date }, "Hold this day"),
          h("button", { type: "button", className: "hs-tab", onClick: props.onClose }, "Cancel"))));
  }

  function RecurrenceForm(props) {
    const brand = props.brand;
    const [recur, setRecur] = useState({ name: "", weekday: "0", weeks: "4", idea: "" });
    function setField(name, value) {
      setRecur(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    return h("div", { className: "hs-stack" },
      (props.recurrences || []).length ? h("ul", { className: "hs-rows" }, props.recurrences.map(function (item) {
        const weekday = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][item.weekday] || "";
        return h("li", { key: item.id, className: "hs-list-row" },
          h("div", { className: "hs-list-main" },
            h("div", null, item.name),
            h("div", { className: "hs-meta" }, [weekday ? "Every " + weekday : "", item.weeks ? item.weeks + " weeks" : "", item.idea].filter(Boolean).join(" · "))),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onApply(item.id); } }, "Hold those days"));
      })) : null,
      h("form", {
        className: "hs-stack",
        onSubmit: function (event) {
          event.preventDefault();
          if (!recur.name.trim() || !recur.idea.trim()) return;
          props.onRecur({ name: recur.name.trim(), idea: recur.idea.trim(), weekday: Number(recur.weekday), weeks: Number(recur.weeks), pillar: "", format: brand.preferred_format || "feed" });
          setRecur(Object.assign({}, recur, { name: "", idea: "" }));
        },
      },
        h("div", { className: "hs-grid-3" },
          field("Name", h("input", { className: "hs-field", value: recur.name, placeholder: "Campfire Friday", onChange: function (event) { setField("name", event.target.value); } })),
          field("Every", h("select", { className: "hs-field", value: recur.weekday, onChange: function (event) { setField("weekday", event.target.value); } },
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map(function (name, index) { return h("option", { key: name, value: String(index) }, name); }))),
          field("For", h("select", { className: "hs-field", value: recur.weeks, onChange: function (event) { setField("weeks", event.target.value); } },
            [1, 2, 3, 4, 5, 6, 7, 8].map(function (count) { return h("option", { key: count, value: String(count) }, count + (count === 1 ? " week" : " weeks")); })))),
        field("Words to hold each week", h("textarea", { className: "hs-area hs-short", value: recur.idea, onChange: function (event) { setField("idea", event.target.value); } })),
        h("div", { className: "hs-row" },
          h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !recur.name.trim() || !recur.idea.trim() }, "Save recurrence"))));
  }

  function Calendar(props) {
    const brand = props.brand || { pillars: [] };
    const entries = (props.calendar && props.calendar.entries) || [];
    const advice = (props.calendar && props.calendar.advice) || { gaps: [], mix: [], warnings: [], slot: { clear: false, detail: "" } };
    const recurrences = (props.calendar && props.calendar.recurrences) || [];
    const [view, setView] = useState(function () { return recall("calendar-view") || "month"; });
    const [cursor, setCursor] = useState(todayET);
    const [colorBy, setColorBy] = useState("status");
    const [platform, setPlatform] = useState("all");
    const [format, setFormat] = useState("all");
    const [pillar, setPillar] = useState("all");
    const [campaign, setCampaign] = useState("all");
    const [planning, setPlanning] = useState(null);
    const [over, setOver] = useState("");
    useEffect(function () { remember("calendar-view", view); }, [view]);
    const filters = { platform: platform, format: format, pillar: pillar, campaign: campaign };
    const filtered = platform !== "all" || format !== "all" || pillar !== "all" || campaign !== "all";
    const visible = entries.filter(function (item) { return entryVisible(item, filters); });
    const dates = gridDates(view, cursor);
    const spanDates = view === "month" ? dates.filter(function (day) { return day.slice(0, 7) === cursor.slice(0, 7); }) : dates;
    const today = todayET();
    const campaigns = entries.reduce(function (list, item) {
      if (item.campaign && list.indexOf(item.campaign) < 0) list.push(item.campaign);
      return list;
    }, []);
    const waiting = visible.filter(function (item) { return item.kind === "piece" && !item.date; });
    const counts = laneCounts(visible, spanDates);
    const legend = legendFor(colorBy, brand.pillars, campaigns, counts);
    const slot = advice.slot || {};
    const missing = (advice.mix || []).filter(function (item) { return !item.n; });

    function moveCursor(direction) {
      if (view === "month") setCursor(shiftMonth(cursor, direction));
      else setCursor(shiftDate(cursor, direction * (view === "week" ? 7 : 1)));
    }

    function plan(date, pillarId) {
      setPlanning({ date: date || (slot.clear && slot.date) || shiftDate(today, 1), pillar: pillarId || "" });
    }

    function allowDrop(event) { event.preventDefault(); }

    function dropOn(event, date) {
      event.preventDefault();
      setOver("");
      const id = event.dataTransfer.getData("text/plain");
      if (id && props.onMove) props.onMove(id, date);
    }

    function chip(item) {
      const color = chipColor(item, colorBy, brand.pillars, campaigns);
      const text = (item.time ? item.time + " · " : "") + (item.title || item.status);
      const published = item.kind === "published";
      function open() {
        if (published) {
          if (item.permalink) window.open(item.permalink, "_blank", "noopener");
          return;
        }
        props.onOpen(item);
      }
      // A div, not a button: Firefox will not start a drag from a button.
      return h("div", {
        key: item.id,
        role: "button",
        tabIndex: 0,
        className: "hs-chip" + (published ? " is-published" : ""),
        draggable: !!item.draggable,
        style: { borderLeftColor: color },
        title: text + (published ? " · published, opens the post" : item.draggable ? " · drag to move" : ""),
        onDragStart: function (event) {
          event.dataTransfer.setData("text/plain", item.id);
          event.dataTransfer.effectAllowed = "move";
        },
        onClick: open,
        onKeyDown: function (event) {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
        },
      }, text);
    }

    function dayCell(day) {
      const items = visible.filter(function (item) { return item.date === day; });
      const outside = view === "month" && day.slice(0, 7) !== cursor.slice(0, 7);
      const limit = view === "month" ? 3 : 99;
      const shown = items.slice(0, limit);
      const past = day < today;
      return h("div", {
        key: day,
        className: "hs-day" + (day === today ? " is-today" : "") + (items.length ? "" : " is-gap") + (outside ? " is-out" : "") + (over === day ? " is-over" : "") + (past ? " is-past" : ""),
        onDragOver: allowDrop,
        onDragEnter: function () { setOver(day); },
        onDrop: function (event) { dropOn(event, day); },
      },
        h("div", { className: "hs-day-head" },
          h("span", { className: "hs-day-num", "aria-label": dayLabel(day, { weekday: "long", month: "long", day: "numeric" }) },
            view === "day" ? dayLabel(day, { weekday: "short", month: "short", day: "numeric" }) : String(Number(day.slice(8)))),
          h("button", {
            type: "button", className: "hs-day-add", title: "Hold an idea on this day",
            "aria-label": "Hold an idea on " + dayLabel(day, { month: "long", day: "numeric" }),
            onClick: function () { plan(day); },
          }, "+")),
        shown.map(chip),
        items.length > limit ? h("button", {
          type: "button", className: "hs-day-more",
          onClick: function () { setView("day"); setCursor(day); },
        }, "+" + (items.length - limit) + " more") : null);
    }

    return h("div", { className: "hs-main" },
      h("div", { className: "hs-cal-toolbar" },
        h("div", { className: "hs-row hs-gap-sm" },
          h("button", { type: "button", className: "hs-tab hs-icon-button", "aria-label": "Previous " + view, onClick: function () { moveCursor(-1); } }, "‹"),
          h("button", { type: "button", className: "hs-tab", onClick: function () { setCursor(today); } }, "Today"),
          h("button", { type: "button", className: "hs-tab hs-icon-button", "aria-label": "Next " + view, onClick: function () { moveCursor(1); } }, "›"),
          h("h3", { className: "hs-cal-title", "aria-live": "polite" }, rangeLabel(view, cursor))),
        h("div", { className: "hs-row hs-gap-sm" },
          h("button", { type: "button", className: "hs-button", onClick: function () { plan(""); } }, "+ Hold a day"),
          h(Segmented, { label: "View", value: view, options: [["month", "Month"], ["week", "Week"], ["day", "Day"]], onChange: setView }))),
      h("div", { className: "hs-cal-filters" },
        h("select", { className: "hs-field", "aria-label": "Platform", value: platform, onChange: function (event) { setPlatform(event.target.value); } },
          h("option", { value: "all" }, "All platforms"),
          PLATFORMS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); })),
        h("select", { className: "hs-field", "aria-label": "Format", value: format, onChange: function (event) { setFormat(event.target.value); } },
          h("option", { value: "all" }, "All formats"),
          FORMATS.map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("select", { className: "hs-field", "aria-label": "Pillar", value: pillar, onChange: function (event) { setPillar(event.target.value); } },
          h("option", { value: "all" }, "All pillars"),
          (brand.pillars || []).map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); })),
        h("select", { className: "hs-field", "aria-label": "Campaign", value: campaign, onChange: function (event) { setCampaign(event.target.value); } },
          h("option", { value: "all" }, "All campaigns"),
          h("option", { value: "(none)" }, "No campaign"),
          campaigns.map(function (name) { return h("option", { key: name, value: name }, name); })),
        h("select", { className: "hs-field", "aria-label": "Color by", value: colorBy, onChange: function (event) { setColorBy(event.target.value); } },
          [["status", "Color by status"], ["pillar", "Color by pillar"], ["campaign", "Color by campaign"], ["platform", "Color by platform"]].map(function (pair) {
            return h("option", { key: pair[0], value: pair[0] }, pair[1]);
          })),
        filtered ? h("button", {
          type: "button", className: "hs-link-button",
          onClick: function () { setPlatform("all"); setFormat("all"); setPillar("all"); setCampaign("all"); },
        }, "Clear filters") : null),
      h("div", { className: "hs-row hs-spread hs-cal-meta" },
        h("div", { className: "hs-legend" }, legend.map(function (pair) {
          return h("span", { key: pair[1], className: "hs-note" }, h("span", { className: "hs-swatch", style: { background: pair[0] } }), pair[1]);
        })),
        h("span", { className: "hs-note" }, counts.open + (counts.open === 1 ? " open day" : " open days") + " in view")),
      slot.detail || missing.length || (advice.warnings || []).length ? h("div", { className: "hs-advice" },
        slot.detail ? h("div", { className: "hs-row hs-gap-sm" },
          h("span", { className: slot.clear ? "hs-voice" : "hs-note" }, slot.clear ? h("strong", null, "Open slot: " + slot.label + ". ") : null, slot.detail),
          slot.clear && slot.date ? h("button", { type: "button", className: "hs-link-button", onClick: function () { plan(slot.date); } }, "Hold " + slot.date + " →") : null,
          (slot.pattern_ids || []).length ? h("button", { type: "button", className: "hs-link-button", onClick: function () { if (props.onWhy) props.onWhy(slot.pattern_ids[0]); } }, "Why?") : null) : null,
        missing.length ? h("div", { className: "hs-row hs-gap-xs" },
          h("span", { className: "hs-note" }, "Nothing held in the next 7 days for"),
          missing.map(function (item) {
            return h("button", { key: item.id, type: "button", className: "hs-chip-button", title: "Hold a " + item.name + " piece", onClick: function () { plan("", item.id); } }, item.name);
          })) : (advice.mix || []).length ? h("p", { className: "hs-note" }, "Every pillar has something in the next 7 days: " + advice.mix.map(function (item) { return item.name + " " + item.n; }).join(" · ") + ".")
          : (advice.gaps || []).map(function (line) { return h("p", { key: line, className: "hs-note" }, line); }),
        (advice.warnings || []).map(function (line) { return h("p", { key: line, className: "hs-warn" }, line); })) : null,
      view === "day" ? null : h("div", { className: "hs-cal-board hs-cal-dows", "aria-hidden": "true" }, WEEKDAYS.map(function (name) {
        return h("div", { key: name, className: "hs-dow" }, name);
      })),
      h("div", { className: (view === "day" ? "hs-cal-day" : "hs-cal-board") + (view === "week" ? " is-week" : "") }, dates.map(dayCell)),
      h("div", { className: "hs-stack" },
        h("div", { className: "hs-row hs-spread" },
          h("div", { className: "hs-name" }, "Not on a day" + (waiting.length ? " · " + waiting.length : "")),
          h("span", { className: "hs-hint" }, "Drag a piece here to take it off its day.")),
        h("div", {
          className: "hs-tray" + (over === "tray" ? " is-over" : ""),
          onDragOver: allowDrop,
          onDragEnter: function () { setOver("tray"); },
          onDrop: function (event) { dropOn(event, ""); },
        }, waiting.length ? waiting.map(chip) : h("p", { className: "hs-note" }, "Every piece has a day."))),
      h(Section, { title: "Repeat on a weekday", note: "Holds the same words on that weekday for up to 8 weeks.", collapsible: true, open: recurrences.length > 0 },
        h(RecurrenceForm, { brand: brand, recurrences: recurrences, busy: props.busy, onRecur: props.onRecur, onApply: props.onApply })),
      planning ? h(PlanDialog, {
        brand: brand, date: planning.date, pillar: planning.pillar, ideas: props.ideas, library: props.library, busy: props.busy,
        onPlan: props.onPlan, onClose: function () { setPlanning(null); },
      }) : null,
    );
  }

  const ASSET_KINDS = ["copy", "template", "image", "logo", "carousel", "video"];

  function readAssetFiles(fileList) {
    return Promise.all(Array.from(fileList || []).map(function (file) {
      return new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function () {
          const text = String(reader.result || "");
          const comma = text.indexOf(",");
          resolve({ name: file.name, data: comma >= 0 ? text.slice(comma + 1) : text });
        };
        reader.onerror = function () { reject(new Error("That file did not read.")); };
        reader.readAsDataURL(file);
      });
    }));
  }

  function assetUrl(id, version, frame) {
    const params = [];
    if (version) params.push("version=" + encodeURIComponent(version));
    if (frame != null) params.push("frame=" + frame);
    const query = params.length ? "?" + params.join("&") : "";
    return "/api/plugins/house-social/assets/" + id + "/file" + query;
  }

  function provenLine(assets, pillar) {
    const found = (assets || []).filter(function (asset) {
      return ((asset.performance && asset.performance.pairings) || []).some(function (row) {
        return row.clear && row.name === pillar;
      });
    });
    if (!found.length) return "No proven asset for this pillar yet.";
    const first = found[0];
    const pairing = (first.performance.pairings || []).find(function (row) { return row.clear && row.name === pillar; });
    return first.name + ". " + ((pairing && pairing.detail) || "");
  }

  function performanceLine(asset) {
    const perf = asset.performance || {};
    if (!perf.uses) return "Not used yet.";
    let line = "Used " + perf.uses;
    if (perf.last_used) line += " · last " + String(perf.last_used).slice(0, 10);
    if (perf.mean == null) return line + ". No engagement data yet.";
    line += " · mean " + perf.mean;
    if (perf.rate != null) line += " · " + perf.rate + " per 100 impressions";
    return line;
  }

  function Library(props) {
    const shelf = props.library || { assets: [], folders: [], tags: [] };
    const assets = shelf.assets || [];
    const [q, setQ] = useState("");
    const [kind, setKind] = useState("all");
    const [folder, setFolder] = useState("all");
    const [tag, setTag] = useState("all");
    const [openId, setOpenId] = useState("");
    const [draft, setDraft] = useState({ kind: "copy", role: "copy", name: "", folder: "", tags: "", body: "", note: "" });
    const [sort, setSort] = useState("updated");
    const visible = assets.filter(function (asset) {
      if (kind !== "all" && asset.kind !== kind) return false;
      if (folder !== "all" && asset.folder !== folder && asset.folder.indexOf(folder + "/") !== 0) return false;
      if (tag !== "all" && (asset.tags || []).indexOf(tag) < 0) return false;
      const hay = [asset.name, asset.folder, asset.note, asset.body, (asset.tags || []).join(" ")].join(" ").toLowerCase();
      return !q.trim() || hay.indexOf(q.trim().toLowerCase()) >= 0;
    });
    const shown = visible.slice().sort(function (left, right) {
      if (sort === "mean") return (right.performance && right.performance.mean || 0) - (left.performance && left.performance.mean || 0);
      if (sort === "quiet") {
        const leftUsed = (left.performance && left.performance.last_used) || "";
        const rightUsed = (right.performance && right.performance.last_used) || "";
        return leftUsed < rightUsed ? -1 : leftUsed > rightUsed ? 1 : 0;
      }
      return (right.updated_at || "") < (left.updated_at || "") ? -1 : 1;
    });
    const open = assets.find(function (asset) { return asset.id === openId; }) || null;

    function setField(field, value) {
      setDraft(function (current) { return Object.assign({}, current, { [field]: value }); });
    }

    function save(event) {
      event.preventDefault();
      const input = event.target.querySelector("input[type=file]");
      const files = input && input.files ? input.files : [];
      readAssetFiles(files).then(function (packed) {
        const body = {
          kind: draft.kind,
          name: draft.name,
          folder: draft.folder,
          tags: draft.tags.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
          note: draft.note,
          body: draft.body,
          role: draft.kind === "copy" || draft.kind === "template" ? draft.role : "",
        };
        if (draft.kind === "carousel") body.files = packed;
        else if (packed[0]) {
          body.data = packed[0].data;
          body.file_name = packed[0].name;
        }
        props.onSave(body);
        setDraft({ kind: draft.kind, role: draft.role, name: "", folder: draft.folder, tags: "", body: "", note: "" });
        if (input) input.value = "";
      }).catch(function (err) { if (props.onFail) props.onFail(messageOf(err)); });
    }

    return h("div", { className: "hs-main" },
      h("div", { className: "hs-cols" },
        h("input", { className: "hs-field", value: q, placeholder: "Search name, tag, folder, or copy", onChange: function (event) { setQ(event.target.value); } }),
        h("select", { className: "hs-field", value: kind, onChange: function (event) { setKind(event.target.value); } },
          h("option", { value: "all" }, "All kinds"),
          ASSET_KINDS.map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("select", { className: "hs-field", value: folder, onChange: function (event) { setFolder(event.target.value); } },
          h("option", { value: "all" }, "All folders"),
          (shelf.folders || []).map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("select", { className: "hs-field", value: tag, onChange: function (event) { setTag(event.target.value); } },
          h("option", { value: "all" }, "All tags"),
          (shelf.tags || []).map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("select", { className: "hs-field", value: sort, onChange: function (event) { setSort(event.target.value); } },
          h("option", { value: "updated" }, "Newest"),
          h("option", { value: "mean" }, "Highest mean"),
          h("option", { value: "quiet" }, "Least recently used"))),
      h("form", { className: "hs-cols", onSubmit: save },
        h("select", { className: "hs-field", value: draft.kind, onChange: function (event) { setField("kind", event.target.value); } },
          ASSET_KINDS.map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("input", { className: "hs-field", value: draft.name, placeholder: "Name", onChange: function (event) { setField("name", event.target.value); } }),
        draft.kind === "copy" || draft.kind === "template" ? h("select", { className: "hs-field", value: draft.role, onChange: function (event) { setField("role", event.target.value); } },
          ["copy", "hook", "cta", "hashtags", "bio"].map(function (item) { return h("option", { key: item, value: item }, item); })) : null,
        h("input", { className: "hs-field", value: draft.folder, placeholder: "Folder, such as cards/ember", onChange: function (event) { setField("folder", event.target.value); } }),
        h("input", { className: "hs-field", value: draft.tags, placeholder: "Tags, comma separated", onChange: function (event) { setField("tags", event.target.value); } }),
        h("textarea", { className: "hs-area", value: draft.body, placeholder: "Copy, template, or a note on the file", onChange: function (event) { setField("body", event.target.value); } }),
        h("input", { className: "hs-field", type: "file", accept: "image/png,image/jpeg,image/webp,image/gif,video/mp4,video/webm", multiple: draft.kind === "carousel" }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !draft.name.trim() }, "Save to the library")),
      h("div", { className: "hs-lib" },
        h("div", null,
          visible.length ? shown.map(function (asset) {
            return h("button", {
              key: asset.id, type: "button",
              className: "hs-piece" + (open && open.id === asset.id ? " is-on" : ""),
              onClick: function () { setOpenId(asset.id); },
            }, h("div", { className: "hs-name" }, asset.kind + " · " + asset.name),
              h("div", { className: "hs-meta" }, [asset.folder, (asset.tags || []).join(", "), performanceLine(asset)].filter(Boolean).join(" · ")));
          }) : h("p", { className: "hs-note" }, "Nothing in this library yet.")),
        open ? h("div", { className: "hs-pillar" },
          h("div", { className: "hs-name" }, open.name),
          open.body ? h("p", { className: "hs-voice" }, open.body) : null,
          open.note ? h("p", { className: "hs-note" }, open.note) : null,
          h("p", { className: "hs-note" }, performanceLine(open)),
          open.performance && open.performance.pairing_detail ? h("p", { className: open.performance.best_version ? "hs-ok" : "hs-note" }, open.performance.pairing_detail) : null,
          open.performance && open.performance.best_detail ? h("p", { className: "hs-note" }, open.performance.best_detail) : null,
          open.mime && open.mime.indexOf("video/") === 0
            ? h("video", { className: "hs-thumb", controls: true, src: assetUrl(open.id) })
            : (open.has_file || (open.frames || []).length)
              ? h("img", { className: "hs-thumb", alt: open.name, src: assetUrl(open.id, "", (open.frames || []).length && !open.mime ? 0 : null) })
              : null,
          (open.uses || []).length ? h("div", null, open.uses.map(function (use) {
            return h("div", { key: use.id, className: "hs-note" }, use.idea || use.post_id || "Used");
          })) : null,
          h("div", { className: "hs-row" },
            props.piece ? h("button", {
              type: "button", className: "hs-button", disabled: props.busy,
              onClick: function () { props.onUse(open.id, { piece_id: props.piece.id }); },
            }, "Attach to the open draft") : null,
            open.kind === "image" || open.kind === "logo" || open.kind === "carousel" ? h("button", {
              type: "button", className: "hs-tab", disabled: props.busy,
              onClick: function () { props.onTags(open.id); },
            }, "Read tags") : null,
            (props.posts || []).slice(0, 6).map(function (post) {
              return h("button", {
                key: post.id, type: "button", className: "hs-tab", disabled: props.busy,
                onClick: function () { props.onUse(open.id, { post_id: post.id }); },
              }, "Used on " + (post.preview || post.id).slice(0, 42));
            })),
          h("div", { className: "hs-name" }, "Versions"),
          (open.versions || []).map(function (version) {
            return h("div", { key: version.id, className: "hs-note" },
              (open.performance && open.performance.best_version === version.id ? "Ahead · " : "") + (version.note || "Saved") + (version.body ? " · " + version.body.slice(0, 80) : ""),
              h("button", {
                type: "button", className: "hs-tab", disabled: props.busy,
                onClick: function () { props.onRevise(open.id, { restore: version.id }); },
              }, "Bring this version back"));
          })) : h("p", { className: "hs-note" }, "Choose an asset to see its versions and where it has been used.")),
    );
  }

  function ApprovalDesk(props) {
    const desk = (props.studio && props.studio.approval) || { steps: ["Approver"], pieces: [], notices: [] };
    const [openId, setOpenId] = useState("");
    const [steps, setSteps] = useState((desk.steps || ["Approver"]).join(", "));
    const [author, setAuthor] = useState("");
    const [comment, setComment] = useState("");
    const open = (desk.pieces || []).find(function (item) { return item.id === openId; }) || null;
    const waiting = open && open.waiting ? open.waiting : (desk.steps || ["Approver"])[0];
    return h("div", { className: "hs-main" },
      (desk.notices || []).length ? h("div", null,
        h("div", { className: "hs-name" }, "Notices"),
        desk.notices.map(function (notice) {
          return h("div", { key: notice.id, className: "hs-row" },
            h("span", { className: "hs-note" }, notice.text),
            h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onRead(notice.id); } }, "Mark read"));
        })) : null,
      h("form", { className: "hs-row", onSubmit: function (event) { event.preventDefault(); props.onSteps(steps.split(",").map(function (item) { return item.trim(); }).filter(Boolean)); } },
        h("input", { className: "hs-field", value: steps, placeholder: "Approver names, in order", onChange: function (event) { setSteps(event.target.value); } }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Save steps")),
      (desk.pieces || []).length ? desk.pieces.map(function (item) {
        return h("div", { key: item.id, className: "hs-pillar" },
          h("button", { type: "button", className: "hs-post", onClick: function () { setOpenId(item.id === openId ? "" : item.id); setAuthor(item.waiting || ""); } },
            h("div", { className: "hs-name" }, item.status + (item.waiting ? " · waiting on " + item.waiting : "")),
            h("div", { className: "hs-meta" }, item.idea)),
          open && open.id === item.id ? h("div", null,
            h("div", { className: "hs-row" },
              h("button", { type: "button", className: "hs-tab", onClick: function () { props.onOpen(item.id); } }, "Open in the composer"),
              item.status !== "pending" && item.status !== "approved" ? h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onReview(item.id); } }, "Send for review") : null),
            (item.comments || []).map(function (note) {
              return h("p", { key: note.id, className: "hs-note" }, note.author + ": " + note.text);
            }),
            (item.signed || []).length ? h("p", { className: "hs-note" }, "Signed: " + item.signed.join(", ")) : null,
            (item.trail || []).length ? h("div", null,
              h("div", { className: "hs-name" }, "Trail"),
              item.trail.map(function (event) {
                return h("p", { key: event.id, className: "hs-note" }, event.author + " · " + event.action + (event.text ? " · " + event.text : ""));
              })) : null,
            item.compare && item.compare.ready ? h("div", null,
              h("div", { className: "hs-name" }, "Last two versions"),
              h("p", { className: "hs-note" }, item.compare.detail || ""),
              item.compare.platforms.map(function (platform) {
                return h("div", { key: platform.platform, className: "hs-preview" },
                  h("div", { className: "hs-name" }, platform.platform + (platform.same ? " · unchanged" : "")),
                  (platform.removed || []).map(function (line, index) { return h("p", { key: "r" + index, className: "hs-bad" }, "Removed: " + line); }),
                  (platform.added || []).map(function (line, index) { return h("p", { key: "a" + index, className: "hs-ok" }, "Added: " + line); }),
                  platform.same ? null : h("p", { className: "hs-note" }, platform.before || "Empty"),
                  platform.same ? null : h("p", { className: "hs-voice" }, platform.after || "Empty"));
              })) : h("p", { className: "hs-note" }, (item.compare && item.compare.detail) || "Nothing earlier to compare."),
            h("div", { className: "hs-cols" },
              h("input", { className: "hs-field", value: author, placeholder: waiting || "Your name", onChange: function (event) { setAuthor(event.target.value); } }),
              h("input", { className: "hs-field", value: comment, placeholder: "Comment", onChange: function (event) { setComment(event.target.value); } })),
            h("div", { className: "hs-row" },
              h("button", { type: "button", className: "hs-tab", disabled: props.busy || !author.trim() || !comment.trim(), onClick: function () { props.onComment(item.id, { author: author, text: comment }); setComment(""); } }, "Comment"),
              item.status === "pending" ? h("button", { type: "button", className: "hs-button", disabled: props.busy || !author.trim(), onClick: function () { props.onDecide(item.id, { author: author || waiting, decision: "approved", comment: comment }); setComment(""); } }, "Approve") : null,
              item.status === "pending" ? h("button", { type: "button", className: "hs-tab", disabled: props.busy || !author.trim(), onClick: function () { props.onDecide(item.id, { author: author || waiting, decision: "changes", comment: comment }); setComment(""); } }, "Ask for changes") : null)) : null);
      }) : h("p", { className: "hs-note" }, "No pieces waiting on this desk."),
    );
  }



  function SeriesApply(props) {
    const saved = (props.series && props.series.items) || [];
    const rows = saved.filter(function (item) { return !item.paused; });
    const [picked, setPicked] = useState(rows[0] ? rows[0].id : "");
    const [topic, setTopic] = useState("");
    const current = rows.some(function (item) { return item.id === picked; }) ? picked : (rows[0] ? rows[0].id : "");
    if (!saved.length) return null;
    if (!rows.length) return h("p", { className: "hs-note" }, "Every saved series is paused.");
    return h("form", { className: "hs-row", onSubmit: function (event) {
      event.preventDefault();
      if (current && topic.trim() && props.onApply) props.onApply(current, topic.trim());
    } },
      h("select", { className: "hs-field", value: current, onChange: function (event) { setPicked(event.target.value); } },
        rows.map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); })),
      h("input", { className: "hs-field", value: topic, placeholder: "New topic for this series", onChange: function (event) { setTopic(event.target.value); } }),
      h("button", { type: "submit", className: "hs-button", disabled: props.busy || !topic.trim() }, "Open in the composer"));
  }

  function SeriesDesk(props) {
    const desk = (props.studio && props.studio.series) || { items: [], suggestions: [] };
    const [draft, setDraft] = useState({ name: "", structure: "", hook: "", media: "", examples: "", tags: "" });
    const [filled, setFilled] = useState({});
    const [q, setQ] = useState("");
    const [tag, setTag] = useState("");
    const items = (desk.items || []).filter(function (item) {
      const blob = (item.name + " " + item.hook + " " + (item.structure || []).join(" ") + " " + (item.tags || []).join(" ")).toLowerCase();
      if (q.trim() && blob.indexOf(q.trim().toLowerCase()) < 0) return false;
      if (tag.trim() && (item.tags || []).map(function (name) { return name.toLowerCase(); }).indexOf(tag.trim().toLowerCase()) < 0) return false;
      return true;
    });
    return h("div", { className: "hs-main" },
      h(SeriesApply, { series: desk, busy: props.busy, onApply: props.onApply }),
      (desk.suggestions || []).map(function (item) {
        return h("div", { key: item.id, className: "hs-pillar" },
          h("p", { className: "hs-note" }, item.detail),
          h(FeedbackButtons, { kind: "series", target: item.id, busy: props.busy, onFeedback: props.onFeedback }),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onKeep(item.id); } }, "Keep " + item.name));
      }),
      h("form", { className: "hs-cols", onSubmit: function (event) {
        event.preventDefault();
        props.onSave({
          name: draft.name,
          structure: draft.structure,
          hook: draft.hook,
          media: draft.media,
          examples: draft.examples.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
          tags: draft.tags.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
        });
      } },
        h("input", { className: "hs-field", value: draft.name, placeholder: "Name", onChange: function (event) { setDraft(Object.assign({}, draft, { name: event.target.value })); } }),
        h("textarea", { className: "hs-area", value: draft.structure, placeholder: "Structure, one section a line. Use {topic} where the new topic goes.", onChange: function (event) { setDraft(Object.assign({}, draft, { structure: event.target.value })); } }),
        h("input", { className: "hs-field", value: draft.hook, placeholder: "Typical hook", onChange: function (event) { setDraft(Object.assign({}, draft, { hook: event.target.value })); } }),
        h("input", { className: "hs-field", value: draft.media, placeholder: "Media note", onChange: function (event) { setDraft(Object.assign({}, draft, { media: event.target.value })); } }),
        h("input", { className: "hs-field", value: draft.examples, placeholder: "Example post ids, comma separated", onChange: function (event) { setDraft(Object.assign({}, draft, { examples: event.target.value })); } }),
        h("input", { className: "hs-field", value: draft.tags, placeholder: "Tags, pillar or free text", onChange: function (event) { setDraft(Object.assign({}, draft, { tags: event.target.value })); } }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !draft.name.trim() || !draft.structure.trim() }, "Save series")),
      h("div", { className: "hs-row" },
        h("input", { className: "hs-field", value: q, placeholder: "Search", onChange: function (event) { setQ(event.target.value); } }),
        h("input", { className: "hs-field", value: tag, placeholder: "Tag", onChange: function (event) { setTag(event.target.value); } })),
      items.length ? items.map(function (item) {
        return h("div", { key: item.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, item.name),
          (item.structure || []).map(function (line, index) { return h("p", { key: index, className: "hs-note" }, line); }),
          item.hook ? h("p", { className: "hs-note" }, item.hook) : null,
          item.media ? h("p", { className: "hs-note" }, item.media) : null,
          h("p", { className: "hs-note" }, item.stats && item.stats.detail),
          item.notice ? h("p", { className: "hs-bad" }, item.notice) : null,
          h("div", { className: "hs-row" },
            h("button", {
              type: "button", className: "hs-tab", disabled: props.busy,
              onClick: function () { if (props.onPause) props.onPause(item.id, !item.paused); },
            }, item.paused ? "Resume" : "Pause"),
            h("button", {
              type: "button", className: "hs-tab", disabled: props.busy || item.paused,
              onClick: async function () {
                const saved = props.onFill ? await props.onFill(item.id) : null;
                if (saved && saved.lines) setFilled(function (current) { return Object.assign({}, current, { [item.id]: saved }); });
              },
            }, "Fill from a pillar")),
          item.paused ? h("p", { className: "hs-note" }, "Paused. Fill and the composer stay off until you resume it.") : null,
          filled[item.id] ? h("div", null,
            h("p", { className: "hs-note" }, "Filled with " + filled[item.id].topic + ". This is not saved. Nothing is sent."),
            (filled[item.id].lines || []).map(function (line, index) { return h("p", { key: "fill-" + index, className: "hs-voice" }, line); })
          ) : null,
          (item.examples || []).map(function (example) {
            return h("p", { key: example.id, className: "hs-note" }, (example.engagements == null ? "Not in the pull" : example.engagements + " engagements") + " · " + example.preview);
          }));
      }) : h("p", { className: "hs-note" }, "No series saved for this brand."));
  }

  function IdeasBoard(props) {
    const board = (props.studio && props.studio.ideas) || { ideas: [], sources: ["spark", "competitor", "trend", "question"], priorities: ["low", "normal", "high"] };
    const [mode, setMode] = useState("board");
    const [source, setSource] = useState("all");
    const [draft, setDraft] = useState({ text: "", source: "spark", priority: "normal", tags: "", note: "", link: "" });
    const [suggested, setSuggested] = useState([]);
    const ideas = (board.ideas || []).filter(function (item) {
      return source === "all" || item.source === source;
    });
    function setField(field, value) {
      setDraft(function (current) { return Object.assign({}, current, { [field]: value }); });
    }
    function save(event) {
      event.preventDefault();
      props.onSave({
        text: draft.text,
        source: draft.source,
        priority: draft.priority,
        tags: draft.tags.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
        note: draft.note,
        link: draft.link,
      });
      setDraft({ text: "", source: draft.source, priority: draft.priority, tags: "", note: "", link: "" });
    }
    function card(item) {
      return h("div", { key: item.id, className: "hs-pillar" },
        h("div", { className: "hs-name" }, item.source_label + " · " + item.priority),
        h("p", { className: "hs-voice" }, item.text),
        item.note ? h("p", { className: "hs-note" }, item.note) : null,
        item.pattern ? h("p", { className: "hs-note" }, item.pattern) : null,
        item.performed ? h("p", { className: "hs-ok" }, "This draft has a post that is at least 3× the others.") : null,
        (item.tags || []).length ? h("p", { className: "hs-note" }, item.tags.join(", ")) : null,
        item.link ? h("a", { href: item.link, target: "_blank", rel: "noopener noreferrer" }, "Open the link") : null,
        h("button", {
          type: "button", className: "hs-button", disabled: props.busy,
          onClick: function () { props.onDraft(item.id); },
        }, item.status === "drafted" ? "Open the draft" : "Make this a draft"));
    }
    const columns = (board.sources || []).map(function (name) {
      return { id: name, items: ideas.filter(function (item) { return item.source === name; }) };
    });
    return h("div", { className: "hs-main" },
      h(SeriesApply, { series: props.studio && props.studio.series, busy: props.busy, onApply: props.onApplySeries }),
      h("form", { className: "hs-cols", onSubmit: save },
        h("textarea", { className: "hs-area", value: draft.text, placeholder: "The idea, still rough", onChange: function (event) { setField("text", event.target.value); } }),
        h("select", { className: "hs-field", value: draft.source, onChange: function (event) { setField("source", event.target.value); } },
          (board.sources || []).map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("select", { className: "hs-field", value: draft.priority, onChange: function (event) { setField("priority", event.target.value); } },
          (board.priorities || []).map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("input", { className: "hs-field", value: draft.tags, placeholder: "Tags, comma separated", onChange: function (event) { setField("tags", event.target.value); } }),
        h("input", { className: "hs-field", value: draft.link, placeholder: "Link, if you have one", onChange: function (event) { setField("link", event.target.value); } }),
        h("input", { className: "hs-field", value: draft.note, placeholder: "Note", onChange: function (event) { setField("note", event.target.value); } }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !draft.text.trim() }, "Save idea")),
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: async function () {
          const found = props.onSuggest ? await props.onSuggest() : null;
          if (found && found.ideas) setSuggested(found.ideas);
        } }, "Suggest from the voice"),
        (suggested || []).map(function (text, index) {
          return h("button", { key: index, type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onSave({ text: text, source: "spark", priority: "normal" }); } }, "Keep");
        })),
      (suggested || []).map(function (text, index) {
        return h("div", { key: "s" + index },
          h("p", { className: "hs-voice" }, text),
          h(FeedbackButtons, { kind: "ideas", target: text, busy: props.busy, onFeedback: props.onFeedback }));
      }),
      h("p", { className: "hs-note" }, (board.lesson && board.lesson.detail) || ""),
      h("div", { className: "hs-name" }, "Ahead after a draft"),
      (board.archive || []).length ? (board.archive || []).map(card) : h("p", { className: "hs-note" }, "No drafted idea has a post that is at least 3× the others yet."),
      h("div", { className: "hs-name" }, "Shapes from posts that are ahead"),
      (board.shapes || []).length ? (board.shapes || []).map(function (item) {
        return h("div", { key: item.id, className: "hs-row" },
          h("span", { className: "hs-note" }, item.engagements + " · " + item.preview),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onKeep(item.id); } }, "Keep this shape"));
      }) : h("p", { className: "hs-note" }, "No post is at least 3× the others."),
      h("div", { className: "hs-name" }, "Comments to keep"),
      (board.comments || []).map(function (item) {
        return h("div", { key: item.id, className: "hs-row" },
          h("span", { className: "hs-note" }, item.text),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onSave({ text: item.text, source: "comment", inbox_id: item.id, note: item.author || "" }); } }, "Keep"));
      }),
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-tab" + (mode === "board" ? " is-on" : ""), onClick: function () { setMode("board"); } }, "Board"),
        h("button", { type: "button", className: "hs-tab" + (mode === "list" ? " is-on" : ""), onClick: function () { setMode("list"); } }, "List"),
        h("button", { type: "button", className: "hs-tab" + (source === "all" ? " is-on" : ""), onClick: function () { setSource("all"); } }, "All"),
        (board.sources || []).map(function (item) {
          return h("button", { key: item, type: "button", className: "hs-tab" + (source === item ? " is-on" : ""), onClick: function () { setSource(item); } }, item);
        })),
      mode === "board" ? h("div", { className: "hs-board" }, columns.map(function (column) {
        return h("div", { key: column.id },
          h("div", { className: "hs-name" }, column.id),
          column.items.length ? column.items.map(card) : h("p", { className: "hs-note" }, "Empty"));
      })) : h("div", null, ideas.length ? ideas.map(card) : h("p", { className: "hs-note" }, "No ideas yet.")),
    );
  }

  function CampaignsDesk(props) {
    const board = (props.studio && props.studio.campaigns) || { campaigns: [], kinds: ["launch", "seasonal", "evergreen"], lessons: [] };
    const [openId, setOpenId] = useState("");
    const [draft, setDraft] = useState({ name: "", kind: "launch", goal: "", goal_posts: "", start: "", end: "", note: "", template: false });
    const open = (board.campaigns || []).find(function (item) { return item.id === openId; }) || null;
    function setField(field, value) {
      setDraft(function (current) { return Object.assign({}, current, { [field]: value }); });
    }
    function save(event) {
      event.preventDefault();
      props.onSave({
        name: draft.name,
        kind: draft.kind,
        goal: draft.goal,
        goal_posts: draft.goal_posts ? Number(draft.goal_posts) : "",
        start: draft.start,
        end: draft.end,
        note: draft.note,
        template: draft.template,
      });
      setDraft({ name: "", kind: draft.kind, goal: "", goal_posts: "", start: "", end: "", note: "", template: false });
    }
    return h("div", { className: "hs-main" },
      (board.lessons || []).map(function (item) {
        return h("p", { key: item.kind || item.detail, className: item.ahead ? "hs-ok" : "hs-note" }, item.detail + (item.approach ? " " + item.approach : ""));
      }),
      h("form", { className: "hs-cols", onSubmit: save },
        h("input", { className: "hs-field", value: draft.name, placeholder: "Campaign name", onChange: function (event) { setField("name", event.target.value); } }),
        h("select", { className: "hs-field", value: draft.kind, onChange: function (event) { setField("kind", event.target.value); } },
          (board.kinds || []).map(function (kind) { return h("option", { key: kind, value: kind }, kind); })),
        h("input", { className: "hs-field", value: draft.goal, placeholder: "Goal, in words", onChange: function (event) { setField("goal", event.target.value); } }),
        h("input", { className: "hs-field", value: draft.goal_posts, placeholder: "How many posts", onChange: function (event) { setField("goal_posts", event.target.value); } }),
        h("input", { className: "hs-field", type: "date", value: draft.start, onChange: function (event) { setField("start", event.target.value); } }),
        h("input", { className: "hs-field", type: "date", value: draft.end, onChange: function (event) { setField("end", event.target.value); } }),
        h("input", { className: "hs-field", value: draft.note, placeholder: "Note", onChange: function (event) { setField("note", event.target.value); } }),
        h("label", { className: "hs-note" },
          h("input", { type: "checkbox", checked: draft.template, onChange: function (event) { setField("template", event.target.checked); } }),
          " Keep as a template"),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !draft.name.trim() }, "Save campaign")),
      (board.campaigns || []).length ? board.campaigns.map(function (item) {
        const progress = item.progress || {};
        const performance = item.performance || {};
        const retro = item.retrospective || {};
        return h("div", { key: item.id, className: "hs-pillar" },
          h("button", { type: "button", className: "hs-post", onClick: function () { setOpenId(item.id === openId ? "" : item.id); } },
            h("div", { className: "hs-name" }, item.name + " · " + item.kind + (item.template ? " · template" : "")),
            h("div", { className: "hs-meta" }, progress.phase + " · " + progress.posts + (progress.goal_posts ? " of " + progress.goal_posts : "") + " posts · " + progress.assets + " assets")),
          open && open.id === item.id ? h("div", null,
            item.goal ? h("p", { className: "hs-voice" }, item.goal) : null,
            h("p", { className: "hs-note" }, [item.start, item.end].filter(Boolean).join(" – ") || "No dates"),
            h("p", { className: "hs-note" }, progress.making + " still being made · " + progress.out + " in the queue"),
            h("p", { className: "hs-note" }, performance.detail),
            performance.posts ? h("p", { className: "hs-note" }, performance.engagements + " engagements · " + performance.shares + " shares" + (performance.saves == null ? "" : " · " + performance.saves + " saves")) : null,
            h("p", { className: "hs-note" }, retro.detail || ""),
            (item.pieces || []).map(function (piece) {
              return h("button", { key: piece.id, type: "button", className: "hs-post", onClick: function () { props.onOpen(piece.id); } }, piece.status + " · " + piece.idea);
            }),
            (item.assets || []).map(function (asset) {
              return h("div", { key: asset.id, className: "hs-note" }, asset.kind + " · " + asset.name);
            }),
            h("div", { className: "hs-row" },
              h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onClone(item.id); } }, "Clone"),
              retro.ready && retro.ahead ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onKeep(item.id); } }, "Keep the lesson") : null,
              h("select", {
                className: "hs-field",
                value: "",
                onChange: function (event) {
                  if (event.target.value) props.onAttach(item.id, { piece_ids: [event.target.value] });
                  event.target.value = "";
                },
              }, h("option", { value: "" }, "Add a piece"),
                (props.pieces || []).filter(function (piece) {
                  return !(item.pieces || []).some(function (row) { return row.id === piece.id; });
                }).map(function (piece) { return h("option", { key: piece.id, value: piece.id }, piece.idea.slice(0, 60)); })),
              h("select", {
                className: "hs-field",
                value: "",
                onChange: function (event) {
                  if (event.target.value) props.onAttach(item.id, { asset_ids: [event.target.value] });
                  event.target.value = "";
                },
              }, h("option", { value: "" }, "Add an asset"),
                ((props.library && props.library.assets) || []).filter(function (asset) {
                  return !(item.assets || []).some(function (row) { return row.id === asset.id; });
                }).map(function (asset) { return h("option", { key: asset.id, value: asset.id }, asset.kind + " · " + asset.name); })))) : null);
      }) : h("p", { className: "hs-note" }, "No campaigns yet."),
    );
  }

  function QueueDesk(props) {
    const queue = (props.studio && props.studio.queue) || { items: [], suggestion: {}, rules: [], formats: [], stages: [], pace: "" };
    const [mode, setMode] = useState("list");
    const [stage, setStage] = useState("all");
    const [picked, setPicked] = useState([]);
    const suggestion = queue.suggestion || {};
    const stages = queue.stages || [];
    const all = queue.items || [];
    const items = all.filter(function (item) { return stage === "all" || item.stage === stage; });
    const live = picked.filter(function (id) { return all.some(function (item) { return item.id === id; }); });
    const every = items.length > 0 && items.every(function (item) { return live.indexOf(item.id) >= 0; });
    function toggle(id) {
      setPicked(function (current) {
        return current.indexOf(id) >= 0 ? current.filter(function (item) { return item !== id; }) : current.concat([id]);
      });
    }
    function bulk(action) {
      props.onBulk(action, live);
      setPicked([]);
    }
    function row(item) {
      const record = item.record || {};
      const weak = item.slot && item.slot.indexOf("underperformed") >= 0;
      const tone = item.status === "pending" ? "pending" : item.status === "scheduled" ? "scheduled" : item.status === "failed" ? "failed" : item.status === "ready" ? "ready" : "draft";
      const on = live.indexOf(item.id) >= 0;
      return h("li", { key: item.id, className: "hs-q hs-q-" + tone + (on ? " is-picked" : "") },
        h("input", { type: "checkbox", checked: on, "aria-label": "Select " + item.idea, onChange: function () { toggle(item.id); } }),
        h("div", { className: "hs-q-body" },
          h("button", { type: "button", className: "hs-q-open", onClick: function () { props.onOpen(item.id); } },
            h("span", { className: "hs-row hs-gap-sm" },
              h("span", { className: "hs-status is-" + (item.status || "draft") }, item.label || item.status),
              item.format ? h("span", { className: "hs-meta" }, item.format) : null,
              item.date ? h("span", { className: "hs-meta" }, dayLabel(item.date, { weekday: "short", month: "short", day: "numeric" }) + (item.time ? " · " + item.time : "")) : null),
            h("span", { className: "hs-q-title" }, item.idea)),
          item.failure ? h("p", { className: "hs-bad" }, item.failure) : null,
          item.slot ? h("p", { className: weak ? "hs-warn" : "hs-note" }, item.slot) : null,
          record.linked ? h("p", { className: "hs-note" }, record.detail, record.permalink ? [" · ", h("a", { key: "a", href: record.permalink, target: "_blank", rel: "noopener noreferrer" }, "Open the post")] : null) : null,
          (item.problems || []).length && item.status !== "failed" ? h("p", { className: "hs-note" }, item.problems[0]) : null));
    }
    const dated = items.filter(function (item) { return item.date; }).reduce(function (map, item) {
      map[item.date] = (map[item.date] || []).concat([item]);
      return map;
    }, {});
    const undated = items.filter(function (item) { return !item.date; }).length;
    const groups = stages.map(function (entry) {
      return { id: entry.id, label: entry.label, rows: items.filter(function (item) { return item.stage === entry.id; }) };
    });
    const empty = groups.filter(function (group) { return !group.rows.length; });
    const formatLine = (queue.formats || []).length
      ? (queue.formats || []).map(function (entry) { return entry.format + " is ahead at " + entry.label + "."; }).join(" ")
      : "No format has a clear hour yet.";
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-advice" },
        suggestion.clear
          ? h("p", { className: "hs-voice" }, h("strong", null, suggestion.label + " is ahead across the posts. "), suggestion.detail, " A format hour wins when that format is clearly ahead.")
          : h("p", { className: "hs-note" }, suggestion.detail || "Not enough hours to suggest a time."),
        h("p", { className: "hs-note" }, formatLine),
        queue.pace ? h("p", { className: "hs-note" }, queue.pace) : null),
      h("div", { className: "hs-cal-toolbar" },
        h("div", { className: "hs-row hs-gap-sm" },
          h(Segmented, { label: "Show", value: mode, options: [["list", "By stage"], ["timeline", "By day"]], onChange: setMode }),
          h("select", { className: "hs-field hs-w-lg", "aria-label": "Stage", value: stage, onChange: function (event) { setStage(event.target.value); } },
            h("option", { value: "all" }, "Every stage · " + all.length),
            stages.map(function (entry) {
              const n = all.filter(function (item) { return item.stage === entry.id; }).length;
              return h("option", { key: entry.id, value: entry.id }, entry.label + " · " + n);
            }))),
        items.length ? h("label", { className: "hs-note" },
          h("input", {
            type: "checkbox", checked: every,
            onChange: function () {
              setPicked(every ? [] : items.map(function (item) { return item.id; }));
            },
          }),
          h("span", null, "Select all " + items.length)) : null),
      live.length ? h("div", { className: "hs-bulk", role: "region", "aria-label": "Selected pieces" },
        h("span", { className: "hs-name" }, live.length + " selected"),
        h("div", { className: "hs-row hs-gap-sm" },
          h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { bulk("pending"); } }, "Send for approval"),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { bulk("schedule"); } }, suggestion.clear ? "Schedule at the clear hour" : "Schedule"),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { bulk("retry"); } }, "Retry failed"),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { bulk("draft"); } }, "Back to draft"),
          h("button", { type: "button", className: "hs-link-button", onClick: function () { setPicked([]); } }, "Clear selection"))) : null,
      !all.length ? h(Empty, null, "Nothing in the queue yet. Create a draft in the Composer or hold a day on the Calendar.")
        : mode === "timeline" ? h("div", { className: "hs-stack" },
          Object.keys(dated).sort().map(function (day) {
            return h("div", { key: day, className: "hs-stack hs-gap-xs" },
              h("div", { className: "hs-overline" }, dayLabel(day, { weekday: "long", month: "long", day: "numeric", year: "numeric" })),
              h("ul", { className: "hs-qlist" }, dated[day].map(row)));
          }),
          !Object.keys(dated).length ? h("p", { className: "hs-note" }, "No piece in this view has a day.") : null,
          undated ? h("p", { className: "hs-hint" }, undated + (undated === 1 ? " piece has" : " pieces have") + " no day. They show when grouped by stage.") : null)
          : h("div", { className: "hs-stack" },
            groups.filter(function (group) { return group.rows.length; }).map(function (group) {
              return h("div", { key: group.id, className: "hs-stack hs-gap-xs" },
                h("div", { className: "hs-overline" }, group.label + " · " + group.rows.length),
                h("ul", { className: "hs-qlist" }, group.rows.map(row)));
            }),
            !items.length ? h("p", { className: "hs-note" }, "Nothing at this stage.") : null,
            stage === "all" && empty.length ? h("p", { className: "hs-hint" }, "Empty: " + empty.map(function (group) { return group.label; }).join(", ") + ".") : null),
      (queue.rules || []).length ? h(Section, { title: "Queue rules", note: "What a piece must pass before it moves.", collapsible: true },
        h("ul", { className: "hs-guard" }, (queue.rules || []).map(function (rule) { return h("li", { key: rule }, rule); }))) : null,
      h(StudioRead, { read: props.studio && props.studio.studio_read, busy: props.busy, onPull: props.onPull }),
    );
  }

  function MemoryDesk(props) {
    const desk = (props.studio && props.studio.memory) || { sections: [], timeline: [] };
    const [exported, setExported] = useState("");
    useEffect(function () { props.onSync(); }, []);
    useEffect(function () {
      if (!props.focus) return;
      const node = document.getElementById("hs-memory-" + props.focus);
      if (node && node.scrollIntoView) node.scrollIntoView({ block: "center" });
    }, [props.focus, desk.sections]);
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onCorrect("reset", ""); } }, "Reset learned patterns"),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: async function () { const found = await props.onExport("markdown"); if (found) setExported(found.body || ""); } }, "Export markdown"),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: async function () { const found = await props.onExport("json"); if (found) setExported(found.body || ""); } }, "Export JSON")),
      exported ? h("textarea", { className: "hs-area", readOnly: true, value: exported }) : null,
      (desk.sections || []).map(function (section) {
        return h("div", { key: section.id },
          h("div", { className: "hs-name" }, section.label),
          (section.lines || []).map(function (line) {
            return h("div", { key: line.id, id: "hs-memory-" + line.id, className: "hs-pillar" },
              h("div", { className: "hs-name" }, line.title + " · " + line.standing + (line.thin ? " · thin" : "")),
              h("p", { className: line.standing === "deleted" ? "hs-bad" : "hs-note" }, line.detail),
              h("div", { className: "hs-row" },
                line.standing !== "pinned" ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onCorrect("pin", line.id); } }, "Pin") : null,
                line.standing !== "demoted" ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onCorrect("demote", line.id); } }, "Lower") : null,
                line.standing !== "deleted" ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onCorrect("delete", line.id); } }, "Delete") : null,
                line.standing !== "open" ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onCorrect("restore", line.id); } }, "Restore") : null));
          }));
      }),
      (desk.accuracy || []).length ? h("div", null,
        h("div", { className: "hs-name" }, "How the range held up"),
        desk.accuracy.map(function (item) { return h("p", { key: item.id, className: "hs-note" }, item.detail); })) : null,
      h("div", { className: "hs-name" }, "Feedback"),
      ((desk.feedback && desk.feedback.lines) || ["No feedback yet."]).map(function (line, index) { return h("p", { key: "fb" + index, className: "hs-note" }, line); }),
      ((desk.feedback && desk.feedback.entries) || []).map(function (entry) {
        return h("div", { key: entry.id, className: "hs-pillar" },
          h("p", { className: "hs-note" }, entry.kind + " · " + entry.target + " · " + entry.verdict + (entry.note ? " · " + entry.note : "")),
          h("div", { className: "hs-row" },
            h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onFeedback({ action: "delete", id: entry.id }); } }, "Delete"),
            ["used", "better", "worse", "off-brand", "irrelevant"].map(function (verdict) {
              return h("button", { key: verdict, type: "button", className: "hs-tab", disabled: props.busy || verdict === entry.verdict, onClick: function () { props.onFeedback({ action: "correct", id: entry.id, verdict: verdict, note: entry.note }); } }, verdict);
            })));
      }),
      h("div", { className: "hs-name" }, "Changes"),
      (desk.timeline || []).length ? (desk.timeline || []).map(function (item) {
        return h("p", { key: item.id, className: "hs-note" }, (item.kind || "") + (item.pattern_id ? " · " + item.pattern_id : "") + (item.after ? " · " + item.after : ""));
      }) : h("p", { className: "hs-note" }, "No changes yet."));
  }

  function IngestDesk(props) {
    const desk = (props.studio && props.studio.ingest) || { fields: [], mapping: {}, log: [], insights: [] };
    const [text, setText] = useState("");
    const [xlsx, setXlsx] = useState("");
    const [filename, setFilename] = useState("paste");
    const [preview, setPreview] = useState(null);
    const [mapping, setMapping] = useState({});
    const [result, setResult] = useState(null);
    const fields = ["", "caption", "published_at", "platform", "likes", "comments", "shares", "saves", "impressions", "reach", "video_views", "permalink", "format", "pillar"];
    async function previewFile() {
      const found = await props.onPreview({ text: xlsx ? "" : text, xlsx: xlsx, filename: filename });
      if (!found) return;
      setPreview(found);
      setMapping(found.suggested || {});
      setResult(null);
    }
    async function commitFile(event) {
      event.preventDefault();
      const saved = await props.onCommit({ text: xlsx ? "" : text, xlsx: xlsx, filename: filename, mapping: mapping });
      if (saved) setResult(saved);
    }
    return h("div", { className: "hs-main" },
      h("textarea", { className: "hs-area", value: text, placeholder: "Paste CSV, tab-separated rows, or JSON", onChange: function (event) { setText(event.target.value); setXlsx(""); } }),
      h("input", {
        className: "hs-field", type: "file", accept: ".csv,.json,.xlsx,text/csv,application/json",
        onChange: function (event) {
          const file = event.target.files && event.target.files[0];
          if (!file) return;
          setFilename(file.name);
          const reader = new FileReader();
          if (/\.xlsx$/i.test(file.name)) {
            reader.onload = function () {
              const value = String(reader.result || "");
              setXlsx(value.slice(value.indexOf(",") + 1));
              setText("");
            };
            reader.readAsDataURL(file);
          } else {
            reader.onload = function () { setText(String(reader.result || "")); setXlsx(""); };
            reader.readAsText(file);
          }
        },
      }),
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-button", disabled: props.busy || (!text.trim() && !xlsx), onClick: previewFile }, "Preview columns")),
      preview ? h("form", { className: "hs-cols", onSubmit: commitFile },
        h("p", { className: "hs-note" }, preview.rows + " rows. Map a column to the caption."),
        (preview.columns || []).map(function (column) {
          return h("label", { key: column, className: "hs-note" }, column,
            h("select", {
              className: "hs-field",
              value: mapping[column] || "",
              onChange: function (event) {
                const value = event.target.value;
                setMapping(function (current) { return Object.assign({}, current, { [column]: value }); });
              },
            }, fields.map(function (field) { return h("option", { key: field || "ignore", value: field }, field || "Ignore"); })));
        }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Import these rows")) : null,
      result ? h("div", null,
        h("p", { className: "hs-note" }, result.accepted + " added. " + result.skipped + " already here. " + result.incomplete + " missing a date or a count."),
        (result.insights || []).map(function (line, index) { return h("p", { key: index, className: "hs-voice" }, line); })) : null,
      (desk.insights || []).length && !result ? (desk.insights || []).map(function (line, index) { return h("p", { key: "old" + index, className: "hs-note" }, line); }) : null,
      h("div", { className: "hs-name" }, "Imports"),
      (desk.log || []).length ? (desk.log || []).map(function (item) {
        return h("p", { key: item.id, className: "hs-note" }, item.filename + " · " + item.accepted + " added · " + item.skipped + " skipped · " + item.incomplete + " incomplete");
      }) : h("p", { className: "hs-note" }, "No import yet."));
  }


  function MapLines(props) {
    const series = props.series || [];
    const colors = { facebook: "#c4a574", instagram: "#7d9a92", threads: "#d4c4a8" };
    if (!series.length) return h("p", { className: "hs-note" }, "No numbers in this window.");
    const points = series.reduce(function (all, row) { return all.concat(row.points || []); }, []);
    const max = Math.max.apply(null, points.map(function (point) { return point.value || 0; }).concat([1]));
    const width = 640;
    const height = 160;
    return h("svg", { className: "hs-chart", viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": "Daily engagements" },
      series.map(function (row) {
        const step = width / Math.max(1, (row.points || []).length - 1);
        const d = (row.points || []).map(function (point, index) {
          const x = (row.points.length === 1 ? width / 2 : index * step);
          const y = height - 16 - ((point.value || 0) / max) * (height - 28);
          return (index ? "L" : "M") + x + " " + y;
        }).join(" ");
        return h("path", { key: row.platform, d: d, fill: "none", stroke: colors[row.platform] || "#8aa4b5", strokeWidth: 2 });
      }));
  }

  function MapDesk(props) {
    const map = (props.studio && props.studio.map) || { windows: {}, posts: [], hourly: false, demographics: false };
    const [size, setSize] = useState("28");
    const [view, setView] = useState("overview");
    const [postId, setPostId] = useState("");
    const window = (map.windows && map.windows[size]) || { cards: {}, series: [], formats: [], heatmap: [], top: [], change: [], followers: [], rates: [] };
    const post = (map.posts || []).find(function (item) { return item.id === postId; }) || (map.posts || [])[0];
    const cards = window.cards || {};
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-row" },
        ["7", "28", "90"].map(function (item) { return h("button", { key: item, type: "button", className: "hs-tab" + (size === item ? " is-on" : ""), onClick: function () { setSize(item); } }, item + " days"); }),
        ["overview", "post", "formats", "audience"].map(function (item) { return h("button", { key: item, type: "button", className: "hs-tab" + (view === item ? " is-on" : ""), onClick: function () { setView(item); } }, item); })),
      view === "overview" ? h("div", null,
        h(MapLines, { series: window.series }),
        ["facebook", "instagram", "threads"].map(function (name) {
          const card = cards[name] || { detail: "No numbers in this window.", rows: [] };
          return h("div", { key: name, className: "hs-pillar" },
            h("div", { className: "hs-name" }, name),
            card.detail ? h("p", { className: "hs-note" }, card.detail) : null,
            (card.rows || []).map(function (row) { return h("p", { key: row.label, className: "hs-note" }, row.label + ": " + (row.value == null ? "—" : row.value)); }));
        }),
        (window.change || []).map(function (item) { return h("p", { key: item.platform, className: "hs-note" }, item.platform + " · " + item.detail); }),
        (window.followers || []).map(function (item) { return h("p", { key: item.platform, className: "hs-note" }, item.detail); })) : null,
      view === "post" ? h("div", null,
        map.hourly ? null : h("p", { className: "hs-note" }, "Hourly counts are not in the pull."),
        h("select", { className: "hs-field", value: post ? post.id : "", onChange: function (event) { setPostId(event.target.value); } },
          (map.posts || []).map(function (item) { return h("option", { key: item.id, value: item.id }, (item.platform || "") + " · " + (item.preview || item.id)); })),
        post ? h("div", { className: "hs-pillar" },
          h("p", { className: "hs-voice" }, post.preview || "No caption in the pull."),
          h("p", { className: "hs-note" }, [post.platform, post.format, post.at].filter(Boolean).join(" · ")),
          h("p", { className: "hs-note" }, "Engagements: " + (post.engagements == null ? "—" : post.engagements) + ". Reach: " + (post.impressions == null ? "—" : post.impressions)),
          (post.parts || []).map(function (part) { return h("p", { key: part.label, className: "hs-note" }, part.label + ": " + part.value); })) : h("p", { className: "hs-note" }, "No post in the pull.")) : null,
      view === "formats" ? h("div", null,
        (window.formats || []).length ? (window.formats || []).map(function (item) { return h("p", { key: item.format, className: "hs-note" }, item.format + " · " + item.detail); }) : h("p", { className: "hs-note" }, "No format in this window."),
        (window.heatmap || []).slice(0, 24).map(function (cell) { return h("p", { key: cell.weekday + cell.hour, className: "hs-note" }, cell.weekday + " " + cell.hour + " · " + cell.mean + " (n=" + cell.n + ")"); }),
        (window.top || []).map(function (item) { return h("p", { key: item.id, className: "hs-note" }, item.platform + " · " + item.format + " · " + (item.engagements == null ? "—" : item.engagements) + (item.rate == null ? "" : " · " + item.rate + " percent") + " · " + item.preview); })) : null,
      view === "audience" ? h("div", null,
        map.demographics ? null : h("p", { className: "hs-note" }, "No city or age breakdown was returned."),
        (window.followers || []).length ? (window.followers || []).map(function (item) { return h("p", { key: item.platform, className: "hs-note" }, item.detail); }) : h("p", { className: "hs-note" }, "No follower numbers in this window."),
        (window.rates || []).length ? (window.rates || []).map(function (item) { return h("p", { key: item.label, className: "hs-note" }, item.detail); }) : h("p", { className: "hs-note" }, "No rate. Reach was not in the pull.")) : null);
  }

  function Performance(props) {
    const perf = (props.studio && props.studio.performance) || { page_days: [], recorded_days: [], hours: [], posts: [], source: "none", ranges: {} };
    const [range, setRange] = useState("7");
    const [campaign, setCampaign] = useState("");
    const report = (perf.ranges && perf.ranges[range]) || { totals: {}, comparison: { lines: [] }, campaigns: [], formats: [], top: [], bottom: [], patterns: [], alerts: [] };
    const [goal, setGoal] = useState({ metric: "engagements", change: "20", start: "", end: "" });
    const totals = report.totals || {};
    const chosen = (report.campaigns || []).find(function (item) { return item.name === campaign; }) || (report.campaigns || [])[0] || null;
    const pageDays = perf.page_days || [];
    const recordedDays = perf.recorded_days || [];
    const usePage = pageDays.length > 0;
    const days = (usePage ? pageDays : recordedDays).map(function (day) {
      return { id: day.id, label: day.label, value: usePage ? day.impressions : day.engagements, raw: day };
    });
    const engagements = usePage ? pageDays.map(function (day) {
      return { id: day.id, label: day.label, value: day.engagements, raw: day };
    }) : [];
    const hours = (perf.hours || []).map(function (hour) {
      return { id: hour.id, label: hour.label + " · n=" + hour.n, value: hour.mean, raw: hour };
    });
    const posts = perf.posts || [];
    const picked = pageDays.concat(recordedDays).find(function (day) { return day.id === props.pickedDay; });
    const post = posts.find(function (item) { return item.id === props.pickedPost; });
    const hourPosts = posts.filter(function (item) { return String(item.local_hour) === props.pickedHour; });
    const formatPoints = (report.formats || []).map(function (item) {
      return { id: item.id, label: item.label + " · n=" + item.n, value: item.mean, raw: item };
    });
    function tile(label, value, note) {
      return h("div", { key: label, className: "hs-pillar" },
        h("div", { className: "hs-note" }, label),
        h("div", { className: "hs-name" }, value == null ? "Not in the pull" : String(value)),
        note ? h("div", { className: "hs-note" }, note) : null);
    }
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-row" },
        [["7", "7 days"], ["28", "28 days"], ["90", "90 days"], ["all", "All"]].map(function (pair) {
          return h("button", {
            key: pair[0], type: "button",
            className: "hs-tab" + (range === pair[0] ? " is-on" : ""),
            onClick: function () { setRange(pair[0]); },
          }, pair[1]);
        })),
      h("div", { className: "hs-previews" },
        tile("Reach", totals.reach, totals.reach_note),
        tile("Impressions", totals.impressions, totals.impressions_note),
        tile("Engagements", totals.engagements, totals.posts + " posts"),
        tile("Rate", totals.rate, totals.rate_note),
        tile("Saves", totals.saves, totals.saves_note),
        tile("Shares", totals.shares, ""),
        tile("Comments", totals.comments, totals.comments_note),
        tile("Clicks", totals.clicks, totals.clicks_note),
        tile("Video completion", totals.video_completion, totals.video_note),
        tile("Follower change", totals.growth, totals.growth_note)),
      h("div", { className: "hs-name" }, "Patterns"),
      (report.patterns || []).map(function (item) {
        return h("p", { key: item.id, className: item.clear ? "hs-ok" : "hs-note" }, item.title + ". " + item.detail);
      }),
      h("div", { className: "hs-name" }, "Outliers"),
      (report.alerts || []).length ? report.alerts.map(function (item) {
        return h("p", { key: item.id, className: "hs-note" }, item.detail);
      }) : h("p", { className: "hs-note" }, "No post in this window is at least 3× the other posts."),
      h("div", { className: "hs-name" }, (report.comparison && report.comparison.label) || "Comparison"),
      ((report.comparison && report.comparison.lines) || []).map(function (line) {
        return h("p", { key: line, className: "hs-note" }, line);
      }),
      h("div", { className: "hs-name" }, "Campaign against the other posts"),
      (report.campaigns || []).some(function (item) { return item.name; }) ? h("select", {
        className: "hs-field",
        value: chosen ? chosen.name : "",
        onChange: function (event) { setCampaign(event.target.value); },
      }, (report.campaigns || []).filter(function (item) { return item.name; }).map(function (item) {
        return h("option", { key: item.name, value: item.name }, item.name);
      })) : null,
      chosen ? h("p", { className: "hs-note" }, chosen.detail) : null,
      h(BarChart, { label: "Mean engagements by format", points: formatPoints, empty: "No format in this window." }),
      h("div", { className: "hs-name" }, "Top posts"),
      (report.top || []).length ? report.top.map(function (item) {
        return h("div", { key: item.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, item.engagements + " engagements"),
          h("div", { className: "hs-note" }, [item.platform, item.format, item.shares + " shares", item.saves == null ? "" : item.saves + " saves", item.preview].filter(Boolean).join(" · ")),
          (item.reasons || []).map(function (reason) { return h("p", { key: reason, className: "hs-note" }, reason); }),
          item.permalink ? h("a", { href: item.permalink, target: "_blank", rel: "noopener noreferrer" }, "Open the post") : null);
      }) : h("p", { className: "hs-note" }, "No posts in this window."),
      h("div", { className: "hs-name" }, "Quiet posts"),
      (report.bottom || []).length ? report.bottom.map(function (item) {
        return h("div", { key: "low-" + item.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, item.engagements + " engagements"),
          h("div", { className: "hs-note" }, item.preview || "Untitled"),
          (item.reasons || []).map(function (reason) { return h("p", { key: reason, className: "hs-note" }, reason); }));
      }) : null,
      h("p", { className: "hs-note" }, usePage
        ? "Page totals from the Facebook ledger. A bar is a day. Click it. These are not estimated."
        : "No page ledger for this brand. Record a result and the bars are the posts you logged."),
      h(BarChart, { label: usePage ? "Organic impressions" : "Recorded engagements", points: days, selected: props.pickedDay, onPick: props.onDay, empty: "No days yet." }),
      engagements.length ? h(BarChart, { label: "Page engagements", points: engagements, selected: props.pickedDay, onPick: props.onDay }) : null,
      picked ? h("p", { className: "hs-note" }, picked.date + (picked.impressions != null ? " · impressions " + picked.impressions : "") + " · engagements " + (picked.engagements || 0) + (picked.follows != null ? " · follows " + picked.follows : "")) : null,
      h(BarChart, { label: "Mean engagements by local hour", points: hours, selected: props.pickedHour, onPick: props.onHour, empty: "No hours yet." }),
      hourPosts.length ? h("div", null, hourPosts.map(function (item) {
        return h("div", { key: item.id, className: "hs-note" }, item.preview || item.id);
      })) : null,
      h("div", { className: "hs-name" }, "Posts"),
      posts.length ? posts.map(function (item) {
        return h("button", {
          key: item.id, type: "button",
          className: "hs-post" + (props.pickedPost === item.id ? " is-on" : ""),
          onClick: function () { props.onPost(item); },
        }, item.engagements + " · " + (item.preview || "Untitled"));
      }) : h("p", { className: "hs-note" }, "No posts in this window."),
      post ? h("div", { className: "hs-pillar" },
        h("div", null, (post.reactions || 0) + " reactions · " + (post.comments || 0) + " comments · " + (post.shares || 0) + " shares"),
        post.permalink ? h("a", { href: post.permalink, target: "_blank", rel: "noopener noreferrer" }, "Open the post") : null,
      ) : null,
      h("div", { className: "hs-name" }, "Goals"),
      h("p", { className: "hs-note" }, (perf.imported || 0) + " imported posts with a date and an engagement count are in these numbers. A row without either stays stored and out of the window."),
      (perf.goals || []).length ? perf.goals.map(function (item) {
        return h("p", { key: item.id, className: "hs-note" }, item.detail);
      }) : h("p", { className: "hs-note" }, "No goal yet."),
      h("form", { className: "hs-row", onSubmit: function (event) {
        event.preventDefault();
        props.onGoal({ metric: goal.metric, change: Number(goal.change), start: goal.start, end: goal.end });
      } },
        h("select", { className: "hs-field", value: goal.metric, onChange: function (event) { setGoal(Object.assign({}, goal, { metric: event.target.value })); } },
          ["engagements", "shares", "saves", "reach", "follows"].map(function (metric) { return h("option", { key: metric, value: metric }, metric); })),
        h("input", { className: "hs-field", value: goal.change, placeholder: "Percent, such as 20", onChange: function (event) { setGoal(Object.assign({}, goal, { change: event.target.value })); } }),
        h("input", { className: "hs-field", type: "date", value: goal.start, onChange: function (event) { setGoal(Object.assign({}, goal, { start: event.target.value })); } }),
        h("input", { className: "hs-field", type: "date", value: goal.end, onChange: function (event) { setGoal(Object.assign({}, goal, { end: event.target.value })); } }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !goal.start || !goal.end }, "Save goal")),
      h("label", { className: "hs-note" }, "Past posts CSV",
        h("input", {
          className: "hs-field", type: "file", accept: ".csv,text/csv",
          onChange: function (event) {
            const file = event.target.files && event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function () { props.onHistory(String(reader.result || "")); };
            reader.readAsText(file);
          },
        })),
      h(RecordForm, { busy: props.busy, onRecorded: props.onRecorded }),
    );
  }

  function RecordForm(props) {
    const [form, setForm] = useState({ platform: "facebook", format: "unknown", published_at: "", local_hour: "", impressions: "", engagements: "", likes: "", comments: "", shares: "", saves: "", follows: "", clicks: "", video_completion: "", note: "" });
    function setField(field, value) { setForm(function (current) { return Object.assign({}, current, { [field]: value }); }); }
    async function submit(event) {
      event.preventDefault();
      const metrics = {};
      ["impressions", "engagements", "likes", "comments", "shares", "saves", "follows", "clicks", "video_completion"].forEach(function (key) {
        if (form[key] !== "") metrics[key] = Number(form[key]);
      });
      const body = { platform: form.platform, format: form.format, metrics: metrics, note: form.note, preview: form.note };
      if (form.published_at) body.published_at = new Date(form.published_at).toISOString();
      if (form.local_hour !== "") body.local_hour = Number(form.local_hour);
      await props.onRecorded(body);
    }
    return h("form", { className: "hs-main", onSubmit: submit },
      h("div", { className: "hs-name" }, "Record a result"),
      h("div", { className: "hs-cols" },
        h("select", { className: "hs-field", value: form.platform, onChange: function (event) { setField("platform", event.target.value); } },
          PLATFORMS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); })),
        h("select", { className: "hs-field", value: form.format, onChange: function (event) { setField("format", event.target.value); } },
          ["unknown"].concat(FORMATS).map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("input", { className: "hs-field", type: "datetime-local", value: form.published_at, onChange: function (event) { setField("published_at", event.target.value); } }),
        h("input", { className: "hs-field", placeholder: "local hour 0-23", value: form.local_hour, onChange: function (event) { setField("local_hour", event.target.value); } }),
        ["impressions", "engagements", "likes", "comments", "shares", "saves", "follows", "clicks", "video_completion"].map(function (key) {
          return h("input", { key: key, className: "hs-field", placeholder: key, value: form[key], onChange: function (event) { setField(key, event.target.value); } });
        })),
      h("input", { className: "hs-field", placeholder: "What the post was", value: form.note, onChange: function (event) { setField("note", event.target.value); } }),
      h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Save result"),
    );
  }

  function HashtagDesk(props) {
    const desk = (props.studio && props.studio.hashtags) || { sets: [], tags: [], formats: { rows: [], detail: "" }, trends: [], feed: [], outside: [], kinds: ["topic", "sound", "format"], suggestion: { tags: [], detail: "" }, pillars: [], campaigns: [] };
    const [setName, setSetName] = useState("");
    const [setTags, setSetTags] = useState("");
    const [pillar, setPillar] = useState("");
    const [campaign, setCampaign] = useState("");
    const [trend, setTrend] = useState({ kind: "topic", name: "", note: "" });
    const formats = desk.formats || { rows: [], detail: "" };
    const suggestion = desk.suggestion || { tags: [], detail: "" };
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-note" }, suggestion.detail || "No hashtag is clearly ahead for this brand."),
      suggestion.tags && suggestion.tags.length ? h("div", null,
        h("p", { className: "hs-ok" }, suggestion.tags.map(function (tag) { return "#" + tag; }).join(" ")),
        suggestion.tags.map(function (tag) { return h(FeedbackButtons, { key: tag, kind: "hashtags", target: tag, busy: props.busy, onFeedback: props.onFeedback }); })) : null,
      props.piece ? h("button", {
        type: "button", className: "hs-tab", disabled: props.busy || !(suggestion.tags || []).length,
        onClick: function () { props.onUse(props.piece.id, props.piece.pillar || ""); },
      }, "Use these on the open draft") : h("p", { className: "hs-note" }, "Open a draft to use the tags that are ahead."),
      h("form", { className: "hs-row", onSubmit: function (event) {
        event.preventDefault();
        props.onSaveSet({ name: setName, tags: setTags.split(/[,\s]+/).filter(Boolean), pillar: pillar, campaign: campaign });
        setSetName("");
        setSetTags("");
      } },
        h("input", { className: "hs-field", value: setName, placeholder: "Set name", onChange: function (event) { setSetName(event.target.value); } }),
        h("input", { className: "hs-field", value: setTags, placeholder: "Tags, up to five", onChange: function (event) { setSetTags(event.target.value); } }),
        h("select", { className: "hs-field", value: pillar, onChange: function (event) { setPillar(event.target.value); } },
          h("option", { value: "" }, "No pillar"),
          (desk.pillars || []).map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); })),
        h("select", { className: "hs-field", value: campaign, onChange: function (event) { setCampaign(event.target.value); } },
          h("option", { value: "" }, "No campaign"),
          (desk.campaigns || []).map(function (name) { return h("option", { key: name, value: name }, name); })),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !setName.trim() || !setTags.trim() }, "Save set")),
      (desk.sets || []).length ? desk.sets.map(function (item) {
        const performance = item.performance || {};
        const where = [item.pillar, item.campaign].filter(Boolean).join(" · ");
        return h("div", { key: item.id, className: "hs-pillar" },
          h("div", { className: "hs-row" },
            h("span", { className: "hs-name" }, item.name + (where ? " · " + where : "")),
            h("span", { className: "hs-note" }, item.tags.map(function (tag) { return "#" + tag; }).join(" ")),
            h("button", {
              type: "button", className: "hs-tab", disabled: props.busy || !props.piece,
              onClick: function () { props.onApply(item.id); },
            }, props.piece ? "Use on the open draft" : "Open a draft to use this")),
          performance.detail ? h("p", { className: performance.ahead ? "hs-ok" : "hs-note" }, performance.detail) : null);
      }) : h("p", { className: "hs-note" }, "No saved sets yet."),
      h("div", { className: "hs-name" }, "Tags these posts used"),
      (desk.tags || []).length ? desk.tags.map(function (item) {
        return h("p", { key: item.tag, className: item.ahead ? "hs-ok" : "hs-note" }, item.detail);
      }) : h("p", { className: "hs-note" }, "No hashtags on the posts in this window."),
      h("div", { className: "hs-name" }, "Formats"),
      h("p", { className: "hs-note" }, formats.detail),
      (formats.rows || []).map(function (item) {
        return h("p", { key: item.id, className: "hs-note" }, item.label + " · " + item.mean + " · n=" + item.n);
      }),
      h("div", { className: "hs-name" }, "Notes"),
      h("p", { className: "hs-note" }, desk.niche || ""),
      h("form", { className: "hs-row", onSubmit: function (event) {
        event.preventDefault();
        props.onTrend(trend);
        setTrend({ kind: trend.kind, name: "", note: "" });
      } },
        h("select", { className: "hs-field", value: trend.kind, onChange: function (event) { setTrend(Object.assign({}, trend, { kind: event.target.value })); } },
          (desk.kinds || []).map(function (kind) { return h("option", { key: kind, value: kind }, kind); })),
        h("input", { className: "hs-field", value: trend.name, placeholder: "Topic, sound, or format", onChange: function (event) { setTrend(Object.assign({}, trend, { name: event.target.value })); } }),
        h("input", { className: "hs-field", value: trend.note, placeholder: "Where you noticed it", onChange: function (event) { setTrend(Object.assign({}, trend, { note: event.target.value })); } }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !trend.name.trim() }, "Save note")),
      h("div", { className: "hs-name" }, "In this brand's words"),
      (desk.feed || []).length ? desk.feed.map(noteRow) : h("p", { className: "hs-note" }, "No saved note uses this brand's pillar or tag words."),
      h("div", { className: "hs-name" }, "Saved, outside those words"),
      (desk.outside || []).length ? desk.outside.map(noteRow) : h("p", { className: "hs-note" }, "Nothing saved outside those words."),
    );
    function noteRow(item) {
      return h("p", { key: item.id, className: "hs-note" }, item.kind + " · " + item.name + (item.note ? " · " + item.note : "") + (item.result ? " · " + item.result : ""));
    }
  }

  function InboxDesk(props) {
    const desk = (props.studio && props.studio.inbox) || { items: [], errors: [], sending: false };
    const [kind, setKind] = useState("attention");
    const [drafts, setDrafts] = useState({});
    const items = (desk.items || []).filter(function (item) {
      if (kind === "attention") return item.needs_attention;
      if (kind === "ahead") return item.ahead;
      if (kind === "all") return true;
      return item.kind === kind;
    });
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: props.onRefresh }, "Refresh"),
        [["attention", "Needs attention"], ["ahead", "On a post that is ahead"], ["all", "All"], ["comment", "Comments"], ["mention", "Mentions"], ["dm", "Messages"]].map(function (pair) {
          return h("button", {
            key: pair[0], type: "button",
            className: "hs-tab" + (kind === pair[0] ? " is-on" : ""),
            onClick: function () { setKind(pair[0]); },
          }, pair[1]);
        })),
      (desk.errors || []).map(function (error) { return h("p", { key: error, className: "hs-bad" }, error); }),
      items.length ? items.map(function (item) {
        const value = drafts[item.id] != null ? drafts[item.id] : (item.reply || "");
        const canIdea = item.kind !== "dm" && (item.question || item.ahead);
        return h("div", { key: item.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, item.kind + " · " + item.platform + " · " + item.author),
          h("p", { className: "hs-voice" }, item.text),
          item.prompt ? h("p", { className: item.ahead ? "hs-ok" : "hs-note" }, item.prompt) : null,
          item.permalink ? h("a", { href: item.permalink, target: "_blank", rel: "noopener noreferrer" }, "Open it") : null,
          h("textarea", {
            className: "hs-area",
            value: value,
            placeholder: "Reply draft",
            onChange: function (event) {
              const next = event.target.value;
              setDrafts(function (current) { return Object.assign({}, current, { [item.id]: next }); });
            },
          }),
          h("div", { className: "hs-row" },
            h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onSuggest(item.id); } }, "Suggest a reply"),
            h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onReply(item.id, { reply: value }); } }, "Save draft"),
            canIdea ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onIdea(item.id); } }, "Keep as an idea") : null,
            h("button", { type: "button", className: "hs-tab", disabled: props.busy || !value.trim(), onClick: function () { props.onVoice(item.id, value); } }, "Keep this reply in the voice"),
            h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onReply(item.id, { reply: value, dismissed: true }); } }, "Dismiss")));
      }) : h("p", { className: "hs-note" }, "Nothing in this view. Refresh after a page is connected."),
    );
  }

  function downloadText(name, text, type) {
    const blob = new Blob([text], { type: type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function reportFileName(title, ext) {
    const slug = String(title || "report").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
    return (slug || "report") + "." + ext;
  }

  function ReportsDesk(props) {
    const desk = (props.studio && props.studio.reports) || { reports: [] };
    const [period, setPeriod] = useState("week");
    const [note, setNote] = useState("");
    const [copied, setCopied] = useState("");
    const rows = desk.reports || [];
    function copy(id, text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { setCopied(id); });
      }
    }
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-row" },
        [["week", "Week"], ["month", "Month"]].map(function (pair) {
          return h("button", {
            key: pair[0], type: "button",
            className: "hs-tab" + (period === pair[0] ? " is-on" : ""),
            onClick: function () { setPeriod(pair[0]); },
          }, pair[1]);
        })),
      h("textarea", {
        className: "hs-area",
        value: note,
        placeholder: "Note for this report",
        onChange: function (event) { setNote(event.target.value); },
      }),
      h("button", {
        type: "button", className: "hs-button", disabled: props.busy,
        onClick: function () { props.onGenerate(period, note); },
      }, "Generate"),
      rows.length ? rows.map(function (row) {
        const totals = (row.document && row.document.totals) || {};
        const recommendations = (row.document && row.document.recommendations) || [];
        return h("div", { key: row.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, row.title),
          h("p", { className: "hs-note" }, row.note || "No note."),
          h("p", { className: "hs-voice" },
            "Engagements " + (totals.engagements == null ? "—" : totals.engagements) +
            " · Shares " + (totals.shares == null ? "—" : totals.shares) +
            " · Reach " + (totals.reach == null ? (totals.reach_note || "Not in the pull") : totals.reach)),
          recommendations.length ? h("p", { className: "hs-note" }, recommendations[0]) : null,
          h("pre", { className: "hs-report" }, row.markdown || ""),
          h("div", { className: "hs-row" },
            h("button", {
              type: "button", className: "hs-tab", disabled: props.busy,
              onClick: function () { props.onInsight(row.id); },
            }, "Write the insight"),
            h("button", {
              type: "button", className: "hs-tab",
              onClick: function () { downloadText(reportFileName(row.title, "md"), row.markdown || "", "text/markdown"); },
            }, "Download markdown"),
            h("button", {
              type: "button", className: "hs-tab",
              onClick: function () {
                const payload = {
                  title: row.title, period: row.period, note: row.note || "",
                  start: row.start, end: row.end, generated_at: row.generated_at,
                  document: row.document || {},
                };
                downloadText(reportFileName(row.title, "json"), JSON.stringify(payload, null, 2), "application/json");
              },
            }, "Download JSON"),
            h("button", {
              type: "button", className: "hs-tab",
              onClick: function () { copy(row.id + ":md", row.markdown || ""); },
            }, copied === row.id + ":md" ? "Copied" : "Copy"),
            h("button", {
              type: "button", className: "hs-tab",
              onClick: function () { copy(row.id + ":id", row.id); },
            }, copied === row.id + ":id" ? "Id copied" : "Copy the report id")));
      }) : h("p", { className: "hs-note" }, "No report yet. Generate a week or a month."),
    );
  }


  function AcrossDesk(props) {
    const desk = (props.studio && props.studio.cross) || { enabled: false, brands: [], lines: [], accepted: [] };
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-note" }, (desk.brands || []).length ? "Included: " + desk.brands.join(", ") : "No brand is included."),
      (desk.lines || []).map(function (item, index) { return h("p", { key: item.key || index, className: item.clear ? "hs-ok" : "hs-note" }, item.detail); }),
      (desk.accepted || []).length ? h("div", { className: "hs-name" }, "Accepted") : null,
      (desk.accepted || []).map(function (item) { return h("p", { key: item.key, className: "hs-note" }, "Accepted. Not applied to a draft. " + item.detail); }));
  }

  function Learning(props) {
    const lessons = (props.studio && props.studio.lessons) || [];
    return h("div", { className: "hs-main" },
      lessons.length ? lessons.map(function (lesson) {
        return h("div", { key: lesson.id, className: "hs-lesson" },
          h("div", { className: "hs-name" }, lesson.title),
          h("p", { className: "hs-voice" }, lesson.detail));
      }) : h("p", { className: "hs-note" }, "No lessons yet."),
    );
  }

  window.__HERMES_PLUGINS__.register("house-social", HouseSocial);
})();

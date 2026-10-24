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
    pages: "Connect signs in through the house Meta or Threads app, then you pick this brand's Page, Instagram account, and Threads account. Tokens go to the vault. Posting is switched on here and in House settings.",
    ideas: "Sparks, competitor notes, trends, questions, and comments. Make this a draft opens it in the composer. A pattern line appears only when the posts already show one. Nothing here is a predicted score.",
    create: "One idea becomes a Facebook, Instagram, and Threads version. The assistant stays inside the brand voice.",
    library: "Images, video, carousels, templates, logos, and copy for this brand. A new save of the words or the file keeps the older version. Files stay beside the desk, not in git.",
    series: "A structure you can reuse with a new topic. Pause holds it. Fill uses a pillar this brand already has and does not save a draft. A shape is suggested only when it is already ahead, and stats wait for three uses with numbers. A series stays on this brand.",
    calendar: "Month, week, or day. Drag a piece onto a day to hold it, or into the tray to take it off. A pillar or campaign filter hides published posts, because a live post is not tagged with either.",
    campaigns: "A campaign holds the posts, the assets, the goal, and the dates. Clone keeps the shape and leaves the pieces. A kind is ahead only when both sides have three posts and the gap is real.",
    approval: "Draft, then needs review, then approved, then scheduled. One person is a single step; more go in order. With approval email on, each approver is emailed and can reply APPROVE or CHANGES. The trail stays after a notice is marked read.",
    queue: "Draft, needs approval, approved, scheduled, posted, on the record, or failed. A scheduled piece posts at its time while posting is on. On the record means a pulled post is tied to the draft.",
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
    run: "Ran once. A piece posts only after someone writes it.",
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
    const ending = (studio.connections || []).filter(function (item) {
      const days = item.expires_at ? daysUntil(item.expires_at) : null;
      return days != null && days <= 7;
    }).length;
    if (ending) out.pages = { n: ending, tone: "warn", label: ending === 1 ? "A sign-in ends soon" : ending + " sign-ins end soon" };
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

  function toneOf() {
    try {
      const root = window.getComputedStyle(document.documentElement);
      const raw = root.getPropertyValue("--background-base").trim() || window.getComputedStyle(document.body).backgroundColor;
      const probe = document.createElement("span");
      probe.style.color = raw;
      document.body.appendChild(probe);
      const rgb = window.getComputedStyle(probe).color.match(/[\d.]+/g) || [];
      probe.remove();
      const channel = function (value) {
        const unit = Number(value) / 255;
        return unit <= 0.03928 ? unit / 12.92 : Math.pow((unit + 0.055) / 1.055, 2.4);
      };
      const light = 0.2126 * channel(rgb[0] || 0) + 0.7152 * channel(rgb[1] || 0) + 0.0722 * channel(rgb[2] || 0);
      return light > 0.4 ? "light" : "dark";
    } catch (err) {
      return "dark";
    }
  }

  function useTone() {
    const [tone, setTone] = useState(toneOf);
    useEffect(function () {
      if (!window.MutationObserver) return undefined;
      const watch = new MutationObserver(function () { setTone(toneOf()); });
      watch.observe(document.documentElement, { attributes: true, attributeFilter: ["style", "class", "data-theme"] });
      return function () { watch.disconnect(); };
    }, []);
    return tone;
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
        h("h2", { className: "hs-h2", id: "hs-desk-title" }, "Add a brand"),
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

  class DeskBoundary extends React.Component {
    constructor(props) {
      super(props);
      this.state = { error: null };
    }
    static getDerivedStateFromError(error) {
      return { error: error };
    }
    componentDidCatch(error) {
      if (window.console) window.console.error("[house-social]", error);
    }
    render() {
      if (!this.state.error) return this.props.children;
      const self = this;
      return h("div", { className: "hs-error", role: "alert" },
        h("p", null, h("strong", null, "This desk hit an error. "), messageOf(this.state.error)),
        h("p", null, "The other desks still work. Nothing was sent."),
        h("button", { type: "button", className: "hs-tab", onClick: function () { self.setState({ error: null }); } }, "Try again"));
    }
  }

  // Facebook and Threads come back with ?code and ?state, or ?error when the
  // person said no. Read it once, then take it off the address bar.
  let signInRead = false;
  function signInReturn() {
    if (signInRead) return null;
    signInRead = true;
    let params;
    try { params = new URLSearchParams(window.location.search); } catch (err) { return null; }
    const state = params.get("state") || "";
    const code = params.get("code") || "";
    const error = params.get("error") || params.get("error_reason") || "";
    if (!state || (!code && !error)) return null;
    const said = params.get("error_description") || params.get("error_message") || "";
    ["code", "state", "error", "error_reason", "error_code", "error_description", "error_message"].forEach(function (key) { params.delete(key); });
    const rest = params.toString();
    try { window.history.replaceState(window.history.state, "", window.location.pathname + (rest ? "?" + rest : "")); }
    catch (err) { /* the code is single use, so leaving it in the address is harmless */ }
    if (error) {
      const cancelled = error === "access_denied" || error === "user_denied";
      return { error: cancelled ? "The sign-in was cancelled. Nothing was connected." : "The sign-in did not finish" + (said ? ": " + said : ".") + " Nothing was connected." };
    }
    return { state: state, code: code };
  }

  // The approval email links here with ?hs_brand and ?hs_review.
  function reviewLink() {
    let params;
    try { params = new URLSearchParams(window.location.search); } catch (err) { return null; }
    const piece = params.get("hs_review") || "";
    if (!piece) return null;
    const brand = params.get("hs_brand") || "";
    params.delete("hs_review");
    params.delete("hs_brand");
    const rest = params.toString();
    try { window.history.replaceState(window.history.state, "", window.location.pathname + (rest ? "?" + rest : "")); }
    catch (err) { /* the link still opened the right piece */ }
    return { piece: piece, brand: brand };
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
    const [panel, setPanel] = useState("");
    const [apps, setApps] = useState({});
    const [house, setHouse] = useState({});
    const [mail, setMail] = useState({});
    const [reviewFocus, setReviewFocus] = useState("");
    const [choice, setChoice] = useState(null);
    const [voiceCheck, setVoiceCheck] = useState(null);
    const [library, setLibrary] = useState({ assets: [], folders: [], tags: [] });
    const [limits, setLimits] = useState({ facebook: 5000, instagram: 2200, threads: 500 });
    const [cardLimit, setCardLimit] = useState(240);
    const [assist, setAssist] = useState(null);
    const [draftRead, setDraftRead] = useState(null);
    const [assistTarget, setAssistTarget] = useState("idea");
    const tone = useTone();
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
      setApps(roster.apps || {});
      setHouse(roster.publishing || {});
      setMail(roster.mail || {});
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
      const done = status === "ready" ? "Marked ready." : status === "planned" ? "Marked planned." : status === "scheduled" ? "Scheduled. It posts at that time while posting is on." : "Draft saved.";
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
      setPanel("");
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

    function saveApps(body) {
      const secret = body && ((body.meta && body.meta.secret) || (body.threads && body.threads.secret));
      return act("POST", "/apps", body, secret ? "House settings saved. The secret went to the vault." : "House settings saved.");
    }

    function pullPosts(id) {
      return act("POST", brandPath(id, "/pull"), undefined, function (pulled) {
        return pulled && pulled.count != null ? pulled.count + " posts pulled." : "Pulled.";
      });
    }

    // Leaves the dashboard for the Facebook or Threads sign-in. It comes back
    // to this same address with a code, which the effect below picks up.
    async function startConnect(kind) {
      const started = await ask("POST", on("/connect"), { provider: kind, redirect_uri: returnAddress() });
      if (!started || !started.url) return;
      remember("brand", brand.id);
      remember("section", "pages");
      window.location.assign(started.url);
    }

    function openChoice(found) {
      setChoice(found);
      remember("choice", found.choice);
      setPanel("");
      setSection("pages");
      if (found.brand_id && found.brand_id !== brandRef.current) setBrandId(found.brand_id);
    }

    function dropChoice() {
      setChoice(null);
      remember("choice", "");
    }

    async function chooseAccounts(body) {
      if (!choice) return null;
      const saved = await ask("POST", "/connect/choices/" + encodeURIComponent(choice.choice), body);
      if (!saved) return null;
      dropChoice();
      const names = (saved.connections || []).map(function (item) { return platformName(item.platform); }).join(" and ");
      notify((names || "The account") + " connected. The token went to the vault.");
      await pullPosts(saved.brand_id);
      return saved;
    }

    async function cancelChoice() {
      if (choice) await ask("DELETE", "/connect/choices/" + encodeURIComponent(choice.choice));
      dropChoice();
    }

    useEffect(function () {
      const review = reviewLink();
      if (review) {
        if (review.brand) setBrandId(review.brand);
        setPanel("");
        setSection("approval");
        setReviewFocus(review.piece);
        return;
      }
      const back = signInReturn();
      if (back && back.error) {
        setSection("pages");
        notify(back.error, "error");
        return;
      }
      if (back) {
        ask("POST", "/connect/finish", { state: back.state, code: back.code }).then(function (found) {
          if (found) openChoice(found);
          else setSection("pages");
        });
        return;
      }
      // A reload while picking keeps the picker for as long as the sign-in lasts.
      const waiting = recall("choice");
      if (!waiting) return;
      api("GET", "/connect/choices/" + encodeURIComponent(waiting)).then(setChoice, function () { remember("choice", ""); });
    }, []);

    function pickBrand(id) {
      setBrandId(id);
      setPanel("");
      setPickedDay("");
      setPickedPost("");
      setPickedHour("");
      setAssist(null);
      setDraftRead(null);
      setVoiceCheck(null);
    }

    function pickSection(id) {
      setSection(id);
      setPanel("");
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
        case "pages": return h(Accounts, {
          brand: brand, studio: studio, busy: busy, apps: apps, choice: choice,
          onOpenHouse: function () { setPanel("house"); },
          onConnect: startConnect,
          onChoose: chooseAccounts,
          onCancelChoice: cancelChoice,
          onDisconnect: function (platform) {
            return act("POST", on("/disconnect"), { platform: platform }, platformName(platform) + " disconnected. Its token is still in the vault.");
          },
          onSave: function (body) { return act("POST", "/connections", Object.assign({ brand_id: brand.id }, body), "Connection saved. The token went to the vault."); },
          onPull: function () { return pullPosts(brand.id); },
          onBrandPosting: function (value) {
            return act("POST", "/posting", { brand_id: brand.id, on: value }, value ? brand.name + " can post now." : brand.name + " will not post.");
          },
          onCheck: function () {
            return act("POST", on("/posting/check"), undefined, function (found) {
              const bad = (found.rows || []).filter(function (row) { return !row.ok; }).length;
              return bad ? bad + (bad === 1 ? " account cannot" : " accounts cannot") + " post yet. See below." : "Every connected account can post.";
            });
          },
          onTest: function (body) {
            return act("POST", on("/posting/test"), body, function (found) {
              const good = (found.rows || []).filter(function (row) { return row.ok; }).length;
              return good + " of " + (found.rows || []).length + " test posts went out.";
            });
          },
          onDeleteTest: function (id) { return act("DELETE", "/posting/tests/" + encodeURIComponent(id), undefined, "Test post deleted."); },
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
          onPostNow: function (id) {
            return act("POST", "/pieces/" + encodeURIComponent(id) + "/publish", undefined, function (done) {
              return done.status === "published" ? "Posted." : "It did not fully post. " + (done.failure || "");
            });
          },
          onBulk: runQueue,
          onPull: function () { return act("POST", on("/studio-read"), undefined, "Read from Studio."); },
        });
        case "approval": return h(ApprovalDesk, {
          studio: studio, busy: busy, focus: reviewFocus, mailReady: !!mail.ready,
          onOpen: openPiece,
          onSteps: function (steps) { return act("POST", on("/approval-steps"), { steps: steps }, "Steps saved."); },
          onReview: function (id) { return act("POST", "/pieces/" + id + "/review", undefined, "Sent for review."); },
          onDecide: function (id, body) {
            return act("POST", "/pieces/" + id + "/decision", body, function (done) {
              if (body.decision !== "approved") return "Changes asked for.";
              return done && done.status === "scheduled" ? "Approved and scheduled." : done && done.status === "pending" ? "Approved. The next step was asked." : "Approved.";
            });
          },
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
          studio: studio, busy: busy, onGo: pickSection,
          onAccept: function (key) { return act("POST", on("/cross"), { accept: true, key: key }, "Accepted."); },
        });
        case "learning": return h(Learning, { studio: studio, onGo: pickSection });
        default: return null;
      }
    }

    return h("div", { className: "hs-page", "data-tone": tone },
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
          h(PostingBadge, {
            house: !!house.on, live: !!(studio && studio.posting),
            onHouse: function () { setPanel("house"); },
            onBrand: function () { pickSection("pages"); },
          }))),
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
            h("div", { className: "hs-rail-links" },
              h("button", { type: "button", className: "hs-link-button", "aria-pressed": panel === "add", onClick: function () { setPanel(panel === "add" ? "" : "add"); } }, panel === "add" ? "Close" : "+ Add a brand"),
              h("button", { type: "button", className: "hs-link-button", "aria-pressed": panel === "house", onClick: function () { setPanel(panel === "house" ? "" : "house"); } }, "House settings"))),
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
        h("section", { className: "hs-desk", "aria-busy": busy ? "true" : "false", "aria-labelledby": "hs-desk-title" },
          busy ? h("div", { className: "hs-progress", "aria-hidden": "true" }) : null,
          panel === "add" ? h(AddBrand, { busy: busy, onAdd: addBrand, onCancel: function () { setPanel(""); } })
            : panel === "house" ? h(HouseSettings, {
              apps: apps, posting: house, mail: mail, busy: busy, onSave: saveApps, onClose: function () { setPanel(""); },
              onSaveMail: function (body) { return act("POST", "/mail", body, body.provider ? "Email settings saved." : "Approval email is off."); },
              onTestMail: function (to) { return act("POST", "/mail/test", { to: to }, "Test email sent to " + to + "."); },
              onPollMail: function () {
                return act("POST", "/mail/poll", undefined, function (read) {
                  return (read.decided || []).length + " decided by email, " + (read.ignored || []).length + " not counted.";
                });
              },
              onPosting: function (value) {
                return act("POST", "/posting", { on: value }, value ? "Posting is on for the house. Each brand still turns it on under Accounts." : "Posting is off. Nothing will post until it is on again.");
              },
              onRunDue: function () {
                return act("POST", "/posting/run", undefined, function (ran) {
                  return (ran.posted || []).length + " posted, " + (ran.failed || []).length + " failed, " + (ran.waiting || []).length + " waiting.";
                });
              },
            })
            : !loaded ? h("p", { className: "hs-note hs-loading" }, "Loading the desk…")
              : !brand ? h("div", { className: "hs-empty" }, "No brand on the roster yet. Add one to start.")
                : h("div", { className: "hs-desk-body", key: brand.id + ":" + desk },
                  h("div", { className: "hs-desk-head" },
                    h("h2", { className: "hs-desk-title", id: "hs-desk-title" }, current ? current.label : ""),
                    DESK_NOTES[desk] ? h("p", { className: "hs-desk-note" }, DESK_NOTES[desk]) : null),
                  ready ? h(DeskBoundary, null, renderDesk()) : h("p", { className: "hs-note hs-loading" }, "Loading the desk…")))),
      h(Toasts, { items: toasts, onDismiss: dismiss }),
    );
  }

  function linesOf(value) {
    return String(value || "").split("\n").map(function (line) { return line.trim(); }).filter(Boolean);
  }

  function voiceForm(guide) {
    const angles = {};
    (guide.pillars || []).forEach(function (pillar) { angles[pillar.id] = (pillar.angles || []).join("\n"); });
    return {
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
    };
  }

  function voicePayload(form, guide) {
    return {
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
    };
  }

  function VoiceGuide(props) {
    const guide = (props.studio && props.studio.voice) || {};
    const desk = (props.studio && props.studio.voice_desk) || { versions: [], lessons: { suggestions: [], detail: "" }, imports: 0 };
    const lessons = desk.lessons || { suggestions: [], detail: "", ready: false };
    const stamp = JSON.stringify(voicePayload(voiceForm(guide), guide));
    const [form, setForm] = useState(function () { return voiceForm(guide); });
    const [example, setExample] = useState({ title: "", text: "" });
    const [manual, setManual] = useState({ text: "", engagements: "", kind: "on", title: "" });
    useEffect(function () { setForm(voiceForm(guide)); }, [stamp]);
    const dirty = JSON.stringify(voicePayload(form, guide)) !== stamp;
    function setField(name, value) {
      setForm(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    function area(name, label, placeholder, hint, tall) {
      return field(label, h("textarea", {
        className: "hs-area" + (tall ? "" : " hs-short"), value: form[name], placeholder: placeholder || "",
        onChange: function (event) { setField(name, event.target.value); },
      }), hint);
    }
    function addExample(kind) {
      const text = example.text.trim();
      if (!text) return;
      setField("examples", (form.examples || []).concat([{ title: example.title.trim(), text: text, kind: kind, source: "written" }]));
      setExample({ title: "", text: "" });
    }
    function save(event) {
      if (event) event.preventDefault();
      props.onSave(voicePayload(form, guide));
    }
    return h("div", { className: "hs-main" },
      h("form", { className: "hs-main", onSubmit: save },
      h(Section, { title: "How it sounds" },
        area("tone", "Tone", "Short paragraphs. Name the hard thing first.", null, true),
        area("personality", "Personality", "In it with them, not above them."),
        h("div", { className: "hs-grid-3" },
          field("Formality", h("select", { className: "hs-field", value: form.formality, onChange: function (event) { setField("formality", event.target.value); } },
            h("option", { value: "" }, "Not set"),
            h("option", { value: "casual" }, "Casual"),
            h("option", { value: "plain" }, "Plain"),
            h("option", { value: "formal" }, "Formal"))),
          field("Humor", h("input", { className: "hs-field", value: form.humor, placeholder: "Dry, none, warm", onChange: function (event) { setField("humor", event.target.value); } })),
          field("Point of view", h("input", { className: "hs-field", value: form.point_of_view, placeholder: "Second person, her scene, the product", onChange: function (event) { setField("point_of_view", event.target.value); } }))),
        h("label", { className: "hs-note" },
          h("input", { type: "checkbox", checked: form.second_person, onChange: function (event) { setField("second_person", event.target.checked); } }),
          h("span", null, h("span", { className: "hs-check-title" }, "Require “you”"), " A draft fails the voice check when it never speaks to the reader."))),
      h(Section, { title: "Rules", note: "One rule or phrase a line. The composer checks each draft against these." },
        h("div", { className: "hs-grid-2" },
          area("dos", "Do", "Validate the feeling before any reframe."),
          area("donts", "Don't", "Cheerful for the sake of cheerful.")),
        h("div", { className: "hs-grid-3" },
          area("banned", "Banned words and phrases", "good vibes only"),
          area("preferred", "Preferred language", "One phrase a line", "A long draft should use one of them."),
          area("required", "Required in the draft", "One phrase a line", "Use ? for a question mark.")),
        h("div", { className: "hs-grid-2" },
          area("differentiation", "Competitor differentiation", "What this brand refuses to sound like"),
          area("visual", "Visual", "Obsidian and ember. Built for a phone scroll."))),
      h(Section, { title: "Pillars and angles", note: "Up to three angles a pillar, one a line. Pillars themselves are set on the brand." },
        (guide.pillars || []).length ? h("div", { className: "hs-grid-2" }, (guide.pillars || []).map(function (pillar) {
          const known = ((props.brand && props.brand.pillars) || []).find(function (item) { return item.id === pillar.id; });
          return h("div", { key: pillar.id }, field(pillar.name, h("textarea", {
            className: "hs-area hs-short",
            placeholder: "One angle a line, up to three",
            value: (form.angles && form.angles[pillar.id]) || "",
            onChange: function (event) {
              const value = event.target.value;
              setForm(function (current) {
                return Object.assign({}, current, { angles: Object.assign({}, current.angles, { [pillar.id]: value }) });
              });
            },
          }), known && known.note ? known.note : null));
        })) : h("p", { className: "hs-note" }, "No pillars on this brand yet.")),
      h(Section, { title: "On-brand and off-brand", note: "Examples the assistant holds itself to. They are saved with the voice." },
        (form.examples || []).length ? h("ul", { className: "hs-rows" }, (form.examples || []).map(function (item, index) {
          return h("li", { key: item.kind + item.text + index, className: "hs-list-row" },
            h("div", { className: "hs-list-main" },
              h("div", { className: "hs-row hs-gap-sm" },
                h("span", { className: "hs-status " + (item.kind === "off" ? "is-failed" : "is-scheduled") }, item.kind === "off" ? "Off-brand" : "On-brand"),
                h("span", { className: "hs-meta" }, [item.source || "written", item.title].filter(Boolean).join(" · "))),
              h("div", null, item.text)),
            h("button", {
              type: "button", className: "hs-tab hs-tab-sm",
              onClick: function () {
                setField("examples", (form.examples || []).filter(function (_item, itemIndex) { return itemIndex !== index; }));
              },
            }, "Remove"));
        })) : h("p", { className: "hs-note" }, "No examples yet."),
        h("div", { className: "hs-grid-2" },
          field("Example title", h("input", { className: "hs-field", value: example.title, placeholder: "Optional", onKeyDown: function (event) { if (event.key === "Enter") event.preventDefault(); }, onChange: function (event) { setExample(Object.assign({}, example, { title: event.target.value })); } })),
          field("Example text", h("textarea", { className: "hs-area hs-short", value: example.text, onChange: function (event) { setExample(Object.assign({}, example, { text: event.target.value })); } }))),
        h("div", { className: "hs-row" },
          h("button", { type: "button", className: "hs-tab", disabled: !example.text.trim(), onClick: function () { addExample("on"); } }, "Add as on-brand"),
          h("button", { type: "button", className: "hs-tab", disabled: !example.text.trim(), onClick: function () { addExample("off"); } }, "Add as off-brand"))),
      h("div", { className: "hs-savebar" + (dirty ? " is-dirty" : "") },
        h("span", { className: dirty ? "hs-warn" : "hs-note" }, dirty ? "Unsaved changes to the voice." : "The voice on screen is the one in use."),
        h("div", { className: "hs-row hs-gap-sm" },
          dirty ? h("button", { type: "button", className: "hs-link-button", onClick: function () { setForm(voiceForm(guide)); } }, "Discard") : null,
          h("button", { type: "submit", className: "hs-button", disabled: props.busy || !dirty }, "Save voice")))),
      h(Section, {
        title: "What the posts suggest",
        note: (dirty ? "Save your edits before you accept a suggestion. " : "") + (lessons.detail || "Pull the page, or paste posts below."),
      },
        (lessons.suggestions || []).length ? h("ul", { className: "hs-rows" }, (lessons.suggestions || []).map(function (item) {
          return h("li", { key: item.id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" },
              h("div", null, item.detail),
              item.example ? h("div", { className: "hs-meta" }, item.example.text) : null),
            h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy || dirty, onClick: function () { props.onAccept(item.id); } }, "Accept"));
        })) : h("p", { className: "hs-note" }, "Nothing to suggest yet.")),
      h(Section, {
        title: "Teach it from old posts",
        note: (desk.imports || 0) + " pasted posts sit on this desk. A row with a date and an engagement count is also in Analytics; a row without a date stays out of the windows.",
        collapsible: true,
      },
        field("A CSV of posts", h("input", {
          className: "hs-field", type: "file", accept: ".csv,text/csv",
          onChange: function (event) {
            const file = event.target.files && event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function () { props.onImport({ csv: String(reader.result || "") }); };
            reader.readAsText(file);
            event.target.value = "";
          },
        })),
        field("Or one post", h("textarea", { className: "hs-area hs-short", placeholder: "Paste one post", value: manual.text, onChange: function (event) { setManual(Object.assign({}, manual, { text: event.target.value })); } })),
        h("div", { className: "hs-grid-3" },
          field("Engagements", h("input", { className: "hs-field", inputMode: "numeric", placeholder: "If you know them", value: manual.engagements, onChange: function (event) { setManual(Object.assign({}, manual, { engagements: event.target.value })); } })),
          field("Keep it as", h("select", { className: "hs-field", value: manual.kind, onChange: function (event) { setManual(Object.assign({}, manual, { kind: event.target.value })); } },
            h("option", { value: "on" }, "An on-brand example"),
            h("option", { value: "off" }, "An off-brand example"),
            h("option", { value: "" }, "Numbers only")))),
        h("div", { className: "hs-row" },
          h("button", {
            type: "button", className: "hs-tab", disabled: props.busy || !manual.text.trim(),
            onClick: async function () {
              const saved = await props.onImport({ text: manual.text, engagements: manual.engagements, kind: manual.kind, title: manual.title });
              if (saved) setManual({ text: "", engagements: "", kind: manual.kind, title: "" });
            },
          }, "Add post"))),
      h(Section, { title: "Versions", note: "Each save keeps the guide it replaced.", collapsible: true },
        (desk.versions || []).length ? h("ul", { className: "hs-rows" }, (desk.versions || []).map(function (version) {
          return h("li", { key: version.id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" },
              h("div", null, version.note || "Saved"),
              h("div", { className: "hs-meta" }, [String(version.at || "").replace("T", " ").slice(0, 16), version.tone].filter(Boolean).join(" · "))),
            h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onRestore(version.id); } }, "Restore"));
        })) : h("p", { className: "hs-note" }, "No saved version yet. The guide on screen is the one in use.")),
    );
  }

  const STATUS_LABELS = {
    draft: "Draft", planned: "Planned", ready: "Ready", pending: "Needs review", approved: "Approved",
    scheduled: "Scheduled", failed: "Failed", published: "Published",
  };

  function statusLabel(status) {
    return STATUS_LABELS[status || "draft"] || String(status || "draft");
  }

  function platformName(id) {
    const pair = PLATFORMS.find(function (item) { return item[0] === id; });
    return pair ? pair[1] : (id || "");
  }

  function count(value) {
    return value == null ? "—" : String(value);
  }

  // Posts as rows: the words, the numbers that exist, and a link out.
  function PostRows(props) {
    const [all, setAll] = useState(false);
    const rows = props.posts || [];
    const limit = props.limit || 10;
    const shown = all ? rows : rows.slice(0, limit);
    if (!rows.length) return h("p", { className: "hs-note" }, props.empty || "No posts yet.");
    return h("div", { className: "hs-stack" },
      h("ul", { className: "hs-rows" }, shown.map(function (item) {
        return h("li", { key: (item.platform || "") + item.id, className: "hs-list-row" },
          h("div", { className: "hs-list-main" },
            h("div", { className: "hs-clamp" }, item.preview || "Untitled"),
            h("div", { className: "hs-meta" }, [platformName(item.platform), item.format, props.detail ? props.detail(item) : null].filter(Boolean).join(" · "))),
          h("div", { className: "hs-row hs-gap-sm" },
            h("span", { className: "hs-num", title: "Engagements" }, count(item.engagements)),
            item.permalink ? h("a", { href: item.permalink, target: "_blank", rel: "noopener noreferrer", "aria-label": "Open the post" }, "Open") : null));
      })),
      rows.length > limit ? h("button", { type: "button", className: "hs-link-button", onClick: function () { setAll(!all); } }, all ? "Show fewer" : "Show all " + rows.length) : null);
  }

  // Where Facebook and Threads send the browser after a sign-in. Each app must
  // list this exact address, so House settings shows it to copy.
  function returnAddress() {
    return window.location.origin + window.location.pathname;
  }

  function appReady(apps, kind) {
    const row = (apps || {})[kind] || {};
    return !!(row.app_id && row.secret_saved);
  }

  function daysUntil(iso) {
    const when = Date.parse(iso || "");
    if (isNaN(when)) return null;
    return Math.ceil((when - Date.now()) / 86400000);
  }

  function CopyField(props) {
    const [copied, setCopied] = useState(false);
    const input = useRef(null);
    function copy() {
      if (input.current) input.current.select();
      const done = function () {
        setCopied(true);
        window.setTimeout(function () { setCopied(false); }, 1800);
      };
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(props.value).then(done, function () { /* the text stays selected to copy by hand */ });
        }
      } catch (err) { /* the text stays selected to copy by hand */ }
    }
    return h("div", { className: "hs-copy" },
      h("input", {
        ref: input, className: "hs-field hs-mono", readOnly: true, value: props.value, "aria-label": props.label,
        onFocus: function (event) { event.target.select(); },
      }),
      h("button", { type: "button", className: "hs-tab hs-tab-sm", onClick: copy }, copied ? "Copied" : "Copy"));
  }

  function AppStatus(props) {
    const row = props.row || {};
    if (row.app_id && row.secret_saved) return h("span", { className: "hs-status is-published" }, "Ready");
    if (row.app_id) return h("span", { className: "hs-status is-pending" }, "Needs the secret");
    return h("span", { className: "hs-status is-planned" }, "Not set");
  }

  // The house apps, once for every brand. Brands sign in through them.
  function workerLine(posting) {
    const worker = posting.worker || {};
    const last = worker.last;
    const parts = [];
    parts.push(worker.started ? "The poster is running" + (worker.last_tick ? ", last checked " + String(worker.last_tick).slice(11, 16) + " UTC." : ".") : "The poster starts with the dashboard.");
    if (last) parts.push("Last run: " + (last.posted || []).length + " posted, " + (last.failed || []).length + " failed, " + (last.late || []).length + " too late.");
    if (worker.error) parts.push("Last error: " + worker.error);
    return parts.join(" ");
  }

  function HouseSettings(props) {
    const apps = props.apps || {};
    const posting = props.posting || {};
    const meta = apps.meta || {};
    const threads = apps.threads || {};
    const [metaId, setMetaId] = useState(meta.app_id || "");
    const [threadsId, setThreadsId] = useState(threads.app_id || "");
    const [metaSecret, setMetaSecret] = useState("");
    const [threadsSecret, setThreadsSecret] = useState("");
    function submit(event) {
      event.preventDefault();
      const body = { meta: { app_id: metaId.trim() }, threads: { app_id: threadsId.trim() } };
      if (metaSecret.trim()) body.meta.secret = metaSecret.trim();
      if (threadsSecret.trim()) body.threads.secret = threadsSecret.trim();
      Promise.resolve(props.onSave(body)).then(function (saved) {
        if (saved) { setMetaSecret(""); setThreadsSecret(""); }
      });
    }
    function secretHint(row) {
      return row.secret_saved ? "Saved in the vault. Paste a new one only to replace it." : "Written to the vault, never to the dashboard.";
    }
    return h("div", { className: "hs-panel hs-panel-wide" },
      h("div", { className: "hs-panel-head" },
        h("h2", { className: "hs-h2", id: "hs-desk-title" }, "House settings"),
        h("p", { className: "hs-note" }, "The Meta app and the Threads app belong to the whole house. Each brand signs in through them on its own Accounts desk.")),
      h(Section, {
        title: "Posting",
        note: "The switch for every brand at once. Each brand also turns posting on for itself under Accounts. While on, the desk checks once a minute and posts what is due.",
        actions: [h("span", { key: "s", className: "hs-status " + (posting.on ? "is-published" : "is-planned") }, posting.on ? "On" : "Off")],
      },
        h(SaveCheck, {
          checked: posting.on, disabled: props.busy, onChange: props.onPosting,
          title: "Let the desk post", note: "Turning it off stops every brand at once. Scheduled pieces wait.",
        }),
        h("p", { className: "hs-note" }, workerLine(posting)),
        h("div", { className: "hs-row hs-gap-sm" },
          h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy || !posting.on, onClick: props.onRunDue }, "Post what is due now"),
          posting.due_soon ? h("span", { className: "hs-hint" }, posting.due_soon + (posting.due_soon === 1 ? " piece is" : " pieces are") + " scheduled in the next 24 hours.") : null)),
      h("form", { className: "hs-stack", onSubmit: submit, "aria-label": "Apps" },
      h(Section, { title: "Meta app", note: "Facebook Pages and Instagram professional accounts sign in through this app.", actions: [h(AppStatus, { key: "s", row: meta })] },
        h("div", { className: "hs-grid-2" },
          field("App id", h("input", { className: "hs-field", value: metaId, inputMode: "numeric", autoComplete: "off", onChange: function (event) { setMetaId(event.target.value); } })),
          field("App secret", h("input", { className: "hs-field", type: "password", value: metaSecret, autoComplete: "new-password", placeholder: meta.secret_saved ? "Saved" : "Paste once", onChange: function (event) { setMetaSecret(event.target.value); } }), secretHint(meta)))),
      h(Section, { title: "Threads app", note: "Threads accounts sign in through their own app id and secret, from the Threads use case.", actions: [h(AppStatus, { key: "s", row: threads })] },
        h("div", { className: "hs-grid-2" },
          field("App id", h("input", { className: "hs-field", value: threadsId, inputMode: "numeric", autoComplete: "off", onChange: function (event) { setThreadsId(event.target.value); } })),
          field("App secret", h("input", { className: "hs-field", type: "password", value: threadsSecret, autoComplete: "new-password", placeholder: threads.secret_saved ? "Saved" : "Paste once", onChange: function (event) { setThreadsSecret(event.target.value); } }), secretHint(threads)))),
      h(Section, { title: "Sign-in address", note: "Facebook and Threads only return a sign-in to an address the app lists. Add this one to both apps." },
        h(CopyField, { value: returnAddress(), label: "Sign-in address" }),
        h("ul", { className: "hs-steps" },
          h("li", null, "Meta app: Facebook Login, then Settings, then Valid OAuth Redirect URIs."),
          h("li", null, "Threads app: the Threads use case, then Settings, then Redirect Callback URLs."),
          h("li", null, "Open the dashboard at this same address when you connect. Meta expects https; plain http is only accepted for localhost, and Threads may refuse it."))),
      h("div", { className: "hs-row" },
        h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Save apps"))),
      h(MailSettings, { mail: props.mail, busy: props.busy, onSave: props.onSaveMail, onTest: props.onTestMail, onPoll: props.onPollMail }),
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-tab", onClick: props.onClose }, "Close")));
  }

  // Who sends approval email, and where replies are read.
  function MailSettings(props) {
    const mail = props.mail || {};
    const agent = mail.agentmail || {};
    const resend = mail.resend || {};
    const [provider, setProvider] = useState(mail.provider || "");
    const [inbox, setInbox] = useState(agent.inbox || "");
    const [agentKey, setAgentKey] = useState("");
    const [from, setFrom] = useState(resend.from || "");
    const [replyTo, setReplyTo] = useState(resend.reply_to || "");
    const [resendKey, setResendKey] = useState("");
    const [testTo, setTestTo] = useState("");
    function submit(event) {
      event.preventDefault();
      const body = {
        provider: provider,
        agentmail: { inbox: inbox.trim() },
        resend: { from: from.trim(), reply_to: replyTo.trim() },
        dashboard_url: returnAddress(),
      };
      if (agentKey.trim()) body.agentmail.key = agentKey.trim();
      if (resendKey.trim()) body.resend.key = resendKey.trim();
      Promise.resolve(props.onSave(body)).then(function (saved) {
        if (saved) { setAgentKey(""); setResendKey(""); }
      });
    }
    const status = mail.ready
      ? h("span", { key: "s", className: "hs-status is-published" }, mail.provider === "resend" ? "Resend" : "AgentMail")
      : h("span", { key: "s", className: "hs-status is-planned" }, "Off");
    const reads = mail.ready
      ? (mail.reads_replies
        ? "Replies are read from " + agent.inbox + " once a minute. An approver replies APPROVE, or CHANGES and what to change."
        : "Replies cannot be read without an AgentMail inbox. Approvers use the link in the email instead.")
      : "Off. Approvers decide on the Approval desk.";
    return h("form", { className: "hs-stack", onSubmit: submit, "aria-label": "Approval email" },
      h(Section, {
        title: "Approval email",
        note: "When a piece needs review, the approver for that step gets the post by email. Add each approver's address on a brand's Approval desk.",
        actions: [status],
      },
        h(Segmented, { label: "Send with", value: provider, options: [["", "Off"], ["agentmail", "AgentMail"], ["resend", "Resend"]], onChange: setProvider }),
        provider ? h("div", { className: "hs-grid-2" },
          field("AgentMail inbox", h("input", { className: "hs-field", type: "email", value: inbox, placeholder: "approvals@agentmail.to", autoComplete: "off", onChange: function (event) { setInbox(event.target.value); } }),
            provider === "resend" ? "Optional. With it, replies to Resend mail can be read." : "Mail is sent from this inbox, and replies are read from it."),
          field("AgentMail API key", h("input", { className: "hs-field", type: "password", value: agentKey, placeholder: agent.key_saved ? "Saved" : "Paste once", autoComplete: "new-password", onChange: function (event) { setAgentKey(event.target.value); } }),
            agent.key_saved ? "Saved in the vault." : "Written to the vault, never to the dashboard.")) : null,
        provider === "resend" ? h("div", { className: "hs-grid-2" },
          field("From", h("input", { className: "hs-field", value: from, placeholder: "House Social <approvals@yourdomain.com>", autoComplete: "off", onChange: function (event) { setFrom(event.target.value); } }),
            "An address on a domain verified in Resend."),
          field("Resend API key", h("input", { className: "hs-field", type: "password", value: resendKey, placeholder: resend.key_saved ? "Saved" : "Paste once", autoComplete: "new-password", onChange: function (event) { setResendKey(event.target.value); } }),
            resend.key_saved ? "Saved in the vault." : "Written to the vault, never to the dashboard."),
          field("Replies go to", h("input", { className: "hs-field", type: "email", value: replyTo, placeholder: inbox || "approvals@agentmail.to", autoComplete: "off", onChange: function (event) { setReplyTo(event.target.value); } }),
            "Use the AgentMail inbox above so replies can be read.")) : null,
        h("p", { className: "hs-note" }, reads),
        mail.dashboard_url ? h("p", { className: "hs-hint" }, "Links in the email open " + mail.dashboard_url + ".") : null,
        mail.poll_error ? h("p", { className: "hs-error" }, "Reading replies failed: " + mail.poll_error) : null,
        h("div", { className: "hs-row hs-gap-sm" },
          h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Save email settings"),
          mail.reads_replies ? h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: props.onPoll }, "Read replies now") : null),
        mail.ready ? h("div", { className: "hs-row hs-gap-sm" },
          h("input", { className: "hs-field hs-grow", type: "email", "aria-label": "Send a test to", placeholder: "you@example.com", value: testTo, onChange: function (event) { setTestTo(event.target.value); } }),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy || !testTo.trim(), onClick: function () { props.onTest(testTo.trim()); } }, "Send a test email")) : null));
  }

  const ACCOUNT_ROWS = [
    { platform: "facebook", label: "Facebook Page", app: "meta", button: "Connect with Facebook", empty: "Sign in with Facebook, then pick this brand's Page." },
    { platform: "instagram", label: "Instagram", app: "meta", button: "Connect with Facebook", empty: "Instagram signs in through Facebook. The account must be a professional account linked to a Page." },
    { platform: "threads", label: "Threads", app: "threads", button: "Connect with Threads", empty: "Sign in with this brand's Threads account." },
  ];

  function accountLine(item) {
    const who = item.platform === "facebook" ? (item.name || "Page") : (item.username ? "@" + item.username : (item.name || "Account"));
    const parts = [who, "id " + item.external_id];
    if (item.via === "facebook") parts.push("found on the Facebook Page");
    else if (item.page_id) parts.push("through Page " + item.page_id);
    if (item.connected_at) parts.push("since " + String(item.connected_at).slice(0, 10));
    return parts.join(" · ");
  }

  function AccountRow(props) {
    const row = props.row;
    const item = props.item;
    const days = item && item.expires_at ? daysUntil(item.expires_at) : null;
    return h("li", { className: "hs-list-row hs-account" },
      h("div", { className: "hs-list-main" },
        h("div", { className: "hs-row hs-gap-xs" },
          h("strong", null, row.label),
          h("span", { className: "hs-status " + (item ? "is-published" : "is-planned") }, item ? "Connected" : "Not connected")),
        h("div", { className: "hs-meta" }, item ? accountLine(item) : row.empty),
        item ? h("div", { className: "hs-meta" }, "Token in ", h("code", { className: "hs-code" }, item.token_vault)) : null,
        item && props.account ? h("div", { className: "hs-meta" }, postingLine(props.account)) : null,
        days != null && days <= 14 ? h("p", { className: days <= 0 ? "hs-error" : "hs-warn" },
          days <= 0 ? "This sign-in has ended. Connect again." : "This sign-in ends in " + days + (days === 1 ? " day" : " days") + ". Connect again to renew it.") : null,
        props.leaving ? h("div", { className: "hs-danger-zone is-open", role: "alertdialog", "aria-label": "Disconnect " + row.label },
          h("p", null, row.platform === "facebook" && props.foundInstagram
            ? "Disconnect the Page and the Instagram account it found? Pulls stop for both. The token stays in the vault until you remove it there."
            : "Disconnect " + row.label + "? Pulls stop for it. The token stays in the vault until you remove it there."),
          h("div", { className: "hs-row" },
            h("button", { type: "button", className: "hs-button is-danger", disabled: props.busy, onClick: props.onDisconnect }, "Disconnect"),
            h("button", { type: "button", className: "hs-tab", onClick: props.onKeep }, "Keep it"))) : null),
      h("div", { className: "hs-row hs-gap-xs" },
        h("button", {
          type: "button", className: item || props.quiet ? "hs-tab hs-tab-sm" : "hs-button",
          disabled: props.busy || !props.ready,
          title: props.ready ? "" : "Set the house app in House settings first",
          onClick: function () { props.onConnect(row.app); },
        }, item ? "Change" : row.button),
        item && !props.leaving ? h("button", { type: "button", className: "hs-chip-button", disabled: props.busy, onClick: props.onLeave }, "Disconnect") : null));
  }

  // After Facebook or Threads signs in: which of what came back is this brand's.
  function AccountPicker(props) {
    const choice = props.choice;
    const pages = choice.pages || [];
    const accounts = choice.instagram || [];
    const startPage = (pages.find(function (page) { return page.current; })
      || (pages.length === 1 ? pages[0] : null)
      || pages.find(function (page) { return page.likely; }) || {}).id || "";
    const [pageId, setPageId] = useState(startPage);
    const [picked, setPicked] = useState(null);
    if (choice.provider === "threads") {
      const account = choice.threads || {};
      const who = account.username ? "@" + account.username : account.name || "this account";
      return h(Section, { title: "Connect Threads to " + choice.brand_name, note: "Threads signed you in as the account below. Its token goes to the vault." },
        h("p", { className: "hs-voice" }, who + (account.name && account.username ? " · " + account.name : "") + (account.current ? " · already on this brand" : "")),
        h("p", { className: "hs-hint" }, (choice.expires_at ? "Threads asks for a new sign-in by " + String(choice.expires_at).slice(0, 10) + ". " : "") + "Wrong account? Cancel, sign out of Threads in this browser, and connect again."),
        h("div", { className: "hs-row" },
          h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onChoose({}); } }, "Connect " + who),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: props.onCancel }, "Cancel")));
    }
    const page = pages.find(function (item) { return item.id === pageId; }) || null;
    const linked = page ? page.instagram_id : "";
    const current = (accounts.find(function (item) { return item.current; }) || {}).id || "";
    const likely = (accounts.find(function (item) { return item.likely; }) || {}).id || "";
    const instagramId = picked === null ? (linked || likely || (pageId ? "" : current)) : picked;
    const account = accounts.find(function (item) { return item.id === instagramId; }) || null;
    const summary = [page ? page.name : "", account ? "@" + (account.username || account.id) : ""].filter(Boolean).join(" and ");
    function option(name, value, on, title, note, onPick) {
      return h("label", { key: value || "none", className: "hs-choice" + (on ? " is-on" : "") },
        h("input", { type: "radio", name: name, value: value, checked: on, onChange: onPick }),
        h("span", { className: "hs-choice-body" },
          h("span", { className: "hs-choice-title" }, title),
          note ? h("span", { className: "hs-note" }, note) : null));
    }
    return h(Section, { title: "Pick " + choice.brand_name + "'s accounts", note: "Facebook shared these for this sign-in. Only what you pick is saved, and its token goes to the vault." },
      h("fieldset", { className: "hs-pick" },
        h("legend", { className: "hs-name" }, "Facebook Page"),
        h("div", { className: "hs-choices" },
          pages.map(function (item) {
            const note = [item.category, item.username ? "@" + item.username : "", item.current ? "on this brand now" : item.likely ? "matches this brand" : ""].filter(Boolean).join(" · ");
            return option("hs-pick-page", item.id, pageId === item.id, item.name, note, function () { setPageId(item.id); setPicked(null); });
          }),
          option("hs-pick-page", "", pageId === "", "No Page", "Leave Facebook as it is.", function () { setPageId(""); setPicked(null); }))),
      h("fieldset", { className: "hs-pick" },
        h("legend", { className: "hs-name" }, "Instagram"),
        accounts.length ? h("div", { className: "hs-choices" },
          accounts.map(function (item) {
            const note = ["on " + item.page_name, item.id === linked ? "linked to the Page you picked" : "", item.current ? "on this brand now" : item.likely ? "matches this brand" : ""].filter(Boolean).join(" · ");
            return option("hs-pick-instagram", item.id, instagramId === item.id, "@" + (item.username || item.id), note, function () { setPicked(item.id); });
          }),
          option("hs-pick-instagram", "", instagramId === "", "No Instagram", "Leave Instagram as it is.", function () { setPicked(""); }))
          : h("p", { className: "hs-note" }, "None of these Pages has a linked Instagram professional account. Link one in the Page's settings, then connect again.")),
      pages.length > 1 ? h("p", { className: "hs-hint" }, "Missing a Page? Connect again and choose it when Facebook asks which Pages to share.") : null,
      h("div", { className: "hs-row" },
        h("button", {
          type: "button", className: "hs-button", disabled: props.busy || !summary,
          onClick: function () { props.onChoose({ page_id: pageId, instagram_id: instagramId }); },
        }, summary ? "Connect " + summary : "Pick a Page or an account"),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: props.onCancel }, "Cancel")));
  }

  // A checkbox that saves on change. It shows the new value while the save runs,
  // and falls back to what the desk says once it answers.
  function SaveCheck(props) {
    const [pending, setPending] = useState(null);
    const shown = pending === null ? !!props.checked : pending;
    return h("label", { className: "hs-note" },
      h("input", {
        type: "checkbox", checked: shown, disabled: props.disabled || pending !== null,
        onChange: function (event) {
          const value = event.target.checked;
          setPending(value);
          Promise.resolve(props.onChange(value)).finally(function () { setPending(null); });
        },
      }),
      h("span", null, h("span", { className: "hs-check-title" }, props.title), " ", props.note));
  }

  // What the header says about posting, and where a click takes you to change it.
  function PostingBadge(props) {
    if (!props.house) {
      return h("button", { type: "button", className: "hs-badge", title: "Posting is off for every brand. Turn it on in House settings.", onClick: props.onHouse }, "Posting off");
    }
    if (!props.live) {
      return h("button", { type: "button", className: "hs-badge", title: "Turn posting on for this brand under Accounts.", onClick: props.onBrand }, "Posting off for this brand");
    }
    return h("button", { type: "button", className: "hs-badge is-mode", title: "Approved, scheduled pieces post at their time.", onClick: props.onBrand },
      h("span", { className: "hs-dot-live", "aria-hidden": "true" }), "Posting on");
  }

  function postingLine(account) {
    if (!account) return "";
    const checked = account.checked || {};
    if (checked.at) return (checked.ok ? "Can post. " : "Cannot post. ") + (checked.detail || "") + " Checked " + String(checked.at).slice(0, 10) + ".";
    if (account.can_post === true) return "This sign-in allows posting. Check posting to prove it.";
    if (account.can_post === false) return "This sign-in does not allow posting. Press Change and connect again.";
    return "Not checked for posting yet. Press Check posting, or Change to sign in again.";
  }

  function andList(names) {
    if (names.length < 2) return names.join("");
    return names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
  }

  const TEST_TEXT = "Testing a post from House Social. This will be deleted.";

  function PostingPanel(props) {
    const posting = props.posting || {};
    const connected = props.connected || [];
    const tests = posting.tests || [];
    const [picked, setPicked] = useState(function () { return connected.filter(function (platform) { return platform !== "instagram"; }); });
    const [text, setText] = useState(TEST_TEXT);
    const [image, setImage] = useState("");
    const [confirming, setConfirming] = useState(false);
    const [made, setMade] = useState(null);
    const usable = picked.filter(function (platform) { return connected.indexOf(platform) >= 0; });
    function toggle(platform) {
      setPicked(function (current) {
        return current.indexOf(platform) >= 0 ? current.filter(function (item) { return item !== platform; }) : current.concat([platform]);
      });
    }
    async function send() {
      const found = await props.onTest({ platforms: usable, text: text, image_url: image.trim() });
      setConfirming(false);
      if (found) setMade(found.rows || []);
    }
    const names = andList(usable.map(platformName));
    return h(Section, {
      title: "Posting",
      note: "Approved, scheduled pieces post at their time while posting is on here and in House settings. A piece more than " + (posting.late_hours || 6) + " hours late waits for a new time.",
    },
      !posting.on && connected.length ? h("div", { className: "hs-callout hs-row hs-spread" },
        h("span", null, "Posting is off for the whole house. This brand will not post until it is on there too."),
        h("button", { type: "button", className: "hs-tab hs-tab-sm", onClick: props.onOpenHouse }, "Open House settings")) : null,
      h(SaveCheck, {
        checked: posting.brand_on, disabled: props.busy, onChange: props.onToggle,
        title: "Post from " + props.brandName, note: "Off until checked. Turning it off stops this brand; scheduled pieces wait.",
      }),
      connected.length ? h("div", { className: "hs-row hs-gap-sm" },
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: props.onCheck }, "Check posting"),
        h("span", { className: "hs-hint" }, "Proves each account can post, and shows the answer on its row above. Nothing visible is left behind.")) : h("p", { className: "hs-note" }, "Connect an account above before posting."),
      connected.length ? h(Section, { title: "Send a test post", collapsible: true, note: "A real, public post marked as a test. Delete it from here afterwards." },
        h("fieldset", { className: "hs-pick" },
          h("legend", { className: "hs-name" }, "Post it on"),
          h("div", { className: "hs-row hs-gap-sm" }, connected.map(function (platform) {
            return h("label", { key: platform, className: "hs-note" },
              h("input", { type: "checkbox", checked: picked.indexOf(platform) >= 0, onChange: function () { toggle(platform); } }),
              h("span", null, platformName(platform)));
          }))),
        field("Words", h("textarea", { className: "hs-area", rows: 2, maxLength: 500, value: text, onChange: function (event) { setText(event.target.value); } })),
        field("Image address", h("input", { className: "hs-field", type: "url", inputMode: "url", placeholder: "https://", value: image, onChange: function (event) { setImage(event.target.value); } }),
          "Optional. Instagram needs one, and it must be a public https JPEG."),
        confirming ? h("div", { className: "hs-danger-zone is-open", role: "alertdialog", "aria-label": "Confirm the test post" },
          h("p", null, "This posts publicly on " + names + " as " + props.brandName + "."),
          h("div", { className: "hs-row" },
            h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: send }, "Post the test"),
            h("button", { type: "button", className: "hs-tab", onClick: function () { setConfirming(false); } }, "Cancel")))
          : h("div", { className: "hs-row" },
            h("button", { type: "button", className: "hs-button", disabled: props.busy || !usable.length || !text.trim(), onClick: function () { setConfirming(true); } }, usable.length ? "Send a test to " + names : "Pick a platform")),
        made && made.some(function (row) { return !row.ok; }) ? h("ul", { className: "hs-checks", "aria-label": "Test result" }, made.filter(function (row) { return !row.ok; }).map(function (row) {
          return h("li", { key: row.platform, className: row.ok ? "is-ok" : "is-bad" },
            h("span", { className: "hs-check-mark", "aria-hidden": "true" }, row.ok ? "✓" : "✕"),
            h("span", null, h("strong", null, platformName(row.platform) + ": "), row.detail));
        })) : null,
        tests.length ? h("ul", { className: "hs-rows" }, tests.map(function (item) {
          return h("li", { key: item.id, className: "hs-list-row" + (item.deleted ? " is-muted" : "") },
            h("div", { className: "hs-list-main" },
              h("strong", null, platformName(item.platform) + " test"),
              h("span", { className: "hs-meta" }, String(item.at || "").replace("T", " ").slice(0, 16) + (item.deleted ? " · deleted" : ""))),
            h("div", { className: "hs-row hs-gap-xs" },
              item.permalink ? h("a", { href: item.permalink, target: "_blank", rel: "noopener noreferrer" }, "Open") : null,
              !item.deleted && item.platform !== "instagram" ? h("button", { type: "button", className: "hs-chip-button", disabled: props.busy, onClick: function () { props.onDeleteTest(item.id); } }, "Delete") : null,
              !item.deleted && item.platform === "instagram" ? h("span", { className: "hs-hint" }, "Delete it in the Instagram app.") : null));
        })) : null) : null);
  }

  function Accounts(props) {
    const studio = props.studio || {};
    const connections = studio.connections || [];
    const pull = studio.pull || {};
    const feed = studio.feed || [];
    const apps = props.apps || {};
    const choice = props.choice && props.choice.brand_id === props.brand.id ? props.choice : null;
    const [leaving, setLeaving] = useState("");
    const [form, setForm] = useState({ platform: "facebook", external_id: "", token: "" });
    const byPlatform = {};
    connections.forEach(function (item) { byPlatform[item.platform] = item; });
    const metaReady = appReady(apps, "meta");
    const threadsReady = appReady(apps, "threads");
    const missing = [!metaReady ? "Meta" : "", !threadsReady ? "Threads" : ""].filter(Boolean);
    function setField(name, value) {
      setForm(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    const houseRow = form.platform === "threads" ? (apps.threads || {}) : (apps.meta || {});
    const houseName = form.platform === "threads" ? "Threads" : "Meta";
    async function paste(event) {
      event.preventDefault();
      const saved = await props.onSave({ platform: form.platform, external_id: form.external_id, token: form.token });
      if (saved) setForm({ platform: form.platform, external_id: "", token: "" });
    }
    return h("div", { className: "hs-main" },
      missing.length ? h("div", { className: "hs-callout hs-row hs-spread" },
        h("span", null, "The house " + missing.join(" and ") + " app" + (missing.length > 1 ? "s are" : " is") + " not set yet. Connect needs an app id and its secret."),
        h("button", { type: "button", className: "hs-tab hs-tab-sm", onClick: props.onOpenHouse }, "Open House settings")) : null,
      choice ? h(AccountPicker, { key: choice.choice, choice: choice, busy: props.busy, onChoose: props.onChoose, onCancel: props.onCancelChoice }) : null,
      h(Section, {
        title: "Connected accounts",
        note: "Connect opens the Facebook or Threads sign-in. You come back here to pick what belongs to " + props.brand.name + ".",
        actions: connections.length ? [h("button", { key: "pull", type: "button", className: choice ? "hs-tab" : "hs-button", disabled: props.busy, onClick: props.onPull }, "Pull posts")] : null,
      },
        h("ul", { className: "hs-rows" }, ACCOUNT_ROWS.map(function (row) {
          return h(AccountRow, {
            key: row.platform, row: row, item: byPlatform[row.platform], busy: props.busy,
            ready: row.app === "meta" ? metaReady : threadsReady,
            leaving: leaving === row.platform,
            quiet: !!choice,
            account: ((studio.publishing || {}).accounts || {})[row.platform],
            foundInstagram: !!(byPlatform.instagram && byPlatform.instagram.via === "facebook"),
            onConnect: props.onConnect,
            onLeave: function () { setLeaving(row.platform); },
            onKeep: function () { setLeaving(""); },
            onDisconnect: async function () {
              const gone = await props.onDisconnect(row.platform);
              if (gone) setLeaving("");
            },
          });
        })),
        pull.pulled_at ? h("p", { className: "hs-note" }, "Last pull " + String(pull.pulled_at).replace("T", " ").slice(0, 16) + " · " + pull.count + " posts.") : null,
        (pull.errors || []).map(function (item) { return h("p", { key: item, className: "hs-error" }, item); })),
      h(PostingPanel, {
        posting: studio.publishing, brandName: props.brand.name, busy: props.busy,
        connected: ACCOUNT_ROWS.map(function (row) { return row.platform; }).filter(function (platform) { return byPlatform[platform]; }),
        onToggle: props.onBrandPosting, onCheck: props.onCheck, onTest: props.onTest, onDeleteTest: props.onDeleteTest,
        onOpenHouse: props.onOpenHouse,
      }),
      h(Section, { title: "Paste a token instead", collapsible: true, note: "For a token made by hand, such as a system user's Page token." },
        h("form", { className: "hs-stack", onSubmit: paste },
          h("div", { className: "hs-grid-2" },
            field("Platform", h("select", { className: "hs-field", value: form.platform, onChange: function (event) { setField("platform", event.target.value); } },
              PLATFORMS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); }))),
            field(form.platform === "facebook" ? "Page id" : "Account id", h("input", { className: "hs-field", value: form.external_id, autoComplete: "off", onChange: function (event) { setField("external_id", event.target.value); } })),
            field(form.platform === "facebook" ? "Page token" : "Token", h("input", { className: "hs-field", type: "password", value: form.token, autoComplete: "off", onChange: function (event) { setField("token", event.target.value); } }),
              "Written to the vault. Leave it empty to keep the saved one.")),
          h("p", { className: "hs-hint" }, houseRow.app_id ? "Uses the house " + houseName + " app " + houseRow.app_id + "." : "Add the house " + houseName + " app id in House settings first."),
          h("div", { className: "hs-row" },
            h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !houseRow.app_id || !form.external_id.trim() }, "Save connection")))),
      h(Section, { title: "On the page", note: "What already went out, newest first." },
        h(PostRows, { posts: feed, empty: connections.length ? "Pull to see what already went out." : "Connect an account, then pull to see what already went out." })),
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
    ["auto", "Fully autonomous", "The agent schedules and posts what it writes, inside the limits below, once you confirm the switch."],
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
        pick === "auto" ? h("p", { className: "hs-warn" }, "Fully autonomous lets the agent schedule and post without asking each time, while posting is on. You can switch back whenever you like.") : null,
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
        props.onSupport({ action: "mail", cadence: "immediate", body: form.body, quiet_start: Number(form.quiet_start), quiet_end: Number(form.quiet_end) });
      },
    },
      h("div", { className: "hs-grid-3" },
        field("Body", h("select", { className: "hs-field", value: form.body, onChange: function (event) { setField("body", event.target.value); } },
          h("option", { value: "short" }, "Facebook words only"),
          h("option", { value: "full" }, "All three versions"))),
        field("Quiet from", h("select", { className: "hs-field", value: form.quiet_start, onChange: function (event) { setField("quiet_start", event.target.value); } },
          hours.map(function (hour) { return h("option", { key: hour, value: String(hour) }, hourLabel(hour)); }))),
        field("Quiet until", h("select", { className: "hs-field", value: form.quiet_end, onChange: function (event) { setField("quiet_end", event.target.value); } },
          hours.map(function (hour) { return h("option", { key: hour, value: String(hour) }, hourLabel(hour)); })))),
      h("p", { className: "hs-hint" }, form.quiet_start === form.quiet_end ? "Same start and end means no quiet hours. Mail goes out right away." : "Eastern time. Mail asked for in quiet hours goes out when they end."),
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
      h(Section, { title: "Profile", note: "Public handles and the website. A handle is not a credential; accounts connect on the Accounts desk." },
        h(ProfileForm, { brand: brand, handles: props.handles, setHandles: props.setHandles, busy: props.busy, onSave: props.onSave, onSaveSite: props.onSaveSite })),
      h(Section, { title: "How far the desk acts", note: "The mode decides what starts without you. Manual and approval need a person to approve every post. Posting itself is switched on under Accounts." },
        h(ModePanel, { mode: studio.modes, busy: props.busy, onMode: props.onMode })),
      h(Section, { title: "Pause", note: "Stops new work for a stretch of days without changing the mode.", collapsible: true, open: !!(support.pause && support.pause.start) },
        h(PausePanel, { pause: support.pause, busy: props.busy, onSupport: props.onSupport })),
      h(Section, { title: "Guardrails", note: "Limits on what autonomous modes may schedule.", collapsible: true, open: !!((support.mix || []).length) },
        h("div", { className: "hs-name" }, "Content mix"),
        h(MixPanel, { mix: support.mix, pillars: brand.pillars, busy: props.busy, onSupport: props.onSupport }),
        h("div", { className: "hs-name" }, "Pace"),
        h(LimitsForm, { limits: mode.limits, busy: props.busy, onMode: props.onMode })),
      h(Section, { title: "Approval email", note: "How this brand's approval email reads. Who gets it is set on the Approval desk; the sender is in House settings.", collapsible: true },
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
              h("span", { className: "hs-status is-" + (piece.status || "draft") }, statusLabel(piece.status)),
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
            h("span", { className: "hs-status is-" + (piece.status || "draft") }, statusLabel(piece.status)),
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
        h("span", { className: "hs-hint" }, "Scheduling holds the time. It posts then while posting is on for this brand."),
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
    const [view, setView] = useState(function () {
      const saved = recall("calendar-view");
      return ["month", "week", "day"].indexOf(saved) >= 0 ? saved : "month";
    });
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

  const COPY_ROLES = [["copy", "Copy"], ["hook", "Hook"], ["cta", "Call to action"], ["hashtags", "Hashtags"], ["bio", "Bio"]];

  function AddAsset(props) {
    const [draft, setDraft] = useState({ kind: "copy", role: "copy", name: "", folder: "", tags: "", body: "" });
    const [files, setFiles] = useState(null);
    const [picker, setPicker] = useState(0);
    const textual = draft.kind === "copy" || draft.kind === "template";
    function setField(name, value) {
      setDraft(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    function save(event) {
      event.preventDefault();
      readAssetFiles(files || []).then(async function (packed) {
        const body = {
          kind: draft.kind,
          name: draft.name,
          folder: draft.folder,
          tags: draft.tags.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
          note: textual ? "" : draft.body,
          body: textual ? draft.body : "",
          role: textual ? draft.role : "",
        };
        if (draft.kind === "carousel") body.files = packed;
        else if (packed[0]) {
          body.data = packed[0].data;
          body.file_name = packed[0].name;
        }
        const saved = await props.onSave(body);
        if (saved) {
          setDraft({ kind: draft.kind, role: draft.role, name: "", folder: draft.folder, tags: "", body: "" });
          setFiles(null);
          setPicker(picker + 1);
        }
      }).catch(function (err) { if (props.onFail) props.onFail(messageOf(err)); });
    }
    return h("form", { className: "hs-stack", onSubmit: save },
      h("div", { className: "hs-grid-3" },
        field("Kind", h("select", { className: "hs-field", value: draft.kind, onChange: function (event) { setField("kind", event.target.value); } },
          ASSET_KINDS.map(function (item) { return h("option", { key: item, value: item }, item); }))),
        field("Name", h("input", { className: "hs-field", value: draft.name, onChange: function (event) { setField("name", event.target.value); } })),
        textual ? field("Role", h("select", { className: "hs-field", value: draft.role, onChange: function (event) { setField("role", event.target.value); } },
          COPY_ROLES.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); })), "Hooks, calls to action, hashtags, and bios insert into the composer.")
          : field(draft.kind === "carousel" ? "Files" : "File", h("input", {
            key: picker,
            className: "hs-field", type: "file", multiple: draft.kind === "carousel",
            accept: "image/png,image/jpeg,image/webp,image/gif,video/mp4,video/webm",
            onChange: function (event) { setFiles(event.target.files); },
          }), draft.kind === "carousel" ? "Choose the frames in order." : null)),
      field(textual ? "The words" : "Note on the file", h("textarea", { className: "hs-area hs-short", value: draft.body, onChange: function (event) { setField("body", event.target.value); } })),
      h("div", { className: "hs-grid-2" },
        field("Folder", h("input", { className: "hs-field", value: draft.folder, placeholder: "cards/ember", onChange: function (event) { setField("folder", event.target.value); } })),
        field("Tags", h("input", { className: "hs-field", value: draft.tags, placeholder: "Comma separated", onChange: function (event) { setField("tags", event.target.value); } }))),
      h("div", { className: "hs-row" },
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !draft.name.trim() }, "Save to the library")));
  }

  function Library(props) {
    const shelf = props.library || { assets: [], folders: [], tags: [] };
    const assets = shelf.assets || [];
    const [q, setQ] = useState("");
    const [kind, setKind] = useState("all");
    const [folder, setFolder] = useState("all");
    const [tag, setTag] = useState("all");
    const [openId, setOpenId] = useState("");
    const [sort, setSort] = useState("updated");
    const visible = assets.filter(function (asset) {
      if (kind !== "all" && asset.kind !== kind) return false;
      if (folder !== "all" && asset.folder !== folder && String(asset.folder || "").indexOf(folder + "/") !== 0) return false;
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
    const filtered = q.trim() || kind !== "all" || folder !== "all" || tag !== "all";
    return h("div", { className: "hs-main" },
      h(Section, { title: "Add to the library", collapsible: true, open: !assets.length },
        h(AddAsset, { busy: props.busy, onSave: props.onSave, onFail: props.onFail })),
      h("div", { className: "hs-cal-filters" },
        h("input", { className: "hs-field hs-grow", type: "search", "aria-label": "Search the library", value: q, placeholder: "Search name, tag, folder, or words", onChange: function (event) { setQ(event.target.value); } }),
        h("select", { className: "hs-field", "aria-label": "Kind", value: kind, onChange: function (event) { setKind(event.target.value); } },
          h("option", { value: "all" }, "All kinds"),
          ASSET_KINDS.map(function (item) { return h("option", { key: item, value: item }, item); })),
        (shelf.folders || []).length ? h("select", { className: "hs-field", "aria-label": "Folder", value: folder, onChange: function (event) { setFolder(event.target.value); } },
          h("option", { value: "all" }, "All folders"),
          (shelf.folders || []).map(function (item) { return h("option", { key: item, value: item }, item); })) : null,
        (shelf.tags || []).length ? h("select", { className: "hs-field", "aria-label": "Tag", value: tag, onChange: function (event) { setTag(event.target.value); } },
          h("option", { value: "all" }, "All tags"),
          (shelf.tags || []).map(function (item) { return h("option", { key: item, value: item }, item); })) : null,
        h("select", { className: "hs-field", "aria-label": "Sort", value: sort, onChange: function (event) { setSort(event.target.value); } },
          h("option", { value: "updated" }, "Newest"),
          h("option", { value: "mean" }, "Highest mean"),
          h("option", { value: "quiet" }, "Least recently used")),
        filtered ? h("button", { type: "button", className: "hs-link-button", onClick: function () { setQ(""); setKind("all"); setFolder("all"); setTag("all"); } }, "Clear") : null),
      !assets.length ? h(Empty, null, "Nothing in this library yet. Add copy, a template, or a file above.")
        : h("div", { className: "hs-lib" },
          visible.length ? h("ul", { className: "hs-rows" }, shown.map(function (asset) {
            const on = open && open.id === asset.id;
            return h("li", { key: asset.id },
              h("button", {
                type: "button", className: "hs-row-button hs-row-tall" + (on ? " is-on" : ""), "aria-current": on ? "true" : null,
                onClick: function () { setOpenId(asset.id); },
              },
                h("span", { className: "hs-list-main" },
                  h("span", null, h("strong", null, asset.name)),
                  h("span", { className: "hs-meta" }, [asset.role || asset.kind, asset.folder, (asset.tags || []).join(", ")].filter(Boolean).join(" · ")),
                  h("span", { className: "hs-meta" }, performanceLine(asset)))));
          })) : h("p", { className: "hs-note" }, "Nothing matches. Clear the search or the filters."),
          open ? h("div", { className: "hs-pillar hs-asset" },
            h("div", { className: "hs-row hs-spread" },
              h("div", { className: "hs-name" }, open.name),
              h("span", { className: "hs-tag" }, open.role || open.kind)),
            open.body ? h("p", { className: "hs-voice hs-pre" }, open.body) : null,
            open.note ? h("p", { className: "hs-note" }, open.note) : null,
            open.mime && open.mime.indexOf("video/") === 0
              ? h("video", { className: "hs-thumb", controls: true, src: assetUrl(open.id) })
              : (open.has_file || (open.frames || []).length)
                ? h("img", { className: "hs-thumb", alt: open.name, src: assetUrl(open.id, "", (open.frames || []).length && !open.mime ? 0 : null) })
                : null,
            h("p", { className: "hs-note" }, performanceLine(open)),
            open.performance && open.performance.pairing_detail ? h("p", { className: open.performance.best_version ? "hs-ok" : "hs-note" }, open.performance.pairing_detail) : null,
            open.performance && open.performance.best_detail ? h("p", { className: "hs-note" }, open.performance.best_detail) : null,
            h("div", { className: "hs-row" },
              props.piece ? h("button", {
                type: "button", className: "hs-button", disabled: props.busy,
                onClick: function () { props.onUse(open.id, { piece_id: props.piece.id }); },
              }, "Attach to the open draft") : null,
              open.kind === "image" || open.kind === "logo" || open.kind === "carousel" ? h("button", {
                type: "button", className: "hs-tab", disabled: props.busy,
                onClick: function () { props.onTags(open.id); },
              }, "Read tags") : null),
            (props.posts || []).length ? field("Record a use on a post", h("select", {
              className: "hs-field", value: "", disabled: props.busy,
              onChange: function (event) {
                if (event.target.value) props.onUse(open.id, { post_id: event.target.value });
                event.target.value = "";
              },
            }, h("option", { value: "" }, "Choose a post…"),
              (props.posts || []).slice(0, 20).map(function (post) {
                return h("option", { key: post.id, value: post.id }, (post.preview || post.id).slice(0, 70));
              }))) : null,
            (open.uses || []).length ? h("div", { className: "hs-stack hs-gap-xs" },
              h("div", { className: "hs-overline" }, "Used on"),
              h("ul", { className: "hs-list" }, open.uses.map(function (use) {
                return h("li", { key: use.id, className: "hs-note" }, use.idea || use.post_id || "Used");
              }))) : null,
            (open.versions || []).length ? h("div", { className: "hs-stack hs-gap-xs" },
              h("div", { className: "hs-overline" }, "Versions"),
              h("ul", { className: "hs-rows" }, open.versions.map(function (version) {
                const best = open.performance && open.performance.best_version === version.id;
                return h("li", { key: version.id, className: "hs-list-row" },
                  h("div", { className: "hs-list-main" },
                    h("div", null, (best ? "Ahead · " : "") + (version.note || "Saved")),
                    version.body ? h("div", { className: "hs-meta" }, version.body.slice(0, 100)) : null),
                  h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onRevise(open.id, { restore: version.id }); } }, "Bring back"));
              }))) : null)
            : h("div", { className: "hs-empty" }, "Choose an asset to see it, where it was used, and its versions.")),
    );
  }

  const REVIEW_GROUPS = [
    ["pending", "Waiting for review", function (status) { return status === "pending"; }],
    ["approved", "Approved", function (status) { return status === "approved"; }],
    ["open", "Not sent for review", function (status) { return ["draft", "planned", "ready", "failed"].indexOf(status || "draft") >= 0; }],
    ["scheduled", "Scheduled", function (status) { return status === "scheduled"; }],
  ];

  function mailLine(mail) {
    if (!mail || !mail.to) return "";
    if (mail.error) return "The email to " + mail.to + " did not send. " + mail.error;
    if (mail.pending) return "Email to " + mail.to + " waits for quiet hours to end.";
    if (mail.sent_at) return "Emailed to " + mail.to + " at " + String(mail.sent_at).replace("T", " ").slice(0, 16) + " UTC. A reply of APPROVE or CHANGES counts.";
    return "";
  }

  function ReviewPanel(props) {
    const item = props.item;
    const [author, setAuthor] = useState(item.waiting || "");
    const [comment, setComment] = useState("");
    const compare = item.compare || {};
    async function decide(decision) {
      const saved = await props.onDecide(item.id, { author: author.trim() || item.waiting, decision: decision, comment: comment });
      if (saved) setComment("");
    }
    return h("div", { className: "hs-review" },
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-tab hs-tab-sm", onClick: function () { props.onOpen(item.id); } }, "Open in the composer"),
        item.status !== "pending" && item.status !== "approved" ? h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onReview(item.id); } }, "Send for review") : null),
      (item.signed || []).length ? h("p", { className: "hs-ok" }, "Signed by " + item.signed.join(", ") + ".") : null,
      mailLine(item.mail) ? h("p", { className: item.mail && item.mail.error ? "hs-error" : "hs-note" }, mailLine(item.mail)) : null,
      h("div", { className: "hs-previews" }, PLATFORMS.filter(function (pair) { return (item.bodies || {})[pair[0]]; }).map(function (pair) {
        return h("div", { key: pair[0], className: "hs-preview" },
          h("div", { className: "hs-name" }, pair[1]),
          h("p", { className: "hs-voice hs-pre" }, item.bodies[pair[0]]));
      })),
      compare.ready ? h("div", { className: "hs-stack" },
        h("div", { className: "hs-overline" }, "What changed since the last version"),
        compare.detail ? h("p", { className: "hs-note" }, compare.detail) : null,
        h("div", { className: "hs-previews" }, (compare.platforms || []).map(function (platform) {
          return h("div", { key: platform.platform, className: "hs-preview" },
            h("div", { className: "hs-row hs-spread" },
              h("div", { className: "hs-name" }, platformName(platform.platform)),
              platform.same ? h("span", { className: "hs-meta" }, "Unchanged") : null),
            (platform.removed || []).map(function (line, index) { return h("p", { key: "r" + index, className: "hs-diff is-removed" }, line); }),
            (platform.added || []).map(function (line, index) { return h("p", { key: "a" + index, className: "hs-diff is-added" }, line); }));
        }))) : h("p", { className: "hs-note" }, compare.detail || "Nothing earlier to compare."),
      (item.comments || []).length || (item.trail || []).length ? h("div", { className: "hs-stack" },
        h("div", { className: "hs-overline" }, "Conversation"),
        h("ul", { className: "hs-thread" },
          (item.comments || []).map(function (note) {
            return h("li", { key: "c" + note.id }, h("strong", null, note.author), " ", note.text);
          }),
          (item.trail || []).map(function (event) {
            return h("li", { key: "t" + event.id, className: "hs-meta" }, event.author + " · " + event.action + (event.text ? " · " + event.text : ""));
          }))) : null,
      h("div", { className: "hs-grid-2" },
        field("Your name", h("input", { className: "hs-field", value: author, placeholder: item.waiting || "Your name", onChange: function (event) { setAuthor(event.target.value); } }),
          item.waiting ? "This step waits on " + item.waiting + "." : null),
        field("Comment", h("input", { className: "hs-field", value: comment, placeholder: "Optional with a decision", onChange: function (event) { setComment(event.target.value); } }))),
      h("div", { className: "hs-row" },
        item.status === "pending" ? h("button", { type: "button", className: "hs-button", disabled: props.busy || !author.trim(), onClick: function () { decide("approved"); } }, "Approve") : null,
        item.status === "pending" ? h("button", { type: "button", className: "hs-tab", disabled: props.busy || !author.trim(), onClick: function () { decide("changes"); } }, "Ask for changes") : null,
        h("button", {
          type: "button", className: "hs-tab", disabled: props.busy || !author.trim() || !comment.trim(),
          onClick: async function () {
            const saved = await props.onComment(item.id, { author: author, text: comment });
            if (saved) setComment("");
          },
        }, "Comment only")));
  }

  function ApprovalDesk(props) {
    const desk = (props.studio && props.studio.approval) || { steps: ["Approver"], pieces: [], notices: [] };
    const [openId, setOpenId] = useState("");
    const pieces = desk.pieces || [];
    useEffect(function () {
      if (!props.focus) return;
      setOpenId(props.focus);
      const node = document.getElementById("hs-review-" + props.focus);
      if (node && node.scrollIntoView) node.scrollIntoView({ block: "start" });
    }, [props.focus, pieces.length]);
    return h("div", { className: "hs-main" },
      (desk.notices || []).length ? h(Section, { title: "Notices" },
        h("ul", { className: "hs-rows" }, desk.notices.map(function (notice) {
          return h("li", { key: notice.id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" }, notice.text),
            h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onRead(notice.id); } }, "Mark read"));
        }))) : null,
      REVIEW_GROUPS.map(function (group) {
        const rows = pieces.filter(function (item) { return group[2](item.status); });
        if (!rows.length && group[0] !== "pending") return null;
        return h(Section, { key: group[0], title: group[1] + " · " + rows.length },
          rows.length ? h("ul", { className: "hs-rows" }, rows.map(function (item) {
            const on = openId === item.id;
            return h("li", { key: item.id, id: "hs-review-" + item.id },
              h("button", {
                type: "button", className: "hs-row-button" + (on ? " is-on" : ""), "aria-expanded": on,
                onClick: function () { setOpenId(on ? "" : item.id); },
              },
                h("span", { className: "hs-status is-" + (item.status || "draft") }, statusLabel(item.status)),
                h("span", { className: "hs-row-text" }, item.idea),
                item.waiting ? h("span", { className: "hs-meta" }, "waiting on " + item.waiting) : null,
                h("span", { className: "hs-chevron", "aria-hidden": "true" }, on ? "▾" : "▸")),
              on ? h(ReviewPanel, { key: item.id, item: item, busy: props.busy, onOpen: props.onOpen, onReview: props.onReview, onDecide: props.onDecide, onComment: props.onComment }) : null);
          })) : h("p", { className: "hs-note" }, "Nothing is waiting for review."));
      }),
      !pieces.length ? h(Empty, null, "No pieces on this desk yet. Send one for review from the Composer or the Queue.") : null,
      h(Section, {
        title: "Review steps",
        note: "One person is a single step. More go in order. With an email, that person is asked by mail when approval email is on in House settings.",
        collapsible: true, open: !(desk.people || []).some(function (row) { return row.email; }),
      },
        h(StepsEditor, { people: desk.people, busy: props.busy, onSave: props.onSteps, mailReady: props.mailReady })),
    );
  }

  function StepsEditor(props) {
    const start = (props.people || []).length ? props.people : [{ name: "Approver", email: "" }];
    const [rows, setRows] = useState(start.map(function (row) { return { name: row.name || "", email: row.email || "" }; }));
    function setRow(index, key, value) {
      setRows(function (current) {
        return current.map(function (row, at) { return at === index ? Object.assign({}, row, { [key]: value }) : row; });
      });
    }
    const named = rows.filter(function (row) { return row.name.trim(); });
    return h("form", {
      className: "hs-stack",
      onSubmit: function (event) {
        event.preventDefault();
        props.onSave(named.map(function (row) { return { name: row.name.trim(), email: row.email.trim() }; }));
      },
    },
      rows.map(function (row, index) {
        return h("div", { key: index, className: "hs-step-row" },
          h("span", { className: "hs-meta" }, (index + 1) + "."),
          h("input", { className: "hs-field", "aria-label": "Step " + (index + 1) + " name", value: row.name, placeholder: "Name", onChange: function (event) { setRow(index, "name", event.target.value); } }),
          h("input", { className: "hs-field", type: "email", "aria-label": "Step " + (index + 1) + " email", value: row.email, placeholder: "Email, to ask by mail", onChange: function (event) { setRow(index, "email", event.target.value); } }),
          rows.length > 1 ? h("button", { type: "button", className: "hs-chip-button", onClick: function () { setRows(rows.filter(function (_, at) { return at !== index; })); } }, "Remove") : h("span", null));
      }),
      h("div", { className: "hs-row hs-gap-sm" },
        h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !named.length }, "Save steps"),
        rows.length < 4 ? h("button", { type: "button", className: "hs-link-button", onClick: function () { setRows(rows.concat([{ name: "", email: "" }])); } }, "+ Add a step") : null,
        props.mailReady ? null : h("span", { className: "hs-hint" }, "Approval email is off in House settings.")));
  }

  function SeriesApply(props) {
    const saved = (props.series && props.series.items) || [];
    const rows = saved.filter(function (item) { return !item.paused; });
    const [picked, setPicked] = useState(rows[0] ? rows[0].id : "");
    const [topic, setTopic] = useState("");
    const current = rows.some(function (item) { return item.id === picked; }) ? picked : (rows[0] ? rows[0].id : "");
    if (!saved.length) return null;
    return h("div", { className: "hs-advice" },
      h("div", { className: "hs-overline" }, "Start from a series"),
      rows.length ? h("form", {
        className: "hs-row hs-gap-sm",
        onSubmit: function (event) {
          event.preventDefault();
          if (current && topic.trim() && props.onApply) props.onApply(current, topic.trim());
        },
      },
        h("select", { className: "hs-field hs-w-md", "aria-label": "Series", value: current, onChange: function (event) { setPicked(event.target.value); } },
          rows.map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); })),
        h("input", { className: "hs-field hs-grow", "aria-label": "New topic", value: topic, placeholder: "A new topic for this series", onChange: function (event) { setTopic(event.target.value); } }),
        h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !topic.trim() }, "Open in the composer"))
        : h("p", { className: "hs-note" }, "Every saved series is paused."));
  }
  function IdeasBoard(props) {
    const board = (props.studio && props.studio.ideas) || { ideas: [], sources: ["spark", "competitor", "trend", "question"], priorities: ["low", "normal", "high"] };
    const [mode, setMode] = useState("board");
    const [source, setSource] = useState("all");
    const [more, setMore] = useState(false);
    const [draft, setDraft] = useState({ text: "", source: "spark", priority: "normal", tags: "", note: "", link: "" });
    const [suggested, setSuggested] = useState([]);
    const [kept, setKept] = useState({});
    const ideas = (board.ideas || []).filter(function (item) {
      return source === "all" || item.source === source;
    });
    const sources = board.sources || [];
    function setField(name, value) {
      setDraft(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    async function save(event) {
      event.preventDefault();
      const saved = await props.onSave({
        text: draft.text,
        source: draft.source,
        priority: draft.priority,
        tags: draft.tags.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
        note: draft.note,
        link: draft.link,
      });
      if (saved) setDraft({ text: "", source: draft.source, priority: draft.priority, tags: "", note: "", link: "" });
    }
    function card(item, inColumn) {
      return h("li", { key: item.id, className: "hs-idea" },
        h("div", { className: "hs-row hs-gap-xs" },
          inColumn === true ? null : h("span", { className: "hs-meta" }, item.source_label),
          item.priority === "high" ? h("span", { className: "hs-tag is-warn" }, "High") : item.priority === "low" ? h("span", { className: "hs-tag" }, "Low") : null,
          item.status === "drafted" ? h("span", { className: "hs-tag" }, "Drafted") : null),
        h("p", { className: "hs-voice" }, item.text),
        item.note ? h("p", { className: "hs-note" }, item.note) : null,
        item.pattern ? h("p", { className: "hs-note" }, item.pattern) : null,
        item.performed ? h("p", { className: "hs-ok" }, "Its draft has a post at least 3× the others.") : null,
        (item.tags || []).length ? h("div", { className: "hs-row hs-gap-xs" }, item.tags.map(function (tag) { return h("span", { key: tag, className: "hs-tag hs-tag-flat" }, tag); })) : null,
        h("div", { className: "hs-row hs-spread" },
          h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onDraft(item.id); } },
            item.status === "drafted" ? "Open the draft" : "Make this a draft"),
          item.link ? h("a", { href: item.link, target: "_blank", rel: "noopener noreferrer", className: "hs-meta" }, "Link") : null));
    }
    const columns = sources.map(function (name) {
      return { id: name, items: ideas.filter(function (item) { return item.source === name; }) };
    });
    const shapes = board.shapes || [];
    const comments = board.comments || [];
    const archive = board.archive || [];
    return h("div", { className: "hs-main" },
      h(Section, { title: "Capture an idea" },
        h("form", { className: "hs-stack", onSubmit: save },
          field("The idea, still rough", h("textarea", { className: "hs-area hs-short", value: draft.text, onChange: function (event) { setField("text", event.target.value); } })),
          h("div", { className: "hs-row" },
            h("select", { className: "hs-field hs-w-md", "aria-label": "Source", value: draft.source, onChange: function (event) { setField("source", event.target.value); } },
              sources.map(function (item) { return h("option", { key: item, value: item }, item); })),
            h("select", { className: "hs-field hs-w-md", "aria-label": "Priority", value: draft.priority, onChange: function (event) { setField("priority", event.target.value); } },
              (board.priorities || []).map(function (item) { return h("option", { key: item, value: item }, item + " priority"); })),
            h("button", { type: "submit", className: "hs-button", disabled: props.busy || !draft.text.trim() }, "Save idea"),
            h("button", { type: "button", className: "hs-link-button", "aria-expanded": more, onClick: function () { setMore(!more); } }, more ? "Fewer fields" : "Tags, link, note…")),
          more ? h("div", { className: "hs-grid-3" },
            field("Tags", h("input", { className: "hs-field", value: draft.tags, placeholder: "Comma separated", onChange: function (event) { setField("tags", event.target.value); } })),
            field("Link", h("input", { className: "hs-field", value: draft.link, placeholder: "https://", onChange: function (event) { setField("link", event.target.value); } })),
            field("Note", h("input", { className: "hs-field", value: draft.note, onChange: function (event) { setField("note", event.target.value); } }))) : null),
        h("div", { className: "hs-row" },
          h("button", {
            type: "button", className: "hs-tab", disabled: props.busy,
            onClick: async function () {
              const found = props.onSuggest ? await props.onSuggest() : null;
              if (found && found.ideas) { setSuggested(found.ideas); setKept({}); }
            },
          }, "Suggest from the voice"),
          suggested.length ? h("button", { type: "button", className: "hs-link-button", onClick: function () { setSuggested([]); } }, "Clear suggestions") : null),
        suggested.length ? h("ul", { className: "hs-options" }, suggested.map(function (text, index) {
          return h("li", { key: "s" + index, className: "hs-option" },
            h("div", { className: "hs-option-text" }, text),
            h("div", { className: "hs-row hs-spread" },
              h("button", {
                type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy || kept[index],
                onClick: async function () {
                  const saved = await props.onSave({ text: text, source: "spark", priority: "normal" });
                  if (saved) setKept(function (current) { return Object.assign({}, current, { [index]: true }); });
                },
              }, kept[index] ? "Kept" : "Keep as an idea"),
              h(FeedbackButtons, { kind: "ideas", target: text, busy: props.busy, onFeedback: props.onFeedback })));
        })) : null,
        board.lesson && board.lesson.detail ? h("p", { className: "hs-note" }, board.lesson.detail) : null),
      h(SeriesApply, { series: props.studio && props.studio.series, busy: props.busy, onApply: props.onApplySeries }),
      h("div", { className: "hs-cal-toolbar" },
        h("div", { className: "hs-row hs-gap-sm" },
          h(Segmented, { label: "Layout", value: mode, options: [["board", "Board"], ["list", "List"]], onChange: setMode }),
          h("select", { className: "hs-field hs-w-lg", "aria-label": "Source", value: source, onChange: function (event) { setSource(event.target.value); } },
            h("option", { value: "all" }, "Every source · " + (board.ideas || []).length),
            sources.map(function (item) {
              const n = (board.ideas || []).filter(function (idea) { return idea.source === item; }).length;
              return h("option", { key: item, value: item }, item + " · " + n);
            })))),
      !(board.ideas || []).length ? h(Empty, null, "No ideas yet. Capture one above, or ask the voice for a few.")
        : mode === "board" ? h("div", { className: "hs-board" }, columns.filter(function (column) { return source === "all" || column.id === source; }).map(function (column) {
          return h("div", { key: column.id, className: "hs-column" },
            h("div", { className: "hs-column-head" }, h("span", null, column.id), h("span", { className: "hs-meta" }, column.items.length)),
            column.items.length ? h("ul", { className: "hs-ideas" }, column.items.map(function (item) { return card(item, true); })) : h("p", { className: "hs-note hs-column-empty" }, "Nothing here."));
        }))
          : ideas.length ? h("ul", { className: "hs-ideas" }, ideas.map(function (item) { return card(item); })) : h("p", { className: "hs-note" }, "No ideas from this source."),
      h(Section, { title: "From the posts", note: "Only what the posts already show. Nothing here is a predicted score.", collapsible: true, open: !!(shapes.length || comments.length) },
        h("div", { className: "hs-name" }, "Ahead after a draft"),
        archive.length ? h("ul", { className: "hs-ideas" }, archive.map(function (item) { return card(item); })) : h("p", { className: "hs-note" }, "No drafted idea has a post that is at least 3× the others yet."),
        h("div", { className: "hs-name" }, "Shapes from posts that are ahead"),
        shapes.length ? h("ul", { className: "hs-rows" }, shapes.map(function (item) {
          return h("li", { key: item.id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" }, h("div", null, item.preview), h("div", { className: "hs-meta" }, item.engagements + " engagements")),
            h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onKeep(item.id); } }, "Keep this shape"));
        })) : h("p", { className: "hs-note" }, "No post is at least 3× the others."),
        h("div", { className: "hs-name" }, "Comments to keep"),
        comments.length ? h("ul", { className: "hs-rows" }, comments.map(function (item) {
          return h("li", { key: item.id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" }, h("div", null, item.text), item.author ? h("div", { className: "hs-meta" }, item.author) : null),
            h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onSave({ text: item.text, source: "comment", inbox_id: item.id, note: item.author || "" }); } }, "Keep as an idea"));
        })) : h("p", { className: "hs-note" }, "No comment is asking for a post yet.")),
    );
  }

  function QueueDesk(props) {
    const queue = (props.studio && props.studio.queue) || { items: [], suggestion: {}, rules: [], formats: [], stages: [], pace: "" };
    const [mode, setMode] = useState("list");
    const [stage, setStage] = useState("all");
    const [picked, setPicked] = useState([]);
    const [posting, setPosting] = useState("");
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
      const tone = item.status === "pending" ? "pending" : item.status === "scheduled" ? "scheduled" : item.status === "failed" ? "failed" : item.status === "ready" ? "ready" : item.status === "published" ? "published" : "draft";
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
          (item.published || []).length ? h("p", { className: "hs-note" }, "Posted on ", (item.published || []).map(function (row, index) {
            return [index ? " · " : "", row.permalink ? h("a", { key: row.platform, href: row.permalink, target: "_blank", rel: "noopener noreferrer" }, platformName(row.platform)) : platformName(row.platform)];
          })) : null,
          item.placeholder ? h("p", { className: "hs-hint" }, "The desk's placeholder. Write the post before it can go out.") : null,
          item.can_post_now && queue.live && !item.placeholder ? (posting === item.id
            ? h("div", { className: "hs-danger-zone is-open", role: "alertdialog", "aria-label": "Post now" },
              h("p", null, "Post this now, in public, to every connected account that has words for it?"),
              h("div", { className: "hs-row" },
                h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: async function () { await props.onPostNow(item.id); setPosting(""); } }, "Post now"),
                h("button", { type: "button", className: "hs-tab", onClick: function () { setPosting(""); } }, "Cancel")))
            : h("div", { className: "hs-row" }, h("button", { type: "button", className: "hs-chip-button", disabled: props.busy, onClick: function () { setPosting(item.id); } }, "Post now…"))) : null,
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

  const STANDINGS = [["all", "All"], ["pinned", "Pinned"], ["demoted", "Lowered"], ["deleted", "Deleted"], ["thin", "Thin"]];
  const STANDING_LABELS = { open: "", pinned: "Pinned", demoted: "Lowered", deleted: "Deleted" };

  function MemoryDesk(props) {
    const desk = (props.studio && props.studio.memory) || { sections: [], timeline: [] };
    const [exported, setExported] = useState("");
    const [filter, setFilter] = useState("all");
    const [resetting, setResetting] = useState(false);
    const [history, setHistory] = useState(false);
    useEffect(function () { props.onSync(); }, []);
    useEffect(function () {
      if (!props.focus) return;
      const node = document.getElementById("hs-memory-" + props.focus);
      if (node && node.scrollIntoView) node.scrollIntoView({ block: "center" });
    }, [props.focus, desk.sections]);
    function keep(line) {
      if (filter === "all") return true;
      if (filter === "thin") return !!line.thin;
      return line.standing === filter;
    }
    const sections = (desk.sections || []).map(function (section) {
      return Object.assign({}, section, { lines: (section.lines || []).filter(keep) });
    }).filter(function (section) { return section.lines.length; });
    const entries = (desk.feedback && desk.feedback.entries) || [];
    const timeline = desk.timeline || [];
    async function exportAs(kind) {
      const found = await props.onExport(kind);
      if (found) setExported(found.body || "");
    }
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-cal-toolbar" },
        h(Segmented, { label: "Show", value: filter, options: STANDINGS, onChange: setFilter }),
        h("div", { className: "hs-row hs-gap-sm" },
          h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { exportAs("markdown"); } }, "Export markdown"),
          h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { exportAs("json"); } }, "Export JSON"),
          h("button", { type: "button", className: "hs-tab hs-tab-sm is-danger", disabled: props.busy, onClick: function () { setResetting(true); } }, "Reset corrections…"))),
      resetting ? h("div", { className: "hs-danger-zone is-open", role: "alertdialog", "aria-label": "Reset corrections" },
        h("p", null, "Reset clears every pin, lower, and delete on this brand. The posts and the patterns they show stay."),
        h("div", { className: "hs-row" },
          h("button", { type: "button", className: "hs-button is-danger", disabled: props.busy, onClick: async function () { await props.onCorrect("reset", ""); setResetting(false); } }, "Reset corrections"),
          h("button", { type: "button", className: "hs-tab", onClick: function () { setResetting(false); } }, "Cancel"))) : null,
      exported ? h("div", { className: "hs-stack" },
        h("textarea", { className: "hs-area hs-mono", readOnly: true, value: exported, "aria-label": "Export" }),
        h("div", { className: "hs-row" },
          h("button", { type: "button", className: "hs-tab hs-tab-sm", onClick: function () { downloadText(exported.trim().charAt(0) === "{" ? "memory.json" : "memory.md", exported, exported.trim().charAt(0) === "{" ? "application/json" : "text/markdown"); } }, "Download"),
          h("button", { type: "button", className: "hs-link-button", onClick: function () { setExported(""); } }, "Close"))) : null,
      sections.length ? sections.map(function (section) {
        return h(Section, { key: section.id, title: section.label + " · " + section.lines.length },
          h("ul", { className: "hs-rows" }, section.lines.map(function (line) {
            const focused = props.focus && props.focus === line.id;
            return h("li", { key: line.id, id: "hs-memory-" + line.id, className: "hs-list-row" + (focused ? " is-focus" : "") + (line.standing === "deleted" ? " is-muted" : "") },
              h("div", { className: "hs-list-main" },
                h("div", { className: "hs-row hs-gap-xs" },
                  h("strong", null, line.title),
                  STANDING_LABELS[line.standing] ? h("span", { className: "hs-tag" + (line.standing === "deleted" ? " is-warn" : "") }, STANDING_LABELS[line.standing]) : null,
                  line.thin ? h("span", { className: "hs-tag hs-tag-flat" }, "Thin") : null),
                h("div", { className: "hs-meta" }, line.detail)),
              h("div", { className: "hs-row hs-gap-xs" },
                line.standing !== "pinned" ? h("button", { type: "button", className: "hs-chip-button", disabled: props.busy, onClick: function () { props.onCorrect("pin", line.id); } }, "Pin") : null,
                line.standing !== "demoted" ? h("button", { type: "button", className: "hs-chip-button", disabled: props.busy, onClick: function () { props.onCorrect("demote", line.id); } }, "Lower") : null,
                line.standing !== "deleted" ? h("button", { type: "button", className: "hs-chip-button", disabled: props.busy, onClick: function () { props.onCorrect("delete", line.id); } }, "Delete") : null,
                line.standing !== "open" ? h("button", { type: "button", className: "hs-chip-button", disabled: props.busy, onClick: function () { props.onCorrect("restore", line.id); } }, "Restore") : null));
          })));
      }) : h(Empty, null, filter === "all" ? "No patterns yet. Ingest or pull posts first." : "No pattern is " + (STANDINGS.find(function (pair) { return pair[0] === filter; }) || ["", filter])[1].toLowerCase() + "."),
      (desk.accuracy || []).length ? h(Section, { title: "How the range held up" },
        h("ul", { className: "hs-list" }, desk.accuracy.map(function (item) { return h("li", { key: item.id, className: "hs-note" }, item.detail); }))) : null,
      h(Section, { title: "Feedback", note: ((desk.feedback && desk.feedback.lines) || ["No feedback yet."]).join(" ") },
        entries.length ? h("ul", { className: "hs-rows" }, entries.map(function (entry) {
          return h("li", { key: entry.id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" },
              h("div", { className: "hs-clamp" }, entry.target),
              h("div", { className: "hs-meta" }, [entry.kind, entry.note].filter(Boolean).join(" · "))),
            h("div", { className: "hs-row hs-gap-xs" },
              h("select", {
                className: "hs-field hs-field-sm hs-w-sm", "aria-label": "Mark", value: entry.verdict, disabled: props.busy,
                onChange: function (event) { props.onFeedback({ action: "correct", id: entry.id, verdict: event.target.value, note: entry.note }); },
              }, VERDICTS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); })),
              h("button", { type: "button", className: "hs-chip-button", disabled: props.busy, onClick: function () { props.onFeedback({ action: "delete", id: entry.id }); } }, "Delete")));
        })) : null),
      h(Section, { title: "Changes · " + timeline.length, collapsible: true },
        timeline.length ? h("ul", { className: "hs-list" }, (history ? timeline : timeline.slice(0, 10)).map(function (item) {
          return h("li", { key: item.id, className: "hs-note" }, [item.kind, item.pattern_id, item.after].filter(Boolean).join(" · "));
        })) : h("p", { className: "hs-note" }, "No changes yet."),
        timeline.length > 10 ? h("button", { type: "button", className: "hs-link-button", onClick: function () { setHistory(!history); } }, history ? "Show fewer" : "Show all " + timeline.length) : null));
  }

  function dayNumber(iso) {
    return Math.round(utcDate(String(iso).slice(0, 10)).getTime() / 86400000);
  }

  // One line a platform on a shared day axis, so the same x is the same day.
  function MapLines(props) {
    const series = (props.series || []).filter(function (row) { return (row.points || []).length; });
    if (!series.length) return h("p", { className: "hs-note" }, "No numbers in this window.");
    const all = series.reduce(function (list, row) { return list.concat(row.points); }, []);
    const days = all.map(function (point) { return dayNumber(point.date); });
    const first = Math.min.apply(null, days);
    const last = Math.max.apply(null, days);
    const span = Math.max(1, last - first);
    const max = Math.max.apply(null, all.map(function (point) { return point.value || 0; }).concat([1]));
    const width = 800;
    const height = 220;
    const pad = { left: 44, right: 12, top: 12, bottom: 26 };
    function x(date) { return pad.left + ((dayNumber(date) - first) / span) * (width - pad.left - pad.right); }
    function y(value) { return height - pad.bottom - ((value || 0) / max) * (height - pad.top - pad.bottom); }
    const firstIso = all.reduce(function (low, point) { return !low || point.date < low ? point.date : low; }, "");
    const lastIso = all.reduce(function (high, point) { return point.date > high ? point.date : high; }, "");
    return h("figure", { className: "hs-chart" },
      h("figcaption", { className: "hs-row hs-spread" },
        h("span", { className: "hs-name" }, "Daily engagements"),
        h("span", { className: "hs-legend" }, series.map(function (row) {
          return h("span", { key: row.platform, className: "hs-note" }, h("span", { className: "hs-swatch", style: { background: PLATFORM_COLORS[row.platform] || NO_COLOR } }), platformName(row.platform));
        }))),
      h("svg", { className: "hs-line-chart", viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": "Daily engagements by platform, " + firstIso + " to " + lastIso },
        [0, 0.5, 1].map(function (step) {
          const value = Math.round(max * step);
          return h("g", { key: step },
            h("line", { x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value), className: "hs-grid-line" }),
            h("text", { x: pad.left - 8, y: y(value) + 4, textAnchor: "end", className: "hs-axis-text" }, formatNumber(value)));
        }),
        h("text", { x: pad.left, y: height - 6, className: "hs-axis-text" }, firstIso.slice(5)),
        h("text", { x: width - pad.right, y: height - 6, textAnchor: "end", className: "hs-axis-text" }, lastIso.slice(5)),
        series.map(function (row) {
          const color = PLATFORM_COLORS[row.platform] || NO_COLOR;
          const sorted = row.points.slice().sort(function (left, right) { return left.date < right.date ? -1 : 1; });
          const d = sorted.map(function (point, index) { return (index ? "L" : "M") + x(point.date).toFixed(1) + " " + y(point.value).toFixed(1); }).join(" ");
          return h("g", { key: row.platform },
            h("path", { d: d, fill: "none", stroke: color, strokeWidth: 2, strokeLinejoin: "round" }),
            sorted.map(function (point) {
              return h("circle", { key: point.date, cx: x(point.date), cy: y(point.value), r: 3.5, fill: color },
                h("title", null, platformName(row.platform) + " · " + point.date + " · " + formatNumber(point.value)));
            }));
        })));
  }

  const HEAT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  function Heatmap(props) {
    const cells = props.cells || [];
    if (!cells.length) return h("p", { className: "hs-note" }, "No post in this window has a local hour.");
    const max = Math.max.apply(null, cells.map(function (cell) { return cell.mean || 0; }).concat([1]));
    const find = {};
    cells.forEach(function (cell) { find[cell.weekday + " " + cell.hour] = cell; });
    const hours = Array.from({ length: 24 }, function (_, index) { return String(index).padStart(2, "0") + ":00"; });
    return h("figure", { className: "hs-chart" },
      h("figcaption", { className: "hs-row hs-spread" },
        h("span", { className: "hs-name" }, "Mean engagements by day and hour"),
        h("span", { className: "hs-meta" }, "Eastern time · darker is higher · highest " + formatNumber(max))),
      h("div", { className: "hs-heat", role: "table", "aria-label": "Mean engagements by weekday and hour" },
        h("div", { className: "hs-heat-row", role: "row" },
          h("span", { role: "columnheader" }),
          hours.map(function (hour, index) { return h("span", { key: hour, role: "columnheader", className: "hs-heat-hour" }, index % 3 === 0 ? hour.slice(0, 2) : ""); })),
        HEAT_DAYS.map(function (day) {
          return h("div", { key: day, className: "hs-heat-row", role: "row" },
            h("span", { role: "rowheader", className: "hs-heat-day" }, day),
            hours.map(function (hour) {
              const cell = find[day + " " + hour];
              const tip = cell ? day + " " + hour + " · mean " + formatNumber(cell.mean) + " · n=" + cell.n : day + " " + hour + " · no posts";
              return h("span", {
                key: hour, role: "cell", title: tip, "aria-label": tip,
                className: "hs-heat-cell" + (cell ? "" : " is-empty"),
                style: cell ? { "--hs-heat": Math.max(0.22, cell.mean / max) } : null,
              });
            }));
        })));
  }

  function MapDesk(props) {
    const map = (props.studio && props.studio.map) || { windows: {}, posts: [], hourly: false, demographics: false };
    const [size, setSize] = useState("28");
    const [view, setView] = useState("overview");
    const [postId, setPostId] = useState("");
    const frame = (map.windows && map.windows[size]) || { cards: {}, series: [], formats: [], heatmap: [], top: [], change: [], followers: [], rates: [] };
    const post = (map.posts || []).find(function (item) { return item.id === postId; }) || (map.posts || [])[0];
    const cards = frame.cards || {};
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-cal-toolbar" },
        h(Segmented, { label: "View", value: view, options: [["overview", "Overview"], ["post", "One post"], ["formats", "Formats and hours"], ["audience", "Audience"]], onChange: setView }),
        h(Segmented, { label: "Window", value: size, options: [["7", "7 days"], ["28", "28 days"], ["90", "90 days"]], onChange: setSize })),
      view === "overview" ? h("div", { className: "hs-stack" },
        h(MapLines, { series: frame.series }),
        h("div", { className: "hs-grid-3 hs-align-start" }, PLATFORMS.map(function (pair) {
          const card = cards[pair[0]] || { detail: "No numbers in this window.", rows: [] };
          const change = (frame.change || []).find(function (item) { return item.platform === pair[0]; });
          return h("div", { key: pair[0], className: "hs-pillar" },
            h("div", { className: "hs-row hs-spread" },
              h("div", { className: "hs-name" }, h("span", { className: "hs-swatch", style: { background: PLATFORM_COLORS[pair[0]] } }), pair[1])),
            (card.rows || []).length ? h("dl", { className: "hs-dl" }, (card.rows || []).map(function (row) {
              return [h("dt", { key: row.label + "t" }, row.label), h("dd", { key: row.label + "d" }, formatNumber(row.value))];
            })) : null,
            card.detail ? h("p", { className: "hs-note" }, card.detail) : null,
            change ? h("p", { className: "hs-note" }, change.detail) : null);
        })),
        (frame.followers || []).map(function (item) { return h("p", { key: item.platform, className: "hs-note" }, item.detail); })) : null,
      view === "post" ? h("div", { className: "hs-stack" },
        map.hourly ? null : h("p", { className: "hs-hint" }, "Hourly counts are not in the pull, so there is no first-48-hours curve."),
        (map.posts || []).length ? field("Post", h("select", { className: "hs-field", value: post ? post.id : "", onChange: function (event) { setPostId(event.target.value); } },
          (map.posts || []).map(function (item) { return h("option", { key: item.id, value: item.id }, platformName(item.platform) + " · " + (item.preview || item.id).slice(0, 80)); }))) : null,
        post ? h(Section, { title: post.preview || "No caption in the pull." },
          h("p", { className: "hs-meta" }, [platformName(post.platform), post.format, String(post.at || "").replace("T", " ").slice(0, 16)].filter(Boolean).join(" · ")),
          h("div", { className: "hs-stats" },
            h(Stat, { label: "Engagements", value: formatNumber(post.engagements), missing: post.engagements == null }),
            h(Stat, { label: "Reach", value: formatNumber(post.impressions), missing: post.impressions == null }),
            (post.parts || []).map(function (part) { return h(Stat, { key: part.label, label: part.label, value: formatNumber(part.value) }); }))) : h("p", { className: "hs-note" }, "No post in the pull.")) : null,
      view === "formats" ? h("div", { className: "hs-stack" },
        h(Section, { title: "Formats" },
          (frame.formats || []).length ? h("ul", { className: "hs-rows" }, (frame.formats || []).map(function (item) {
            return h("li", { key: item.format, className: "hs-list-row" }, h("div", { className: "hs-list-main" }, h("strong", null, item.format), h("span", { className: "hs-meta" }, item.detail)));
          })) : h("p", { className: "hs-note" }, "No format in this window.")),
        h(Heatmap, { cells: frame.heatmap }),
        h(Section, { title: "Top posts" },
          (frame.top || []).length ? h("ul", { className: "hs-rows" }, (frame.top || []).map(function (item) {
            return h("li", { key: item.id, className: "hs-list-row" },
              h("div", { className: "hs-list-main" },
                h("div", { className: "hs-clamp" }, item.preview),
                h("div", { className: "hs-meta" }, [platformName(item.platform), item.format, item.rate == null ? "" : item.rate + " percent"].filter(Boolean).join(" · "))),
              h("span", { className: "hs-num" }, formatNumber(item.engagements)));
          })) : h("p", { className: "hs-note" }, "No posts in this window."))) : null,
      view === "audience" ? h("div", { className: "hs-stack" },
        map.demographics ? null : h("p", { className: "hs-hint" }, "No city or age breakdown was returned, so none is shown."),
        h(Section, { title: "Followers" },
          (frame.followers || []).length ? (frame.followers || []).map(function (item) { return h("p", { key: item.platform, className: "hs-voice" }, item.detail); }) : h("p", { className: "hs-note" }, "No follower numbers in this window.")),
        h(Section, { title: "Rates", note: "Each rate names what it divides by. No rate appears without its denominator." },
          (frame.rates || []).length ? (frame.rates || []).map(function (item) { return h("p", { key: item.label, className: "hs-voice" }, item.detail); }) : h("p", { className: "hs-note" }, "No rate. Reach was not in the pull."))) : null);
  }

  function formatNumber(value) {
    if (value == null || value === "") return "—";
    const number = Number(value);
    if (!isFinite(number)) return String(value);
    return number.toLocaleString("en-US", { maximumFractionDigits: 1 });
  }

  // Bars as HTML: they fill the width, take focus, and say their value.
  function BarChart(props) {
    const points = props.points || [];
    if (!points.length) return h("div", { className: "hs-chart" },
      h("div", { className: "hs-name" }, props.label),
      h("p", { className: "hs-note" }, props.empty || "No numbers yet."));
    const values = points.map(function (point) { return Number(point.value) || 0; });
    const max = Math.max.apply(null, values.concat([1]));
    const every = Math.max(1, Math.ceil(points.length / 12));
    const pickable = !!props.onPick;
    return h("figure", { className: "hs-chart" },
      h("figcaption", { className: "hs-row hs-spread" },
        h("span", { className: "hs-name" }, props.label),
        h("span", { className: "hs-meta" }, "Highest " + formatNumber(max))),
      h("div", { className: "hs-bars", style: { "--hs-bars": points.length } },
        points.map(function (point, index) {
          const on = props.selected === point.id;
          const tip = (point.label || point.id) + ": " + formatNumber(values[index]) + (point.note ? " · " + point.note : "");
          const fill = h("span", { className: "hs-bar-fill", style: { height: Math.max(2, (values[index] / max) * 100) + "%" } });
          return pickable
            ? h("button", { key: point.id, type: "button", className: "hs-bar-col" + (on ? " is-on" : ""), title: tip, "aria-label": tip, "aria-pressed": on, onClick: function () { props.onPick(point); } }, fill)
            : h("div", { key: point.id, className: "hs-bar-col", title: tip, role: "img", "aria-label": tip }, fill);
        })),
      h("div", { className: "hs-bars hs-bar-axis", style: { "--hs-bars": points.length }, "aria-hidden": "true" },
        points.map(function (point, index) {
          return h("span", { key: point.id }, index % every === 0 ? String(point.label || point.id).split(" · ")[0] : "");
        })));
  }

  const METRICS = [
    ["reach", "Reach", "reach_note"],
    ["impressions", "Impressions", "impressions_note"],
    ["engagements", "Engagements", null],
    ["rate", "Rate", "rate_note"],
    ["saves", "Saves", "saves_note"],
    ["shares", "Shares", null],
    ["comments", "Comments", "comments_note"],
    ["clicks", "Clicks", "clicks_note"],
    ["video_completion", "Video completion", "video_note"],
    ["growth", "Follower change", "growth_note"],
  ];

  function Performance(props) {
    const perf = (props.studio && props.studio.performance) || { page_days: [], recorded_days: [], hours: [], posts: [], source: "none", ranges: {} };
    const [range, setRange] = useState("28");
    const [campaign, setCampaign] = useState("");
    const report = (perf.ranges && perf.ranges[range]) || { totals: {}, comparison: { lines: [] }, campaigns: [], formats: [], top: [], bottom: [], patterns: [], alerts: [] };
    const totals = report.totals || {};
    const named = (report.campaigns || []).filter(function (item) { return item.name; });
    const chosen = named.find(function (item) { return item.name === campaign; }) || named[0] || null;
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
      return { id: hour.id, label: hour.label, note: "n=" + hour.n, value: hour.mean, raw: hour };
    });
    const posts = perf.posts || [];
    const picked = pageDays.concat(recordedDays).find(function (day) { return day.id === props.pickedDay; });
    const post = posts.find(function (item) { return item.id === props.pickedPost; });
    const hourPosts = posts.filter(function (item) { return String(item.local_hour) === props.pickedHour; });
    const formatPoints = (report.formats || []).map(function (item) {
      return { id: item.id, label: item.label, note: "n=" + item.n, value: item.mean, raw: item };
    });
    const shown = METRICS.filter(function (metric) { return totals[metric[0]] != null; });
    const missing = METRICS.filter(function (metric) { return totals[metric[0]] == null; });
    const patterns = report.patterns || [];
    const clear = patterns.filter(function (item) { return item.clear; });
    const thin = patterns.filter(function (item) { return !item.clear; });
    function postList(rows, empty) {
      if (!rows.length) return h("p", { className: "hs-note" }, empty);
      return h("ul", { className: "hs-rows" }, rows.map(function (item) {
        return h("li", { key: item.id, className: "hs-list-row" },
          h("div", { className: "hs-list-main" },
            h("div", { className: "hs-clamp" }, item.preview || "Untitled"),
            h("div", { className: "hs-meta" }, [platformName(item.platform), item.format, item.shares != null ? item.shares + " shares" : "", item.saves != null ? item.saves + " saves" : ""].filter(Boolean).join(" · ")),
            (item.reasons || []).map(function (reason) { return h("div", { key: reason, className: "hs-meta" }, reason); })),
          h("div", { className: "hs-row hs-gap-sm" },
            h("span", { className: "hs-num", title: "Engagements" }, formatNumber(item.engagements)),
            item.permalink ? h("a", { href: item.permalink, target: "_blank", rel: "noopener noreferrer" }, "Open") : null));
      }));
    }
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-cal-toolbar" },
        h(Segmented, { label: "Window", value: range, options: [["7", "7 days"], ["28", "28 days"], ["90", "90 days"], ["all", "All"]], onChange: setRange }),
        h("span", { className: "hs-note" }, (totals.posts != null ? totals.posts + " posts in this window" : "") + (perf.imported ? " · " + perf.imported + " imported" : ""))),
      h("div", { className: "hs-stats" }, shown.map(function (metric) {
        return h(Stat, {
          key: metric[0], label: metric[1],
          value: formatNumber(totals[metric[0]]),
          note: metric[0] === "engagements" ? (totals.posts != null ? totals.posts + " posts" : null) : metric[2] ? totals[metric[2]] : null,
        });
      })),
      missing.length ? h("p", { className: "hs-hint" }, "Not in the pull: " + missing.map(function (metric) { return metric[1].toLowerCase(); }).join(", ") + ". They stay missing rather than zero.") : null,
      h("div", { className: "hs-grid-2 hs-align-start" },
        h(Section, { title: (report.comparison && report.comparison.label) || "Against the period before" },
          ((report.comparison && report.comparison.lines) || []).length
            ? h("ul", { className: "hs-list" }, report.comparison.lines.map(function (line) { return h("li", { key: line, className: "hs-note" }, line); }))
            : h("p", { className: "hs-note" }, "Nothing to compare yet.")),
        h(Section, { title: "Patterns", note: clear.length ? null : "Nothing is clear in this window yet." },
          clear.length ? h("ul", { className: "hs-checks" }, clear.map(function (item) {
            return h("li", { key: item.id, className: "is-ok" },
              h("span", { className: "hs-check-mark", "aria-hidden": "true" }, "✓"),
              h("span", null, h("strong", null, item.title + ". "), item.detail));
          })) : null,
          thin.length ? h("details", { className: "hs-more" },
            h("summary", null, "Not clear yet · " + thin.length),
            h("ul", { className: "hs-list" }, thin.map(function (item) { return h("li", { key: item.id, className: "hs-note" }, h("strong", null, item.title + ". "), item.detail); }))) : null,
          (report.alerts || []).length ? h("div", { className: "hs-stack hs-gap-xs" },
            h("div", { className: "hs-overline" }, "Outliers"),
            report.alerts.map(function (item) { return h("p", { key: item.id, className: "hs-voice" }, item.detail); })) : null)),
      h(Section, { title: "Charts", note: usePage ? "Page totals come from the Facebook ledger, a bar a day. They are not estimated." : "No page ledger for this brand, so the daily bars are the posts you logged." },
        h("div", { className: "hs-grid-2" },
          h(BarChart, { label: "Mean engagements by format", points: formatPoints, empty: "No format in this window." }),
          h(BarChart, { label: "Mean engagements by local hour", points: hours, selected: props.pickedHour, onPick: props.onHour, empty: "No hours yet." })),
        hourPosts.length ? h("div", { className: "hs-advice" },
          h("div", { className: "hs-overline" }, "Posted at " + props.pickedHour.padStart(2, "0") + ":00"),
          hourPosts.map(function (item) { return h("p", { key: item.id, className: "hs-note" }, formatNumber(item.engagements) + " · " + (item.preview || item.id)); })) : null,
        h(BarChart, { label: usePage ? "Organic impressions by day" : "Recorded engagements by day", points: days, selected: props.pickedDay, onPick: props.onDay, empty: "No days yet." }),
        engagements.length ? h(BarChart, { label: "Page engagements by day", points: engagements, selected: props.pickedDay, onPick: props.onDay }) : null,
        picked ? h("p", { className: "hs-advice" }, h("strong", null, picked.date), (picked.impressions != null ? " · impressions " + formatNumber(picked.impressions) : "") + " · engagements " + formatNumber(picked.engagements) + (picked.follows != null ? " · follows " + formatNumber(picked.follows) : "")) : null),
      h("div", { className: "hs-grid-2 hs-align-start" },
        h(Section, { title: "Top posts" }, postList(report.top || [], "No posts in this window.")),
        h(Section, { title: "Quiet posts" }, postList(report.bottom || [], "No quiet posts in this window."))),
      named.length ? h(Section, { title: "A campaign against the other posts" },
        h("select", { className: "hs-field hs-w-lg", "aria-label": "Campaign", value: chosen ? chosen.name : "", onChange: function (event) { setCampaign(event.target.value); } },
          named.map(function (item) { return h("option", { key: item.name, value: item.name }, item.name); })),
        chosen ? h("p", { className: "hs-note" }, chosen.detail) : null) : null,
      h(Section, { title: "Every post · " + posts.length, collapsible: true },
        posts.length ? h("ul", { className: "hs-rows" }, posts.map(function (item) {
          const on = props.pickedPost === item.id;
          return h("li", { key: item.id },
            h("button", { type: "button", className: "hs-row-button" + (on ? " is-on" : ""), "aria-expanded": on, onClick: function () { props.onPost(item); } },
              h("span", { className: "hs-num" }, formatNumber(item.engagements)),
              h("span", { className: "hs-row-text" }, item.preview || "Untitled")),
            on && post ? h("div", { className: "hs-review" },
              h("p", { className: "hs-note" }, formatNumber(post.reactions) + " reactions · " + formatNumber(post.comments) + " comments · " + formatNumber(post.shares) + " shares"),
              post.permalink ? h("a", { href: post.permalink, target: "_blank", rel: "noopener noreferrer" }, "Open the post") : null) : null);
        })) : h("p", { className: "hs-note" }, "No posts in this window.")),
      h(Section, { title: "Goals", note: (perf.imported || 0) + " imported posts with a date and an engagement count are in these numbers." },
        (perf.goals || []).length ? h("ul", { className: "hs-list" }, perf.goals.map(function (item) { return h("li", { key: item.id, className: "hs-voice" }, item.detail); })) : h("p", { className: "hs-note" }, "No goal yet."),
        h(GoalForm, { busy: props.busy, onGoal: props.onGoal })),
      h(Section, { title: "Add numbers by hand", note: "For posts the pull cannot see. A missing number stays missing.", collapsible: true },
        field("A CSV of past posts", h("input", {
          className: "hs-field", type: "file", accept: ".csv,text/csv",
          onChange: function (event) {
            const file = event.target.files && event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function () { props.onHistory(String(reader.result || "")); };
            reader.readAsText(file);
            event.target.value = "";
          },
        }), "The Ingest desk maps columns for you, if the CSV has other names."),
        h(RecordForm, { busy: props.busy, onRecorded: props.onRecorded })),
    );
  }

  function GoalForm(props) {
    const [goal, setGoal] = useState({ metric: "engagements", change: "20", start: "", end: "" });
    function setField(name, value) {
      setGoal(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    return h("form", {
      className: "hs-stack",
      onSubmit: async function (event) {
        event.preventDefault();
        const saved = await props.onGoal({ metric: goal.metric, change: Number(goal.change), start: goal.start, end: goal.end });
        if (saved) setGoal(Object.assign({}, goal, { start: "", end: "" }));
      },
    },
      h("div", { className: "hs-grid-4" },
        field("Metric", h("select", { className: "hs-field", value: goal.metric, onChange: function (event) { setField("metric", event.target.value); } },
          ["engagements", "shares", "saves", "reach", "follows"].map(function (metric) { return h("option", { key: metric, value: metric }, metric); }))),
        field("Change, in percent", h("input", { className: "hs-field", inputMode: "decimal", value: goal.change, onChange: function (event) { setField("change", event.target.value); } })),
        field("From", h("input", { className: "hs-field", type: "date", value: goal.start, onChange: function (event) { setField("start", event.target.value); } })),
        field("Through", h("input", { className: "hs-field", type: "date", value: goal.end, min: goal.start || undefined, onChange: function (event) { setField("end", event.target.value); } }))),
      h("div", { className: "hs-row" }, h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !goal.start || !goal.end }, "Save goal")));
  }

  const RECORD_FIELDS = [
    ["impressions", "Impressions"], ["engagements", "Engagements"], ["likes", "Likes"], ["comments", "Comments"], ["shares", "Shares"],
    ["saves", "Saves"], ["follows", "Follows"], ["clicks", "Clicks"], ["video_completion", "Video completion"],
  ];

  function RecordForm(props) {
    const blank = { platform: "facebook", format: "unknown", published_at: "", local_hour: "", note: "" };
    RECORD_FIELDS.forEach(function (pair) { blank[pair[0]] = ""; });
    const [form, setForm] = useState(blank);
    function setField(name, value) { setForm(function (current) { return Object.assign({}, current, { [name]: value }); }); }
    async function submit(event) {
      event.preventDefault();
      const metrics = {};
      RECORD_FIELDS.forEach(function (pair) {
        if (form[pair[0]] !== "") metrics[pair[0]] = Number(form[pair[0]]);
      });
      const body = { platform: form.platform, format: form.format, metrics: metrics, note: form.note, preview: form.note };
      if (form.published_at) body.published_at = new Date(form.published_at).toISOString();
      if (form.local_hour !== "") body.local_hour = Number(form.local_hour);
      const saved = await props.onRecorded(body);
      if (saved) setForm(Object.assign({}, blank, { platform: form.platform }));
    }
    return h("form", { className: "hs-stack", onSubmit: submit },
      h("div", { className: "hs-overline" }, "Record one result"),
      field("What the post was", h("input", { className: "hs-field", value: form.note, onChange: function (event) { setField("note", event.target.value); } })),
      h("div", { className: "hs-grid-4" },
        field("Platform", h("select", { className: "hs-field", value: form.platform, onChange: function (event) { setField("platform", event.target.value); } },
          PLATFORMS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); }))),
        field("Format", h("select", { className: "hs-field", value: form.format, onChange: function (event) { setField("format", event.target.value); } },
          ["unknown"].concat(FORMATS).map(function (item) { return h("option", { key: item, value: item }, item); }))),
        field("Published", h("input", { className: "hs-field", type: "datetime-local", value: form.published_at, onChange: function (event) { setField("published_at", event.target.value); } })),
        field("Local hour", h("input", { className: "hs-field", inputMode: "numeric", placeholder: "0 to 23", value: form.local_hour, onChange: function (event) { setField("local_hour", event.target.value); } }))),
      h("div", { className: "hs-grid-4" }, RECORD_FIELDS.map(function (pair) {
        return h("label", { key: pair[0], className: "hs-note" }, pair[1],
          h("input", { className: "hs-field", inputMode: "decimal", placeholder: "—", value: form[pair[0]], onChange: function (event) { setField(pair[0], event.target.value); } }));
      })),
      h("div", { className: "hs-row" }, h("button", { type: "submit", className: "hs-tab", disabled: props.busy }, "Save result")));
  }

  function SeriesForm(props) {
    const blank = { name: "", structure: "", hook: "", media: "", examples: "", tags: "" };
    const [draft, setDraft] = useState(blank);
    function setField(name, value) {
      setDraft(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    return h("form", {
      className: "hs-stack",
      onSubmit: async function (event) {
        event.preventDefault();
        const saved = await props.onSave({
          name: draft.name,
          structure: draft.structure,
          hook: draft.hook,
          media: draft.media,
          examples: draft.examples.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
          tags: draft.tags.split(",").map(function (item) { return item.trim(); }).filter(Boolean),
        });
        if (saved) setDraft(blank);
      },
    },
      h("div", { className: "hs-grid-2" },
        field("Name", h("input", { className: "hs-field", value: draft.name, placeholder: "Unlearned", onChange: function (event) { setField("name", event.target.value); } })),
        field("Typical hook", h("input", { className: "hs-field", value: draft.hook, placeholder: "What I had to unlearn about", onChange: function (event) { setField("hook", event.target.value); } }))),
      field("Structure", h("textarea", { className: "hs-area hs-short", value: draft.structure, placeholder: "Hook: the thing I had to unlearn about {topic}\nThe old rule\nWhat broke it", onChange: function (event) { setField("structure", event.target.value); } }),
        "One section a line. Write {topic} where the new topic goes."),
      h("div", { className: "hs-grid-3" },
        field("Media note", h("input", { className: "hs-field", value: draft.media, placeholder: "Quote card", onChange: function (event) { setField("media", event.target.value); } })),
        field("Example post ids", h("input", { className: "hs-field", value: draft.examples, placeholder: "Comma separated", onChange: function (event) { setField("examples", event.target.value); } })),
        field("Tags", h("input", { className: "hs-field", value: draft.tags, placeholder: "A pillar, or free text", onChange: function (event) { setField("tags", event.target.value); } }))),
      h("div", { className: "hs-row" },
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !draft.name.trim() || !draft.structure.trim() }, "Save series")));
  }

  function SeriesDesk(props) {
    const desk = (props.studio && props.studio.series) || { items: [], suggestions: [] };
    const [filled, setFilled] = useState({});
    const [q, setQ] = useState("");
    const [tag, setTag] = useState("all");
    const all = desk.items || [];
    const items = all.filter(function (item) {
      const blob = (item.name + " " + item.hook + " " + (item.structure || []).join(" ") + " " + (item.tags || []).join(" ")).toLowerCase();
      if (q.trim() && blob.indexOf(q.trim().toLowerCase()) < 0) return false;
      if (tag !== "all" && (item.tags || []).indexOf(tag) < 0) return false;
      return true;
    });
    return h("div", { className: "hs-main" },
      h(SeriesApply, { series: desk, busy: props.busy, onApply: props.onApply }),
      (desk.suggestions || []).length ? h(Section, { title: "Shapes that are already ahead", note: "Keep one to make it a series on this brand." },
        h("ul", { className: "hs-options" }, desk.suggestions.map(function (item) {
          return h("li", { key: item.id, className: "hs-option" },
            h("div", { className: "hs-option-text" }, item.detail),
            h("div", { className: "hs-row hs-spread" },
              h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onKeep(item.id); } }, "Keep " + item.name),
              h(FeedbackButtons, { kind: "series", target: item.id, busy: props.busy, onFeedback: props.onFeedback })));
        }))) : null,
      h(Section, { title: "New series", collapsible: true, open: !all.length },
        h(SeriesForm, { busy: props.busy, onSave: props.onSave })),
      all.length > 2 ? h("div", { className: "hs-cal-filters" },
        h("input", { className: "hs-field hs-grow", type: "search", "aria-label": "Search series", value: q, placeholder: "Search name, hook, or structure", onChange: function (event) { setQ(event.target.value); } }),
        (desk.tags || []).length ? h("select", { className: "hs-field", "aria-label": "Tag", value: tag, onChange: function (event) { setTag(event.target.value); } },
          h("option", { value: "all" }, "All tags"),
          (desk.tags || []).map(function (name) { return h("option", { key: name, value: name }, name); })) : null) : null,
      !all.length ? h(Empty, null, "No series on this brand yet. Save one above, or keep a shape that is already ahead.")
        : items.length ? items.map(function (item) {
          const fill = filled[item.id];
          return h("section", { key: item.id, className: "hs-section" + (item.paused ? " is-paused" : "") },
            h("div", { className: "hs-section-head" },
              h("div", { className: "hs-section-titles" },
                h("div", { className: "hs-row hs-gap-xs" },
                  h("h3", { className: "hs-h3" }, item.name),
                  item.paused ? h("span", { className: "hs-tag is-warn" }, "Paused") : null,
                  (item.tags || []).map(function (name) { return h("span", { key: name, className: "hs-tag hs-tag-flat" }, name); })),
                [item.hook, item.media].filter(Boolean).length ? h("p", { className: "hs-note" }, [item.hook, item.media].filter(Boolean).join(" · ")) : null),
              h("div", { className: "hs-row hs-gap-sm" },
                h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy || item.paused, title: item.paused ? "Resume it first" : "Fill with a pillar this brand already has", onClick: async function () {
                  const saved = props.onFill ? await props.onFill(item.id) : null;
                  if (saved && saved.lines) setFilled(function (current) { return Object.assign({}, current, { [item.id]: saved }); });
                } }, "Fill from a pillar"),
                h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { if (props.onPause) props.onPause(item.id, !item.paused); } }, item.paused ? "Resume" : "Pause"))),
            h("ol", { className: "hs-steps" }, (item.structure || []).map(function (line, index) { return h("li", { key: index }, line); })),
            item.stats && item.stats.detail ? h("p", { className: "hs-note" }, item.stats.detail) : null,
            item.notice ? h("p", { className: "hs-warn" }, item.notice) : null,
            item.paused ? h("p", { className: "hs-hint" }, "Paused. Fill and the composer stay off until you resume it.") : null,
            fill ? h("div", { className: "hs-advice" },
              h("div", { className: "hs-row hs-spread" },
                h("div", { className: "hs-overline" }, "Filled with " + fill.topic + " · not saved"),
                h("button", { type: "button", className: "hs-link-button", onClick: function () { setFilled(function (current) { const next = Object.assign({}, current); delete next[item.id]; return next; }); } }, "Clear")),
              (fill.lines || []).map(function (line, index) { return h("p", { key: "fill-" + index, className: "hs-voice" }, line); })) : null,
            (item.examples || []).length ? h("div", { className: "hs-stack hs-gap-xs" },
              h("div", { className: "hs-overline" }, "Examples"),
              h("ul", { className: "hs-list" }, item.examples.map(function (example) {
                return h("li", { key: example.id, className: "hs-note" }, (example.engagements == null ? "Not in the pull" : example.engagements + " engagements") + " · " + example.preview);
              }))) : null);
        }) : h("p", { className: "hs-note" }, "No series matches. Clear the search or the tag."));
  }

  function CampaignForm(props) {
    const kinds = props.kinds || ["launch", "seasonal", "evergreen"];
    const blank = { name: "", kind: kinds[0], goal: "", goal_posts: "", start: "", end: "", note: "", template: false };
    const [draft, setDraft] = useState(blank);
    function setField(name, value) {
      setDraft(function (current) { return Object.assign({}, current, { [name]: value }); });
    }
    return h("form", {
      className: "hs-stack",
      onSubmit: async function (event) {
        event.preventDefault();
        const saved = await props.onSave({
          name: draft.name, kind: draft.kind, goal: draft.goal,
          goal_posts: draft.goal_posts ? Number(draft.goal_posts) : "",
          start: draft.start, end: draft.end, note: draft.note, template: draft.template,
        });
        if (saved) setDraft(Object.assign({}, blank, { kind: draft.kind }));
      },
    },
      h("div", { className: "hs-grid-3" },
        field("Name", h("input", { className: "hs-field", value: draft.name, onChange: function (event) { setField("name", event.target.value); } })),
        field("Kind", h("select", { className: "hs-field", value: draft.kind, onChange: function (event) { setField("kind", event.target.value); } },
          kinds.map(function (kind) { return h("option", { key: kind, value: kind }, kind); }))),
        field("Posts", h("input", { className: "hs-field", inputMode: "numeric", value: draft.goal_posts, placeholder: "How many", onChange: function (event) { setField("goal_posts", event.target.value.replace(/[^0-9]/g, "")); } }))),
      field("Goal", h("input", { className: "hs-field", value: draft.goal, placeholder: "In words", onChange: function (event) { setField("goal", event.target.value); } })),
      h("div", { className: "hs-grid-3" },
        field("Starts", h("input", { className: "hs-field", type: "date", value: draft.start, onChange: function (event) { setField("start", event.target.value); } })),
        field("Ends", h("input", { className: "hs-field", type: "date", value: draft.end, min: draft.start || undefined, onChange: function (event) { setField("end", event.target.value); } })),
        field("Note", h("input", { className: "hs-field", value: draft.note, onChange: function (event) { setField("note", event.target.value); } }))),
      h("label", { className: "hs-note" },
        h("input", { type: "checkbox", checked: draft.template, onChange: function (event) { setField("template", event.target.checked); } }),
        h("span", null, h("span", { className: "hs-check-title" }, "Keep as a template"), " Clone it later for the next launch.")),
      h("div", { className: "hs-row" },
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !draft.name.trim() }, "Save campaign")));
  }

  function CampaignsDesk(props) {
    const board = (props.studio && props.studio.campaigns) || { campaigns: [], kinds: ["launch", "seasonal", "evergreen"], lessons: [] };
    const [openId, setOpenId] = useState("");
    const campaigns = board.campaigns || [];
    return h("div", { className: "hs-main" },
      (board.lessons || []).length ? h("div", { className: "hs-advice" }, board.lessons.map(function (item) {
        return h("p", { key: item.kind || item.detail, className: item.ahead ? "hs-ok" : "hs-note" }, item.detail + (item.approach ? " " + item.approach : ""));
      })) : null,
      h(Section, { title: "New campaign", collapsible: true, open: !campaigns.length },
        h(CampaignForm, { kinds: board.kinds, busy: props.busy, onSave: props.onSave })),
      !campaigns.length ? h(Empty, null, "No campaigns yet. A campaign holds the posts, the assets, the goal, and the dates.")
        : h("ul", { className: "hs-rows" }, campaigns.map(function (item) {
          const progress = item.progress || {};
          const performance = item.performance || {};
          const retro = item.retrospective || {};
          const on = openId === item.id;
          const share = progress.goal_posts ? Math.min(1, (progress.posts || 0) / progress.goal_posts) : null;
          const loosePieces = (props.pieces || []).filter(function (piece) { return !(item.pieces || []).some(function (row) { return row.id === piece.id; }); });
          const looseAssets = ((props.library && props.library.assets) || []).filter(function (asset) { return !(item.assets || []).some(function (row) { return row.id === asset.id; }); });
          return h("li", { key: item.id },
            h("button", { type: "button", className: "hs-row-button hs-row-tall" + (on ? " is-on" : ""), "aria-expanded": on, onClick: function () { setOpenId(on ? "" : item.id); } },
              h("span", { className: "hs-list-main" },
                h("span", { className: "hs-row hs-gap-xs" },
                  h("strong", null, item.name),
                  h("span", { className: "hs-tag hs-tag-flat" }, item.kind),
                  item.template ? h("span", { className: "hs-tag" }, "Template") : null),
                h("span", { className: "hs-meta" }, [progress.phase, (progress.posts || 0) + (progress.goal_posts ? " of " + progress.goal_posts : "") + " posts", (progress.assets || 0) + " assets", [item.start, item.end].filter(Boolean).join(" – ")].filter(Boolean).join(" · ")),
                share != null ? h("span", { className: "hs-meter", "aria-hidden": "true" }, h("span", { style: { width: Math.round(share * 100) + "%" } })) : null),
              h("span", { className: "hs-chevron", "aria-hidden": "true" }, on ? "▾" : "▸")),
            on ? h("div", { className: "hs-review" },
              item.goal ? h("p", { className: "hs-voice" }, item.goal) : null,
              h("p", { className: "hs-note" }, (progress.making || 0) + " still being made · " + (progress.out || 0) + " in the queue"),
              performance.detail ? h("p", { className: "hs-note" }, performance.detail) : null,
              performance.posts ? h("p", { className: "hs-note" }, formatNumber(performance.engagements) + " engagements · " + formatNumber(performance.shares) + " shares" + (performance.saves == null ? "" : " · " + formatNumber(performance.saves) + " saves")) : null,
              retro.detail ? h("p", { className: retro.ahead ? "hs-ok" : "hs-note" }, retro.detail) : null,
              (item.pieces || []).length ? h("div", { className: "hs-stack hs-gap-xs" },
                h("div", { className: "hs-overline" }, "Pieces"),
                h("ul", { className: "hs-rows" }, item.pieces.map(function (piece) {
                  return h("li", { key: piece.id },
                    h("button", { type: "button", className: "hs-row-button", onClick: function () { props.onOpen(piece.id); } },
                      h("span", { className: "hs-status is-" + (piece.status || "draft") }, statusLabel(piece.status)),
                      h("span", { className: "hs-row-text" }, piece.idea)));
                }))) : null,
              (item.assets || []).length ? h("div", { className: "hs-stack hs-gap-xs" },
                h("div", { className: "hs-overline" }, "Assets"),
                h("div", { className: "hs-row hs-gap-xs" }, item.assets.map(function (asset) { return h("span", { key: asset.id, className: "hs-tag hs-tag-flat" }, asset.kind + " · " + asset.name); }))) : null,
              h("div", { className: "hs-row" },
                loosePieces.length ? h("select", {
                  className: "hs-field hs-w-lg", value: "", "aria-label": "Add a piece",
                  onChange: function (event) {
                    if (event.target.value) props.onAttach(item.id, { piece_ids: [event.target.value] });
                    event.target.value = "";
                  },
                }, h("option", { value: "" }, "Add a piece…"),
                  loosePieces.map(function (piece) { return h("option", { key: piece.id, value: piece.id }, piece.idea.slice(0, 60)); })) : null,
                looseAssets.length ? h("select", {
                  className: "hs-field hs-w-lg", value: "", "aria-label": "Add an asset",
                  onChange: function (event) {
                    if (event.target.value) props.onAttach(item.id, { asset_ids: [event.target.value] });
                    event.target.value = "";
                  },
                }, h("option", { value: "" }, "Add an asset…"),
                  looseAssets.map(function (asset) { return h("option", { key: asset.id, value: asset.id }, asset.kind + " · " + asset.name); })) : null),
              h("div", { className: "hs-row" },
                h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onClone(item.id); } }, "Clone"),
                retro.ready && retro.ahead ? h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onKeep(item.id); } }, "Keep the lesson") : null)) : null);
        })));
  }

  function HashtagDesk(props) {
    const desk = (props.studio && props.studio.hashtags) || { sets: [], tags: [], formats: { rows: [], detail: "" }, trends: [], feed: [], outside: [], kinds: ["topic", "sound", "format"], suggestion: { tags: [], detail: "" }, pillars: [], campaigns: [] };
    const [set, setSet] = useState({ name: "", tags: "", pillar: "", campaign: "" });
    const [trend, setTrend] = useState({ kind: (desk.kinds || ["topic"])[0], name: "", note: "" });
    const formats = desk.formats || { rows: [], detail: "" };
    const suggestion = desk.suggestion || { tags: [], detail: "" };
    const ahead = suggestion.tags || [];
    function noteRow(item) {
      return h("li", { key: item.id, className: "hs-list-row" },
        h("div", { className: "hs-list-main" },
          h("div", null, h("span", { className: "hs-tag hs-tag-flat" }, item.kind), " ", item.name),
          [item.note, item.result].filter(Boolean).length ? h("div", { className: "hs-meta" }, [item.note, item.result].filter(Boolean).join(" · ")) : null));
    }
    return h("div", { className: "hs-main" },
      h(Section, { title: "Ahead on this brand", note: suggestion.detail || "No hashtag is clearly ahead for this brand." },
        ahead.length ? h("ul", { className: "hs-options" }, ahead.map(function (tag) {
          return h("li", { key: tag, className: "hs-option" },
            h("div", { className: "hs-row hs-spread" },
              h("strong", null, "#" + tag),
              h(FeedbackButtons, { kind: "hashtags", target: tag, busy: props.busy, onFeedback: props.onFeedback })));
        })) : null,
        props.piece ? h("button", {
          type: "button", className: "hs-button", disabled: props.busy || !ahead.length,
          onClick: function () { props.onUse(props.piece.id, props.piece.pillar || ""); },
        }, "Use these on the open draft") : ahead.length ? h("p", { className: "hs-hint" }, "Open a draft in the Composer to use the tags that are ahead.") : null),
      h(Section, { title: "Saved sets", note: "Up to five tags, for a pillar or a campaign when you want one." },
        (desk.sets || []).length ? h("ul", { className: "hs-rows" }, desk.sets.map(function (item) {
          const performance = item.performance || {};
          const where = [item.pillar, item.campaign].filter(Boolean).join(" · ");
          return h("li", { key: item.id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" },
              h("div", null, h("strong", null, item.name), where ? h("span", { className: "hs-meta" }, " · " + where) : null),
              h("div", { className: "hs-row hs-gap-xs" }, item.tags.map(function (tag) { return h("span", { key: tag, className: "hs-tag hs-tag-flat" }, "#" + tag); })),
              performance.detail ? h("div", { className: performance.ahead ? "hs-ok" : "hs-meta" }, performance.detail) : null),
            h("button", {
              type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy || !props.piece,
              title: props.piece ? "" : "Open a draft in the Composer first",
              onClick: function () { props.onApply(item.id); },
            }, "Use on the draft"));
        })) : h("p", { className: "hs-note" }, "No saved sets yet."),
        h("form", {
          className: "hs-stack",
          onSubmit: async function (event) {
            event.preventDefault();
            const saved = await props.onSaveSet({ name: set.name, tags: set.tags.split(/[,\s]+/).filter(Boolean), pillar: set.pillar, campaign: set.campaign });
            if (saved) setSet({ name: "", tags: "", pillar: set.pillar, campaign: set.campaign });
          },
        },
          h("div", { className: "hs-grid-2" },
            field("Set name", h("input", { className: "hs-field", value: set.name, onChange: function (event) { setSet(Object.assign({}, set, { name: event.target.value })); } })),
            field("Tags", h("input", { className: "hs-field", value: set.tags, placeholder: "misfit outcast metal", onChange: function (event) { setSet(Object.assign({}, set, { tags: event.target.value })); } }), "Up to five, with or without #.")),
          h("div", { className: "hs-grid-2" },
            field("Pillar", h("select", { className: "hs-field", value: set.pillar, onChange: function (event) { setSet(Object.assign({}, set, { pillar: event.target.value })); } },
              h("option", { value: "" }, "Any pillar"),
              (desk.pillars || []).map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); }))),
            field("Campaign", h("select", { className: "hs-field", value: set.campaign, onChange: function (event) { setSet(Object.assign({}, set, { campaign: event.target.value })); } },
              h("option", { value: "" }, "No campaign"),
              (desk.campaigns || []).map(function (name) { return h("option", { key: name, value: name }, name); })))),
          h("div", { className: "hs-row" }, h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !set.name.trim() || !set.tags.trim() }, "Save set")))),
      h("div", { className: "hs-grid-2 hs-align-start" },
        h(Section, { title: "Tags these posts used" },
          (desk.tags || []).length ? h("ul", { className: "hs-list" }, desk.tags.map(function (item) {
            return h("li", { key: item.tag, className: item.ahead ? "hs-ok" : "hs-note" }, item.detail);
          })) : h("p", { className: "hs-note" }, "No hashtags on the posts in this window.")),
        h(Section, { title: "Formats", note: formats.detail },
          (formats.rows || []).length ? h("dl", { className: "hs-dl" }, (formats.rows || []).map(function (item) {
            return [h("dt", { key: item.id + "t" }, item.label + " · n=" + item.n), h("dd", { key: item.id + "d" }, formatNumber(item.mean))];
          })) : null)),
      h(Section, { title: "Notes", note: desk.niche || "Topics, sounds, and formats you noticed. Filtered by this brand's own words; not a popularity chart." },
        h("form", {
          className: "hs-inline-form",
          onSubmit: async function (event) {
            event.preventDefault();
            const saved = await props.onTrend(trend);
            if (saved) setTrend({ kind: trend.kind, name: "", note: "" });
          },
        },
          h("select", { className: "hs-field hs-w-sm", "aria-label": "Kind", value: trend.kind, onChange: function (event) { setTrend(Object.assign({}, trend, { kind: event.target.value })); } },
            (desk.kinds || []).map(function (kind) { return h("option", { key: kind, value: kind }, kind); })),
          h("input", { className: "hs-field hs-grow", "aria-label": "What you noticed", value: trend.name, placeholder: "Topic, sound, or format", onChange: function (event) { setTrend(Object.assign({}, trend, { name: event.target.value })); } }),
          h("input", { className: "hs-field hs-grow", "aria-label": "Where you noticed it", value: trend.note, placeholder: "Where you noticed it", onChange: function (event) { setTrend(Object.assign({}, trend, { note: event.target.value })); } }),
          h("button", { type: "submit", className: "hs-tab", disabled: props.busy || !trend.name.trim() }, "Save note")),
        h("div", { className: "hs-overline" }, "In this brand's words"),
        (desk.feed || []).length ? h("ul", { className: "hs-rows" }, desk.feed.map(noteRow)) : h("p", { className: "hs-note" }, "No saved note uses this brand's pillar or tag words."),
        (desk.outside || []).length ? h("details", { className: "hs-more" },
          h("summary", null, "Saved, outside those words · " + desk.outside.length),
          h("ul", { className: "hs-rows" }, desk.outside.map(noteRow))) : null));
  }

  const INBOX_VIEWS = [["attention", "Needs attention"], ["ahead", "On a post that is ahead"], ["all", "All"], ["comment", "Comments"], ["mention", "Mentions"], ["dm", "Messages"]];

  function InboxDesk(props) {
    const desk = (props.studio && props.studio.inbox) || { items: [], errors: [], sending: false };
    const [kind, setKind] = useState("attention");
    const [drafts, setDrafts] = useState({});
    const all = desk.items || [];
    function matches(item, view) {
      if (view === "attention") return item.needs_attention;
      if (view === "ahead") return item.ahead;
      if (view === "all") return true;
      return item.kind === view;
    }
    const items = all.filter(function (item) { return matches(item, kind); });
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-cal-toolbar" },
        h("select", { className: "hs-field hs-w-lg", "aria-label": "Show", value: kind, onChange: function (event) { setKind(event.target.value); } },
          INBOX_VIEWS.map(function (pair) {
            return h("option", { key: pair[0], value: pair[0] }, pair[1] + " · " + all.filter(function (item) { return matches(item, pair[0]); }).length);
          })),
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: props.onRefresh }, "Refresh")),
      (desk.errors || []).map(function (error) { return h("p", { key: error, className: "hs-error" }, error); }),
      items.length ? h("ul", { className: "hs-ideas" }, items.map(function (item) {
        const value = drafts[item.id] != null ? drafts[item.id] : (item.reply || "");
        const canIdea = item.kind !== "dm" && (item.question || item.ahead);
        const label = { comment: "Comment", mention: "Mention", dm: "Message" }[item.kind] || item.kind;
        return h("li", { key: item.id, className: "hs-idea" },
          h("div", { className: "hs-row hs-spread" },
            h("div", { className: "hs-row hs-gap-xs" },
              h("span", { className: "hs-tag hs-tag-flat" }, label),
              h("span", { className: "hs-meta" }, platformName(item.platform) + " · " + item.author),
              item.needs_attention ? h("span", { className: "hs-tag is-warn" }, "Needs attention") : null),
            item.permalink ? h("a", { href: item.permalink, target: "_blank", rel: "noopener noreferrer", className: "hs-meta" }, "Open it") : null),
          h("blockquote", { className: "hs-quote" }, item.text),
          item.prompt ? h("p", { className: item.ahead ? "hs-ok" : "hs-note" }, item.prompt) : null,
          field("Your reply, as a draft", h("textarea", {
            className: "hs-area hs-short",
            value: value,
            onChange: function (event) {
              const next = event.target.value;
              setDrafts(function (current) { return Object.assign({}, current, { [item.id]: next }); });
            },
          }), "Saved here only. Nothing is sent."),
          h("div", { className: "hs-row hs-spread" },
            h("div", { className: "hs-row hs-gap-sm" },
              h("button", { type: "button", className: "hs-button", disabled: props.busy || value === (item.reply || ""), onClick: function () { props.onReply(item.id, { reply: value }); } }, "Save draft"),
              h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onSuggest(item.id); } }, "Suggest a reply"),
              canIdea ? h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onIdea(item.id); } }, "Keep as an idea") : null,
              h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy || !value.trim(), title: "Keeps your reply as an on-brand example, not their words", onClick: function () { props.onVoice(item.id, value); } }, "Keep this reply in the voice")),
            h("button", { type: "button", className: "hs-link-button", disabled: props.busy, onClick: function () { props.onReply(item.id, { reply: value, dismissed: true }); } }, "Dismiss")));
      })) : h(Empty, null, all.length ? "Nothing in this view." : "No comments, mentions, or messages yet. Refresh after a page is connected."));
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
      h(Section, { title: "New report" },
        h("form", {
          className: "hs-stack",
          onSubmit: async function (event) {
            event.preventDefault();
            const saved = await props.onGenerate(period, note);
            if (saved) setNote("");
          },
        },
          h(Segmented, { label: "Period", value: period, options: [["week", "Last week"], ["month", "Last month"]], onChange: setPeriod }),
          field("Note", h("textarea", { className: "hs-area hs-short", value: note, placeholder: "Optional. It leads the report.", onChange: function (event) { setNote(event.target.value); } })),
          h("div", { className: "hs-row" }, h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Generate report")))),
      rows.length ? rows.map(function (row, index) {
        const totals = (row.document && row.document.totals) || {};
        const recommendations = (row.document && row.document.recommendations) || [];
        return h("section", { key: row.id, className: "hs-section" },
          h("div", { className: "hs-section-head" },
            h("div", { className: "hs-section-titles" },
              h("h3", { className: "hs-h3" }, row.title),
              h("p", { className: "hs-note" }, row.note || "No note.")),
            h("button", { type: "button", className: "hs-tab hs-tab-sm", disabled: props.busy, onClick: function () { props.onInsight(row.id); } }, "Write the insight")),
          h("div", { className: "hs-stats" },
            h(Stat, { label: "Engagements", value: formatNumber(totals.engagements), missing: totals.engagements == null }),
            h(Stat, { label: "Shares", value: formatNumber(totals.shares), missing: totals.shares == null }),
            h(Stat, { label: "Reach", value: totals.reach == null ? (totals.reach_note || "Not in the pull") : formatNumber(totals.reach), missing: totals.reach == null })),
          recommendations.length ? h("p", { className: "hs-voice" }, recommendations[0]) : null,
          h("details", { className: "hs-more", open: index === 0 },
            h("summary", null, "The full report"),
            h("pre", { className: "hs-report", tabIndex: 0, role: "region", "aria-label": "Full report, " + row.title }, row.markdown || "")),
          h("div", { className: "hs-row hs-gap-sm" },
            h("button", { type: "button", className: "hs-tab hs-tab-sm", onClick: function () { copy(row.id + ":md", row.markdown || ""); } }, copied === row.id + ":md" ? "Copied" : "Copy markdown"),
            h("button", { type: "button", className: "hs-tab hs-tab-sm", onClick: function () { downloadText(reportFileName(row.title, "md"), row.markdown || "", "text/markdown"); } }, "Download markdown"),
            h("button", {
              type: "button", className: "hs-tab hs-tab-sm",
              onClick: function () {
                const payload = { title: row.title, period: row.period, note: row.note || "", start: row.start, end: row.end, generated_at: row.generated_at, document: row.document || {} };
                downloadText(reportFileName(row.title, "json"), JSON.stringify(payload, null, 2), "application/json");
              },
            }, "Download JSON"),
            h("button", { type: "button", className: "hs-link-button", onClick: function () { copy(row.id + ":id", row.id); } }, copied === row.id + ":id" ? "Id copied" : "Copy the report id")));
      }) : h(Empty, null, "No report yet. Generate a week or a month."));
  }

  const INGEST_FIELDS = [
    ["", "Ignore"], ["caption", "Caption"], ["published_at", "Published at"], ["platform", "Platform"], ["likes", "Likes"],
    ["comments", "Comments"], ["shares", "Shares"], ["saves", "Saves"], ["impressions", "Impressions"], ["reach", "Reach"],
    ["video_views", "Video views"], ["permalink", "Link"], ["format", "Format"], ["pillar", "Pillar"],
  ];

  function IngestDesk(props) {
    const desk = (props.studio && props.studio.ingest) || { fields: [], mapping: {}, log: [], insights: [] };
    const [text, setText] = useState("");
    const [xlsx, setXlsx] = useState("");
    const [filename, setFilename] = useState("paste");
    const [preview, setPreview] = useState(null);
    const [mapping, setMapping] = useState({});
    const [result, setResult] = useState(null);
    const hasCaption = Object.keys(mapping).some(function (column) { return mapping[column] === "caption"; });
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
      if (saved) { setResult(saved); setPreview(null); }
    }
    return h("div", { className: "hs-main" },
      h(Section, { title: "1 · Bring the rows", note: "Paste rows, or choose a CSV, JSON, or Excel file." },
        h("textarea", { className: "hs-area hs-mono", "aria-label": "Rows to import", value: text, placeholder: "caption,published_at,platform,likes,comments\n…", onChange: function (event) { setText(event.target.value); setXlsx(""); setFilename("paste"); setPreview(null); } }),
        h("div", { className: "hs-row" },
          h("input", {
            className: "hs-field hs-w-lg", type: "file", "aria-label": "Choose a file", accept: ".csv,.json,.xlsx,text/csv,application/json",
            onChange: function (event) {
              const file = event.target.files && event.target.files[0];
              if (!file) return;
              setFilename(file.name);
              setPreview(null);
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
          xlsx ? h("span", { className: "hs-meta" }, filename + " is ready.") : null,
          h("button", { type: "button", className: "hs-button", disabled: props.busy || (!text.trim() && !xlsx), onClick: previewFile }, "Preview columns"))),
      preview ? h(Section, { title: "2 · Map the columns", note: preview.rows + " rows. Map one column to the caption; the rest are optional." },
        h("form", { className: "hs-stack", onSubmit: commitFile },
          h("div", { className: "hs-grid-3" }, (preview.columns || []).map(function (column) {
            return h("label", { key: column, className: "hs-note" }, column,
              h("select", {
                className: "hs-field",
                value: mapping[column] || "",
                onChange: function (event) {
                  const value = event.target.value;
                  setMapping(function (current) { return Object.assign({}, current, { [column]: value }); });
                },
              }, INGEST_FIELDS.map(function (pair) { return h("option", { key: pair[0] || "ignore", value: pair[0] }, pair[1]); })));
          })),
          h("div", { className: "hs-row" },
            h("button", { type: "submit", className: "hs-button", disabled: props.busy || !hasCaption }, "Import " + preview.rows + " rows"),
            !hasCaption ? h("span", { className: "hs-hint" }, "Map a column to the caption first.") : null))) : null,
      result ? h(Section, { title: "Imported" },
        h("div", { className: "hs-stats" },
          h(Stat, { label: "Added", value: formatNumber(result.accepted) }),
          h(Stat, { label: "Already here", value: formatNumber(result.skipped) }),
          h(Stat, { label: "Missing a date or a count", value: formatNumber(result.incomplete) })),
        (result.insights || []).map(function (line, index) { return h("p", { key: index, className: "hs-voice" }, line); })) : null,
      !result && (desk.insights || []).length ? h(Section, { title: "What the imported posts show" },
        h("ul", { className: "hs-list" }, desk.insights.map(function (line, index) { return h("li", { key: index, className: "hs-note" }, line); }))) : null,
      h(Section, { title: "Imports", collapsible: true, open: false },
        (desk.log || []).length ? h("ul", { className: "hs-rows" }, desk.log.map(function (item) {
          return h("li", { key: item.id, className: "hs-list-row" },
            h("div", { className: "hs-list-main" },
              h("div", null, item.filename),
              h("div", { className: "hs-meta" }, item.accepted + " added · " + item.skipped + " skipped · " + item.incomplete + " incomplete")));
        })) : h("p", { className: "hs-note" }, "No import yet.")));
  }

  function AcrossDesk(props) {
    const desk = (props.studio && props.studio.cross) || { enabled: false, brands: [], lines: [], accepted: [] };
    const brands = desk.brands || [];
    return h("div", { className: "hs-main" },
      h(Section, { title: "Included brands" },
        brands.length ? h("div", { className: "hs-row hs-gap-xs" }, brands.map(function (name) { return h("span", { key: name, className: "hs-tag hs-tag-flat" }, name); })) : h("p", { className: "hs-note" }, "No brand is included yet."),
        brands.length < 2 ? h("button", { type: "button", className: "hs-link-button", onClick: function () { props.onGo("brief"); } }, "Include this brand from its Brief →") : null),
      h(Section, { title: "What the counts show", note: "Format, hour, and content counts only, and only when the gap is real." },
        (desk.lines || []).length ? h("ul", { className: "hs-checks" }, desk.lines.map(function (item, index) {
          return h("li", { key: item.key || index, className: item.clear ? "is-ok" : "" },
            h("span", { className: "hs-check-mark", "aria-hidden": "true" }, item.clear ? "✓" : "·"),
            h("span", { className: item.clear ? "" : "hs-note" }, item.detail));
        })) : h("p", { className: "hs-note" }, brands.length < 2 ? "Comparisons start once two brands are included." : "Nothing is clear across the included brands yet.")),
      (desk.accepted || []).length ? h(Section, { title: "Accepted", note: "Accepting does not change a draft." },
        h("ul", { className: "hs-list" }, desk.accepted.map(function (item) { return h("li", { key: item.key, className: "hs-note" }, item.detail); }))) : null);
  }

  function Learning(props) {
    const lessons = (props.studio && props.studio.lessons) || [];
    return h("div", { className: "hs-main" },
      lessons.length ? h("ul", { className: "hs-ideas" }, lessons.map(function (lesson) {
        return h("li", { key: lesson.id, className: "hs-idea" },
          h("div", { className: "hs-name" }, lesson.title),
          h("p", { className: "hs-voice" }, lesson.detail));
      })) : h(Empty, null,
        h("p", null, "No lessons yet. A lesson needs three observations on each side."),
        h("button", { type: "button", className: "hs-link-button", onClick: function () { props.onGo("ingest"); } }, "Import past posts on Ingest →")));
  }

  window.__HERMES_PLUGINS__.register("house-social", HouseSocial);
})();

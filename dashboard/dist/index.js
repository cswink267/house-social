(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const React = SDK.React;
  const { useCallback, useEffect, useMemo, useState } = SDK.hooks;
  const h = React.createElement;
  const PLATFORMS = [["facebook", "Facebook"], ["instagram", "Instagram"], ["threads", "Threads"]];
  const FORMATS = ["feed", "quote-image", "carousel", "reel", "story", "thread", "text"];

  function messageOf(error) {
    if (!error) return "";
    const detail = error.detail || error.message || String(error);
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }

  function BarChart(props) {
    const points = props.points || [];
    if (!points.length) return h("p", { className: "hs-note" }, props.empty || "No numbers yet.");
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

  function HouseSocial() {
    const [brands, setBrands] = useState([]);
    const [pieces, setPieces] = useState([]);
    const [studio, setStudio] = useState(null);
    const [brandId, setBrandId] = useState("josie-blackthorn");
    const [section, setSection] = useState("brief");
    const [idea, setIdea] = useState("");
    const [pillar, setPillar] = useState("");
    const [format, setFormat] = useState("quote-image");
    const [hypothesis, setHypothesis] = useState("");
    const [activeId, setActiveId] = useState("");
    const [handles, setHandles] = useState({});
    const [pickedDay, setPickedDay] = useState("");
    const [pickedPost, setPickedPost] = useState("");
    const [pickedHour, setPickedHour] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [adding, setAdding] = useState(false);
    const [fresh, setFresh] = useState({ id: "", name: "", site: "", voice: "" });
    const [voiceCheck, setVoiceCheck] = useState(null);
    const [library, setLibrary] = useState({ assets: [], folders: [], tags: [] });
    const [limits, setLimits] = useState({ facebook: 5000, instagram: 2200, threads: 500 });
    const [cardLimit, setCardLimit] = useState(240);
    const [assist, setAssist] = useState(null);
    const [draftRead, setDraftRead] = useState(null);
    const [assistTarget, setAssistTarget] = useState("idea");

    const brand = useMemo(function () {
      return brands.find(function (item) { return item.id === brandId; }) || brands[0] || null;
    }, [brands, brandId]);
    const active = useMemo(function () {
      return pieces.find(function (item) { return item.id === activeId; }) || null;
    }, [pieces, activeId]);

    const refresh = useCallback(async function (nextBrand) {
      const roster = await SDK.fetchJSON("/api/plugins/house-social/roster");
      const queue = await SDK.fetchJSON("/api/plugins/house-social/pieces");
      const id = nextBrand || brandId;
      const desk = await SDK.fetchJSON("/api/plugins/house-social/brands/" + id + "/studio");
      const shelf = await SDK.fetchJSON("/api/plugins/house-social/brands/" + id + "/library");
      setBrands(roster.brands || []);
      setLimits(roster.limits || { facebook: 5000, instagram: 2200, threads: 500 });
      setCardLimit(roster.card_limit || 240);
      setPieces(queue.pieces || []);
      setStudio(desk);
      setLibrary(shelf || { assets: [], folders: [], tags: [] });
      return desk;
    }, [brandId]);

    useEffect(function () {
      refresh(brandId).catch(function (err) { setError(messageOf(err)); });
    }, [brandId]);

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
      setError("");
      try { return await action(); }
      catch (err) { setError(messageOf(err)); return null; }
      finally { setBusy(false); }
    }

    async function shapeIdea() {
      const piece = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/pieces", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ brand_id: brand.id, idea: idea, pillar: pillar, format: format, hypothesis: hypothesis }),
        });
      });
      if (!piece) return;
      setActiveId(piece.id);
      setIdea("");
      setHypothesis("");
      await refresh(brand.id);
    }

    async function checkVoice() {
      const fields = { idea: idea };
      if (active && active.brand_id === brand.id && active.variants) {
        PLATFORMS.forEach(function (pair) {
          fields[pair[0]] = (active.variants[pair[0]] || {}).body || "";
        });
      }
      const report = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/voice-check", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(fields),
        });
      });
      if (report) setVoiceCheck(report);
    }

    function assistText() {
      if (assistTarget === "idea") return idea;
      const variant = active && active.variants ? active.variants[assistTarget] || {} : {};
      return variant.body || idea;
    }

    async function readDraft(text) {
      const report = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/draft-read", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text == null ? assistText() : text }),
        });
      });
      if (report) setDraftRead(report);
      return report;
    }

    async function askAssist(action, misses) {
      const fields = { action: action, text: action === "draft" ? idea : assistText() };
      if (active && active.brand_id === brand.id) fields.piece_id = active.id;
      if (misses && misses.length) fields.misses = misses;
      if (action === "remix") {
        const reading = draftRead && draftRead.remix && draftRead.remix.ready ? draftRead : await readDraft(assistText());
        if (!reading || !reading.remix || !reading.remix.ready) {
          setError((reading && reading.remix && reading.remix.detail) || "No post is at least 3× the others, so there is nothing to remix.");
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
          setError("Attach an image from the library before asking for a caption.");
          return;
        }
        fields.asset_id = image.id;
      }
      const report = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/assist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(fields),
        });
      });
      if (report) setAssist(report);
    }

    async function improveDraft() {
      const reading = await readDraft(assistText());
      if (reading && reading.misses && reading.misses.length) askAssist("rewrite", reading.misses);
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

    async function saveChannels() {
      const body = {};
      PLATFORMS.forEach(function (pair) {
        const existing = (brand.channels || []).find(function (channel) { return channel.platform === pair[0]; }) || {};
        body[pair[0]] = { handle: handles[pair[0]] || "", external_id: existing.external_id || "" };
      });
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/channels", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    function editVariant(platform, field, value) {
      setPieces(function (current) {
        return current.map(function (piece) {
          if (piece.id !== activeId) return piece;
          const variants = Object.assign({}, piece.variants);
          variants[platform] = Object.assign({}, variants[platform], { [field]: value });
          return Object.assign({}, piece, { variants: variants });
        });
      });
    }

    async function savePiece(extra) {
      if (!active) return;
      const variants = {};
      PLATFORMS.forEach(function (pair) {
        const variant = active.variants[pair[0]] || {};
        variants[pair[0]] = { body: variant.body || "", hashtags: variant.hashtags || [], image_ready: !!variant.image_ready, first_comment: variant.first_comment || "" };
      });
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/pieces/" + active.id, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(Object.assign({ variants: variants }, extra || {})),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function saveApprovalSteps(steps) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/approval-steps", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps: steps }),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function sendReview(id) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/pieces/" + id + "/review", { method: "POST" });
      });
      if (saved) await refresh(brand.id);
    }

    async function decidePiece(id, body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/pieces/" + id + "/decision", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function commentPiece(id, body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/pieces/" + id + "/comments", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function readNotice(id) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/notices/" + id + "/read", { method: "POST" });
      });
      if (saved) await refresh(brand.id);
    }

    async function refreshInbox() {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/inbox", { method: "POST" });
      });
      if (saved) await refresh(brand.id);
    }

    async function saveInboxDraft(id, body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/inbox/" + encodeURIComponent(id) + "/reply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function suggestInbox(id) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/inbox/" + encodeURIComponent(id) + "/suggest", { method: "POST" });
      });
      if (saved) await refresh(brand.id);
    }

    async function generateReport(period, note) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/reports", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ period: period, note: note }),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function saveHashtagSet(body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/hashtag-sets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function applyHashtagSet(setId) {
      if (!active || active.brand_id !== brand.id) return;
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/hashtag-sets/" + setId + "/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ piece_id: active.id }),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function saveTrendNote(body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/trends", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function saveIdea(body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/ideas", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function draftIdea(id) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/ideas/" + id + "/draft", { method: "POST" });
      });
      if (!saved) return;
      if (saved.piece_id) {
        setActiveId(saved.piece_id);
        setSection("create");
      }
      await refresh(brand.id);
    }

    async function saveCampaign(body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/campaigns", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function attachCampaign(id, body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/campaigns/" + id + "/attach", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function runQueue(action, ids) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/queue", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: ids, action: action }),
        });
      });
      if (!saved) return;
      const bad = (saved.results || []).filter(function (item) { return !item.ok; });
      if (bad.length) setError(bad.map(function (item) { return item.error; }).filter(Boolean).join(" "));
      await refresh(brand.id);
    }

    async function placePiece(id, date) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/pieces/" + id, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scheduled_for: date }),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function planPiece(body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/pieces", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(Object.assign({ brand_id: brand.id, status: "planned" }, body)),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function saveAsset(body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/assets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function reviseAsset(id, body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/assets/" + id, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function useAsset(id, body) {
      const saved = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/assets/" + id + "/use", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      });
      if (saved) await refresh(brand.id);
    }

    async function removePiece(id) {
      const done = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/pieces/" + id, { method: "DELETE" });
      });
      if (!done) return;
      if (activeId === id) setActiveId("");
      await refresh(brand.id);
    }

    async function addBrand(event) {
      event.preventDefault();
      const created = await run(function () {
        return SDK.fetchJSON("/api/plugins/house-social/brands", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(fresh),
        });
      });
      if (!created) return;
      setAdding(false);
      setFresh({ id: "", name: "", site: "", voice: "" });
      setBrandId(created.id);
    }

    const sections = (brand && brand.sections) || [];
    return h("div", { className: "hs-page" },
      h("div", null,
        h("h1", { className: "text-xl font-semibold" }, "House Social"),
        h("p", { className: "hs-lede" },
          "One desk for each brand. Brief, create, calendar, the numbers, and what the numbers are allowed to teach. Nothing is sent."),
      ),
      error ? h("p", { className: "hs-error" }, error) : null,
      h("div", { className: "hs-layout" },
        h("div", { className: "hs-brands" },
          brands.map(function (item) {
            const known = (item.channels || []).filter(function (channel) { return channel.known; }).length;
            return h("button", {
              key: item.id,
              type: "button",
              className: "hs-brand" + (brand && item.id === brand.id ? " is-on" : ""),
              onClick: function () { setBrandId(item.id); setPickedDay(""); setPickedPost(""); setPickedHour(""); },
            },
              h("div", { className: "hs-name" }, item.name),
              h("div", { className: "hs-meta" }, known + " of 3 channels known"),
            );
          }),
          h("button", { type: "button", className: "hs-button", onClick: function () { setAdding(!adding); } }, adding ? "Close" : "Add a brand"),
        ),
        brand ? h("div", { className: "hs-main" },
          h("div", { className: "hs-tabs" },
            sections.map(function (item) {
              return h("button", {
                key: item.id,
                type: "button",
                className: "hs-tab" + (section === item.id ? " is-on" : ""),
                onClick: function () { setSection(item.id); },
              }, item.label);
            })),
          section === "brief" ? h(Brief, { brand: brand, handles: handles, setHandles: setHandles, busy: busy, onSave: saveChannels }) : null,
          section === "voice" ? h(VoiceGuide, {
            brand: brand, studio: studio, busy: busy,
            onSave: async function (body) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/voice", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(body),
                });
              });
              if (saved) await refresh(brand.id);
            },
            onImport: async function (body) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/voice/import", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(body),
                });
              });
              if (saved) await refresh(brand.id);
            },
            onAccept: async function (id) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/voice/accept", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ id: id }),
                });
              });
              if (saved) await refresh(brand.id);
            },
            onRestore: async function (id) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/voice/restore", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ id: id }),
                });
              });
              if (saved) await refresh(brand.id);
            },
          }) : null,
          section === "pages" ? h(Pages, {
            brand: brand,
            studio: studio,
            busy: busy,
            onSave: async function (body) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/connections", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(Object.assign({ brand_id: brand.id }, body)),
                });
              });
              if (saved) await refresh(brand.id);
              return saved;
            },
            onPull: async function () {
              const pulled = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/pull", { method: "POST" });
              });
              if (pulled) await refresh(brand.id);
              return pulled;
            },
          }) : null,
          section === "ideas" ? h(IdeasBoard, {
            studio: studio,
            busy: busy,
            onSave: saveIdea,
            onDraft: draftIdea,
            onSuggest: async function () {
              return run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/ideas/suggest", { method: "POST" });
              });
            },
            onKeep: async function (postId) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/ideas/shapes/" + encodeURIComponent(postId), { method: "POST" });
              });
              if (saved) await refresh(brand.id);
            },
          }) : null,
          section === "create" ? h(CreatePanel, {
            brand: brand, idea: idea, setIdea: setIdea, pillar: pillar, setPillar: setPillar,
            format: format, setFormat: setFormat, hypothesis: hypothesis, setHypothesis: setHypothesis,
            busy: busy, onShape: shapeIdea, onCheck: checkVoice, voiceCheck: voiceCheck, active: active, pieces: pieces, onEdit: editVariant,
            onSave: savePiece, onDelete: removePiece, onOpen: function (piece) { setActiveId(piece.id); },
            library: library,
            onInsert: function (asset) {
              if (!asset || typeof asset === "string") {
                const text = String(asset || "");
                setIdea(function (current) { return current ? current + "\n\n" + text : text; });
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
                setIdea(function (current) { return current ? current + "\n\n" + text : text; });
                return;
              }
              const variant = (active.variants && active.variants[assistTarget]) || {};
              editVariant(assistTarget, "body", variant.body ? variant.body + "\n\n" + text : text);
            },
            onAttach: function (assetId) {
              if (active && active.brand_id === brand.id) useAsset(assetId, { piece_id: active.id });
            },
            limits: limits,
            cardLimit: cardLimit,
            assist: assist,
            assistTarget: assistTarget,
            setAssistTarget: setAssistTarget,
            onAssist: askAssist,
            onApply: applyAssist,
            onHashtag: applyHashtag,
            onRead: function () { readDraft(assistText()); },
            onImprove: improveDraft,
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
          }) : null,
          section === "library" ? h(Library, {
            library: library,
            busy: busy,
            piece: active && active.brand_id === brand.id ? active : null,
            posts: (studio && studio.feed) || [],
            onSave: saveAsset,
            onRevise: reviseAsset,
            onUse: useAsset,
            onTags: async function (id) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/assets/" + encodeURIComponent(id) + "/tags", { method: "POST" });
              });
              if (saved) await refresh(brand.id);
            },
            onFail: function (text) { setError(text); },
          }) : null,
          section === "calendar" ? h(Calendar, {
            brand: brand,
            calendar: studio && studio.calendar,
            ideas: studio && studio.ideas,
            library: library,
            busy: busy,
            onOpen: function (item) { setActiveId(item.id); setSection("create"); },
            onMove: placePiece,
            onPlan: planPiece,
            onRecur: async function (body) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/recurrences", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(body),
                });
              });
              if (saved) await refresh(brand.id);
            },
            onApply: async function (id) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/recurrences/" + encodeURIComponent(id) + "/apply", { method: "POST" });
              });
              if (saved) await refresh(brand.id);
            },
          }) : null,
          section === "queue" ? h(QueueDesk, {
            studio: studio,
            busy: busy,
            onOpen: function (id) { setActiveId(id); setSection("create"); },
            onBulk: runQueue,
          }) : null,
          section === "approval" ? h(ApprovalDesk, {
            studio: studio,
            busy: busy,
            onOpen: function (id) { setActiveId(id); setSection("create"); },
            onSteps: saveApprovalSteps,
            onReview: sendReview,
            onDecide: decidePiece,
            onComment: commentPiece,
            onRead: readNotice,
          }) : null,
          section === "campaigns" ? h(CampaignsDesk, {
            studio: studio,
            pieces: pieces.filter(function (piece) { return brand && piece.brand_id === brand.id; }),
            library: library,
            busy: busy,
            onOpen: function (id) { setActiveId(id); setSection("create"); },
            onSave: saveCampaign,
            onAttach: attachCampaign,
            onClone: async function (id) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/campaigns/" + encodeURIComponent(id) + "/clone", { method: "POST" });
              });
              if (saved) await refresh(brand.id);
            },
            onKeep: async function (id) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/campaigns/" + encodeURIComponent(id) + "/retrospective", { method: "POST" });
              });
              if (saved) await refresh(brand.id);
            },
          }) : null,
          section === "performance" ? h(Performance, {
            brand: brand, studio: studio, busy: busy, pickedDay: pickedDay, pickedPost: pickedPost, pickedHour: pickedHour,
            onDay: function (point) { setPickedDay(point.id); },
            onPost: function (point) { setPickedPost(point.id); },
            onHour: function (point) { setPickedHour(point.id); },
            onRecorded: async function (body) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/stats", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(Object.assign({ brand_id: brand.id }, body)),
                });
              });
              if (saved) await refresh(brand.id);
            },
            onHistory: async function (csv) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/history", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ csv: csv }),
                });
              });
              if (saved) await refresh(brand.id);
            },
            onGoal: async function (body) {
              const saved = await run(function () {
                return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/goals", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(body),
                });
              });
              if (saved) await refresh(brand.id);
            },
          }) : null,
          section === "hashtags" ? h(HashtagDesk, {
            studio: studio,
            piece: active && active.brand_id === brand.id ? active : null,
            busy: busy,
            onSaveSet: saveHashtagSet,
            onApply: applyHashtagSet,
            onTrend: saveTrendNote,
          }) : null,
          section === "inbox" ? h(InboxDesk, {
            studio: studio,
            busy: busy,
            onRefresh: refreshInbox,
            onReply: saveInboxDraft,
            onSuggest: suggestInbox,
          }) : null,
          section === "reports" ? h(ReportsDesk, {
            studio: studio,
            busy: busy,
            onGenerate: generateReport,
          }) : null,
          section === "learning" ? h(Learning, { studio: studio }) : null,
        ) : null,
      ),
      adding ? h("form", { className: "hs-cols", onSubmit: addBrand },
        ["id", "name", "site", "voice"].map(function (field) {
          return h("input", {
            key: field, className: "hs-field", placeholder: field, value: fresh[field],
            onChange: function (event) {
              const value = event.target.value;
              setFresh(function (current) { return Object.assign({}, current, { [field]: value }); });
            },
          });
        }),
        h("button", { type: "submit", className: "hs-button", disabled: busy }, "Add brand"),
      ) : null,
    );
  }

  function VoiceScore(props) {
    const report = props.report || { label: "", fields: [] };
    const missed = (report.fields || []).some(function (field) {
      return (field.checks || []).some(function (check) { return !check.ok; });
    });
    return h("div", { className: "hs-pillar" },
      h("div", { className: "hs-name" }, report.label || "Voice"),
      (report.fields || []).map(function (field) {
        return h("div", { key: field.field },
          h("div", { className: "hs-note" }, field.field),
          (field.checks || []).map(function (check) {
            return h("div", { key: field.field + check.id, className: check.ok ? "hs-ok" : "hs-bad" }, (check.ok ? "Yes. " : "No. ") + check.label);
          }));
      }),
      missed ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: props.onRewrite }, "Suggest a rewrite") : null,
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
        h("p", { className: "hs-note" }, "The memory of this brand. Composer checks a draft against it. A suggestion below is saved only when you accept it, and only when the posts actually show the gap."),
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
      h("p", { className: "hs-note" },
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

  function Brief(props) {
    const brand = props.brand;
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-voice" }, brand.audience || brand.voice),
      h("p", { className: "hs-voice" }, brand.voice),
      (brand.guards || []).length ? h("ul", { className: "hs-guard" }, brand.guards.map(function (guard) {
        return h("li", { key: guard }, guard);
      })) : null,
      h("div", { className: "hs-pillars" }, (brand.pillars || []).map(function (item) {
        return h("div", { key: item.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, item.name),
          h("p", { className: "hs-note" }, item.note));
      })),
      h("div", { className: "hs-cols" }, PLATFORMS.map(function (pair) {
        return h("label", { key: pair[0], className: "hs-meta" }, pair[1],
          h("input", {
            className: "hs-field",
            value: props.handles[pair[0]] || "",
            placeholder: "handle, or leave open",
            onChange: function (event) {
              const value = event.target.value;
              props.setHandles(function (current) { return Object.assign({}, current, { [pair[0]]: value }); });
            },
          }));
      })),
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: props.onSave }, "Save handles")),
    );
  }

  function CreatePanel(props) {
    const brand = props.brand;
    const mine = props.pieces.filter(function (piece) { return piece.brand_id === brand.id; });
    const [holdDay, setHoldDay] = useState("");
    return h("div", { className: "hs-main" },
      h("div", { className: "hs-cols" },
        h("select", { className: "hs-field", value: props.pillar, onChange: function (event) { props.setPillar(event.target.value); } },
          h("option", { value: "" }, "Pillar"),
          (brand.pillars || []).map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); })),
        h("select", { className: "hs-field", value: props.format, onChange: function (event) { props.setFormat(event.target.value); } },
          FORMATS.map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("input", {
          className: "hs-field", value: props.hypothesis, placeholder: "Hypothesis, if this is an experiment",
          onChange: function (event) { props.setHypothesis(event.target.value); },
        })),
      h("textarea", {
        className: "hs-area", value: props.idea, placeholder: "The idea, in your words.",
        onChange: function (event) { props.setIdea(event.target.value); },
      }),
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-button", disabled: props.busy || !props.idea.trim(), onClick: props.onShape }, "Shape three posts"),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy || (!props.idea.trim() && !(props.active && props.active.brand_id === brand.id)), onClick: props.onCheck }, "Check voice")),
      h("div", { className: "hs-row" },
        h("select", { className: "hs-field", value: props.assistTarget || "idea", onChange: function (event) { props.setAssistTarget(event.target.value); } },
          h("option", { value: "idea" }, "Idea"),
          PLATFORMS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); })),
        ["draft", "rewrite", "shorten", "expand", "variations", "hooks", "caption", "comment", "hashtags", "remix"].map(function (action) {
          return h("button", {
            key: action, type: "button", className: "hs-tab", disabled: props.busy,
            onClick: function () { props.onAssist(action); },
          }, action);
        }),
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: props.onImprove }, "Improve this draft"),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: props.onRead }, "What the posts say")),
      props.assist && (props.assist.options || []).length ? h("div", { className: "hs-pillar" },
        h("div", { className: "hs-name" }, props.assist.source === "brand" ? "Hashtags from this brand" : "Held to the voice guide"),
        props.assist.options.map(function (option, index) {
          const label = props.assist.action === "hashtags" ? "#" + option.text : option.text;
          return h("button", {
            key: index, type: "button", className: "hs-post",
            onClick: function () {
              if (props.assist.action === "hashtags") props.onHashtag(option.text);
              else props.onApply(option.text);
            },
          }, label,
          option.voice && option.voice.total ? h("span", { className: "hs-note" }, "  " + option.voice.passed + "/" + option.voice.total) : null,
          (option.reading && option.reading.lines || []).length
            ? (option.reading.lines || []).map(function (line, lineIndex) { return h("p", { key: lineIndex, className: "hs-note" }, line); })
            : option.reading ? h("p", { className: "hs-note" }, "No historical pattern matches this line.") : null);
        })) : null,
      (props.library && (props.library.assets || []).length) ? h("div", null,
        h("div", { className: "hs-name" }, "From the library"),
        props.pillar ? h("p", { className: "hs-note" }, provenLine(props.library.assets, props.pillar)) : null,
        h("div", { className: "hs-row" }, (props.library.assets || []).filter(function (asset) {
          return asset.kind === "copy" || asset.kind === "template" || asset.kind === "image" || asset.kind === "logo";
        }).slice(0, 8).map(function (asset) {
          const textual = asset.kind === "copy" || asset.kind === "template";
          return h("button", {
            key: asset.id, type: "button", className: "hs-tab",
            onClick: function () {
              if (textual && props.onInsert) props.onInsert(asset);
              else if (props.onAttach) props.onAttach(asset.id);
            },
          }, (textual ? (asset.role || "copy") : asset.kind) + " · " + asset.name);
        }))) : null,
      props.draftRead ? h("div", { className: "hs-pillar" },
        h("div", { className: "hs-name" }, "What the posts say"),
        h("p", { className: "hs-note" }, props.draftRead.hook),
        h("p", { className: "hs-note" }, props.draftRead.cta),
        h("p", { className: "hs-voice" }, props.draftRead.improve),
        (props.draftRead.similar || []).length ? (props.draftRead.similar || []).map(function (item) {
          return h("p", { key: item.id, className: "hs-note" }, item.engagements + " engagements" + (item.ahead ? " · ahead of the others" : "") + " · " + item.preview);
        }) : h("p", { className: "hs-note" }, "No saved post shares words with this draft.")) : null,
      h("div", { className: "hs-row" },
        h("input", { className: "hs-field", type: "date", value: holdDay, onChange: function (event) { setHoldDay(event.target.value); } }),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy || !holdDay, onClick: function () { props.onHold(holdDay); } }, "Hold this day"),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: props.onSaveCopy }, "Save copy to the library")),
      props.voiceCheck ? h(VoiceScore, {
        report: props.voiceCheck,
        busy: props.busy,
        onRewrite: function () {
          const misses = [];
          (props.voiceCheck.fields || []).forEach(function (field) {
            (field.checks || []).forEach(function (check) {
              if (!check.ok) misses.push(field.field + ": " + check.label);
            });
          });
          props.onAssist("rewrite", misses);
        },
      }) : null,
      props.active && props.active.brand_id === brand.id ? h(PieceEditor, {
        piece: props.active, brand: brand, busy: props.busy, limits: props.limits, cardLimit: props.cardLimit,
        library: props.library, onAttach: props.onAttach, onQueue: props.onQueue,
        onEdit: props.onEdit, onSave: props.onSave, onDelete: function () { props.onDelete(props.active.id); },
      }) : null,
      h("div", { className: "hs-name" }, "This brand's queue"),
      mine.length ? mine.map(function (piece) {
        return h("button", {
          key: piece.id, type: "button",
          className: "hs-piece" + (props.active && piece.id === props.active.id ? " is-on" : ""),
          onClick: function () { props.onOpen(piece); },
        }, h("div", { className: "hs-name" }, piece.status + (piece.format ? " · " + piece.format : "")),
          h("div", { className: "hs-meta" }, piece.idea));
      }) : h("p", { className: "hs-note" }, "No drafts yet."),
    );
  }

  const LANE_COLORS = { planned: "#8aa4b5", draft: "#c4b89a", ready: "#9bb8a4", scheduled: "#c4a36a", published: "#7d9a78" };
  const PILLAR_COLORS = ["#c4b89a", "#8aa4b5", "#9bb8a4", "#c4a36a", "#c48a9a", "#a8b0c4"];
  const CAMPAIGN_COLORS = ["#d4a574", "#9bb8a4", "#8aa4b5", "#c4b89a", "#b7a8c9", "#e0b4ae"];
  const PLATFORM_COLORS = { facebook: "#8aa4b5", instagram: "#c4b89a", threads: "#9bb8a4" };
  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

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

  function monthLabel(iso) {
    const parts = iso.split("-").map(Number);
    return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(parts[0], parts[1] - 1, 1)));
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

  function quickHoldButtons(props, advice, planDate, setPlanIdea, setPlanDate) {
    const ideas = ((props.ideas && props.ideas.ideas) || []).filter(function (item) { return item.status !== "drafted"; }).slice(0, 4);
    const copies = ((props.library && props.library.assets) || []).filter(function (asset) { return asset.kind === "copy" || asset.kind === "template"; }).slice(0, 4);
    function useText(value) {
      setPlanIdea(value || "");
      if (!planDate && advice.slot && advice.slot.date) setPlanDate(advice.slot.date);
    }
    const buttons = ideas.map(function (item) {
      return h("button", { key: item.id, type: "button", className: "hs-tab", onClick: function () { useText(item.text); } }, (item.text || "").slice(0, 36));
    });
    copies.forEach(function (asset) {
      buttons.push(h("button", { key: asset.id, type: "button", className: "hs-tab", onClick: function () { useText(asset.body || asset.name); } }, asset.name));
    });
    return buttons;
  }

  function chipColor(item, colorBy, pillars, campaigns) {
    if (colorBy === "pillar") {
      const index = (pillars || []).findIndex(function (pillar) { return pillar.id === item.pillar; });
      return index < 0 ? "#6e7278" : PILLAR_COLORS[index % PILLAR_COLORS.length];
    }
    if (colorBy === "campaign") {
      const index = (campaigns || []).indexOf(item.campaign);
      return index < 0 ? "#6e7278" : CAMPAIGN_COLORS[index % CAMPAIGN_COLORS.length];
    }
    if (colorBy === "platform") {
      return PLATFORM_COLORS[(item.platforms || [])[0]] || "#6e7278";
    }
    return LANE_COLORS[item.status] || LANE_COLORS.draft;
  }

  function balanceLine(items, dates, pillars) {
    const inView = items.filter(function (item) { return dates.indexOf(item.date) >= 0; });
    const lanes = { planned: 0, draft: 0, ready: 0, scheduled: 0, published: 0 };
    const pillarCounts = {};
    inView.forEach(function (item) {
      const lane = Object.prototype.hasOwnProperty.call(lanes, item.status) ? item.status : "draft";
      lanes[lane] += 1;
      if (item.pillar) pillarCounts[item.pillar] = (pillarCounts[item.pillar] || 0) + 1;
    });
    const open = dates.filter(function (day) {
      return !inView.some(function (item) { return item.date === day; });
    }).length;
    const names = (pillars || []).reduce(function (map, pillar) { map[pillar.id] = pillar.name; return map; }, {});
    const mix = Object.keys(pillarCounts).map(function (id) { return (names[id] || id) + " " + pillarCounts[id]; });
    return open + (open === 1 ? " open day" : " open days")
      + " · planned " + lanes.planned
      + " · drafted " + lanes.draft
      + " · ready " + lanes.ready
      + " · scheduled " + lanes.scheduled
      + " · published " + lanes.published
      + (mix.length ? " · " + mix.join(" · ") : "");
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
    if (perf.mean == null) return line + ". No numbers yet.";
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
      h("p", { className: "hs-note" }, "Images, video, carousels, templates, logos, and copy for this brand. A new save of the words or the file keeps the older version. Files stay beside the desk, not in git."),
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
      h("p", { className: "hs-note" }, "Draft, then needs review, then approved, then scheduled. One name is enough. More names go in order. Notices stay on this desk."),
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
            item.compare && item.compare.ready ? h("div", null,
              h("div", { className: "hs-name" }, "Last two versions"),
              item.compare.platforms.map(function (platform) {
                return h("div", { key: platform.platform, className: "hs-preview" },
                  h("div", { className: "hs-name" }, platform.platform + (platform.same ? " · unchanged" : "")),
                  h("p", { className: "hs-note" }, platform.before || "Empty"),
                  h("p", { className: "hs-voice" }, platform.after || "Empty"));
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
      h("p", { className: "hs-note" }, "Sparks, competitor notes, trends, questions, and comments. Make this a draft opens it in the composer. A pattern line appears only when the posts already show one. Nothing here is a predicted score."),
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
      (suggested || []).map(function (text, index) { return h("p", { key: "s" + index, className: "hs-voice" }, text); }),
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
      h("p", { className: "hs-note" }, "A campaign holds the posts, the assets, the goal, and the dates. Clone keeps the shape and leaves the pieces. A kind is ahead only when both sides have three posts and the gap is real. Nothing is sent."),
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
    const [status, setStatus] = useState("all");
    const [picked, setPicked] = useState([]);
    const suggestion = queue.suggestion || {};
    const stages = queue.stages || [];
    const items = (queue.items || []).filter(function (item) {
      if (status === "all") return true;
      if (status === "draft") return item.stage === "draft";
      if (status === "recorded") return item.stage === "recorded";
      return item.status === status;
    });
    function toggle(id) {
      setPicked(function (current) {
        return current.indexOf(id) >= 0 ? current.filter(function (item) { return item !== id; }) : current.concat([id]);
      });
    }
    function row(item) {
      const tone = item.status === "pending" ? "pending" : item.status === "scheduled" ? "scheduled" : item.status === "failed" ? "failed" : item.status === "ready" ? "ready" : "draft";
      const record = item.record || {};
      const weak = item.slot && item.slot.indexOf("underperformed") >= 0;
      return h("div", { key: item.id, className: "hs-q hs-q-" + tone },
        h("input", { type: "checkbox", checked: picked.indexOf(item.id) >= 0, onChange: function () { toggle(item.id); } }),
        h("div", null,
          h("button", { type: "button", className: "hs-post", onClick: function () { props.onOpen(item.id); } },
            h("div", { className: "hs-name" }, item.label + (item.format ? " · " + item.format : "") + (item.time ? " · " + item.date + " " + item.time : "")),
            h("div", { className: "hs-meta" }, item.idea),
            item.failure ? h("div", { className: "hs-bad" }, item.failure) : null,
            item.slot ? h("div", { className: weak ? "hs-bad" : "hs-note" }, item.slot) : null,
            record.linked ? h("div", { className: "hs-note" }, record.detail) : null,
            (item.problems || []).length && item.status !== "failed" ? h("div", { className: "hs-note" }, item.problems[0]) : null),
          record.permalink ? h("a", { href: record.permalink, target: "_blank", rel: "noopener" }, "The post") : null));
    }
    const dated = items.filter(function (item) { return item.date; }).reduce(function (map, item) {
      const key = item.date || "No day";
      map[key] = (map[key] || []).concat([item]);
      return map;
    }, {});
    const formatLine = (queue.formats || []).length
      ? (queue.formats || []).map(function (entry) { return entry.format + " is ahead at " + entry.label + "."; }).join(" ")
      : "No format has a clear hour yet.";
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-note" }, "Draft, needs approval, approved, scheduled, on the record, or failed. On the record means a post is already tied to this draft. This desk does not send."),
      suggestion.clear ? h("p", { className: "hs-note" }, suggestion.label + " is ahead across the posts. " + suggestion.detail + " A format hour wins when that format is clearly ahead.") : h("p", { className: "hs-note" }, suggestion.detail || "Not enough hours to suggest a time."),
      h("p", { className: "hs-note" }, formatLine),
      h("p", { className: "hs-note" }, queue.pace || ""),
      h("ul", { className: "hs-guard" }, (queue.rules || []).map(function (rule) { return h("li", { key: rule }, rule); })),
      h("div", { className: "hs-row" },
        ["list", "timeline"].map(function (name) {
          return h("button", { key: name, type: "button", className: "hs-tab" + (mode === name ? " is-on" : ""), onClick: function () { setMode(name); } }, name);
        }),
        [["all", "All"], ["draft", "Draft"], ["pending", "Needs review"], ["approved", "Approved"], ["scheduled", "Scheduled"], ["recorded", "On the record"], ["failed", "Failed"]].map(function (pair) {
          return h("button", { key: pair[0], type: "button", className: "hs-tab" + (status === pair[0] ? " is-on" : ""), onClick: function () { setStatus(pair[0]); } }, pair[1]);
        })),
      picked.length ? h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onBulk("pending", picked); setPicked([]); } }, "Send for approval"),
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onBulk("schedule", picked); setPicked([]); } }, suggestion.clear ? "Schedule at the clear hour" : "Schedule"),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onBulk("retry", picked); setPicked([]); } }, "Retry failed"),
        h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onBulk("draft", picked); setPicked([]); } }, "Back to draft")) : null,
      mode === "timeline" ? h("div", null, Object.keys(dated).sort().map(function (day) {
        return h("div", { key: day }, h("div", { className: "hs-name" }, day), dated[day].map(row));
      })) : h("div", null, stages.map(function (stage) {
        const rows = items.filter(function (item) { return item.stage === stage.id; });
        return h("div", { key: stage.id },
          h("div", { className: "hs-name" }, stage.label),
          rows.length ? rows.map(row) : h("p", { className: "hs-note" }, "Nothing in this stage."));
      })),
    );
  }

  function Calendar(props) {
    const brand = props.brand || { pillars: [] };
    const entries = (props.calendar && props.calendar.entries) || [];
    const advice = (props.calendar && props.calendar.advice) || { gaps: [], mix: [], warnings: [], slot: { clear: false, detail: "" } };
    const recurrences = (props.calendar && props.calendar.recurrences) || [];
    const [view, setView] = useState("month");
    const [cursor, setCursor] = useState(todayET);
    const [colorBy, setColorBy] = useState("status");
    const [platform, setPlatform] = useState("all");
    const [format, setFormat] = useState("all");
    const [pillar, setPillar] = useState("all");
    const [campaign, setCampaign] = useState("all");
    const [planDate, setPlanDate] = useState("");
    const [planIdea, setPlanIdea] = useState("");
    const [planCampaign, setPlanCampaign] = useState("");
    const [planPillar, setPlanPillar] = useState("");
    const [planFormat, setPlanFormat] = useState(brand.preferred_format || "feed");
    const [recur, setRecur] = useState({ name: "", weekday: "0", weeks: "4", idea: "", pillar: "", format: brand.preferred_format || "feed" });
    const [over, setOver] = useState("");
    useEffect(function () {
      setCampaign("all");
      setPillar("all");
      setPlanDate("");
      setPlanFormat(brand.preferred_format || "feed");
    }, [brand.id]);
    const filters = { platform: platform, format: format, pillar: pillar, campaign: campaign };
    const visible = entries.filter(function (item) { return entryVisible(item, filters); });
    const dates = gridDates(view, cursor);
    const spanDates = view === "month" ? dates.filter(function (day) { return day.slice(0, 7) === cursor.slice(0, 7); }) : dates;
    const today = todayET();
    const campaigns = entries.reduce(function (list, item) {
      if (item.campaign && list.indexOf(item.campaign) < 0) list.push(item.campaign);
      return list;
    }, []);
    const waiting = visible.filter(function (item) { return item.kind === "piece" && !item.date; });

    function moveCursor(direction) {
      if (view === "month") setCursor(shiftMonth(cursor, direction));
      else setCursor(shiftDate(cursor, direction * (view === "week" ? 7 : 1)));
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
      return h("div", {
        key: item.id,
        className: "hs-chip",
        draggable: !!item.draggable,
        style: { borderLeftColor: color },
        title: text,
        onDragStart: function (event) {
          event.dataTransfer.setData("text/plain", item.id);
          event.dataTransfer.effectAllowed = "move";
        },
        onClick: function () {
          if (item.kind === "published") {
            if (item.permalink) window.open(item.permalink, "_blank", "noopener");
            return;
          }
          props.onOpen(item);
        },
      }, text);
    }

    function dayCell(day) {
      const items = visible.filter(function (item) { return item.date === day; });
      const outside = view === "month" && day.slice(0, 7) !== cursor.slice(0, 7);
      const shown = view === "month" ? items.slice(0, 3) : items;
      return h("div", {
        key: day,
        className: "hs-day" + (day === today ? " is-today" : "") + (items.length ? "" : " is-gap") + (outside ? " is-out" : "") + (over === day ? " is-over" : ""),
        onDragOver: allowDrop,
        onDragEnter: function () { setOver(day); },
        onDrop: function (event) { dropOn(event, day); },
      },
        h("div", { className: "hs-dow" }, view === "day" ? day : String(Number(day.slice(8)))),
        items.length ? null : h("div", { className: "hs-note" }, "Open"),
        shown.map(chip),
        view === "month" && items.length > 3 ? h("div", { className: "hs-note" }, "+" + (items.length - 3)) : null,
        h("button", { type: "button", className: "hs-tab", onClick: function () { setPlanDate(day); } }, "Plan"));
    }

    return h("div", { className: "hs-main" },
      h("p", { className: "hs-note" }, "Month, week, or day. Drag a piece onto a day to hold it. Drag it back down to take it off. Published posts are already on the page. A pillar or campaign filter hides them, because a live post is not tagged with either."),
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-tab", onClick: function () { moveCursor(-1); } }, "Back"),
        h("button", { type: "button", className: "hs-tab", onClick: function () { setCursor(today); } }, "Today"),
        h("button", { type: "button", className: "hs-tab", onClick: function () { moveCursor(1); } }, "Next"),
        h("div", { className: "hs-name" }, view === "day" ? cursor : monthLabel(cursor)),
        ["month", "week", "day"].map(function (name) {
          return h("button", {
            key: name, type: "button",
            className: "hs-tab" + (view === name ? " is-on" : ""),
            onClick: function () { setView(name); },
          }, name);
        }),
        h("button", { type: "button", className: "hs-tab" + (colorBy === "status" ? " is-on" : ""), onClick: function () { setColorBy("status"); } }, "By status"),
        h("button", { type: "button", className: "hs-tab" + (colorBy === "pillar" ? " is-on" : ""), onClick: function () { setColorBy("pillar"); } }, "By pillar"),
        h("button", { type: "button", className: "hs-tab" + (colorBy === "campaign" ? " is-on" : ""), onClick: function () { setColorBy("campaign"); } }, "By campaign"),
        h("button", { type: "button", className: "hs-tab" + (colorBy === "platform" ? " is-on" : ""), onClick: function () { setColorBy("platform"); } }, "By platform")),
      h("div", { className: "hs-cols" },
        h("select", { className: "hs-field", value: platform, onChange: function (event) { setPlatform(event.target.value); } },
          h("option", { value: "all" }, "All platforms"),
          PLATFORMS.map(function (pair) { return h("option", { key: pair[0], value: pair[0] }, pair[1]); })),
        h("select", { className: "hs-field", value: format, onChange: function (event) { setFormat(event.target.value); } },
          h("option", { value: "all" }, "All formats"),
          FORMATS.map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("select", { className: "hs-field", value: pillar, onChange: function (event) { setPillar(event.target.value); } },
          h("option", { value: "all" }, "All pillars"),
          (brand.pillars || []).map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); })),
        h("select", { className: "hs-field", value: campaign, onChange: function (event) { setCampaign(event.target.value); } },
          h("option", { value: "all" }, "All campaigns"),
          h("option", { value: "(none)" }, "No campaign"),
          campaigns.map(function (name) { return h("option", { key: name, value: name }, name); }))),
      h("div", { className: "hs-legend" }, [
        ["planned", "Planned"], ["draft", "Drafted"], ["ready", "Ready"], ["scheduled", "Scheduled"], ["published", "Published"],
      ].map(function (pair) {
        return h("span", { key: pair[0], className: "hs-note" },
          h("span", { className: "hs-swatch", style: { background: LANE_COLORS[pair[0]] } }),
          pair[1]);
      })),
      h("p", { className: "hs-note" }, balanceLine(visible, spanDates, brand.pillars)),
      advice.slot && advice.slot.detail ? h("p", { className: advice.slot.clear ? "hs-ok" : "hs-note" }, advice.slot.clear ? ("Open slot: " + advice.slot.label + ". " + advice.slot.detail) : advice.slot.detail) : null,
      advice.slot && advice.slot.clear && advice.slot.date ? h("button", {
        type: "button", className: "hs-tab", disabled: props.busy,
        onClick: function () { setPlanDate(advice.slot.date); },
      }, "Plan " + advice.slot.date) : null,
      (advice.gaps || []).map(function (line) { return h("p", { key: line, className: "hs-note" }, line); }),
      (advice.mix || []).length ? h("p", { className: "hs-note" }, "Next 7 days: " + advice.mix.map(function (item) { return item.name + " " + item.n; }).join(" · ")) : null,
      (advice.warnings || []).map(function (line) { return h("p", { key: line, className: "hs-bad" }, line); }),
      planDate ? h("form", {
        className: "hs-cols",
        onSubmit: function (event) {
          event.preventDefault();
          if (!planIdea.trim()) return;
          props.onPlan({
            idea: planIdea.trim(),
            campaign: planCampaign.trim(),
            pillar: planPillar,
            format: planFormat,
            scheduled_for: planDate,
          });
          setPlanIdea("");
          setPlanCampaign("");
          setPlanDate("");
        },
      },
        h("div", { className: "hs-name" }, "Hold " + planDate),
        h("input", { className: "hs-field", value: planIdea, placeholder: "The idea for this day", onChange: function (event) { setPlanIdea(event.target.value); } }),
        h("input", { className: "hs-field", value: planCampaign, placeholder: "Campaign, if it has one", onChange: function (event) { setPlanCampaign(event.target.value); } }),
        h("select", { className: "hs-field", value: planPillar, onChange: function (event) { setPlanPillar(event.target.value); } },
          h("option", { value: "" }, "Pillar"),
          (brand.pillars || []).map(function (item) { return h("option", { key: item.id, value: item.id }, item.name); })),
        h("select", { className: "hs-field", value: planFormat, onChange: function (event) { setPlanFormat(event.target.value); } },
          FORMATS.map(function (item) { return h("option", { key: item, value: item }, item); })),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !planIdea.trim() }, "Hold it on this day")) : null,
      h("div", { className: "hs-row" }, quickHoldButtons(props, advice, planDate, setPlanIdea, setPlanDate)),
      h("form", { className: "hs-cols", onSubmit: function (event) {
        event.preventDefault();
        if (!recur.name.trim() || !recur.idea.trim() || !props.onRecur) return;
        props.onRecur({ name: recur.name.trim(), idea: recur.idea.trim(), weekday: Number(recur.weekday), weeks: Number(recur.weeks), pillar: recur.pillar, format: recur.format });
        setRecur(Object.assign({}, recur, { name: "", idea: "" }));
      } },
        h("div", { className: "hs-name" }, "Repeat"),
        h("input", { className: "hs-field", value: recur.name, placeholder: "Recurrence name", onChange: function (event) { setRecur(Object.assign({}, recur, { name: event.target.value })); } }),
        h("textarea", { className: "hs-area hs-short", value: recur.idea, placeholder: "Words to hold each week", onChange: function (event) { setRecur(Object.assign({}, recur, { idea: event.target.value })); } }),
        h("select", { className: "hs-field", value: recur.weekday, onChange: function (event) { setRecur(Object.assign({}, recur, { weekday: event.target.value })); } },
          ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map(function (name, index) { return h("option", { key: name, value: String(index) }, name); })),
        h("input", { className: "hs-field", value: recur.weeks, placeholder: "Weeks, 1 to 8", onChange: function (event) { setRecur(Object.assign({}, recur, { weeks: event.target.value })); } }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !recur.name.trim() || !recur.idea.trim() }, "Save recurrence")),
      recurrences.map(function (item) {
        return h("div", { key: item.id, className: "hs-row" },
          h("span", { className: "hs-note" }, item.name),
          h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onApply(item.id); } }, "Hold those days"));
      }),
      view === "day" ? null : h("div", { className: "hs-cal-board" }, WEEKDAYS.map(function (name) {
        return h("div", { key: name, className: "hs-dow" }, name);
      })),
      h("div", { className: view === "day" ? "hs-cal-day" : "hs-cal-board" }, dates.map(dayCell)),
      h("div", { className: "hs-name" }, "Not on a day"),
      h("div", {
        className: "hs-day" + (over === "tray" ? " is-over" : ""),
        onDragOver: allowDrop,
        onDragEnter: function () { setOver("tray"); },
        onDrop: function (event) { dropOn(event, ""); },
      }, waiting.length ? waiting.map(chip) : h("p", { className: "hs-note" }, "Nothing waiting. Drag a piece here to take it off its day.")),
    );
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
      h("p", { className: "hs-note" }, "Numbers for this brand only. A missing pull stays missing. Nothing here is a rate unless the count exists."),
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
    const desk = (props.studio && props.studio.hashtags) || { sets: [], tags: [], formats: { rows: [], detail: "" }, trends: [], kinds: ["topic", "sound", "format"] };
    const [setName, setSetName] = useState("");
    const [setTags, setSetTags] = useState("");
    const [trend, setTrend] = useState({ kind: "topic", name: "", note: "" });
    const formats = desk.formats || { rows: [], detail: "" };
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-note" }, "Five tags in a set. A tag is only called ahead when three posts used it, three did not, and the gap is real. Trend notes are what you wrote down. They are not a live chart."),
      h("form", { className: "hs-row", onSubmit: function (event) {
        event.preventDefault();
        props.onSaveSet({ name: setName, tags: setTags.split(/[,\s]+/).filter(Boolean) });
        setSetName("");
        setSetTags("");
      } },
        h("input", { className: "hs-field", value: setName, placeholder: "Set name", onChange: function (event) { setSetName(event.target.value); } }),
        h("input", { className: "hs-field", value: setTags, placeholder: "Tags, up to five", onChange: function (event) { setSetTags(event.target.value); } }),
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !setName.trim() || !setTags.trim() }, "Save set")),
      (desk.sets || []).length ? desk.sets.map(function (item) {
        return h("div", { key: item.id, className: "hs-row" },
          h("span", { className: "hs-name" }, item.name),
          h("span", { className: "hs-note" }, item.tags.map(function (tag) { return "#" + tag; }).join(" ")),
          h("button", {
            type: "button", className: "hs-tab", disabled: props.busy || !props.piece,
            onClick: function () { props.onApply(item.id); },
          }, props.piece ? "Use on the open draft" : "Open a draft to use this"));
      }) : h("p", { className: "hs-note" }, "No saved sets yet."),
      h("div", { className: "hs-name" }, "Tags these posts used"),
      (desk.tags || []).length ? desk.tags.map(function (item) {
        return h("p", { key: item.tag, className: item.clear ? "hs-ok" : "hs-note" }, item.detail);
      }) : h("p", { className: "hs-note" }, "No hashtags on the posts in this window."),
      h("div", { className: "hs-name" }, "Formats"),
      h("p", { className: "hs-note" }, formats.detail),
      (formats.rows || []).map(function (item) {
        return h("p", { key: item.id, className: "hs-note" }, item.label + " · " + item.mean + " · n=" + item.n);
      }),
      h("div", { className: "hs-name" }, "Notes"),
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
      (desk.trends || []).length ? desk.trends.map(function (item) {
        return h("p", { key: item.id, className: "hs-note" }, item.kind + " · " + item.name + (item.note ? " · " + item.note : ""));
      }) : h("p", { className: "hs-note" }, "No notes yet."),
    );
  }

  function InboxDesk(props) {
    const desk = (props.studio && props.studio.inbox) || { items: [], errors: [], sending: false };
    const [kind, setKind] = useState("attention");
    const [drafts, setDrafts] = useState({});
    const items = (desk.items || []).filter(function (item) {
      if (kind === "attention") return item.needs_attention;
      if (kind === "all") return true;
      return item.kind === kind;
    });
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-note" }, "Recent comments, mentions, and messages that this brand's token can read. A reply stays a draft on this desk. Nothing is sent."),
      h("div", { className: "hs-row" },
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: props.onRefresh }, "Refresh"),
        [["attention", "Needs attention"], ["all", "All"], ["comment", "Comments"], ["mention", "Mentions"], ["dm", "Messages"]].map(function (pair) {
          return h("button", {
            key: pair[0], type: "button",
            className: "hs-tab" + (kind === pair[0] ? " is-on" : ""),
            onClick: function () { setKind(pair[0]); },
          }, pair[1]);
        })),
      (desk.errors || []).map(function (error) { return h("p", { key: error, className: "hs-bad" }, error); }),
      items.length ? items.map(function (item) {
        const value = drafts[item.id] != null ? drafts[item.id] : (item.reply || "");
        return h("div", { key: item.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, item.kind + " · " + item.platform + " · " + item.author),
          h("p", { className: "hs-voice" }, item.text),
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
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-note" }, "A week or a month of this brand, with the numbers the pull actually returned and a note you write. Download it. Nothing here is mailed, and the file does not include a token."),
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
        return h("div", { key: row.id, className: "hs-pillar" },
          h("div", { className: "hs-name" }, row.title),
          h("p", { className: "hs-note" }, row.note || "No note."),
          h("p", { className: "hs-voice" },
            "Engagements " + (totals.engagements == null ? "—" : totals.engagements) +
            " · Shares " + (totals.shares == null ? "—" : totals.shares) +
            " · Reach " + (totals.reach == null ? (totals.reach_note || "Not in the pull") : totals.reach)),
          h("pre", { className: "hs-report" }, row.markdown || ""),
          h("div", { className: "hs-row" },
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
              onClick: function () {
                const text = row.markdown || "";
                if (navigator.clipboard && navigator.clipboard.writeText) {
                  navigator.clipboard.writeText(text).then(function () { setCopied(row.id); });
                }
              },
            }, copied === row.id ? "Copied" : "Copy")));
      }) : h("p", { className: "hs-note" }, "No report yet. Generate a week or a month."),
    );
  }

  function Learning(props) {
    const lessons = (props.studio && props.studio.lessons) || [];
    return h("div", { className: "hs-main" },
      h("p", { className: "hs-note" }, "Standing rules stay on the Brief. A lesson here is only what the numbers support, and a comparison waits for three observations."),
      lessons.length ? lessons.map(function (lesson) {
        return h("div", { key: lesson.id, className: "hs-lesson" },
          h("div", { className: "hs-name" }, lesson.title),
          h("p", { className: "hs-voice" }, lesson.detail));
      }) : h("p", { className: "hs-note" }, "No lessons yet."),
    );
  }

  function platformLimit(brand, platform, limits, cardLimit) {
    if (brand && brand.id === "josie-blackthorn" && platform === "facebook") return cardLimit || 240;
    return (limits && limits[platform]) || 500;
  }

  function PieceEditor(props) {
    const piece = props.piece;
    const brand = props.brand || {};
    const [when, setWhen] = useState("");
    const attached = ((props.library && props.library.assets) || []).filter(function (asset) {
      return (piece.asset_ids || []).indexOf(asset.id) >= 0;
    });
    const loose = ((props.library && props.library.assets) || []).filter(function (asset) {
      return (piece.asset_ids || []).indexOf(asset.id) < 0;
    });
    return h("div", null,
      h("div", { className: "hs-previews" }, PLATFORMS.map(function (pair) {
        const variant = (piece.variants && piece.variants[pair[0]]) || { body: "", hashtags: [], note: "", first_comment: "" };
        const limit = platformLimit(brand, pair[0], props.limits, props.cardLimit);
        const count = (variant.body || "").length;
        const commentCount = (variant.first_comment || "").length;
        return h("div", { key: pair[0], className: "hs-preview" },
          h("div", { className: "hs-name" }, pair[1]),
          h("div", { className: count > limit ? "hs-bad" : "hs-note" }, count + " / " + limit),
          variant.note ? h("p", { className: "hs-note" }, variant.note) : null,
          h("textarea", { className: "hs-area", value: variant.body || "", onChange: function (event) { props.onEdit(pair[0], "body", event.target.value); } }),
          pair[0] === "instagram" ? h("input", {
            className: "hs-field", value: (variant.hashtags || []).join(" "), placeholder: "hashtags, kept out of the caption",
            onChange: function (event) { props.onEdit(pair[0], "hashtags", event.target.value.split(/\s+/).filter(Boolean)); },
          }) : null,
          h("textarea", {
            className: "hs-area", value: variant.first_comment || "", placeholder: "First comment, not the post",
            onChange: function (event) { props.onEdit(pair[0], "first_comment", event.target.value); },
          }),
          h("div", { className: commentCount > 1000 ? "hs-bad" : "hs-note" }, "First comment " + commentCount + " / 1000"),
          variant.needs_image ? h("label", { className: "hs-note" },
            h("input", { type: "checkbox", checked: !!variant.image_ready, onChange: function (event) { props.onEdit(pair[0], "image_ready", event.target.checked); } }),
            " Quote image is ready") : null);
      })),
      h("p", { className: "hs-note" }, "Hashtags stay out of the Instagram caption. Threads stops at 500 characters. Josie's Facebook card stops at 240."),
      h("div", { className: "hs-name" }, "Media"),
      attached.length ? h("div", { className: "hs-row" }, attached.map(function (asset) {
        const image = asset.mime && asset.mime.indexOf("image/") === 0;
        return h("div", { key: asset.id, className: "hs-pillar" },
          image ? h("img", { className: "hs-thumb", alt: asset.name, src: assetUrl(asset.id) }) : h("div", { className: "hs-name" }, asset.kind),
          h("div", { className: "hs-note" }, asset.name));
      })) : h("p", { className: "hs-note" }, "No media on this draft yet."),
      loose.length ? h("select", {
        className: "hs-field",
        value: "",
        onChange: function (event) {
          if (event.target.value && props.onAttach) props.onAttach(event.target.value);
          event.target.value = "";
        },
      }, h("option", { value: "" }, "Attach from the library"),
        loose.map(function (asset) { return h("option", { key: asset.id, value: asset.id }, asset.kind + " · " + asset.name); })) : null,
      h("div", { className: "hs-row" },
        h("input", {
          className: "hs-field",
          defaultValue: piece.campaign || "",
          placeholder: "Campaign, if this belongs to one",
          onBlur: function (event) {
            const value = event.target.value.trim();
            if (value !== (piece.campaign || "")) props.onSave({ campaign: value });
          },
        }),
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onSave(); } }, "Save edits"),
        props.onQueue ? h("button", { type: "button", className: "hs-tab", disabled: props.busy, onClick: function () { props.onQueue(piece.id); } }, "Send for approval") : null,
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onSave({ status: "planned" }); } }, "Mark planned"),
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onSave({ status: "ready" }); } }, "Mark ready"),
        h("input", { className: "hs-field", type: "datetime-local", value: when, onChange: function (event) { setWhen(event.target.value); } }),
        h("button", { type: "button", className: "hs-button", disabled: props.busy || !when, onClick: function () { props.onSave({ status: "scheduled", scheduled_for: new Date(when).toISOString() }); } }, "Schedule"),
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: props.onDelete }, "Delete")),
    );
  }

  window.__HERMES_PLUGINS__.register("house-social", HouseSocial);
})();

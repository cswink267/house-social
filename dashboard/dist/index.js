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
      setBrands(roster.brands || []);
      setPieces(queue.pieces || []);
      setStudio(desk);
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
        variants[pair[0]] = { body: variant.body || "", hashtags: variant.hashtags || [], image_ready: !!variant.image_ready };
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
          section === "voice" ? h(VoiceGuide, { brand: brand, studio: studio, busy: busy, onSave: async function (body) {
            const saved = await run(function () {
              return SDK.fetchJSON("/api/plugins/house-social/brands/" + brand.id + "/voice", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
              });
            });
            if (saved) await refresh(brand.id);
          } }) : null,
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
          section === "create" ? h(CreatePanel, {
            brand: brand, idea: idea, setIdea: setIdea, pillar: pillar, setPillar: setPillar,
            format: format, setFormat: setFormat, hypothesis: hypothesis, setHypothesis: setHypothesis,
            busy: busy, onShape: shapeIdea, onCheck: checkVoice, voiceCheck: voiceCheck, active: active, pieces: pieces, onEdit: editVariant,
            onSave: savePiece, onDelete: removePiece, onOpen: function (piece) { setActiveId(piece.id); },
          }) : null,
          section === "calendar" ? h(Calendar, {
            brand: brand,
            calendar: studio && studio.calendar,
            busy: busy,
            onOpen: function (item) { setActiveId(item.id); setSection("create"); },
            onMove: placePiece,
            onPlan: planPiece,
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
    return h("div", { className: "hs-pillar" },
      h("div", { className: "hs-name" }, report.label || "Voice"),
      (report.fields || []).map(function (field) {
        return h("div", { key: field.field },
          h("div", { className: "hs-note" }, field.field),
          (field.checks || []).map(function (check) {
            return h("div", { key: field.field + check.id, className: check.ok ? "hs-ok" : "hs-bad" }, (check.ok ? "Yes. " : "No. ") + check.label);
          }));
      }));
  }

  function linesOf(value) {
    return String(value || "").split("\n").map(function (line) { return line.trim(); }).filter(Boolean);
  }

  function VoiceGuide(props) {
    const guide = (props.studio && props.studio.voice) || {};
    const stamp = [
      guide.tone, guide.personality, guide.visual,
      (guide.dos || []).join("|"), (guide.donts || []).join("|"),
      (guide.banned || []).join("|"), (guide.required || []).join("|"),
      guide.second_person ? "1" : "0",
      ((guide.examples || [])[0] || {}).text || "",
    ].join("\n");
    const [form, setForm] = useState(null);
    useEffect(function () {
      setForm({
        tone: guide.tone || "",
        personality: guide.personality || "",
        visual: guide.visual || "",
        dos: (guide.dos || []).join("\n"),
        donts: (guide.donts || []).join("\n"),
        banned: (guide.banned || []).join("\n"),
        required: (guide.required || []).join("\n"),
        second_person: !!guide.second_person,
        exampleTitle: ((guide.examples || [])[0] || {}).title || "",
        exampleText: ((guide.examples || [])[0] || {}).text || "",
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
        visual: form.visual,
        dos: linesOf(form.dos),
        donts: linesOf(form.donts),
        banned: linesOf(form.banned),
        required: linesOf(form.required),
        second_person: form.second_person,
        examples: (form.exampleText ? [{ title: form.exampleTitle, text: form.exampleText }] : []).concat((guide.examples || []).slice(1)),
      });
    }
    return h("form", { className: "hs-main", onSubmit: save },
      h("p", { className: "hs-note" }, "The voice for this brand. Create checks a draft against the banned lines, the required lines, and second person when that box is on."),
      h("label", { className: "hs-note" }, "Tone", h("textarea", { className: "hs-area", value: form.tone, onChange: function (event) { setField("tone", event.target.value); } })),
      h("label", { className: "hs-note" }, "Personality", h("textarea", { className: "hs-area", value: form.personality, onChange: function (event) { setField("personality", event.target.value); } })),
      h("label", { className: "hs-note" }, "Do", h("textarea", { className: "hs-area", placeholder: "One rule a line", value: form.dos, onChange: function (event) { setField("dos", event.target.value); } })),
      h("label", { className: "hs-note" }, "Don't", h("textarea", { className: "hs-area", placeholder: "One rule a line", value: form.donts, onChange: function (event) { setField("donts", event.target.value); } })),
      h("label", { className: "hs-note" }, "Visual", h("textarea", { className: "hs-area", value: form.visual, onChange: function (event) { setField("visual", event.target.value); } })),
      h("label", { className: "hs-note" }, "Banned words and phrases", h("textarea", { className: "hs-area", placeholder: "One phrase a line", value: form.banned, onChange: function (event) { setField("banned", event.target.value); } })),
      h("label", { className: "hs-note" }, "Required in the draft", h("textarea", { className: "hs-area", placeholder: "One phrase a line. Use ? for a question mark.", value: form.required, onChange: function (event) { setField("required", event.target.value); } })),
      h("label", { className: "hs-note" }, h("input", { type: "checkbox", checked: form.second_person, onChange: function (event) { setField("second_person", event.target.checked); } }), " Require you"),
      h("label", { className: "hs-note" }, "Example title", h("input", { className: "hs-field", value: form.exampleTitle, onChange: function (event) { setField("exampleTitle", event.target.value); } })),
      h("label", { className: "hs-note" }, "Example that nails it", h("textarea", { className: "hs-area", value: form.exampleText, onChange: function (event) { setField("exampleText", event.target.value); } })),
      (guide.examples || []).slice(1).map(function (example) {
        return h("div", { key: example.text, className: "hs-pillar" },
          h("div", { className: "hs-name" }, example.title || "Another line"),
          h("p", { className: "hs-note" }, example.text));
      }),
      (props.brand.pillars || []).length ? h("div", null,
        h("div", { className: "hs-name" }, "Pillars"),
        h("div", { className: "hs-pillars" }, props.brand.pillars.map(function (item) {
          return h("div", { key: item.id, className: "hs-pillar" }, h("div", { className: "hs-name" }, item.name), h("p", { className: "hs-note" }, item.note));
        }))) : null,
      (props.brand.guards || []).length ? h("ul", { className: "hs-guard" }, props.brand.guards.map(function (guard) {
        return h("li", { key: guard }, guard);
      })) : null,
      h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Save voice"),
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
      props.voiceCheck ? h(VoiceScore, { report: props.voiceCheck }) : null,
      props.active && props.active.brand_id === brand.id ? h(PieceEditor, {
        piece: props.active, busy: props.busy, onEdit: props.onEdit, onSave: props.onSave, onDelete: function () { props.onDelete(props.active.id); },
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

  function chipColor(item, colorBy, pillars) {
    if (colorBy === "pillar") {
      const index = (pillars || []).findIndex(function (pillar) { return pillar.id === item.pillar; });
      return index < 0 ? "#6e7278" : PILLAR_COLORS[index % PILLAR_COLORS.length];
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

  function Calendar(props) {
    const brand = props.brand || { pillars: [] };
    const entries = (props.calendar && props.calendar.entries) || [];
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
      const color = chipColor(item, colorBy, brand.pillars);
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
        h("button", { type: "button", className: "hs-tab" + (colorBy === "pillar" ? " is-on" : ""), onClick: function () { setColorBy("pillar"); } }, "By pillar")),
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
        h("button", { type: "submit", className: "hs-button", disabled: props.busy || !planIdea.trim() }, "Put it on this day")) : null,
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
    const perf = (props.studio && props.studio.performance) || { page_days: [], recorded_days: [], hours: [], posts: [], source: "none" };
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
    return h("div", { className: "hs-main" },
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
      h(RecordForm, { busy: props.busy, onRecorded: props.onRecorded }),
    );
  }

  function RecordForm(props) {
    const [form, setForm] = useState({ platform: "facebook", format: "unknown", published_at: "", local_hour: "", impressions: "", engagements: "", likes: "", comments: "", shares: "", note: "" });
    function setField(field, value) { setForm(function (current) { return Object.assign({}, current, { [field]: value }); }); }
    async function submit(event) {
      event.preventDefault();
      const metrics = {};
      ["impressions", "engagements", "likes", "comments", "shares"].forEach(function (key) {
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
        ["impressions", "engagements", "likes", "comments", "shares"].map(function (key) {
          return h("input", { key: key, className: "hs-field", placeholder: key, value: form[key], onChange: function (event) { setField(key, event.target.value); } });
        })),
      h("input", { className: "hs-field", placeholder: "What the post was", value: form.note, onChange: function (event) { setField("note", event.target.value); } }),
      h("button", { type: "submit", className: "hs-button", disabled: props.busy }, "Save result"),
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

  function PieceEditor(props) {
    const piece = props.piece;
    const [when, setWhen] = useState("");
    return h("div", null,
      h("div", { className: "hs-cols" }, PLATFORMS.map(function (pair) {
        const variant = (piece.variants && piece.variants[pair[0]]) || { body: "", hashtags: [], note: "" };
        return h("div", { key: pair[0] },
          h("div", { className: "hs-name" }, pair[1]),
          variant.note ? h("p", { className: "hs-note" }, variant.note) : null,
          h("textarea", { className: "hs-area", value: variant.body || "", onChange: function (event) { props.onEdit(pair[0], "body", event.target.value); } }),
          pair[0] === "instagram" ? h("input", {
            className: "hs-field", value: (variant.hashtags || []).join(" "), placeholder: "hashtags",
            onChange: function (event) { props.onEdit(pair[0], "hashtags", event.target.value.split(/\s+/).filter(Boolean)); },
          }) : null,
          variant.needs_image ? h("label", { className: "hs-note" },
            h("input", { type: "checkbox", checked: !!variant.image_ready, onChange: function (event) { props.onEdit(pair[0], "image_ready", event.target.checked); } }),
            " Quote image is ready") : null);
      })),
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
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onSave({ status: "planned" }); } }, "Mark planned"),
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: function () { props.onSave({ status: "ready" }); } }, "Mark ready"),
        h("input", { className: "hs-field", type: "datetime-local", value: when, onChange: function (event) { setWhen(event.target.value); } }),
        h("button", { type: "button", className: "hs-button", disabled: props.busy || !when, onClick: function () { props.onSave({ status: "scheduled", scheduled_for: new Date(when).toISOString() }); } }, "Schedule"),
        h("button", { type: "button", className: "hs-button", disabled: props.busy, onClick: props.onDelete }, "Delete")),
    );
  }

  window.__HERMES_PLUGINS__.register("house-social", HouseSocial);
})();

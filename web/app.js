"use strict";

const TOKEN = document.querySelector('meta[name="m4-token"]').content;
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "style") n.style.cssText = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) n.append(k.nodeType ? k : document.createTextNode(k));
  return n;
};
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
};

const ICONS = {
  performance: '<path d="M4 15a8 8 0 1 1 16 0"/><path d="m12 15 4-5"/>',
  lighting: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.4 1 1.1 1 1.8V16h5v-.3c0-.7.4-1.4 1-1.8A6 6 0 0 0 12 3Z"/>',
  buttons: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 3v6M6 9.5h12"/>',
  power: '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/>',
  setups: '<path d="M4 6h16M4 12h16M4 18h10"/><circle cx="18" cy="18" r="2"/>',
  reset: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  storage: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  history: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5v.7"/><path d="M12 17h.01"/>',
  manual: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z"/><path d="M4 19a2 2 0 0 1 2-2h13v4H6a2 2 0 0 1-2-2Z"/>',
};
const PAGES = { performance: "Performance", lighting: "Lighting", buttons: "Buttons", power: "Power", setups: "Setups", reset: "Reset & backup",
  storage: "Storage", history: "History", help: "Help", manual: "Manual" };
const NAV = [["performance", "lighting", "buttons", "power"], ["setups", "reset", "storage", "history"], ["help", "manual"]];
const MANUAL_URL = "https://cherryxtrfy.com/wp/wp-content/uploads/2021/12/Xtrfy-M4-RGB-Wireless-Quick-Start-Guide-20211206.pdf";

const EFFECTS = [[2, "Static"], [1, "Breathing"], [5, "Marquee"], [0, "Spectrum flow"], [7, "Colour breathing"], [3, "Neon"]];
const EFFECT_NAME = Object.fromEntries(EFFECTS);
const HAS_COLOR = new Set([1, 2, 5]);
const HAS_SPEED = new Set([0, 1, 3, 5, 7]);
const LED_OFF = 4;
const SWATCHES = ["#FF0000", "#FF7D00", "#FFE600", "#00FF00", "#00FFFF", "#0060FF", "#8000FF", "#FF00FF", "#FFFFFF"];
const POLLING = [125, 250, 500, 1000];
const SLEEP = [10, 30, 60, 120, 300, 600, 900, 1200];
const PHYSICAL = [
  { name: "Left button", x: 27, y: 16 },
  { name: "Right button", x: 73, y: 16 },
  { name: "Wheel click", x: 50, y: 20 },
  { name: "Side back", x: 5, y: 45 },
  { name: "Side forward", x: 5, y: 34 },
  { name: "Top button", x: 50, y: 46 },
];
const ACTIONS = [["Mouse", ["Left click", "Right click", "Middle click", "Back", "Forward"]], ["DPI", ["DPI cycle", "DPI up", "DPI down"]], ["", ["Disabled"]]];
const CAT_COLORS = { DPI: "#6b8fd6", Sensor: "#4fb3a5", Buttons: "#c99a4b", Lighting: "#b083c9", Power: "#86b05a", Unknown: "#5f646b", "Custom data": "#d97b7b", Free: "transparent" };
const HISTORY_FILTERS = [["all", "All"], ["Mouse button", "Mouse"], ["This app", "App"], ["auto", "Automatic"]];
const AUTO_SOURCES = new Set(["Auto lighting", "Restore", "Factory reset", "While app was closed"]);

let state = null;
let cfg = null;
let pending = {};
let saveTimer = null;
let saving = false;
let page = location.hash.slice(1) || store.get("m4.page", "performance");
if (!PAGES[page] || page === "manual") page = "performance";
let helpTopic = store.get("m4.help", "setup");
let historyFilter = "all";
let historyRows = [];
let menuOwner = null;

async function api(path, opts = {}) {
  const r = await fetch(path, {
    method: opts.method || "GET",
    headers: { "X-Token": TOKEN, ...(opts.body ? { "Content-Type": "application/json" } : {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (r.status === 403) { location.reload(); throw new Error("Reconnecting…"); }
  if (opts.raw) {
    if (!r.ok) throw new Error((await r.json()).error || r.statusText);
    return r;
  }
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

/* ---------------- saving ---------------- */

function change(patch, delay = 300) {
  if (!cfg) return;
  Object.assign(pending, patch);
  Object.assign(cfg, patch);
  if ("lights_on" in patch) {
    state.lights_off = !patch.lights_on;
    if (patch.lights_on) cfg.led_mode = state.last_led_mode ?? 2;
  }
  if ("led_mode" in patch) state.lights_off = false;
  for (const k of ["charge_cover", "autostart", "dpi_popup"]) if (k in patch) state[k] = patch[k];
  render();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flush, delay);
}

async function flush() {
  if (saving || !Object.keys(pending).length) return;
  const body = pending;
  pending = {};
  saving = true;
  setSave("saving");
  try {
    applyState(await api("/api/config", { method: "POST", body }));
    setSave(state.queued ? "queued" : "ok");
  } catch (e) {
    setSave("err", e.message);
    applyState(await api("/api/state"));
  } finally {
    saving = false;
    if (Object.keys(pending).length) flush();
  }
}

function setSave(kind, msg) {
  const s = $("#save");
  clearTimeout(s._fade);
  s.className = "save" + (kind === "err" ? " err" : "");
  s.textContent = kind === "saving" ? "Saving…" : kind === "ok" ? "Saved" : kind === "queued" ? "Saved, sends when the mouse wakes" : "Couldn't save: " + msg;
  if (kind === "ok") s._fade = setTimeout(() => s.classList.add("fade"), 1600);
}

function applyState(s) {
  state = s;
  cfg = s.config ? { ...s.config, ...pending } : null;
  render();
}

/* ---------------- shell ---------------- */

function buildNav() {
  const nav = $("#nav");
  NAV.forEach((ids, i) => {
    if (i) nav.append(el("hr"));
    for (const id of ids) {
      const b = el("button", { class: "nav-item", type: "button", "data-page": id, onclick: () => go(id) });
      b.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[id]}</svg><span>${PAGES[id]}</span>` +
        (id === "manual" ? '<svg class="ext" viewBox="0 0 24 24" aria-label="opens in your browser"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>' : "");
      nav.append(b);
    }
  });
}

function openManual() {
  if (window.pywebview?.api) window.pywebview.api.open_manual();
  else window.open(MANUAL_URL, "_blank", "noopener");
}

function go(id) {
  if (id === "manual") return openManual();
  page = id;
  store.set("m4.page", id);
  history.replaceState(null, "", "#" + id);
  if (id === "history") loadHistory();
  closeMenu();
  render();
  $("#pages").scrollTop = 0;
}

async function loadArt() {
  const names = [...new Set($$("[data-art]").map((n) => n.dataset.art))];
  const svgs = Object.fromEntries(await Promise.all(names.map(async (n) => [n, await (await fetch(`assets/${n}.svg`)).text()])));
  for (const n of $$("[data-art]")) n.innerHTML = svgs[n.dataset.art];
}

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (err ? " err" : "");
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.className = "toast"), 2600);
}

function confirmDialog(title, text, ok, danger = false) {
  const d = $("#dialog");
  $("#dialogTitle").textContent = title;
  $("#dialogText").textContent = text;
  const b = $("#dialogOk");
  b.textContent = ok;
  b.className = "btn " + (danger ? "btn-danger" : "btn-primary");
  d.showModal();
  return new Promise((res) => d.addEventListener("close", () => res(d.returnValue === "ok"), { once: true }));
}

/* One dropdown for every "pick one of many" control. */
function openMenu(anchor, groups, current, onPick, owner = anchor) {
  if (menuOwner === owner) return closeMenu();
  const m = $("#menu");
  m.replaceChildren(...groups.flatMap(([g, items]) => [
    g ? el("div", { class: "menu-group" }, g) : null,
    ...items.map(([value, label]) => el("button", { type: "button", role: "menuitemradio", "aria-checked": String(value === current),
      onclick: () => { closeMenu(); onPick(value); } }, label)),
  ].filter(Boolean)));
  m.hidden = false;
  menuOwner = owner;
  const r = anchor.getBoundingClientRect();
  m.style.minWidth = r.width + "px";
  const h = m.offsetHeight, w = m.offsetWidth;
  m.style.left = Math.min(window.innerWidth - w - 8, r.left) + "px";
  m.style.top = (r.bottom + h + 6 > window.innerHeight ? Math.max(8, r.top - h - 4) : r.bottom + 4) + "px";
  ($('[aria-checked="true"]', m) || $("button", m))?.focus();
}

function closeMenu() {
  $("#menu").hidden = true;
  menuOwner = null;
  if (cfg) markButton(null);
}

/* ---------------- render ---------------- */

function render() {
  $$(".nav-item").forEach((b) => (b.dataset.page === page ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current")));
  $("#pageTitle").textContent = PAGES[page];
  renderBanner();
  $$(".page").forEach((p) => p.classList.toggle("active", p.dataset.page === page));
  renderStatus();

  const needsMouse = !["help", "history"].includes(page);
  const ready = ["ready", "asleep"].includes(state?.status) && cfg;
  const asleep = state?.status === "asleep" && cfg;
  // Sleeping is normal and the header already says so; only speak up when changes are waiting to be sent.
  $("#notice").hidden = !(asleep && state.queued);
  $("#notice").textContent = "Your changes will be sent when you move the mouse.";
  $("#scanMacros").disabled = !!asleep;
  $("#empty").hidden = !needsMouse || !!ready;
  $("#pages").style.visibility = needsMouse && !ready ? "hidden" : "";
  renderHelp();
  if (!ready) return;
  renderPerformance();
  renderLighting();
  renderButtons();
  renderPower();
  renderSetups();
  renderReset();
  renderStorage();
  if (page === "history") renderHistory();
}

function renderStatus() {
  const s = state?.status;
  if (s === "asleep") {
    $("#emptyTitle").textContent = "The mouse is asleep";
    $("#emptyText").textContent = "Move it to wake it up. Its settings will show here.";
  } else {
    $("#emptyTitle").textContent = "No mouse found";
    $("#emptyText").textContent = "Plug in the receiver or the USB cable, and slide the switch under the mouse out of OFF.";
  }
}

function fact(label, value, colour) {
  return el("div", {}, el("dt", {}, label), el("dd", {}, colour && el("span", { class: "fdot", style: `--c:${colour}` }), value));
}

function renderBanner() {
  const s = state?.status, b = state?.battery;
  const status = !state ? "Starting…" : s === "ready" ? (state.connection === "cable" ? "Wired" : "Wireless") : s === "asleep" ? "Asleep" : "Not connected";
  const dotColour = s === "ready" ? "var(--ok)" : s === "asleep" ? "var(--warn)" : "var(--text-3)";
  const facts = [fact("Connection", status, dotColour)];
  if (b) facts.push(fact("Battery", `${b.percent}%${b.charging ? ", charging" : ""}`));
  if (cfg && (s === "ready" || s === "asleep")) {
    facts.push(fact("Polling", `${cfg.polling} Hz`));
    facts.push(fact("Sensitivity", `${cfg.dpi[cfg.active_stage].toLocaleString()} DPI`, cfg.colors[cfg.active_stage]));
  }
  $("#facts").replaceChildren(...facts);
  renderViews();
}

/* Every drawing of the mouse shows its real lighting: effect, colour, brightness and speed. */
function renderViews() {
  let fx = "fx-off", led = "#ffffff", bri = 0.8, dur = 3;
  if (cfg && state?.status === "ready") {
    const covering = state.lights_off && state.covering;
    const on = !state.lights_off && cfg.led_mode !== LED_OFF;
    if (on || covering) {
      fx = `fx-${cfg.led_mode}`;
      led = cfg.led_color;
      bri = 0.25 + cfg.led_brightness * 0.075;
      dur = 6.5 - cfg.led_speed * 0.55;
    }
  }
  for (const v of $$("[data-view]")) {
    v.className = v.className.replace(/\bfx-\S+/g, "").trim() + " " + fx;
    v.style.setProperty("--led", led);
    v.style.setProperty("--bri", bri.toFixed(2));
    v.style.setProperty("--dur", dur.toFixed(2) + "s");
  }
  const cap = $("#previewCaption");
  if (cap && cfg) {
    cap.textContent = state.lights_off ? (state.covering ? "Lights off · faint glow while charging" : "Lights off")
      : `${EFFECT_NAME[cfg.led_mode] ?? "Custom"} · brightness ${cfg.led_brightness}/10`;
  }
}

function seg(container, values, current, label, onPick) {
  if (container.children.length !== values.length) {
    container.replaceChildren(...values.map((v) => el("button", { type: "button", "data-v": v, onclick: () => onPick(v) }, label(v))));
  }
  for (const b of container.children) b.setAttribute("aria-pressed", String(b.dataset.v === String(current)));
}

function setRange(input, value, out, fmt) {
  if (document.activeElement !== input) input.value = value;
  input.style.setProperty("--fill", ((input.value - input.min) / (input.max - input.min)) * 100 + "%");
  out.textContent = fmt(input.value);
}

function renderPerformance() {
  const box = $("#stages");
  if (!box.children.length) {
    box.replaceChildren(...cfg.dpi.map((_, i) => el("div", { class: "stage", role: "radio", tabindex: "0", "data-i": i,
      onclick: () => pickStage(i),
      onkeydown: (e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); pickStage(i); } } },
      el("span", { class: "radio" }),
      el("label", { class: "chip-colour", title: "Change colour", onclick: (e) => e.stopPropagation() },
        el("input", { type: "color", "aria-label": `Stage ${i + 1} colour`,
          onchange: (e) => change({ colors: cfg.colors.map((c, k) => (k === i ? e.target.value.toUpperCase() : c)) }, 0) })),
      el("span", { class: "stage-name" }, `Stage ${i + 1}`),
      el("span", { class: "dpi-field" },
        el("input", { inputmode: "numeric", "aria-label": `Stage ${i + 1} DPI`, onclick: (e) => e.stopPropagation(),
          onkeydown: (e) => { if (e.key === "Enter") e.target.blur(); }, onchange: (e) => commitDpi(i, e.target) }),
        el("span", {}, "DPI")),
      el("button", { class: "stage-remove", type: "button", "aria-label": `Remove stage ${i + 1}`, title: "Remove this stage",
        onclick: (e) => { e.stopPropagation(); removeStage(i); } }, "×"))));
  }
  [...box.children].forEach((row, i) => {
    row.style.setProperty("--c", cfg.colors[i]);
    row.classList.toggle("active", i === cfg.active_stage);
    row.classList.toggle("idle", i >= cfg.stage_count);
    row.setAttribute("aria-checked", String(i === cfg.active_stage));
    row.title = i >= cfg.stage_count ? "Not in the DPI button's cycle. Click to add it." : "";
    $(".stage-remove", row).hidden = i >= cfg.stage_count || cfg.stage_count === 1;
    const input = $(".dpi-field input", row);
    if (document.activeElement !== input) input.value = cfg.dpi[i].toLocaleString();
    $('input[type="color"]', row).value = cfg.colors[i].toLowerCase();
  });
  $("#stageCount").textContent = cfg.stage_count;
  const active = cfg.active_stage;
  $("#readoutDot").style.setProperty("--c", cfg.colors[active]);
  $("#readoutValue").textContent = cfg.dpi[active].toLocaleString();
  $("#readoutStage").textContent = `Stage ${active + 1} of ${cfg.stage_count}`;
  const lad = $("#ladder");
  if (!$(".mark", lad)) cfg.dpi.forEach((_, i) => lad.append(el("button", { class: "mark", type: "button", tabindex: "-1", "aria-hidden": "true", onclick: () => pickStage(i) })));
  const pos = (d) => ((Math.log(d) - Math.log(50)) / (Math.log(19000) - Math.log(50))) * 100;
  $$(".mark", lad).forEach((m, i) => {
    m.style.left = pos(cfg.dpi[i]) + "%";
    m.style.setProperty("--c", cfg.colors[i]);
    m.classList.toggle("active", i === active);
    m.classList.toggle("idle", i >= cfg.stage_count);
    m.title = `Stage ${i + 1}: ${cfg.dpi[i].toLocaleString()} DPI`;
  });
  seg($("#polling"), POLLING, cfg.polling, (v) => `${v} Hz`, (v) => change({ polling: v }, 0));
  seg($("#lod"), [1, 2], cfg.lod, (v) => `${v} mm`, (v) => change({ lod: v }, 0));
  setRange($("#debounce"), cfg.debounce, $("#debounceOut"), (v) => `${v} ms`);
  for (const sw of $$(".switch[data-key]")) sw.checked = !!cfg[sw.dataset.key];
}

/* The mouse always stores 8 slots; removing one moves the later ones up and parks it after the last used slot. */
function removeStage(i) {
  const order = [...Array(8).keys()].filter((k) => k !== i);
  order.splice(cfg.stage_count - 1, 0, i);
  const a = cfg.active_stage;
  change({
    dpi: order.map((k) => cfg.dpi[k]),
    colors: order.map((k) => cfg.colors[k]),
    stage_count: cfg.stage_count - 1,
    active_stage: a > i ? a - 1 : a === i ? Math.min(i, cfg.stage_count - 2) : a,
  }, 0);
  toast(`Removed stage ${i + 1} (${cfg.dpi[cfg.stage_count] ?? ""} DPI). Press + to bring a stage back.`.replace(" ( DPI)", ""));
}

function sortStages() {
  const used = [...Array(cfg.stage_count).keys()].sort((x, y) => cfg.dpi[x] - cfg.dpi[y]);
  const order = [...used, ...[...Array(8).keys()].slice(cfg.stage_count)];
  if (order.every((k, i) => k === i)) return toast("Stages are already in order.");
  change({ dpi: order.map((k) => cfg.dpi[k]), colors: order.map((k) => cfg.colors[k]), active_stage: order.indexOf(cfg.active_stage) }, 0);
}

function pickStage(i) {
  change(i >= cfg.stage_count ? { stage_count: i + 1, active_stage: i } : { active_stage: i }, 0);
}

function commitDpi(i, input) {
  const raw = parseInt(String(input.value).replace(/\D/g, ""), 10);
  if (!raw) return render();
  let v = Math.max(50, Math.min(19000, raw));
  v = v <= 10000 ? Math.round(v / 50) * 50 : Math.round(v / 100) * 100;
  if (v !== raw) toast(`Set to ${v.toLocaleString()} DPI, the nearest value the sensor supports.`);
  change({ dpi: cfg.dpi.map((d, k) => (k === i ? v : d)) }, 0);
}

function renderLighting() {
  const on = !state.lights_off && cfg.led_mode !== LED_OFF;
  $("#lightsOn").checked = on;
  $("#effect").textContent = EFFECT_NAME[on ? cfg.led_mode : state.last_led_mode] ?? "Static";
  const needs = { on, colour: on && HAS_COLOR.has(cfg.led_mode), speed: on && HAS_SPEED.has(cfg.led_mode) };
  $$('[data-page="lighting"] [data-needs]').forEach((r) => r.classList.toggle("off", !needs[r.dataset.needs]));
  $("#colourHint").textContent = on && !needs.colour ? `${EFFECT_NAME[cfg.led_mode]} uses its own colours.` : "";

  const sw = $("#swatches");
  if (!sw.children.length) {
    sw.replaceChildren(...SWATCHES.map((c) => el("button", { class: "swatch", type: "button", style: `--c:${c}`, "data-c": c,
      "aria-label": `Colour ${c}`, onclick: () => change({ led_color: c }, 0) })),
      el("label", { class: "swatch custom", title: "Custom colour" }, "+",
        el("input", { type: "color", id: "customColour", "aria-label": "Custom colour", onchange: (e) => change({ led_color: e.target.value.toUpperCase() }, 0) })));
  }
  for (const b of $$(".swatch[data-c]", sw)) b.setAttribute("aria-pressed", String(b.dataset.c === cfg.led_color));
  $("#customColour").value = cfg.led_color.toLowerCase();
  setRange($("#ledBri"), cfg.led_brightness, $("#ledBriOut"), (v) => `${v}/10`);
  setRange($("#ledSpeed"), cfg.led_speed, $("#ledSpeedOut"), (v) => `${v}/10`);
  $("#chargeCover").checked = !!state.charge_cover;
  $("#coverHint").hidden = !state.charge_cover || !!state.autostart;
}

function renderButtons() {
  const pins = $("#pins"), rows = $("#buttonRows");
  if (!pins.children.length) {
    PHYSICAL.forEach((p, i) => {
      pins.append(el("button", { class: "pin", type: "button", style: `left:${p.x}%;top:${p.y}%`, "aria-label": p.name,
        onclick: (e) => openActions(i, $(`.select[data-i="${i}"]`)), onmouseenter: () => markButton(i), onmouseleave: () => markButton(null) }, String(i + 1)));
      rows.append(el("div", { class: "row", onmouseenter: () => markButton(i), onmouseleave: () => markButton(null) },
        el("div", { class: "row-text" }, el("div", { class: "row-label" }, el("span", { class: "num" }, String(i + 1)), p.name)),
        el("button", { class: "select", type: "button", "data-i": i, onclick: (e) => openActions(i, e.currentTarget) })));
    });
  }
  $$(".select[data-i]", rows).forEach((b, i) => (b.textContent = cfg.buttons[i]));
}

function markButton(i) {
  const sel = menuOwner?.dataset?.i != null ? +menuOwner.dataset.i : null;
  $$("#pins .pin").forEach((p, k) => p.classList.toggle("on", k === i || k === sel));
  $$("#buttonRows .row").forEach((r, k) => r.classList.toggle("on", k === i || k === sel));
}

function openActions(i, anchor) {
  openMenu(anchor, ACTIONS.map(([g, items]) => [g, items.map((a) => [a, a])]), cfg.buttons[i], (a) => assign(i, a));
  markButton(i);
}

async function assign(i, action) {
  const next = cfg.buttons.map((b, k) => (k === i ? action : b));
  if (!next.includes("Left click") &&
      !(await confirmDialog("No button set to left click", "You'd have to use the keyboard to change it back. Save anyway?", "Save anyway", true))) return;
  change({ buttons: next }, 0);
}

function renderSetups() {
  const list = $("#setupList");
  const items = state.setups || [];
  const active = items.find((x) => x.active);
  $("#setupSwitch").textContent = active ? active.name : items.length ? "Unsaved setup" : "No saved setups";
  $("#setupSwitch").classList.toggle("unsaved", !active);
  if (!items.length) {
    list.replaceChildren(el("div", { class: "row" }, el("div", { class: "row-text" },
      el("div", { class: "row-label" }, "No setups yet"),
      el("div", { class: "row-hint" }, "Set the mouse up the way you like, then save it below. You can switch back to it any time."))));
    return;
  }
  list.replaceChildren(...items.map((x) => el("div", { class: "row setup-row" + (x.active ? " current" : "") },
    el("div", { class: "row-text" },
      el("div", { class: "row-label" }, el("span", { class: "fdot", style: `--c:${x.colour}` }), x.name),
      el("div", { class: "row-hint" }, `${x.dpi.toLocaleString()} DPI · ${x.polling} Hz · saved ${x.created}`)),
    el("div", { class: "setup-actions" },
      x.active ? el("span", { class: "in-use" }, "In use")
        : el("button", { class: "btn", type: "button", onclick: () => applySetup(x) }, "Apply"),
      el("button", { class: "icon-btn more", type: "button", "aria-label": `More actions for ${x.name}`,
        onclick: (e) => openMenu(e.currentTarget, [["", [["update", "Update with current settings"], ["rename", "Rename…"], ["delete", "Delete…"]]]], null,
          (a) => setupAction(a, x)) }, "⋯")))));
}

async function applySetup(x) {
  try { applyState(await api("/api/setups/apply", { method: "POST", body: { id: x.id } })); toast(`Switched to ${x.name}.`); }
  catch (e) { toast("Couldn't switch: " + e.message, true); }
}

async function setupAction(action, x) {
  try {
    if (action === "update") {
      if (!(await confirmDialog(`Update ${x.name}?`, "It will store the mouse's current settings instead of the old ones.", "Update"))) return;
      applyState(await api("/api/setups", { method: "POST", body: { overwrite: x.id } }));
      toast(`${x.name} updated.`);
    } else if (action === "rename") {
      const name = window.prompt("New name", x.name);
      if (name && name.trim()) applyState(await api("/api/setups/rename", { method: "POST", body: { id: x.id, name } }));
    } else if (action === "delete") {
      if (!(await confirmDialog(`Delete ${x.name}?`, "The setup is removed from this PC. The mouse's current settings don't change.", "Delete", true))) return;
      applyState(await api(`/api/setups/${x.id}`, { method: "DELETE" }));
    }
  } catch (e) { toast(e.message, true); }
}

function renderPower() {
  const b = state.battery;
  $("#batteryValue").textContent = b ? `${b.percent}%${b.charging ? ", charging" : ""}` : "—";
  $("#sleep").textContent = fmtSleep(cfg.sleep_s);
  $("#autostart").checked = !!state.autostart;
  $("#dpiPopup").checked = state.dpi_popup !== false;
}
const fmtSleep = (s) => (s < 60 ? `${s} seconds` : s === 60 ? "1 minute" : `${s / 60} minutes`);

function renderReset() {
  $("#factoryReset").disabled = state.connection !== "cable" || state.status !== "ready";
  $("#factoryHint").textContent = state.connection === "cable"
    ? "Xtrfy's defaults: 800 DPI, rainbow lighting."
    : "Xtrfy's defaults: 800 DPI, rainbow lighting. Plug the cable into the mouse to use this.";
  const o = state.original;
  $("#originalHint").textContent = o
    ? `How the mouse was the first time this app read it: ${o.dpi.toLocaleString()} DPI, ${o.led_mode === LED_OFF ? "lights off" : (EFFECT_NAME[o.led_mode] ?? "custom").toLowerCase() + " lighting"}.`
    : "How the mouse was the first time this app read it.";
  $("#restoreOriginal").disabled = !!state.is_original || !o;
  $("#restoreOriginal").textContent = state.is_original ? "In use" : "Restore…";
}

function renderStorage() {
  const st = state.storage;
  const bytes = st.page.match(/../g).map((h) => parseInt(h, 16));
  const regionAt = (a) => st.regions.find(([s, n]) => a >= s && a < s + n);
  const catOf = (a) => { const r = regionAt(a); return r[3] === "Free" && bytes[a] !== 0xff ? "Custom data" : r[3]; };
  const totals = {};
  bytes.forEach((_, a) => { const c = catOf(a); totals[c] = (totals[c] || 0) + 1; });
  $("#storageSummary").textContent = `256 bytes: ${st.profile_len} hold settings, ${totals.Free || 0} are free` +
    (totals["Custom data"] ? `, ${totals["Custom data"]} hold custom data.` : ".");
  const order = ["DPI", "Buttons", "Sensor", "Lighting", "Power", "Unknown", "Custom data", "Free"].filter((c) => totals[c]);
  $("#usage").replaceChildren(...order.filter((c) => c !== "Free").map((c) => el("span", { style: `width:${(totals[c] / 256) * 100}%;background:${CAT_COLORS[c]}`, title: `${c}: ${totals[c]} bytes` })));
  $("#legend").replaceChildren(...order.map((c) => el("span", {}, el("i", { style: c === "Free" ? "box-shadow:inset 0 0 0 1px var(--line-2)" : `background:${CAT_COLORS[c]}` }), `${c} ${totals[c]}`)));

  const map = $("#bytemap");
  if (!map.children.length) {
    map.append(el("span"));
    for (let c = 0; c < 16; c++) map.append(el("span", { class: "h" }, c.toString(16).toUpperCase()));
    for (let r = 0; r < 16; r++) {
      map.append(el("span", { class: "h" }, r.toString(16).toUpperCase() + "0"));
      for (let c = 0; c < 16; c++) {
        const a = r * 16 + c;
        map.append(el("button", { class: "byte", type: "button", "data-a": a, "aria-label": `Byte 0x${a.toString(16)}`,
          onmouseenter: () => showByte(a), onfocus: () => showByte(a) }));
      }
    }
  }
  for (const b of $$(".byte", map)) {
    const c = catOf(+b.dataset.a);
    b.classList.toggle("free", c === "Free");
    b.style.background = c === "Free" ? "" : CAT_COLORS[c];
  }
  renderStorage.ctx = { bytes, regionAt, catOf };
}

function showByte(a) {
  const { bytes, regionAt, catOf } = renderStorage.ctx;
  const [start, n, name] = regionAt(a);
  const cat = catOf(a);
  $$(".byte").forEach((b) => b.classList.toggle("sel", +b.dataset.a === a));
  $("#byteDetail").replaceChildren(
    el("div", { class: "addr" }, "0x" + a.toString(16).toUpperCase().padStart(2, "0")),
    el("div", {}, cat === "Free" ? "Free space" : cat === "Custom data" ? "Custom data" : name),
    el("dl", { class: "kv" },
      el("dt", {}, "Group"), el("dd", {}, cat),
      el("dt", {}, "Byte"), el("dd", {}, `${a - start + 1} of ${n}`),
      el("dt", {}, "Value"), el("dd", {}, `0x${bytes[a].toString(16).toUpperCase().padStart(2, "0")} (${bytes[a]})`)));
}

async function scanMacros() {
  const btn = $("#scanMacros");
  btn.disabled = true;
  $("#macroText").textContent = "Scanning…";
  try {
    const r = await api("/api/macros/scan", { method: "POST" });
    $("#macroText").textContent = r.used_slots.length
      ? `${r.used_slots.length} of 16 slots in use (${r.used_bytes} bytes)` : "Empty: no macros or key bindings stored";
  } catch (e) {
    $("#macroText").textContent = "Scan failed: " + e.message;
  } finally {
    btn.disabled = false;
  }
}

/* ---------------- history ---------------- */

async function loadHistory() {
  try { historyRows = await api("/api/history"); } catch { historyRows = []; }
  renderHistory();
}

function renderHistory() {
  seg($("#historyFilter"), HISTORY_FILTERS.map(([k]) => k), historyFilter,
    (k) => HISTORY_FILTERS.find(([x]) => x === k)[1], (k) => { historyFilter = k; renderHistory(); });
  const keep = (r) => historyFilter === "all" || (historyFilter === "auto" ? AUTO_SOURCES.has(r.source) : r.source === historyFilter);
  const rows = historyRows.filter(keep).reverse();
  const tl = $("#timeline");
  $("#clearHistory").disabled = !historyRows.length;
  if (!rows.length) {
    tl.replaceChildren(el("p", { class: "empty-note" }, historyRows.length ? "Nothing matches this filter." : "No changes yet. Changes from this app and from the mouse's own buttons appear here."));
    return;
  }
  const today = new Date().toISOString().slice(0, 10);
  const out = [];
  let day = null;
  for (const r of rows) {
    const [d, t] = r.time.split(" ");
    if (d !== day) {
      day = d;
      out.push(el("div", { class: "day" }, d === today ? "Today" : new Date(d + "T00:00").toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })));
    }
    out.push(el("div", { class: "entry" }, el("time", {}, t.slice(0, 5)), el("div", {}, r.change), el("span", { class: "src" }, r.source)));
  }
  tl.replaceChildren(...out);
}

/* ---------------- help ---------------- */

function renderHelp() {
  const nav = $("#helpNav");
  if (!nav.children.length) {
    for (const g of window.HELP) {
      nav.append(el("div", { class: "group-label" }, g.group));
      for (const t of g.topics) nav.append(el("button", { type: "button", "data-id": t.id,
        onclick: () => { helpTopic = t.id; store.set("m4.help", t.id); renderHelp(); $("#pages").scrollTop = 0; } }, t.title));
    }
  }
  const all = window.HELP.flatMap((g) => g.topics);
  const t = all.find((x) => x.id === helpTopic) || all[0];
  for (const b of $$("button", nav)) b.setAttribute("aria-current", String(b.dataset.id === t.id));
  const body = $("#helpBody");
  if (body.dataset.id === t.id) return;
  body.dataset.id = t.id;
  const fig = (img) => el("figure", {}, el("img", { src: `assets/help/${img}.webp`, alt: `Quick-start guide illustration: ${t.title}`, loading: "lazy" }));
  body.replaceChildren(...[
    el("h2", {}, t.title),
    el("p", {}, t.lead),
    t.steps && el("ol", {}, t.steps.map((s) => el("li", {}, s))),
    t.list && el("ul", {}, t.list.map(([k, v]) => el("li", {}, el("strong", {}, k), ": ", v))),
    t.dots && el("div", { class: "levels" }, t.dots.map(([c, l]) => el("span", {}, el("i", { style: `background:${c}` }), l))),
    t.note && el("p", { class: "muted" }, t.note),
    fig(t.img),
    t.extra && fig(t.extra),
    el("div", { class: "help-actions" },
      t.link && t.link[0] !== "manual" && el("button", { class: "btn", type: "button", onclick: () => go(t.link[0]) }, t.link[1]),
      el("button", { class: "btn btn-quiet", type: "button", onclick: openManual }, "Open the full manual")),
  ].filter(Boolean));
}

/* ---------------- wiring ---------------- */

async function restoreAction(path, title, text, ok, done) {
  if (!(await confirmDialog(title, text, ok, true))) return;
  try {
    applyState(await api(path, { method: "POST" }));
    toast(done);
  } catch (e) {
    toast(e.message, true);
  }
}

function wire() {
  $("#sortStages").addEventListener("click", sortStages);
  $$(".stepper [data-step]").forEach((b) => b.addEventListener("click", () => {
    const n = Math.max(1, Math.min(8, cfg.stage_count + +b.dataset.step));
    if (n !== cfg.stage_count) change({ stage_count: n, active_stage: Math.min(cfg.active_stage, n - 1) });
  }));
  const range = (id, key) => {
    const i = $(id);
    i.addEventListener("input", () => { cfg[key] = +i.value; render(); });
    i.addEventListener("change", () => change({ [key]: +i.value }, 0));
  };
  range("#debounce", "debounce");
  range("#ledBri", "led_brightness");
  range("#ledSpeed", "led_speed");
  $$(".switch[data-key]").forEach((s) => s.addEventListener("change", () => change({ [s.dataset.key]: s.checked }, 0)));
  $("#lightsOn").addEventListener("change", (e) => change({ lights_on: e.target.checked }, 0));
  $("#chargeCover").addEventListener("change", (e) => change({ charge_cover: e.target.checked }, 0));
  $("#autostart").addEventListener("change", (e) => change({ autostart: e.target.checked }, 0));
  $("#dpiPopup").addEventListener("change", (e) => change({ dpi_popup: e.target.checked }, 0));
  $("#setupSwitch").addEventListener("click", (e) => {
    const items = state?.setups || [];
    if (!items.length) return go("setups");
    openMenu(e.currentTarget, [["Setups", items.map((x) => [x.id, x.name])], ["", [["__manage", "Manage setups…"]]]],
      items.find((x) => x.active)?.id, (id) => (id === "__manage" ? go("setups") : applySetup(items.find((x) => x.id === id))));
  });
  $("#setupForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("#setupName").value.trim();
    if (!name) return $("#setupName").focus();
    try {
      applyState(await api("/api/setups", { method: "POST", body: { name } }));
      $("#setupName").value = "";
      toast(`Saved ${name}.`);
    } catch (err) { toast("Couldn't save: " + err.message, true); }
  });
  $("#effect").addEventListener("click", (e) => openMenu(e.currentTarget, [["", EFFECTS]], cfg.led_mode, (m) => change({ led_mode: m }, 0)));
  $("#sleep").addEventListener("click", (e) => openMenu(e.currentTarget, [["", SLEEP.map((s) => [s, fmtSleep(s)])]], cfg.sleep_s, (s) => change({ sleep_s: s }, 0)));

  $("#factoryReset").addEventListener("click", () => restoreAction("/api/factory-reset", "Reset to factory settings?",
    "Every setting goes back to Xtrfy's defaults: 800 DPI and rainbow lighting. You can undo this with Your original settings or a backup.",
    "Reset", "Factory settings restored."));
  $("#restoreOriginal").addEventListener("click", () => restoreAction("/api/restore-original", "Restore your original settings?",
    "Every setting goes back to how the mouse was before this app first changed it.", "Restore", "Original settings restored."));
  $("#backupBtn").addEventListener("click", async () => {
    try {
      if (window.pywebview?.api) {
        const name = await window.pywebview.api.save_backup();
        if (name) toast(`Saved as ${name}.`);
        return;
      }
      const blob = await (await api("/api/backup", { raw: true })).blob();
      el("a", { href: URL.createObjectURL(blob), download: "xtrfy-m4-backup.m4" }).click();
    } catch (e) { toast("Couldn't save the backup: " + e.message, true); }
  });
  $("#restoreFile").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    const buf = new Uint8Array(await f.arrayBuffer());
    let bin = "";
    buf.forEach((b) => (bin += String.fromCharCode(b)));
    try { applyState(await api("/api/restore", { method: "POST", body: { data: btoa(bin) } })); toast(`Loaded ${f.name}.`); }
    catch (err) { toast("Couldn't load that file: " + err.message, true); }
  });
  $("#scanMacros").addEventListener("click", scanMacros);
  $("#clearHistory").addEventListener("click", async () => {
    if (!(await confirmDialog("Clear history?", "All recorded changes are deleted. This can't be undone.", "Clear", true))) return;
    historyRows = await api("/api/history", { method: "DELETE" });
    renderHistory();
  });

  document.addEventListener("click", (e) => { if (!$("#menu").hidden && !e.target.closest(".menu, .select, .pin")) closeMenu(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });
  $("#pages").addEventListener("scroll", closeMenu, { passive: true });
  window.addEventListener("resize", closeMenu);
  window.addEventListener("hashchange", () => { const p = location.hash.slice(1); if (PAGES[p] && p !== page) go(p); });
}

function connect() {
  const es = new EventSource(`/api/events?token=${encodeURIComponent(TOKEN)}`);
  es.onmessage = (e) => {
    const s = JSON.parse(e.data);
    const changed = state && s.version !== state.version;
    if (!saving) applyState(s);
    if (changed && page === "history") loadHistory();
  };
  es.onerror = () => {
    renderStatus();
    clearTimeout(connect.retry);
    connect.retry = setTimeout(() => api("/api/state").then(applyState).catch(() => {}), 2000);
  };
}

buildNav();
wire();
loadArt();
go(page);
api("/api/state").then(applyState).catch(() => {});
connect();

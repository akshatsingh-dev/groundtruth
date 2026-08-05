/* Deliverable — local client.
 *
 * Reads the agent's stream and renders it. Nothing here computes a permit
 * answer; every number on the page arrives from agent/ over the wire.
 */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const KIND_TAG = {
  plan: "PLAN",
  reasoning: "REASON",
  thought: "THINK",
  tool: "TOOL",
  observation: "RESULT",
  conclusion: "CONCLUDE",
  note: "NOTE",
  error: "ERROR",
};

const PATHWAY_SEVERITY = {
  permit_by_rule: "good",
  minor_nsr: "good",
  synthetic_minor: "warn",
  major_psd: "crit",
  major_nonattainment_nsr: "crit",
};

const state = {
  ctx: null,
  running: false,
  follow: true,
  filter: "all",
  stepCount: 0,
  report: null,
  armed: null,
  altEstimate: null,
};

/* ------------------------------------------------------------------ utils */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function fmt(n, digits = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function months(n) {
  return n === null || n === undefined ? "—" : fmt(n, 0);
}

/* Minimal markdown: paragraphs and **bold**. The narrative comes back from the
   model with those two things in it and nothing else. */
function prose(text, className) {
  const wrap = el("div", className);
  String(text || "")
    .split(/\n{2,}/)
    .filter((p) => p.trim())
    .forEach((para) => {
      const p = el("p");
      para.split(/(\*\*[^*]+\*\*)/g).forEach((chunk) => {
        if (chunk.startsWith("**") && chunk.endsWith("**")) {
          p.appendChild(el("strong", null, chunk.slice(2, -2)));
        } else if (chunk) {
          p.appendChild(document.createTextNode(chunk.replace(/\n/g, " ")));
        }
      });
      wrap.appendChild(p);
    });
  return wrap;
}

/* ------------------------------------------------------------------ setup */

async function boot() {
  const res = await fetch("/api/context");
  const ctx = await res.json();
  state.ctx = ctx;

  $("#m-auth").textContent = ctx.auth_label;
  $("#m-auth").title = ctx.auth_detail;
  $("#m-provider").textContent = ctx.provider;
  $("#m-provider").title = ctx.provider_note;
  $("#m-session").textContent = fmt(ctx.account.credits_spent);
  $("#m-cache").textContent = fmt(ctx.account.cache_hits);

  fillSelect($("#f-prime"), ctx.prime_movers);
  fillSelect($("#f-fuel"), ctx.fuels);
  fillSelect($("#f-controls"), ctx.controls);
  $("#f-loop").value = ctx.auth === "none" ? "none" : "llm";

  renderKeyWarnings(ctx);
  renderPresets(ctx.presets);
  renderFilters();
  applyPreset(ctx.presets[1]);
  updateRunCost();

  if (!ctx.demo_available) $("#btn-replay").disabled = true;
}

function fillSelect(select, options) {
  select.innerHTML = "";
  options.forEach((o) => {
    const opt = el("option", null, o.label);
    opt.value = o.value;
    select.appendChild(opt);
  });
}

function renderKeyWarnings(ctx) {
  const host = $("#key-warnings");
  host.innerHTML = "";
  const missing = ctx.keys.filter((k) => !k.present);
  const hasLoop = ctx.keys.some(
    (k) => k.present && (k.name === "CLAUDE_CODE_OAUTH_TOKEN" || k.name === "ANTHROPIC_API_KEY")
  );
  missing
    .filter((k) => !(hasLoop && (k.name === "CLAUDE_CODE_OAUTH_TOKEN" || k.name === "ANTHROPIC_API_KEY")))
    .forEach((k) => {
      const box = el("div", "keywarn");
      box.appendChild(el("div", "keywarn-head", `${k.name} is not set in .env`));
      box.appendChild(el("div", "keywarn-body", k.enables));
      host.appendChild(box);
    });
  if (!ctx.dotenv) {
    const box = el("div", "keywarn");
    box.appendChild(el("div", "keywarn-head", "python-dotenv is not installed"));
    box.appendChild(
      el("div", "keywarn-body", "Keys are read from the environment only. pip install -r requirements.txt.")
    );
    host.appendChild(box);
  }
}

function renderPresets(presets) {
  const host = $("#presets");
  host.innerHTML = "";
  presets.forEach((p) => {
    const btn = el("button", "preset");
    btn.type = "button";
    btn.setAttribute("aria-pressed", "false");
    btn.dataset.id = p.id;
    btn.appendChild(el("span", "preset-name", `${p.name} · ${p.address}`));
    btn.appendChild(el("span", "preset-sub", p.subtitle));
    const controls = p.controls.length
      ? p.controls.map((c) => c.replace(/_/g, " ")).join(" + ")
      : "uncontrolled";
    btn.appendChild(
      el("span", "preset-spec", `${p.mw} MW ${p.prime_mover.replace(/_/g, " ")} · ${controls}`)
    );
    btn.addEventListener("click", () => applyPreset(p));
    host.appendChild(btn);
  });
}

function applyPreset(p) {
  if (!p) return;
  $("#f-address").value = p.address;
  $("#f-county").value = p.county || "";
  $("#f-state").value = p.state || "";
  $("#f-mw").value = p.mw;
  $("#f-prime").value = p.prime_mover;
  $("#f-fuel").value = p.fuel;
  $("#f-target").value = p.target || "";
  $$("#f-controls option").forEach((o) => {
    o.selected = p.controls.includes(o.value);
  });
  $$(".preset").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.id === p.id)));
  disarm();
}

function renderFilters() {
  const host = $("#trace-filters");
  host.innerHTML = "";
  [["all", "ALL"], ["plan", "PLAN"], ["reasoning", "REASON"], ["tool", "TOOL"], ["observation", "RESULT"], ["conclusion", "CONCLUDE"]].forEach(
    ([kind, label]) => {
      const btn = el("button", "filter", label);
      btn.type = "button";
      btn.setAttribute("aria-pressed", String(state.filter === kind));
      btn.addEventListener("click", () => {
        state.filter = kind;
        $$(".filter", host).forEach((b) => b.setAttribute("aria-pressed", "false"));
        btn.setAttribute("aria-pressed", "true");
        applyFilter();
      });
      host.appendChild(btn);
    }
  );
}

function applyFilter() {
  $$("#log .step").forEach((row) => {
    row.hidden = state.filter !== "all" && row.dataset.kind !== state.filter;
  });
}

/* ------------------------------------------------------------------- trace */

function clearLog() {
  $("#log").innerHTML = "";
  state.stepCount = 0;
}

function appendStep(step) {
  const log = $("#log");
  state.stepCount += 1;
  const kind = step.kind || "note";
  const row = el("div", `step step--${kind}${step.source === "ui" ? " step--ui" : ""}`);
  row.dataset.kind = kind;

  row.appendChild(el("div", "step-index num", step.index || state.stepCount));
  row.appendChild(el("div", "step-kind", KIND_TAG[kind] || kind.toUpperCase()));

  const main = el("div", "step-main");
  const title = el("div", "step-title", step.title || "");
  main.appendChild(title);
  if (step.stage) main.appendChild(el("div", "step-stage", step.stage));
  if (step.why) main.appendChild(el("div", "step-why", step.why));
  if (step.conclusion) main.appendChild(el("div", "step-conclusion", step.conclusion));
  if (step.citation) main.appendChild(el("div", "step-cite", `[${step.citation}]`));

  if (step.tool_input && Object.keys(step.tool_input).length) {
    main.appendChild(payload("input", step.tool_input));
  }
  if (step.result && Object.keys(step.result).length) {
    main.appendChild(payload("result", step.result));
  }
  row.appendChild(main);

  const meta = el("div", "step-meta");
  const bits = [];
  if (typeof step.elapsed_s === "number") bits.push(`${step.elapsed_s.toFixed(2)}s`);
  meta.appendChild(document.createTextNode(bits.join(" ")));
  if (step.mireye_credits > 0) {
    meta.appendChild(document.createElement("br"));
    meta.appendChild(el("span", "billed", `+${fmt(step.mireye_credits)} cr`));
  } else if (step.cache_hits > 0) {
    meta.appendChild(document.createElement("br"));
    meta.appendChild(el("span", "cached", `cached · 0 cr`));
  }
  row.appendChild(meta);

  row.hidden = state.filter !== "all" && kind !== state.filter;
  log.appendChild(row);

  if (state.follow) log.scrollTop = log.scrollHeight;
  updateMeters(step);
}

function payload(label, data) {
  const wrap = el("details", "payload");
  const sum = el("summary", null, label);
  wrap.appendChild(sum);
  const pre = el("pre", null, JSON.stringify(data, null, 2));
  wrap.appendChild(pre);
  return wrap;
}

function updateMeters(step) {
  if (typeof step.run_credits === "number") {
    const run = $("#m-run");
    run.textContent = fmt(step.run_credits);
    run.classList.toggle("hot", step.run_credits > 0);
  }
  if (typeof step.account_credits === "number") {
    $("#m-session").textContent = fmt(step.account_credits);
  }
}

/* Follow-the-tail, but never yank the user back down. */
function wireFollow() {
  const log = $("#log");
  const live = $("#btn-live");
  log.addEventListener("scroll", () => {
    const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 24;
    if (!atBottom && state.follow) {
      state.follow = false;
      $("#f-follow").checked = false;
    }
    live.hidden = atBottom || !state.running;
  });
  $("#f-follow").addEventListener("change", (e) => {
    state.follow = e.target.checked;
    if (state.follow) log.scrollTop = log.scrollHeight;
  });
  live.addEventListener("click", () => {
    state.follow = true;
    $("#f-follow").checked = true;
    log.scrollTop = log.scrollHeight;
    live.hidden = true;
  });
}

/* --------------------------------------------------------------------- SSE */

async function stream(url, body, handlers) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch (e) {
      /* body was not JSON */
    }
    handlers.error({ message: detail });
    handlers.done({ ok: false });
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let split;
    while ((split = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      if (frame.startsWith(":")) continue;
      let event = "message";
      const data = [];
      frame.split("\n").forEach((line) => {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trim());
      });
      if (!data.length) continue;
      const parsed = JSON.parse(data.join("\n"));
      if (handlers[event]) handlers[event](parsed);
    }
  }
}

function setRunning(on, label) {
  state.running = on;
  $("#btn-run").disabled = on;
  $("#btn-replay").disabled = on || !state.ctx.demo_available;
  const alt = $("#btn-alt");
  if (alt) alt.disabled = on;
  $("#log-status").textContent = label || (on ? "running" : "idle");
  $("#log-status").className = on ? "running" : "";
  if (on) {
    state.follow = true;
    $("#f-follow").checked = true;
    $("#btn-live").hidden = true;
  }
}

const handlers = {
  start(data) {
    $("#m-run").textContent = "0";
    if (data.mode === "replay") {
      $("#log-status").textContent = data.note || "replay";
    }
    appendStep({
      index: 0,
      kind: "note",
      stage: "client",
      title: data.replay ? "Replaying a recorded run" : `Run started · ${data.mode}`,
      why:
        data.note ||
        `${data.project}. Provider ${data.provider}.` +
          (data.ceiling ? ` Credit ceiling ${fmt(data.ceiling)} for this run.` : ""),
      source: "ui",
    });
  },
  step: appendStep,
  report(data) {
    state.report = data;
    renderReport(data);
  },
  alternate(data) {
    if (state.report) state.report.alternate_sites = data;
    if (state.report) state.report.alternate_gated = false;
    renderAlternate(data);
  },
  error(data) {
    appendStep({
      index: 0,
      kind: "error",
      stage: "client",
      title: "Run stopped",
      why: data.message,
      source: "ui",
    });
  },
  done(data) {
    setRunning(false, data.ok === false ? "stopped" : "complete");
    if (typeof data.run_credits === "number") {
      $("#m-run").textContent = fmt(data.run_credits);
      $("#m-run").classList.toggle("hot", data.run_credits > 0);
    }
    if (typeof data.account_credits === "number") {
      $("#m-session").textContent = fmt(data.account_credits);
    }
    refreshCounters();
    disarm();
  },
};

async function refreshCounters() {
  try {
    const ctx = await (await fetch("/api/context")).json();
    $("#m-cache").textContent = fmt(ctx.account.cache_hits);
    $("#m-session").textContent = fmt(ctx.account.credits_spent);
  } catch (e) {
    /* the counters are cosmetic; a failed refresh is not worth an alert */
  }
}

/* ------------------------------------------------------------------ verdict */

function severity(pathwayKey) {
  return PATHWAY_SEVERITY[pathwayKey] || "warn";
}

function renderReport(report) {
  $("#sec-verdict").hidden = false;
  $("#sec-triggers").hidden = false;
  $("#sec-act").hidden = false;
  $("#sec-appendix").hidden = false;

  renderRefusal(report);
  renderVerdict(report);
  renderTriggers(report);
  renderEmissions(report);
  renderAlternate(report.alternate_sites, report.alternate_gated);
  renderConfigs(report.config_alternatives);
  renderAppendix(report);

  const run = report.run || {};
  $("#foot-run").textContent =
    `${report.project.config} · ${report.site.county || "unresolved"} ${report.site.state || ""} · ` +
    `${run.mode || ""} · ${run.tool_calls || 0} tool calls · generated ${report.generated_at}` +
    (report.replay ? " · replayed from outputs/demo" : "");
}

function renderRefusal(report) {
  const host = $("#refusal");
  host.innerHTML = "";
  if (report.site && report.site.resolved) {
    host.hidden = true;
    return;
  }
  host.hidden = false;
  const box = el("div", "refusal");
  box.appendChild(el("div", "refusal-head", "Refused — by design"));
  box.appendChild(el("div", "refusal-title", "The geocode would not resolve this to a parcel."));
  box.appendChild(
    prose(
      (report.site.resolution_note || "No detail returned.") +
        "\n\nThe provider raises **ResolutionError** below its confidence floor instead of " +
        "returning the nearest plausible point. A county centroid standing in for a parcel " +
        "produces a permit answer for the wrong county, and somebody options land on it. " +
        (report.site.county
          ? `Screening continued against the declared jurisdiction — **${report.site.county} County, ${report.site.state}** — ` +
            "and everything below is unverified at parcel level. Terrain, pipeline distance and " +
            "receptors are unknown, not absent."
          : "No county was declared, so there is no pathway to state.")
    )
  );
  host.appendChild(box);
}

function renderVerdict(report) {
  const host = $("#verdict");
  host.innerHTML = "";
  const p = report.pathway;
  const prob = report.probability || {};

  $("#verdict-note").textContent = report.project.config;

  if (!p) {
    host.appendChild(
      prose(
        "No pathway determined. The run refused rather than inventing a jurisdiction.",
        "prose"
      )
    );
    return;
  }

  const sev = severity(p.pathway);
  const grid = el("div", `verdict sev-${sev}`);

  const c1 = el("div", "vcell");
  c1.appendChild(el("div", "vlabel", "Pathway"));
  c1.appendChild(el("div", "vpathway", p.label));
  if (p.controlling_pollutant) {
    c1.appendChild(
      el(
        "div",
        "vfine",
        `${p.controlling_pollutant} ${fmt(p.controlling_tpy)} tpy against a ${fmt(
          p.applicable_threshold_tpy
        )} tpy threshold`
      )
    );
  }
  c1.appendChild(el("div", "vsub", p.source_category.reasoning));
  c1.appendChild(el("div", "vfine", p.source_category.citation));
  grid.appendChild(c1);

  const c2 = el("div", "vcell");
  c2.appendChild(el("div", "vlabel", "Permit clock"));
  const m = el("div", "vmonths num");
  m.appendChild(document.createTextNode(`${months(p.months_low)}–${months(p.months_high)}`));
  m.appendChild(el("span", "unit", "MONTHS"));
  c2.appendChild(m);
  c2.appendChild(el("div", "vfine", `likely ${months(p.months_likely)} months of agency review`));
  c2.appendChild(rangeMeter(p.months_low, p.months_likely, p.months_high));
  if (p.offsets_required_tons) {
    c2.appendChild(
      el("div", "vfine", `${fmt(p.offsets_required_tons)} tons of offsets required`)
    );
  }
  grid.appendChild(c2);

  const c3 = el("div", "vcell");
  c3.appendChild(el("div", "vlabel", "On the announced date"));
  const value = prob.probability_on_announced_schedule;
  const num = el("div", `vnum sev-${value === null || value === undefined ? "warn" : value >= 0.6 ? "good" : value >= 0.3 ? "warn" : "crit"}`);
  num.textContent = value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
  c3.appendChild(num);
  (prob.basis || []).forEach((line) => c3.appendChild(el("div", "vfine", line)));
  (prob.caps_applied || []).forEach((line) => c3.appendChild(el("div", "vfine", line)));
  grid.appendChild(c3);

  host.appendChild(grid);

  (p.hard_stops || []).forEach((stop) => {
    const box = el("div", "hardstop");
    box.appendChild(el("div", "block-label", "Hard stop"));
    box.appendChild(el("p", null, stop));
    host.appendChild(box);
  });
}

/* Low ── likely ── high. One row, one axis, no decoration. */
function rangeMeter(low, likely, high) {
  const wrap = el("div", "range");
  const track = el("div", "range-track");
  const max = Math.max(high * 1.05, 12);
  const pct = (v) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;

  const span = el("div", "range-span");
  span.style.left = pct(low);
  span.style.width = `calc(${pct(high)} - ${pct(low)})`;
  track.appendChild(span);

  [["range-mark", low], ["range-mark range-likely", likely], ["range-mark", high]].forEach(
    ([cls, v]) => {
      const mark = el("div", cls);
      mark.style.left = pct(v);
      track.appendChild(mark);
    }
  );
  wrap.appendChild(track);

  const scale = el("div", "range-scale");
  scale.appendChild(el("span", null, `${months(low)} optimistic`));
  scale.appendChild(el("span", null, `${months(likely)} likely`));
  scale.appendChild(el("span", null, `${months(high)} pessimistic`));
  wrap.appendChild(scale);
  return wrap;
}

function renderTriggers(report) {
  const host = $("#triggers");
  host.innerHTML = "";
  const fired = (report.pathway && report.pathway.triggers_fired) || [];
  if (!fired.length) {
    host.appendChild(el("p", "prose", "No triggers fired."));
    return;
  }
  fired
    .slice()
    .sort((a, b) => (b.months_added || 0) - (a.months_added || 0))
    .forEach((t) => {
      const row = el("div", "trigger");
      const left = el("div");
      left.appendChild(el("div", "trigger-name", t.name.replace(/_/g, " ")));
      left.appendChild(el("div", "trigger-cite", t.citation));
      row.appendChild(left);
      row.appendChild(el("div", "trigger-detail", t.detail));
      const added = t.months_added || 0;
      const mo = el("div", `trigger-months num${added === 0 ? " zero" : added >= 6 ? " big" : ""}`);
      mo.appendChild(document.createTextNode(added ? `+${fmt(added)}` : "—"));
      mo.appendChild(el("span", "unit", added ? "MONTHS" : "NO MONTHS"));
      row.appendChild(mo);
      host.appendChild(row);
    });

  const clear = (report.pathway && report.pathway.triggers_clear) || [];
  if (clear.length) {
    const block = el("div", "block");
    block.appendChild(el("div", "block-label", "Tested and clear"));
    const chips = el("div", "chips");
    clear.forEach((name) => chips.appendChild(el("span", "chip chip-clear", name.replace(/_/g, " "))));
    block.appendChild(chips);
    host.appendChild(block);
  }
}

function renderEmissions(report) {
  const host = $("#emissions");
  host.innerHTML = "";
  const e = report.emissions;
  const full = report.emissions_full;
  if (!e) return;

  const wrap = el("div", "pte");

  const left = el("div");
  left.appendChild(el("div", "block-label", "Potential to emit"));
  const table = el("table");
  const tons = (full && full.tons_per_year) || e.tons_per_year || {};
  const lbs = (full && full.lb_per_hour) || {};
  const overSer = e.above_significant_emission_rate || {};
  /* The recorded fixture carries tons but not lb/hr, so the third column
     falls back to what it does have: whether the pollutant clears its PSD
     significant emission rate. */
  const hasLbs = Object.keys(lbs).length > 0;

  const thead = el("thead");
  const hr = el("tr");
  ["Pollutant", "tpy", hasLbs ? "lb/hr" : "over SER"].forEach((h, i) => {
    hr.appendChild(el("th", i ? "num-col" : null, h));
  });
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = el("tbody");
  Object.entries(tons)
    .sort((a, b) => b[1] - a[1])
    .forEach(([pollutant, tpy]) => {
      const tr = el("tr");
      if (pollutant in overSer) tr.className = "over";
      tr.appendChild(el("td", "strong", pollutant));
      tr.appendChild(el("td", "num-col", fmt(tpy, 1)));
      tr.appendChild(
        el(
          "td",
          "num-col",
          hasLbs
            ? lbs[pollutant] === undefined
              ? "—"
              : fmt(lbs[pollutant], 2)
            : pollutant in overSer
            ? "yes"
            : "—"
        )
      );
      tbody.appendChild(tr);
    });
  table.appendChild(tbody);
  left.appendChild(table);
  wrap.appendChild(left);

  const right = el("div");
  right.appendChild(el("div", "block-label", "Basis"));
  const basis = (full && full.basis) || e.basis || {};
  const dl = el("dl", "kv");
  [
    ["heat input", basis.heat_input],
    ["heat rate", basis.heat_rate],
    ["hours", basis.hours_basis],
    ["emission factors", basis.emission_factors],
    ["controls", basis.controls],
    ["method", basis.method],
  ].forEach(([k, v]) => {
    if (!v) return;
    dl.appendChild(el("dt", null, k));
    dl.appendChild(el("dd", null, v));
  });
  right.appendChild(dl);
  wrap.appendChild(right);

  host.appendChild(wrap);
}

/* ---------------------------------------------------------------------- act */

function renderAlternate(alt, gated) {
  const host = $("#alternate");
  host.innerHTML = "";

  const panel = el("div", "alt-panel");
  panel.appendChild(el("div", "block-label", "Alternate site"));

  if (alt && alt.best) {
    const top = el("div", "alt-top");
    const left = el("div");
    const delta = el("div", "headline-delta");
    const text = alt.delta_statement || "";
    const match = text.match(/(saves?|save)\s+([\d.]+)\s+months?/i);
    if (match) {
      const idx = text.toLowerCase().indexOf(match[0].toLowerCase());
      left.appendChild(delta);
      delta.appendChild(document.createTextNode(text.slice(0, idx)));
      delta.appendChild(el("em", null, text.slice(idx, idx + match[0].length)));
      delta.appendChild(document.createTextNode(text.slice(idx + match[0].length)));
    } else {
      delta.textContent = text;
      left.appendChild(delta);
    }
    const b = alt.best;
    const chips = el("div", "chips");
    (b.triggers_cleared || []).forEach((t) =>
      chips.appendChild(el("span", "chip chip-clear", `clears ${t.replace(/_/g, " ")}`))
    );
    (b.triggers_added || []).forEach((t) =>
      chips.appendChild(el("span", "chip chip-add", `adds ${t.replace(/_/g, " ")}`))
    );
    left.appendChild(chips);
    /* The honest notes ride with the recommendation, in the same column, not
       tucked underneath it. */
    (alt.notes || []).forEach((n) => left.appendChild(el("div", "note", n)));
    top.appendChild(left);

    const dl = el("dl", "kv");
    [
      ["parcel", `${b.county} County, ${b.state}`],
      ["coordinate", `${b.latitude.toFixed(4)}, ${b.longitude.toFixed(4)}`],
      ["distance", `${fmt(b.distance_miles, 0)} mi ${b.bearing} · ${fmt(b.distance_km, 0)} km`],
      ["pathway", b.pathway_label],
      ["clock", `${months(b.months_low)}–${months(b.months_high)} months, likely ${months(b.months_likely)}`],
      ["gas pipeline", b.gas_pipeline_km === null ? "unknown" : `${fmt(b.gas_pipeline_km, 1)} km`],
      ["screened", `${alt.candidates_resolved} of ${alt.candidates_considered} parcels to ${fmt(Math.max(...(alt.rings_km || [0])))} km`],
      ["line crossed", alt.crossed_state_line ? "state" : alt.crossed_county_line ? "county" : "none"],
      ["credits", fmt(alt.credits_spent)],
    ].forEach(([k, v]) => {
      dl.appendChild(el("dt", null, k));
      dl.appendChild(el("dd", null, v));
    });
    top.appendChild(dl);
    panel.appendChild(top);
  } else if (gated || (alt && !alt.candidates_considered)) {
    panel.appendChild(
      el(
        "div",
        "note",
        (alt && alt.notes && alt.notes[0]) ||
          "Not run. The alternate-site search resolves a fresh parcel on every ring, so it sits behind its own button."
      )
    );
  } else if (alt) {
    panel.appendChild(el("div", "note", (alt.notes || []).join(" ") || "No better parcel found."));
  }

  panel.appendChild(altRunner());
  host.appendChild(panel);
}

function altRunner() {
  const row = el("div", "alt-run");
  const radius = el("select");
  [15, 30, 60].forEach((r) => {
    const o = el("option", null, `start at ${r} km`);
    o.value = r;
    radius.appendChild(o);
  });
  radius.value = "30";
  radius.id = "alt-radius";

  const count = el("select");
  [8, 16, 24].forEach((n) => {
    const o = el("option", null, `${n} candidates`);
    o.value = n;
    count.appendChild(o);
  });
  count.value = "16";
  count.id = "alt-n";

  const btn = el("button", "btn", "Search for a better parcel");
  btn.type = "button";
  btn.id = "btn-alt";

  const estimate = el("span", "alt-estimate");
  estimate.id = "alt-estimate";

  const refresh = async () => {
    const res = await fetch(`/api/alternate-estimate?radius_km=${radius.value}&n=${count.value}`);
    const data = await res.json();
    state.altEstimate = data;
    estimate.innerHTML = "";
    estimate.appendChild(
      document.createTextNode(
        `${data.candidates} parcels · ${data.provider_calls} provider calls · up to `
      )
    );
    estimate.appendChild(el("strong", null, `${fmt(data.credits_if_uncached)} credits`));
    estimate.appendChild(
      document.createTextNode(` if none are cached. Rings ${data.rings_km.join(", ")} km.`)
    );
    if (btn.dataset.armed) disarmAlt(btn);
  };

  radius.addEventListener("change", refresh);
  count.addEventListener("change", refresh);
  btn.addEventListener("click", () => {
    if (!btn.dataset.armed) {
      btn.dataset.armed = "1";
      btn.textContent = `Confirm — bill up to ${fmt(state.altEstimate ? state.altEstimate.credits_if_uncached : 0)} credits`;
      btn.classList.add("btn-primary");
      return;
    }
    disarmAlt(btn);
    runAlternate(Number(radius.value), Number(count.value));
  });

  row.appendChild(radius);
  row.appendChild(count);
  row.appendChild(btn);
  row.appendChild(estimate);
  refresh();
  return row;
}

function disarmAlt(btn) {
  delete btn.dataset.armed;
  btn.textContent = "Search for a better parcel";
  btn.classList.remove("btn-primary");
}

async function runAlternate(radius_km, n) {
  setRunning(true, "searching parcels");
  await stream(
    "/api/alternate-search",
    { radius_km, n, ceiling: Number($("#f-ceiling").value) * 2 || 600 },
    handlers
  );
}

function renderConfigs(configs) {
  const host = $("#configs");
  host.innerHTML = "";
  if (!configs || !configs.options || !configs.options.length) return;

  const block = el("div", "block");
  block.appendChild(el("div", "block-label", "Config alternatives at this parcel"));

  const best = configs.options.reduce(
    (acc, o) => Math.max(acc, o.months_saved || 0),
    0
  );

  const top = configs.options[0];
  if (top && top.months_saved > 0) {
    const headline = el("div", "headline-delta");
    headline.appendChild(document.createTextNode(`${top.label} — `));
    headline.appendChild(el("em", null, `save ${fmt(top.months_saved, 0)} months`));
    block.appendChild(headline);
  }

  const table = el("div", "cfg");
  configs.options.forEach((o) => {
    const row = el("div", "cfg-row");

    const left = el("div");
    left.appendChild(el("div", "cfg-label", o.label));
    left.appendChild(
      el(
        "div",
        "cfg-path",
        `${o.pathway_label} · ${months(o.months_likely)} mo${
          o.controlling_pollutant ? ` · ${o.controlling_pollutant} ${fmt(o.controlling_tpy, 1)} tpy` : ""
        }`
      )
    );
    row.appendChild(left);

    const saved = el("div", "saved");
    const value = el(
      "div",
      `saved-value num ${o.months_saved > 0 ? "good" : "none"}`,
      o.months_saved > 0 ? `−${fmt(o.months_saved, 0)} mo` : "no change"
    );
    saved.appendChild(value);
    const bar = el("div", `bar${o.months_saved > 0 ? "" : " none"}`);
    const fill = el("span");
    fill.style.width = `${best ? Math.max(2, (o.months_saved / best) * 100) : 2}%`;
    bar.appendChild(fill);
    saved.appendChild(bar);
    saved.appendChild(el("div", "avail", `availability ${Math.round((o.availability || 0) * 100)}%`));
    row.appendChild(saved);

    const note = el("div", "cfg-note", o.cost_note);
    row.appendChild(note);

    const cleared = el("div");
    const chips = el("div", "chips");
    (o.triggers_cleared || []).forEach((t) =>
      chips.appendChild(el("span", "chip chip-clear", t.replace(/_/g, " ")))
    );
    (o.hard_stops || []).forEach((t) => chips.appendChild(el("span", "chip chip-add", t)));
    cleared.appendChild(chips);
    (o.warnings || []).forEach((w) => cleared.appendChild(el("div", "cfg-warn", w)));
    row.appendChild(cleared);

    table.appendChild(row);
  });
  block.appendChild(table);

  (configs.notes || []).forEach((n) => {
    const note = el("div", "note");
    note.style.marginTop = "12px";
    note.textContent = n;
    block.appendChild(note);
  });

  host.appendChild(block);
}

/* ----------------------------------------------------------------- appendix */

function renderAppendix(report) {
  const narrative = $("#narrative");
  narrative.innerHTML = "";
  if (report.narrative) {
    const block = el("div", "block");
    block.appendChild(el("div", "block-label", "The agent's read"));
    block.appendChild(prose(report.narrative, "narrative"));
    narrative.appendChild(block);
  }

  const caveats = $("#caveats");
  caveats.innerHTML = "";
  if ((report.caveats || []).length) {
    const block = el("div", "block");
    block.appendChild(el("div", "block-label", "What this run does not know"));
    const list = el("div", "caveat-list");
    report.caveats.forEach((c) => list.appendChild(el("div", "caveat", c)));
    block.appendChild(list);
    caveats.appendChild(block);
  }

  renderProvenance(report);
}

function renderProvenance(report) {
  const rows = report.provenance_rows || provenanceFromMap(report.provenance);
  const tbody = $("#provenance tbody");
  const table = $("#provenance");
  $("#prov-count").textContent = `${rows.length} facts · source, fetch time and confidence for every one`;

  let sortKey = "field";
  let ascending = true;

  const draw = () => {
    tbody.innerHTML = "";
    const sorted = rows.slice().sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      const cmp = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return ascending ? cmp : -cmp;
    });
    sorted.forEach((r) => {
      const tr = el("tr");
      tr.appendChild(el("td", "strong", r.field));
      tr.appendChild(el("td", null, r.value));
      tr.appendChild(el("td", null, r.source || "—"));
      tr.appendChild(el("td", null, (r.fetched || "—").replace("T", " ").replace("+00:00", "Z")));
      tr.appendChild(
        el("td", "num-col", r.confidence === null || r.confidence === undefined ? "—" : Number(r.confidence).toFixed(2))
      );
      tbody.appendChild(tr);
    });
    $$("#provenance th.sortable").forEach((th) => {
      if (th.dataset.sort === sortKey) th.setAttribute("aria-sort", ascending ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    });
  };

  $$("#provenance th.sortable").forEach((th) => {
    th.onclick = () => {
      if (sortKey === th.dataset.sort) ascending = !ascending;
      else {
        sortKey = th.dataset.sort;
        ascending = true;
      }
      draw();
    };
  });
  draw();
  table.hidden = false;
}

/* The replayed fixture carries provenance as a map without values. */
function provenanceFromMap(map) {
  return Object.entries(map || {}).map(([field, meta]) => ({
    field,
    value: "—",
    source: meta.source,
    fetched: meta.fetched,
    confidence: meta.confidence,
  }));
}

/* -------------------------------------------------------------------- run */

function updateRunCost() {
  const ceiling = Number($("#f-ceiling").value || 0);
  const node = $("#run-cost");
  const nullProvider = state.ctx && state.ctx.provider === "null";
  if (nullProvider) {
    node.textContent = "NullProvider — no physical lookups, no credits.";
    node.classList.remove("warn");
    return;
  }
  node.textContent =
    `A parcel the cache has not seen bills roughly 86 credits for the full physical read. ` +
    `A parcel it has seen bills 0. Ceiling for this run: ${fmt(ceiling)}.`;
  node.classList.toggle("warn", ceiling > (state.ctx ? state.ctx.expensive_credits : 200));
}

function disarm() {
  state.armed = null;
  const btn = $("#btn-run");
  btn.textContent = "Run the screen";
  updateRunCost();
}

function formPayload() {
  return {
    address: $("#f-address").value.trim(),
    county: $("#f-county").value.trim() || null,
    state: $("#f-state").value.trim().toUpperCase() || null,
    mw: Number($("#f-mw").value),
    prime_mover: $("#f-prime").value,
    fuel: $("#f-fuel").value,
    controls: $$("#f-controls option").filter((o) => o.selected).map((o) => o.value),
    target: $("#f-target").value || null,
    no_llm: $("#f-loop").value === "none",
    ceiling: Number($("#f-ceiling").value) || null,
  };
}

function wireRun() {
  $("#run-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = formPayload();
    const expensive =
      state.ctx.provider !== "null" && Number($("#f-ceiling").value) > state.ctx.expensive_credits;
    if (expensive && !state.armed) {
      state.armed = true;
      $("#btn-run").textContent = `Confirm — allow up to ${fmt(Number($("#f-ceiling").value))} credits`;
      $("#run-cost").classList.add("warn");
      return;
    }
    disarm();
    clearLog();
    setRunning(true, "running");
    await stream("/api/run", body, handlers);
  });

  $("#btn-replay").addEventListener("click", async () => {
    clearLog();
    setRunning(true, "replaying");
    await stream("/api/replay", {}, handlers);
  });

  $("#f-ceiling").addEventListener("input", disarm);
  $$("#run-form input, #run-form select").forEach((node) =>
    node.addEventListener("change", () => {
      if (state.armed) disarm();
    })
  );
}

wireFollow();
wireRun();
boot();

#!/usr/bin/env python3
"""
Generate an Interactive HTML Dashboard for Item-Level Stigma Profiles.

Reads Table5_item_stigma_profile.csv and outputs a self-contained
index.html (Chart.js embedded inline) to visualize item-level stigma
score trends across vignettes (PLE, DEP, APS, SCZ) in EN and ZH.

Usage:
  python scripts/generate_dashboard.py analysis_13models_20260419/
  python scripts/generate_dashboard.py analysis_13models_20260419/ --output custom_dir/
"""

import csv
import json
import math
import argparse
import sys
import urllib.request
from pathlib import Path

CHARTJS_URL = (
    "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"
)
CHARTJS_CDN_FALLBACK = (
    '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4'
    '/dist/chart.umd.min.js"></script>'
)

# Protocol order: GPT family -> Claude -> Gemini -> Other
MODEL_ORDER = [
    "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4 Mini",
    "Claude Sonnet 4.5", "Claude Opus 4.6",
    "Gemini 2.5 Flash", "Gemini 3.1 Pro Preview", "Gemini 3.1 Flash-Lite Preview",
    "Gemma 4 31B IT", "Llama 3.3 70B", "DeepSeek V3.2",
]

# Per-model colours matching analyze_results.R / family_colors
MODEL_COLORS = {
    "GPT-3.5":               "#1B5E20",
    "GPT-4o":                "#2E7D32",
    "GPT-OSS-120B":          "#A5D6A7",
    "GPT-5.4":               "#388E3C",
    "GPT-5.4 Mini":          "#66BB6A",
    "Claude Sonnet 4.5":     "#FF9800",
    "Claude Opus 4.6":       "#E65100",
    "Gemini 2.5 Flash":      "#0D47A1",
    "Gemini 3.1 Pro Preview":        "#1565C0",
    "Gemini 3.1 Flash-Lite Preview": "#42A5F5",
    "Gemma 4 31B IT":        "#90CAF9",
    "Llama 3.3 70B":         "#6A1B9A",
    "DeepSeek V3.2":         "#C62828",
}

# ---------------------------------------------------------------------------
# HTML template
# Placeholders (no curly-brace conflicts with CSS/JS):
#   %%CHARTJS%%        <- <script> tag with embedded or CDN Chart.js
#   %%MODEL_ORDER%%    <- JSON array of model names in protocol order
#   %%MODEL_COLORS%%   <- JSON object {model: hexcolor}
#   %%ITEM_TEXT_MAP%%  <- JSON object {Item_ID: Item_Text}
#   %%DATA%%           <- JSON array of row objects from CSV
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Stigma – Item-Level Dashboard</title>
%%CHARTJS%%
<style>
  *, *::before, *::after { box-sizing: border-box; }
  body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    margin: 0; padding: 0;
    display: flex; height: 100vh;
    color: #333; background: #fff;
  }
  #sidebar {
    width: 290px; flex-shrink: 0;
    background: #f8f9fa; padding: 18px;
    border-right: 1px solid #dee2e6;
    overflow-y: auto;
  }
  #main { flex: 1; padding: 28px; overflow-y: auto; background: #fff; }
  h2 { font-size: 1.1rem; margin: 0 0 14px; padding-bottom: 8px;
       border-bottom: 2px solid #dee2e6; }
  h3 { font-size: 0.9rem; color: #495057; margin: 16px 0 6px; text-transform: uppercase;
       letter-spacing: 0.05em; }
  .btn-row { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
  .btn {
    padding: 3px 10px; font-size: 0.78rem; cursor: pointer;
    background: #e9ecef; border: 1px solid #ced4da; border-radius: 3px;
    line-height: 1.4;
  }
  .btn:hover { background: #d3d8de; }
  .checkbox-list {
    max-height: 230px; overflow-y: auto;
    border: 1px solid #ced4da; padding: 8px 10px;
    background: #fff; border-radius: 4px; font-size: 0.82rem;
  }
  .checkbox-list label { display: flex; align-items: baseline; gap: 6px;
                         margin-bottom: 5px; cursor: pointer; line-height: 1.3; }
  .item-group-header {
    font-size: 0.72rem; font-weight: bold; color: #6c757d;
    text-transform: uppercase; letter-spacing: 0.06em;
    padding: 4px 0 2px; margin-top: 6px; border-top: 1px solid #e9ecef;
  }
  .item-id-badge {
    font-family: monospace; font-size: 0.8rem; font-weight: bold;
    color: #495057; white-space: nowrap;
  }
  .item-id-badge.total { color: #0d6efd; }
  .item-text-snippet { color: #6c757d; font-size: 0.78rem; }
  .item-section {
    margin-bottom: 48px; padding-bottom: 28px;
    border-bottom: 1px solid #eee;
  }
  .item-title {
    font-size: 1.25rem; font-weight: bold; margin-bottom: 4px; color: #212529;
  }
  .item-subtitle { font-size: 0.88rem; color: #6c757d; margin-bottom: 4px; }
  .item-subtitle-zh { font-size: 0.82rem; color: #adb5bd; margin-bottom: 14px; }
  .item-text-zh { color: #adb5bd; font-size: 0.75rem; }
  .charts-row { display: flex; gap: 18px; }
  .chart-container {
    flex: 1; height: 380px;
    background: #fdfdfd; border: 1px solid #eaecef;
    border-radius: 6px; padding: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .placeholder {
    color: #adb5bd; text-align: center;
    margin-top: 18%; font-size: 1rem;
  }
  /* Score tables below charts */
  .score-tables-row {
    display: flex; gap: 18px; margin-top: 10px;
  }
  .score-table-wrapper {
    flex: 1; overflow-x: auto;
    border: 1px solid #eaecef; border-radius: 6px;
    background: #fdfdfd;
  }
  .score-table {
    width: 100%; border-collapse: collapse;
    font-size: 0.76rem;
  }
  .score-table th {
    background: #f1f3f5; font-weight: 600;
    padding: 4px 8px; text-align: center;
    border-bottom: 2px solid #dee2e6;
    position: sticky; top: 0;
  }
  .score-table th:first-child { text-align: left; }
  .score-table td {
    padding: 3px 8px; text-align: center;
    border-bottom: 1px solid #f0f0f0;
  }
  .score-table td:first-child { text-align: left; white-space: nowrap; }
  .score-table tbody tr:last-child td { border-bottom: none; }
  .score-table-lang-label {
    font-size: 0.72rem; font-weight: bold; color: #6c757d;
    padding: 4px 8px 2px; text-transform: uppercase; letter-spacing: 0.05em;
    border-bottom: 1px solid #eee;
  }
</style>
</head>
<body>

<div id="sidebar">
  <h2>Dashboard Controls</h2>

  <h3>Models</h3>
  <div class="btn-row">
    <button class="btn" onclick="selectAll('model-cb', true)">All</button>
    <button class="btn" onclick="selectAll('model-cb', false)">None</button>
  </div>
  <div id="model-list" class="checkbox-list"></div>

  <h3>Items</h3>
  <div class="btn-row">
    <button class="btn" onclick="selectAll('item-cb', true)">All</button>
    <button class="btn" onclick="selectAll('item-cb', false)">None</button>
    <button class="btn" onclick="selectAll('item-cb', false); selectGroup('TOTAL')">Totals</button>
    <button class="btn" onclick="selectAll('item-cb', false); selectGroup('SD')">SD</button>
    <button class="btn" onclick="selectAll('item-cb', false); selectGroup('PJ')">PJ</button>
  </div>
  <div id="item-list" class="checkbox-list"></div>
</div>

<div id="main">
  <div id="charts-wrapper">
    <p class="placeholder">Select items and models to view data.</p>
  </div>
</div>

<script>
// ---- Injected data --------------------------------------------------------
const RAW_DATA     = %%DATA%%;
const ITEM_TEXT    = %%ITEM_TEXT_MAP%%;
const MODEL_ORDER  = %%MODEL_ORDER%%;
const MODEL_COLORS = %%MODEL_COLORS%%;
const CI_DATA      = %%CI_DATA%%;  // ci[model][item_id][lang][vignette]={lo,hi}

// ---- Constants ------------------------------------------------------------
const VIGNETTES = ["PLE", "DEP", "APS", "SCZ"];
const FALLBACK_COLOR = "#6c757d";

// ---- Fast lookup: model -> item_id -> row ---------------------------------
const DATA_MAP = new Map();
RAW_DATA.forEach(d => {
  if (!DATA_MAP.has(d.Model)) DATA_MAP.set(d.Model, new Map());
  DATA_MAP.get(d.Model).set(d.Item_ID, d);
});

// ---- State ----------------------------------------------------------------
let activeCharts = [];

// Base items from CSV, sorted SD01..SD19 then PJ01..PJ21
const uniqueBaseItems = (() => {
  const all = [...new Set(RAW_DATA.map(d => d.Item_ID))];
  return all.sort((a, b) => {
    const pa = a.replace(/\d+/g, ""), pb = b.replace(/\d+/g, "");
    const scaleOrder = {"SD": 0, "PJ": 1};
    if (pa !== pb) return (scaleOrder[pa] ?? 99) - (scaleOrder[pb] ?? 99);
    return parseInt(a.replace(/\D+/g, "")) - parseInt(b.replace(/\D+/g, ""));
  });
})();

const SD_ITEMS = uniqueBaseItems.filter(id => id.startsWith("SD"));
const PJ_ITEMS = uniqueBaseItems.filter(id => id.startsWith("PJ"));

// ---- Synthetic total rows: sum of SD01-SD19 / PJ01-PJ21 per model --------
const SYNTHETIC_ROWS = (() => {
  const result = [];
  const models = MODEL_ORDER.filter(m => RAW_DATA.some(d => d.Model === m));
  for (const model of models) {
    for (const [synId, items] of [["SD_TOTAL", SD_ITEMS], ["PJ_TOTAL", PJ_ITEMS]]) {
      const row = { Model: model, Item_ID: synId };
      for (const lang of ["EN", "ZH"]) {
        for (const vig of VIGNETTES) {
          const key = `Mean_${lang}_${vig}`;
          let sum = 0, cnt = 0;
          items.forEach(itemId => {
            const r = DATA_MAP.get(model)?.get(itemId);
            if (r) { const v = parseFloat(r[key]); if (!isNaN(v)) { sum += v; cnt++; } }
          });
          row[key] = cnt > 0 ? String(sum) : "";
        }
      }
      result.push(row);
    }
  }
  return result;
})();

// Fast lookup for synthetic rows
const SYNTHETIC_MAP = new Map();
SYNTHETIC_ROWS.forEach(d => {
  if (!SYNTHETIC_MAP.has(d.Model)) SYNTHETIC_MAP.set(d.Model, new Map());
  SYNTHETIC_MAP.get(d.Model).set(d.Item_ID, d);
});

// All items: totals first, then base items
const uniqueItems = ["SD_TOTAL", "PJ_TOTAL", ...uniqueBaseItems];

// Models present in CSV, in protocol order
const uniqueModels = MODEL_ORDER.filter(m => RAW_DATA.some(d => d.Model === m));

// Y-axis config per item type
function getYAxis(itemId) {
  if (itemId === "SD_TOTAL") return { min: 19, max: 76, label: "SD Scale Total (19–76)" };
  if (itemId === "PJ_TOTAL") return { min: 21, max: 84, label: "PJ Scale Total (21–84)" };
  return { min: 1.0, max: 4.0, label: "Mean Item Score (1–4)" };
}

// Display metadata for synthetic items
const SYNTHETIC_META = {
  "SD_TOTAL": {
    title: "SD_TOTAL — Social Distance Scale Total",
    en: `Sum of SD01–SD19 (${SD_ITEMS.length} items, range ${SD_ITEMS.length}–${SD_ITEMS.length * 4}, higher = more stigma)`,
    zh: "",
  },
  "PJ_TOTAL": {
    title: "PJ_TOTAL — Prejudice Scale Total",
    en: `Sum of PJ01–PJ21 (${PJ_ITEMS.length} items, range ${PJ_ITEMS.length}–${PJ_ITEMS.length * 4}, higher = more stigma)`,
    zh: "",
  },
};

// ---- Score lookup ---------------------------------------------------------
function getScore(model, itemId, vignette, lang) {
  const key = `Mean_${lang.toUpperCase()}_${vignette.toUpperCase()}`;
  const map = (itemId === "SD_TOTAL" || itemId === "PJ_TOTAL") ? SYNTHETIC_MAP : DATA_MAP;
  const row = map.get(model)?.get(itemId);
  if (!row) return null;
  const val = parseFloat(row[key]);
  return isNaN(val) ? null : val;
}

// ---- Boot -----------------------------------------------------------------
function init() {
  buildModelList();
  buildItemList();
  document.querySelectorAll(".model-cb").forEach(cb => cb.checked = true);
  const first = document.querySelector(".item-cb");
  if (first) first.checked = true;
  renderCharts();
}

// ---- Sidebar builders ----------------------------------------------------
function buildModelList() {
  const el = document.getElementById("model-list");
  el.innerHTML = uniqueModels.map(m => `
    <label>
      <input type="checkbox" class="model-cb" value="${m}" onchange="renderCharts()">
      <span style="color:${MODEL_COLORS[m] || FALLBACK_COLOR}; font-weight:bold;">■</span>
      ${m}
    </label>`).join("");
}

function buildItemList() {
  const el = document.getElementById("item-list");
  let html = "";

  // Scale totals group
  html += `<div class="item-group-header">Scale Totals</div>`;
  for (const [synId, meta] of Object.entries(SYNTHETIC_META)) {
    html += `
      <label>
        <input type="checkbox" class="item-cb" data-prefix="TOTAL"
               value="${synId}" onchange="renderCharts()">
        <span>
          <span class="item-id-badge total">${synId}</span>
          <span class="item-text-snippet"> ${meta.en}</span>
        </span>
      </label>`;
  }

  // Individual items
  let lastPrefix = null;
  const groupLabel = {"SD": "Social Distance (SD01–SD19)",
                      "PJ": "Prejudice (PJ01–PJ21)"};
  uniqueBaseItems.forEach(id => {
    const prefix = id.replace(/\d+/g, "");
    if (prefix !== lastPrefix) {
      html += `<div class="item-group-header">${groupLabel[prefix] || prefix}</div>`;
      lastPrefix = prefix;
    }
    const bi = ITEM_TEXT[id] || {};
    const enSnip = (bi.en || "").slice(0, 44) + ((bi.en||"").length > 44 ? "…" : "");
    const zhSnip = (bi.zh || "").slice(0, 22) + ((bi.zh||"").length > 22 ? "…" : "");
    html += `
      <label>
        <input type="checkbox" class="item-cb" data-prefix="${prefix}"
               value="${id}" onchange="renderCharts()">
        <span>
          <span class="item-id-badge">${id}</span>
          <span class="item-text-snippet">${enSnip}</span>
          ${zhSnip ? `<br><span class="item-text-snippet item-text-zh">${zhSnip}</span>` : ""}
        </span>
      </label>`;
  });
  el.innerHTML = html;
}

// ---- Selection helpers ----------------------------------------------------
function selectAll(cls, state) {
  document.querySelectorAll(`.${cls}`).forEach(cb => cb.checked = state);
  renderCharts();
}

function selectGroup(prefix) {
  document.querySelectorAll(`.item-cb[data-prefix="${prefix}"]`).forEach(cb => {
    cb.checked = true;
  });
  renderCharts();
}

// ---- Score table below each chart ----------------------------------------
function buildScoreTable(itemId, models, lang, langLabel) {
  const dec = (itemId === "SD_TOTAL" || itemId === "PJ_TOTAL") ? 2 : 3;
  const head = `<tr><th>Model</th>${VIGNETTES.map(v => `<th>${v}</th>`).join("")}</tr>`;
  const body = models.map(model => {
    const cells = VIGNETTES.map(v => {
      const val = getScore(model, itemId, v, lang);
      if (val === null) return `<td>—</td>`;
      const ci = CI_DATA?.[model]?.[itemId]?.[lang.toUpperCase()]?.[v];
      const ciStr = ci
        ? `<br><span style="color:#9e9e9e;font-size:0.72rem;">[${ci.lo.toFixed(dec)}, ${ci.hi.toFixed(dec)}]</span>`
        : "";
      return `<td>${val.toFixed(dec)}${ciStr}</td>`;
    });
    const color = MODEL_COLORS[model] || FALLBACK_COLOR;
    return `<tr>
      <td style="color:${color};font-weight:bold;">${model}</td>
      ${cells.join("")}
    </tr>`;
  }).join("");
  return `<div class="score-table-wrapper">
    <div class="score-table-lang-label">${langLabel}</div>
    <table class="score-table">
      <thead>${head}</thead>
      <tbody>${body}</tbody>
    </table>
  </div>`;
}

// ---- Rendering -----------------------------------------------------------
function renderCharts() {
  const selModels = [...document.querySelectorAll(".model-cb:checked")].map(c => c.value);
  const selItems  = [...document.querySelectorAll(".item-cb:checked")].map(c => c.value);

  const wrapper = document.getElementById("charts-wrapper");
  wrapper.innerHTML = "";
  activeCharts.forEach(c => c.destroy());
  activeCharts = [];

  if (!selItems.length || !selModels.length) {
    wrapper.innerHTML = '<p class="placeholder">No data selected.</p>';
    return;
  }

  selItems.forEach(itemId => {
    const isSynthetic = itemId === "SD_TOTAL" || itemId === "PJ_TOTAL";
    const bi = ITEM_TEXT[itemId] || {};
    const meta = SYNTHETIC_META[itemId] || null;

    const titleText    = meta ? meta.title    : itemId;
    const subtitleEn   = meta ? meta.en       : (bi.en || "");
    const subtitleZh   = meta ? meta.zh       : (bi.zh || "");

    const section = document.createElement("div");
    section.className = "item-section";
    section.innerHTML = `
      <div class="item-title">${titleText}</div>
      <div class="item-subtitle">${subtitleEn}</div>
      ${subtitleZh ? `<div class="item-subtitle item-subtitle-zh">${subtitleZh}</div>` : ""}
      <div class="charts-row">
        <div class="chart-container"><canvas id="cv-${itemId}-EN"></canvas></div>
        <div class="chart-container"><canvas id="cv-${itemId}-ZH"></canvas></div>
      </div>
      <div class="score-tables-row" id="st-${itemId}"></div>`;
    wrapper.appendChild(section);

    drawChart(`cv-${itemId}-EN`, itemId, selModels, "EN", "English Prompts");
    drawChart(`cv-${itemId}-ZH`, itemId, selModels, "ZH", "Chinese Prompts (Traditional)");

    // Score tables below charts
    const stRow = document.getElementById(`st-${itemId}`);
    stRow.innerHTML =
      buildScoreTable(itemId, selModels, "EN", "EN — Scores by Vignette") +
      buildScoreTable(itemId, selModels, "ZH", "ZH — Scores by Vignette");
  });
}

function drawChart(canvasId, itemId, models, lang, title) {
  const ctx = document.getElementById(canvasId).getContext("2d");
  const yAxis = getYAxis(itemId);

  const datasets = models.map(model => {
    const scores = VIGNETTES.map(v => getScore(model, itemId, v, lang));
    return {
      label: model,
      data: scores,
      borderColor:     MODEL_COLORS[model] || FALLBACK_COLOR,
      backgroundColor: MODEL_COLORS[model] || FALLBACK_COLOR,
      tension: 0.15,
      pointRadius: 4,
      pointHoverRadius: 6,
      borderWidth: 2,
      spanGaps: true,
    };
  });

  const chart = new Chart(ctx, {
    type: "line",
    data: { labels: VIGNETTES, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: title,
          font: { size: 14, weight: "bold" },
          padding: { bottom: 10 },
        },
        legend: {
          position: "bottom",
          labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(3) ?? "N/A"}`,
          },
        },
      },
      scales: {
        y: {
          min: yAxis.min,
          max: yAxis.max,
          title: { display: true, text: yAxis.label },
          ticks: { stepSize: (itemId === "SD_TOTAL" || itemId === "PJ_TOTAL") ? 5 : 0.5 },
          grid: { color: "#f0f0f0" },
        },
        x: {
          title: { display: true, text: "Clinical Vignette" },
          grid: { display: false },
        },
      },
    },
  });
  activeCharts.push(chart);
}

init();
</script>
</body>
</html>
"""


def _t_crit_95(df: int) -> float:
    """Approximate two-tailed t-critical value for 95% CI."""
    if df >= 120: return 1.980
    if df >= 60:  return 2.000
    if df >= 40:  return 2.021
    if df >= 29:  return 2.045
    if df >= 24:  return 2.060
    if df >= 19:  return 2.086
    if df >= 14:  return 2.131
    if df >= 9:   return 2.228
    if df >= 4:   return 2.571
    return 12.706


def _ci_from_vals(vals: list) -> dict | None:
    n = len(vals)
    if n < 2:
        return None
    mean_v = sum(vals) / n
    var = sum((v - mean_v) ** 2 for v in vals) / (n - 1)
    se = math.sqrt(var / n)
    margin = _t_crit_95(n - 1) * se
    return {"lo": round(mean_v - margin, 3), "hi": round(mean_v + margin, 3)}


def compute_ci_data(input_path: Path) -> dict:
    """
    Returns ci[model][item_id][lang][vignette] = {"lo": float, "hi": float}.
    Item-level CI comes from scored_value in raw results CSVs.
    Scale-total CI comes from scale_score_primary in run_level_scale_scores.csv.
    """
    ci: dict = {}

    for lang in ["en", "zh"]:
        lang_upper = lang.upper()
        lang_dir = input_path / lang
        if not lang_dir.is_dir():
            continue

        # Item-level CI
        csv_files = sorted(lang_dir.glob("results_*.csv"))
        if csv_files:
            groups: dict[tuple, list] = {}
            with open(csv_files[0], "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    sv = row.get("scored_value", "").strip()
                    if not sv:
                        continue
                    try:
                        val = float(sv)
                    except ValueError:
                        continue
                    key = (
                        row.get("model", "").strip(),
                        row.get("item_id", "").strip().upper(),
                        row.get("vignette", "").strip().upper(),
                    )
                    groups.setdefault(key, []).append(val)
            for (model, item_id, vignette), vals in groups.items():
                result = _ci_from_vals(vals)
                if result:
                    ci.setdefault(model, {}).setdefault(item_id, {}).setdefault(lang_upper, {})[vignette] = result

        # Scale-total CI (SD_TOTAL / PJ_TOTAL)
        rls_path = lang_dir / "run_level_scale_scores.csv"
        if rls_path.exists():
            scale_groups: dict[tuple, list] = {}
            with open(rls_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    sp = row.get("scale_score_primary", "").strip()
                    if not sp or sp.upper() == "NA":
                        continue
                    try:
                        val = float(sp)
                    except ValueError:
                        continue
                    scale_type = row.get("scale_type", "").strip().lower()
                    syn_id = "SD_TOTAL" if scale_type == "social_distance" else "PJ_TOTAL"
                    key = (
                        row.get("model", "").strip(),
                        syn_id,
                        row.get("vignette", "").strip().upper(),
                    )
                    scale_groups.setdefault(key, []).append(val)
            for (model, syn_id, vignette), vals in scale_groups.items():
                result = _ci_from_vals(vals)
                if result:
                    ci.setdefault(model, {}).setdefault(syn_id, {}).setdefault(lang_upper, {})[vignette] = result

    return ci


def _fetch_chartjs() -> str:
    """Return an inline <script> tag with Chart.js, falling back to CDN."""
    try:
        req = urllib.request.Request(
            CHARTJS_URL,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            js = resp.read().decode("utf-8")
        print(f"  Embedded Chart.js inline ({len(js)//1024} KB).")
        return f"<script>{js}</script>"
    except Exception as exc:
        print(f"  Warning: could not fetch Chart.js ({exc}). Using CDN link.")
        return CHARTJS_CDN_FALLBACK


def _sort_key(item_id: str):
    prefix = "".join(c for c in item_id if c.isalpha())
    num    = int("".join(c for c in item_id if c.isdigit()) or "0")
    return ({"SD": 0, "PJ": 1}.get(prefix, 99), num)


def main():
    parser = argparse.ArgumentParser(
        description="Generate interactive HTML dashboard for item-level stigma scores."
    )
    parser.add_argument(
        "input_dir",
        help="Analysis directory containing Table5_item_stigma_profile.csv",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output directory (default: <input_dir>/stigma_dashboard/)",
    )
    args = parser.parse_args()

    input_path = Path(args.input_dir).resolve()
    if not input_path.is_dir():
        sys.exit(f"Error: directory not found: {input_path}")

    csv_file = input_path / "Table5_item_stigma_profile.csv"
    if not csv_file.exists():
        found = list(input_path.rglob("Table5_item_stigma_profile.csv"))
        if not found:
            sys.exit(f"Error: Table5_item_stigma_profile.csv not found in {input_path}")
        csv_file = found[0]
        print(f"  Found CSV at: {csv_file}")

    # Load CSV ---------------------------------------------------------------
    rows: list[dict] = []
    with open(csv_file, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    if not rows:
        sys.exit("Error: CSV is empty.")

    print(f"  Loaded {len(rows)} rows from {csv_file.name}")

    # Build bilingual item label map: {Item_ID: {"en": ..., "zh": ...}}.
    # Public dashboard intentionally shows Item_ID + Item_Domain only —
    # the verbatim scale wording is copyrighted (Wang 2020) and is not
    # included in the released CSV. If Item_Text columns are present
    # locally (private workflow), they are used; otherwise the label
    # falls back to "Item_ID (Item_Domain)".
    item_text_map: dict[str, dict] = {}
    for row in rows:
        iid = row.get("Item_ID", "")
        if not iid or iid in item_text_map:
            continue
        domain = row.get("Item_Domain", "")
        fallback = f"{iid} ({domain})" if domain else iid
        en_txt = row.get("Item_Text", "") or fallback
        item_text_map[iid] = {"en": en_txt, "zh": fallback}

    # Optional: enrich with ZH wording if a private (gitignored) raw CSV
    # is present locally. Skipped silently when not available.
    zh_csv = next(
        (p for p in (input_path / "zh").glob("results_*.csv") if p.is_file()),
        None,
    )
    if zh_csv:
        with open(zh_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                iid = row.get("item_id", "")
                zh_txt = row.get("item_text", "")
                if iid in item_text_map and zh_txt:
                    item_text_map[iid]["zh"] = zh_txt
        print(f"  Loaded ZH item wording from {zh_csv.name} (private)")
    else:
        print("  Note: ZH raw CSV absent — using Item_ID/Domain labels only.")

    # Sort items SD01→SD19, PJ01→PJ21 ----------------------------------------
    item_text_map = dict(sorted(item_text_map.items(), key=lambda kv: _sort_key(kv[0])))

    # Compute 95% CI ----------------------------------------------------------
    print("Computing 95% CI from run-level data...")
    ci_data = compute_ci_data(input_path)
    n_ci_cells = sum(
        len(vigs)
        for model_d in ci_data.values()
        for item_d in model_d.values()
        for lang_d in item_d.values()
        for vigs in [lang_d]
    )
    print(f"  CI computed for {n_ci_cells} (model × item × lang × vignette) cells.")

    # Fetch Chart.js ----------------------------------------------------------
    print("Fetching Chart.js...")
    chartjs_script = _fetch_chartjs()

    # Build HTML --------------------------------------------------------------
    html = HTML_TEMPLATE
    html = html.replace("%%CHARTJS%%",      chartjs_script)
    html = html.replace("%%DATA%%",         json.dumps(rows,          ensure_ascii=False))
    html = html.replace("%%ITEM_TEXT_MAP%%", json.dumps(item_text_map, ensure_ascii=False))
    html = html.replace("%%MODEL_ORDER%%",  json.dumps(MODEL_ORDER,   ensure_ascii=False))
    html = html.replace("%%MODEL_COLORS%%", json.dumps(MODEL_COLORS,  ensure_ascii=False))
    html = html.replace("%%CI_DATA%%",      json.dumps(ci_data,       ensure_ascii=False))

    # Write output ------------------------------------------------------------
    out_dir = Path(args.output) if args.output else input_path / "stigma_dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"
    out_file.write_text(html, encoding="utf-8")

    print(f"\nDashboard written to: {out_file}")
    print(f"Open in browser:      file://{out_file.resolve()}")


if __name__ == "__main__":
    main()

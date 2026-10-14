#!/usr/bin/env python3
"""
Self-contained model metadata + run-level data loader for the JAMA Network Open
(0624) 14-model submission figures.

This module makes the submission figure scripts independent of the poster: it
vendors the model metadata (release dates, display names, families, palette,
deployment mode, Wang human baselines, scale ranges) and the pure data helpers
(decimal_year, xpos, load_model_means, jittered_year) that figure3_trend_dual_lang
_2x2_0624.py needs. It deliberately carries NO plotting code and NO OLS-trend
helper — the submission Figure 3 shows no fitted trend line (0625 statistical
revision). A separate copy is used for conference material; the two are intentionally separate so neither depends
on the other.

Reads run-level prorated scale scores from analysis_14models_20260614/{en,zh}/.
"""
# Model names (2026-10-12): the model tables in this script use the collection names of the authors' merged files
# (e.g. "Gemini 2.5 Flash"), as in the analysis behind the article. analyze_stage1.R run on data_public/ writes the
# article names ("Gemini-2.5-Flash"; scripts_public/Models_name.md); rename them back before running this script.
from __future__ import annotations

import csv
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

# This module lives at scripts_public/figure_metadata_14model.py,
# so the repo root is two levels up (one shallower than the poster copy).
REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = REPO_ROOT / "analysis_14models_20260614"

# ── Model metadata (mirrors analyze_stage1.R / poster) ─────────────────────
# Keys = spaced data ids (match run_level_scale_scores.csv); DISPLAY = canonical
# hyphenated names (scripts_public/Models_name.md).
# Release month (YYYY-MM) of the API identifier queried (Supplementary Table 1, Part B): the stable release (the
# snapshot release for gpt-3.5-turbo-0125; general availability for the Gemini Flash models), or the preview release
# for the two preview-designated Gemini 3.1 models. Checked against the providers' announcements, model cards and
# changelogs on 2026-10-12 (editorial audit, item E01); models are plotted at the middle of the month.
RELEASE = {
    "GPT-3.5": "2024-02", "GPT-4o": "2024-05", "GPT-OSS-120B": "2025-08",
    "GPT-5.4": "2026-03", "GPT-5.4 Mini": "2026-03",
    "Claude Sonnet 4.5": "2025-09", "Claude Opus 4.6": "2026-02",
    "Gemini 2.5 Flash": "2025-06", "Gemini 3.1 Pro Preview": "2026-02",
    "Gemini 3.1 Flash-Lite Preview": "2026-03", "Gemini 3.5 Flash": "2026-05",
    "Gemma 4 31B IT": "2026-04", "Llama 3.3 70B": "2024-12",
    "DeepSeek V3.2": "2025-12",
}
DISPLAY = {
    "GPT-3.5": "GPT-3.5", "GPT-4o": "GPT-4o", "GPT-OSS-120B": "GPT-OSS-120B",
    "GPT-5.4": "GPT-5.4", "GPT-5.4 Mini": "GPT-5.4-Mini",
    "Claude Sonnet 4.5": "Claude Sonnet 4.5", "Claude Opus 4.6": "Claude Opus 4.6",
    "Gemini 2.5 Flash": "Gemini-2.5-Flash", "Gemini 3.1 Pro Preview": "Gemini-3.1-Pro-Preview",
    "Gemini 3.1 Flash-Lite Preview": "Gemini-3.1-Flash-Lite-Preview",
    "Gemini 3.5 Flash": "Gemini-3.5-Flash", "Gemma 4 31B IT": "Gemma-4-31B-IT",
    "Llama 3.3 70B": "Llama-3.3-70B", "DeepSeek V3.2": "DeepSeek-V3.2",
}
FAMILY = {
    "GPT-3.5": "GPT", "GPT-4o": "GPT", "GPT-OSS-120B": "GPT", "GPT-5.4": "GPT",
    "GPT-5.4 Mini": "GPT", "Claude Sonnet 4.5": "Claude", "Claude Opus 4.6": "Claude",
    "Gemini 2.5 Flash": "Gemini", "Gemini 3.1 Pro Preview": "Gemini",
    "Gemini 3.1 Flash-Lite Preview": "Gemini", "Gemini 3.5 Flash": "Gemini",
    "Gemma 4 31B IT": "Gemini", "Llama 3.3 70B": "Llama", "DeepSeek V3.2": "DeepSeek",
}
# Okabe-Ito family palette (same as draft figure 2/3)
FAM_PAL = {
    "GPT": "#009E73", "Claude": "#E69F00", "Gemini": "#0072B2",
    "Llama": "#CC79A7", "DeepSeek": "#D55E00",
}
FAM_ORDER = ["GPT", "Claude", "Gemini", "Llama", "DeepSeek"]
FAM_LEGEND = {
    "GPT": "GPT (OpenAI)", "Claude": "Claude (Anthropic)",
    "Gemini": "Gemini incl. Gemma (Google)", "Llama": "Llama (Meta)",
    "DeepSeek": "DeepSeek",
}
DEPLOYMENT = {m: ("Open-weight" if m in
                  {"GPT-OSS-120B", "Gemma 4 31B IT", "Llama 3.3 70B", "DeepSeek V3.2"}
                  else "API") for m in RELEASE}

# Wang et al. (Taiwan general public) human baselines, per vignette (zh instrument).
WANG_BASELINE = {
    "social_distance": {"PLE": 38.78, "DEP": 48.10, "APS": 47.98, "SCZ": 53.55},
    "prejudice":       {"PLE": 42.25, "DEP": 48.56, "APS": 48.13, "SCZ": 52.62},
}

SCALE_META = {
    "social_distance": dict(fig="Figure1", label="Social Distance", lo=19, hi=76),
    "prejudice":       dict(fig="Figure2", label="Prejudice",       lo=21, hi=84),
}

HORIZON = 2026.70  # just past the newest release; controls the log-time x-axis


def decimal_year(s: str) -> float:
    """Decimal year of an ISO date; a month (YYYY-MM) is placed at its 15th day."""
    d = date.fromisoformat(s + "-15" if len(s) == 7 else s)
    start = date(d.year, 1, 1).toordinal()
    return d.year + (d.toordinal() - start) / (date(d.year, 12, 31).toordinal() - start + 1)


def xpos(year: float) -> float:
    """Reverse log-of-time-to-horizon: older -> left, newer -> right, recent expanded."""
    return -math.log10(HORIZON - year)


def load_model_means(lang: str, scale: str) -> dict[str, dict]:
    """Per model: grand mean across vignettes + 95% CI across runs (vignette-averaged)."""
    path = ANALYSIS_DIR / lang / "run_level_scale_scores.csv"
    run_overall: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["scale_type"] != scale:
                continue
            if (r.get("in_primary_analysis") or r.get("in_primary")) != "TRUE":
                continue
            try:
                run_overall[r["model"]][r["analysis_run"]].append(float(r["scale_score_primary"]))
            except (ValueError, KeyError):
                continue
    out = {}
    for model, runs in run_overall.items():
        per_run = [statistics.fmean(v) for v in runs.values() if v]
        if not per_run:
            continue
        n = len(per_run); m = statistics.fmean(per_run)
        sd = statistics.stdev(per_run) if n > 1 else 0.0
        t = 2.045 if n >= 20 else (2.262 if n >= 10 else 2.5)
        half = t * sd / math.sqrt(n) if n > 1 else 0.0
        out[model] = dict(mean=m, lo=m - half, hi=m + half, n=n)
    return out


def jittered_year(models: list[str]) -> dict[str, float]:
    """Tiny date jitter so models sharing a release date don't overprint."""
    by_date: dict[str, list[str]] = defaultdict(list)
    for mdl in models:
        by_date[RELEASE[mdl]].append(mdl)
    yr = {}
    for _, group in by_date.items():
        g = sorted(group)
        for i, mdl in enumerate(g):
            offset = (i - (len(g) - 1) / 2) * 0.020
            yr[mdl] = decimal_year(RELEASE[mdl]) + offset
    return yr

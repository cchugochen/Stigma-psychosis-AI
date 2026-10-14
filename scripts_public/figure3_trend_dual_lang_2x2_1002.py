#!/usr/bin/env python3
"""
Figure 3 (npj Digital Medicine revision, 2026-10-02) — LLM stigma score vs release year.

Copy of figure3_trend_dual_lang_2x2_0703.py (which produced the submitted figure),
with the corrections listed in the October 2026 revision notes (§3.2):

  1. The descriptive OLS trend line and its 95% CI ribbon are REMOVED. The ribbon
     used t(.975, df = 12), i.e. it treated the 14 model means as independent
     observations, which contradicts the revised Methods ("the 14 models ... do not
     constitute a sample from any population of models") and the reason given for
     removing the pooled estimates from Figure 2 (Reviewer 3, Minor 3). This
     supersedes the 2026-07-03 decision to restore the line.
  2. The within-family trajectory lines are KEPT; they carry the descriptive
     content (Reviewer 1, Comment 7; Reviewer 3, Comment 6).
  3. The human reference star (Wang et al., 2020; Chinese-language Taiwanese sample)
     is drawn on the Mandarin Chinese panels only, and is dated 2020, not 2019
     (Reviewer 2, Comment 9).
  4. Panel labels in lower-case bold a-d (npj figure guideline).
  5. Figure text set in Arial (the 0703 render used matplotlib's default DejaVu Sans).
  6. Labels are placed after the shared y-limits and tight_layout are fixed, with a wider
     repulsion margin, so that they no longer overlap their own markers.
  7. (2026-10-12) Release months follow Supplementary Table 1, Part B: the release month of the API
     identifier queried (stable release; preview release for the two preview-designated Gemini 3.1
     models), plotted at mid-month (RELEASE in figure_metadata_14model.py). Rendered as --suffix 1012, and again as --suffix 1013 (2026-10-13, unchanged).

Everything else (palette, shapes, reverse-log time-to-horizon x-axis, DeepSeek
annotation, adjustText labels, sans-serif figure text) matches the 0703 script.

Reads run-level prorated scale scores from analysis_14models_20260614/{en,zh}/.

Usage:
  python3 scripts_public/figure3_trend_dual_lang_2x2_1002.py \
      [--out outputs/figures_tables] [--suffix 1002]
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
# npj figure guideline: Arial/Helvetica, used consistently (Figures 1-2 are Helvetica);
# the 0703 render used matplotlib's default DejaVu Sans. TrueType fonts embedded in the PDF.
plt.rcParams.update({"font.family": "Arial", "pdf.fonttype": 42, "ps.fonttype": 42})
from matplotlib.lines import Line2D
from adjustText import adjust_text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figure_metadata_14model import (  # noqa: E402
    RELEASE, DISPLAY, FAMILY, FAM_PAL, FAM_ORDER, FAM_LEGEND,
    DEPLOYMENT, WANG_BASELINE, SCALE_META,
    decimal_year, xpos, load_model_means, jittered_year,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

LANG_TITLE = {"en": "English (EN) prompts", "zh": "Mandarin Chinese (ZH) prompts"}
SCALE_ROWLAB = {
    "social_distance": "Social Distance\nMean Score (19–76)",
    "prejudice": "Prejudice\nMean Score (21–84)",
}
GRID = [
    [("social_distance", "en", "a"), ("social_distance", "zh", "b")],
    [("prejudice", "en", "c"), ("prejudice", "zh", "d")],
]


def draw_panel(ax, lang, scale, ylo, *, show_title, show_xlabel, show_ylabel, tag):
    means = load_model_means(lang, scale)
    models = [m for m in RELEASE if m in means]
    yr = jittered_year(models)
    X = {m: xpos(yr[m]) for m in models}

    xs = [X[m] for m in models]
    ys = [means[m]["mean"] for m in models]

    # ── within-family trajectory lines (release order; ≥2 models) ───────────
    fam_models = defaultdict(list)
    for m in models:
        fam_models[FAMILY[m]].append(m)
    for fam, ms in fam_models.items():
        if len(ms) < 2:
            continue
        ms_sorted = sorted(ms, key=lambda m: (decimal_year(RELEASE[m]), m))
        ax.plot([X[m] for m in ms_sorted], [means[m]["mean"] for m in ms_sorted],
                color=FAM_PAL[fam], lw=1.0, alpha=0.45, zorder=2,
                solid_capstyle="round")

    # ── points + error bars (shape = access mode) ────────────────────────────
    texts = []
    is_sd_zh = (scale == "social_distance" and lang == "zh")  # Panel B
    for m in models:
        x = X[m]
        d = means[m]
        col = FAM_PAL[FAMILY[m]]
        open_w = DEPLOYMENT[m] == "Open-weight"
        ax.errorbar(x, d["mean"], yerr=[[d["mean"] - d["lo"]], [d["hi"] - d["mean"]]],
                    fmt="D" if open_w else "o", ms=6.5,
                    color=col, ecolor=col, elinewidth=1.0, capsize=2.0,
                    markerfacecolor=("white" if open_w else col),
                    markeredgecolor=col, markeredgewidth=1.2, zorder=3)
        if is_sd_zh and m == "DeepSeek V3.2":
            lab = f"DeepSeek-V3.2 = {d['mean']:.1f}"
            texts.append(ax.text(x, d["mean"], lab, fontsize=7.0, color=col,
                                 fontweight="bold", ha="center", va="center"))
        else:
            texts.append(ax.text(x, d["mean"], DISPLAY[m], fontsize=6.0,
                                 color="#222222", ha="center", va="center"))

    # human reference star at the 2019 position — Mandarin Chinese panels only
    # (Wang et al., 2020 is a Chinese-language Taiwanese sample)
    star_x, star_y = [], []
    if lang == "zh":
        hb = statistics.fmean(WANG_BASELINE[scale].values())
        hx = xpos(2019.0)
        ax.plot(hx, hb, marker="*", ms=17, mfc="black", mec="black", zorder=4)
        texts.append(ax.text(hx, hb, "Human\n(Wang, 2020)", fontsize=6.8, color="black",
                             fontweight="bold", ha="center", va="center"))
        star_x, star_y = [hx], [hb]

    ticks = [2019, 2022, 2024, 2025, 2026, 2026.5]
    ax.set_xticks([xpos(t) for t in ticks])
    ax.set_xticklabels(["2019", "2022", "2024", "2025", "2026", "2026.5"])
    ax.set_xlim(xpos(2018.5), xpos(2026.5))
    ax.set_ylim(ylo, None)
    if show_xlabel:
        ax.set_xlabel("Model release year (log time-to-horizon scale)")
    if show_title:
        ax.set_title(LANG_TITLE[lang], fontweight="bold", fontsize=12)
    if show_ylabel:
        ax.set_ylabel(SCALE_ROWLAB[scale], fontweight="bold")
    ax.grid(axis="y", color="0.92", lw=0.6)
    ax.set_axisbelow(True)
    ax.text(0.012, 0.975, tag, transform=ax.transAxes, fontsize=15,
            fontweight="bold", va="top", ha="left")
    # labels are positioned later, after the row's shared y-limits are set
    return texts, xs + star_x, ys + star_y


def place_labels(ax, texts, x, y):
    adjust_text(texts, x=x, y=y, ax=ax,
                arrowprops=dict(arrowstyle="-", color="0.55", lw=0.5),
                expand=(1.4, 2.6), force_text=(0.4, 0.6), min_arrow_len=3,  # wider margin: markers have size
                iter_lim=1000)  # fixed iterations (the default 1-s time limit is not reproducible)


def build_figure(out_dir: Path, suffix: str):
    fig, axes = plt.subplots(2, 2, figsize=(15, 14.5))
    labels = {}
    for r, row in enumerate(GRID):
        for c, (scale, lang, tag) in enumerate(row):
            labels[(r, c)] = draw_panel(
                axes[r][c], lang, scale, ylo=SCALE_META[scale]["lo"],
                show_title=(r == 0), show_xlabel=(r == 1),
                show_ylabel=(c == 0), tag=tag,
            )
        lo = min(axes[r][0].get_ylim()[0], axes[r][1].get_ylim()[0])
        hi = max(axes[r][0].get_ylim()[1], axes[r][1].get_ylim()[1])
        axes[r][0].set_ylim(lo, hi)
        axes[r][1].set_ylim(lo, hi)

    fam_handles = [Line2D([0], [0], marker="o", linestyle="-", lw=1.0, alpha=0.9,
                          color=FAM_PAL[f], markerfacecolor=FAM_PAL[f],
                          markeredgecolor=FAM_PAL[f],
                          markersize=8, label=FAM_LEGEND[f]) for f in FAM_ORDER]
    mode_handles = [
        Line2D([0], [0], marker="o", linestyle="None", markerfacecolor="0.35",
               markeredgecolor="0.35", markersize=8, label="API-served"),
        Line2D([0], [0], marker="D", linestyle="None", markerfacecolor="white",
               markeredgecolor="0.35", markeredgewidth=1.2, markersize=8,
               label="Open-weight"),
        Line2D([0], [0], marker="*", linestyle="None", markerfacecolor="black",
               markeredgecolor="black", markersize=14,
               label="Human baseline (Wang, 2020; Mandarin Chinese panels only)"),
    ]
    leg1 = fig.legend(handles=fam_handles, loc="lower center", ncol=5, frameon=False,
                      fontsize=8.5, bbox_to_anchor=(0.5, 0.045),
                      title="Developer family (lines connect models within a family in release order)",
                      title_fontproperties={"weight": "bold", "size": 9})
    fig.add_artist(leg1)
    fig.legend(handles=mode_handles, loc="lower center", ncol=3, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, 0.012))

    fig.tight_layout(rect=(0, 0.075, 1, 0.97))
    # place labels last, once the shared y-limits and the final axes geometry are fixed
    for (r, c), lab in labels.items():
        place_labels(axes[r][c], *lab)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "figure3_release_date_scatter_dual_lang"
    if suffix:
        stem = f"{stem}_{suffix}"
    base = out_dir / stem
    fig.savefig(base.with_suffix(".pdf"))
    fig.savefig(base.with_suffix(".png"), dpi=300)
    plt.close(fig)
    print(f"  wrote {base.with_suffix('.pdf')} / .png")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="outputs/figures_tables",
                   help="Output directory (relative to repo root).")
    p.add_argument("--suffix", default="1002",
                   help="Filename date stamp (mmdd). Pass '' to omit.")
    args = p.parse_args()
    out_dir = REPO_ROOT / args.out
    print(f"Building Figure 3 (2x2; family trajectories, no OLS line/ribbon) -> {out_dir}")
    build_figure(out_dir, args.suffix)
    print("Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Supplementary Fig. 4 (Reviewer 1, Minor 4): response flow, by prompt language.

All counts are computed here from the dataset of record (analysis_14models_20260614/):
master item-level CSVs (response_type, raw_response), run_level_scale_scores.csv
(in_primary_analysis, in_complete_case_analysis) and tableS3_reliability.csv.
The first box counts the scheduled item queries, each with one stored outcome; retries were not logged, so the number of
HTTP attempts is not known (2026-10-12, editorial audit E14). Output suffix 1013 since 2026-10-13 (same figure).

Usage: python scripts_public/efigure4_flow_diagram_1007.py
"""
import csv
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({"font.family": "Arial", "pdf.fonttype": 42, "ps.fonttype": 42})
REPO = Path(__file__).resolve().parent.parent
AN = REPO / "analysis_14models_20260614"
OUT = REPO / "outputs" / "figures_tables"


def counts(lang):
    c, api, n = Counter(), 0, 0
    with open(AN / lang / f"results_14models_{lang}.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            n += 1
            c[r["response_type"]] += 1
            api += (r["raw_response"] or "").startswith("[API_ERROR]")
    rl = list(csv.DictReader(open(AN / lang / "run_level_scale_scores.csv", encoding="utf-8")))
    rel = list(csv.DictReader(open(AN / lang / "tableS3_reliability.csv", encoding="utf-8")))
    d = dict(calls=n, valid=c["valid"], refusal=sum(v for k, v in c.items() if k.startswith("refusal")),
             unparse=c["unparseable"] + c.get("safety", 0), api=api, runs=len(rl),
             retained=sum(r["in_primary_analysis"] == "TRUE" for r in rl),
             complete=sum(r["in_complete_case_analysis"] == "TRUE" for r in rl),
             cells=len({(r["model"], r["vignette"], r["scale_type"]) for r in rl}),
             grad=len({(r["model"], r["scale_type"]) for r in rl}),
             evaluable=sum(r["mean_pairwise_spearman"] not in ("NA", "") for r in rel))
    assert d["valid"] + d["refusal"] + d["unparse"] == n
    d["excluded"] = d["runs"] - d["retained"]
    return d


def main():
    en, zh = counts("en"), counts("zh")
    f = lambda k: f"{en[k]:,}  |  {zh[k]:,}"
    fig, ax = plt.subplots(figsize=(10, 11))
    ax.set_xlim(0, 100); ax.set_ylim(0, 112); ax.axis("off")

    def box(x, y, w, h, title, lines, fc="#F4F6F8"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                    fc=fc, ec="#4A4A4A", lw=1.0))
        ax.text(x + w / 2, y + h - 2.2, title, ha="center", va="top", fontsize=10.5, fontweight="bold")
        ax.text(x + w / 2, y + h - 6.0, "\n".join(lines), ha="center", va="top", fontsize=9.5, linespacing=1.45)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color="#4A4A4A", lw=1.1, shrinkA=0, shrinkB=0))

    ax.text(50, 111, "Counts shown as English  |  Mandarin Chinese", ha="center", va="top", fontsize=10, style="italic")
    box(14, 92, 56, 15, "Item-level queries",
        ["14 models × 30 runs × 4 vignettes × 40 items", f(("calls")),
         "One stored outcome per query; retries not logged"])
    arrow(42, 92, 42, 86)
    box(14, 64, 56, 21.5, "Responses classified by the locked classifier",
        [f"Valid: {f('valid')}", f"Refusal: {f('refusal')}",
         f"Unparseable or error: {f('unparse')}", f"   of which API errors: {f('api')}",
         "Non-valid items were treated as missing"])
    arrow(42, 64, 42, 58)
    box(14, 46, 56, 11.5, "Run-level scale scores",
        ["model × vignette × scale × run", f("runs")])
    arrow(42, 46, 42, 40)
    arrow(70, 51.5, 76, 51.5)
    box(76.5, 45, 22, 13, "Excluded", ["< 80% of scale items", "valid", f("excluded")], fc="#FBEFEF")
    box(14, 27, 56, 12.5, "Qualifying runs (primary analysis)",
        [f("retained"), f"All items valid (complete case): {f('complete')}"])
    arrow(42, 27, 42, 21)
    box(14, 1.5, 56, 19, "Analyzed cells",
        [f"Model × vignette × scale: {f('cells')}", "(descriptive and cross-language analyses)",
         f"Model × scale: {f('grad')} (gradient concordance)",
         f"Reliability evaluable (≥ 10 complete runs): {f('evaluable')}"])
    OUT.mkdir(parents=True, exist_ok=True)
    stem = OUT / "efigure4_flow_diagram_1013"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    print("EN", en, "\nZH", zh)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Supplementary Table 11 (Reviewer 1, Comment 4): elicitation-format sensitivity, four models.

Reads analysis_sen_20260930/comparison/*.csv (compare_frames_4model.R output) and writes the
five parts of the table to analysis_sen_20260930/comparison/supp_table11_part{A..E}.csv.
Gradient classification uses the primary rule of the revised Methods (strict_rule column:
unrounded means, an exact tie at either boundary is non-concordant).

Usage: python scripts_public/supp_table11_4model.py
"""
import csv
import statistics
from pathlib import Path

C = Path(__file__).resolve().parent.parent / "analysis_sen_20260930" / "comparison"
LABEL = {"Original_pub": "Original prompt, main study", "Original_oct": "Original prompt, October re-run",
         "Humanlike": "Role-play instruction", "Fullscale": "Full-scale administration"}
LANG = {"en": "English", "zh": "Mandarin Chinese"}
MODELS = ["GPT-5.4", "GPT-OSS-120B", "Claude Sonnet 4.5", "Gemini-3.5-Flash"]


def rows(name):
    return list(csv.DictReader(open(C / name, encoding="utf-8")))


def write(name, data):
    with open(C / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader(); w.writerows(data)
    print(f"wrote {name} ({len(data)} rows)")


def main():
    # Part A: score shifts vs the same-session original prompt (+ drift)
    con = rows("contrasts_all.csv")
    fam = [("Humanlike_vs_Original_oct", "Role-play instruction − original prompt (October)"),
           ("Fullscale_vs_Original_oct", "Full-scale administration − original prompt (October)"),
           ("Original_oct_vs_Original_pub", "Original prompt (October) − original prompt (main study)")]
    A = []
    for f, lab in fam:
        for lang in ("en", "zh"):
            g = [r for r in con if r["family"] == f and r["language"] == lang]
            d = [float(r["diff"]) for r in g]
            A.append(dict(comparison=lab, language=LANG[lang], cells=len(g),
                          median_difference=round(statistics.median(d), 2),
                          median_absolute_difference=round(statistics.median(abs(x) for x in d), 2),
                          cells_higher=sum(x > 0 for x in d),
                          cells_ci_excludes_zero=sum(float(r["diff_ci_low"]) > 0 or float(r["diff_ci_high"]) < 0 for r in g),
                          min_difference=round(min(d), 2), max_difference=round(max(d), 2),
                          cells_abs_delta_ge_0474=sum(abs(float(r["cliffs_delta"])) >= 0.474 for r in g)))
    write("supp_table11_partA_shifts.csv", A)

    # Part B: gradient classification (strict rule) and agreement with the October original prompt
    gr = rows("gradient_by_arm.csv")
    cls = {(r["arm"], r["language"], r["model"], r["scale_type"]): r["strict_rule"] == "TRUE" for r in gr}
    B = []
    for lang in ("en", "zh"):
        for arm in ("Original_pub", "Original_oct", "Humanlike", "Fullscale"):
            keys = [k for k in cls if k[0] == arm and k[1] == lang]
            ref = "Original_oct" if arm != "Original_oct" else None
            same = sum(cls[k] == cls[("Original_oct",) + k[1:]] for k in keys) if ref else ""
            B.append(dict(language=LANG[lang], condition=LABEL[arm], cells=len(keys),
                          concordant=sum(cls[k] for k in keys), same_classification_as_october_original=same))
    write("supp_table11_partB_gradient.csv", B)

    # Part C: cross-language direction
    cl = {r["arm"]: r for r in rows("crosslanguage_counts_by_arm.csv")}
    Cc = [dict(condition=LABEL[a], mandarin_higher_dep_aps_scz=f'{cl[a]["zh_higher_dep_aps_scz"]}/{cl[a]["dep_aps_scz_cells"]}',
               english_higher_ple=f'{cl[a]["en_higher_ple"]}/{cl[a]["ple_cells"]}',
               range_zh_minus_en=f'{float(cl[a]["min_diff"]):.1f} to {float(cl[a]["max_diff"]):.1f}')
          for a in ("Original_pub", "Original_oct", "Humanlike", "Fullscale")]
    write("supp_table11_partC_crosslanguage.csv", Cc)

    # Part D: English PLE − DEP difference by model and scale
    pdg = {(r["arm"], r["model"], r["scale_type"]): float(r["ple_minus_dep"]) for r in rows("ple_dep_gap_by_arm.csv")
           if r["language"] == "en"}
    D = []
    for m in MODELS:
        for sc in ("social_distance", "prejudice"):
            D.append(dict(model=m, scale="Social Distance" if sc == "social_distance" else "Prejudice",
                          **{LABEL[a]: round(pdg[(a, m, sc)], 2) for a in ("Original_pub", "Original_oct", "Humanlike", "Fullscale")}))
    write("supp_table11_partD_ple_dep.csv", D)

    # Part E: response validity by condition and language
    rt = rows("response_types_by_arm.csv")
    comp = rows("Fullscale_completeness.csv")
    trunc = rows("Fullscale_truncation.csv")
    sl = rows("straightlining_by_arm.csv")
    E = []
    for arm in ("Original_pub", "Original_oct", "Humanlike", "Fullscale"):
        for lang in ("en", "zh"):
            g = [r for r in rt if r["arm"] == arm and r["language"] == lang]
            items = sum(int(r["items"]) - int(r["api_error"]) for r in g)
            nonvalid = sum(int(r["refusal_any"]) + int(r["unparseable_excl_api"]) for r in g)
            oss = [r for r in g if r["model"] == "GPT-OSS-120B"][0]
            oss_items = int(oss["items"]) - int(oss["api_error"])
            row = dict(condition=LABEL[arm], language=LANG[lang],
                       nonvalid_pct_all_models=round(100 * nonvalid / items, 2),
                       gpt_oss_refusal_pct=round(100 * int(oss["refusal_any"]) / oss_items, 1),
                       identity_refusals=sum(int(r["refusal_identity"]) for r in g),
                       api_errors=sum(int(r["api_error"]) for r in g),
                       max_straightlining_pct=round(100 * max(float(r["straightline_rate"]) for r in sl
                                                              if r["arm"] == arm and r["language"] == lang), 1))
            if arm == "Fullscale":
                cg = [r for r in comp if r["language"] == lang]
                row["fullscale_calls_all40_valid"] = f'{sum(int(r["all_40_valid"]) for r in cg)}/{sum(int(r["calls"]) for r in cg)}'
                row["fullscale_whole_call_refusals_gpt_oss"] = [r for r in cg if r["model"] == "GPT-OSS-120B"][0]["whole_call_refusal"]
                row["fullscale_truncated_calls"] = sum(int(r["truncated_calls"]) for r in trunc if r["language"] == lang)
            else:
                row["fullscale_calls_all40_valid"] = row["fullscale_whole_call_refusals_gpt_oss"] = row["fullscale_truncated_calls"] = ""
            E.append(row)
    write("supp_table11_partE_validity.csv", E)


if __name__ == "__main__":
    main()

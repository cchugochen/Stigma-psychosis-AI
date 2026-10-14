#!/usr/bin/env python3
"""Build the public data release in data_public/ (Reviewer 2, Comment 10; corresponding author, 2026-10-07).

Sources (dataset of record and sensitivity analyses) -> data_public/:
  analysis_14models_20260614/{en,zh}/results_14models_{lang}.csv  -> item_level_responses_14models_{lang}.csv
  analysis_14models_20260614/{en,zh}/run_level_scale_scores.csv   -> run_level_scale_scores_14models_{lang}.csv
  outputs/figures_tables/eTable6_pairwise_full.csv (written by build_etables_0622.py)
                                                                  -> supplementary_data_1_pairwise_14models.csv
  results_20260930_4models/{Original_oct,Humanlike,Fullscale}.csv -> sensitivity_analyses/elicitation_4models_*.csv
  analysis_14models_20260614/robust_temperature/raw_collection/results_0508_tempsens_t1p0.csv
                                                                  -> sensitivity_analyses/temperature_claude_sonnet_4_5_t1p0.csv
Instrument wording is not redistributed: the item_text column is dropped (item_id, item_domain and is_reverse are
kept); where a model quoted vignette or item wording back in its response, the quoted wording is replaced by
"[instrument text removed]"; and every public cell is then checked against the verbatim vignette and item text
(vignettes.json, items.json).
Model names are those of the article (scripts_public/Models_name.md; 2026-10-12, replacing the former model_display
column): the merged files keep the collection names (e.g. "Gemini 2.5 Flash"), and data_public/ gives "Gemini-2.5-Flash",
the names analyze_stage1.R expects. Values are otherwise unchanged. The 13-model pairwise file (eTable6_pairwise_full.csv)
is replaced.
Writes data_public/MANIFEST.csv (rows, columns, SHA-256). Nothing is committed or pushed.

Usage: python scripts_public/export_public_data_1007.py
"""
import csv
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AN = REPO / "analysis_14models_20260614"
OUT = REPO / "data_public"
SENS = OUT / "sensitivity_analyses"
DISPLAY = {"GPT-5.4 Mini": "GPT-5.4-Mini", "Gemini 2.5 Flash": "Gemini-2.5-Flash",
           "Gemini 3.1 Pro Preview": "Gemini-3.1-Pro-Preview", "Gemini 3.1 Flash-Lite Preview": "Gemini-3.1-Flash-Lite-Preview",
           "Gemini 3.5 Flash": "Gemini-3.5-Flash", "Gemma 4 31B IT": "Gemma-4-31B-IT", "Llama 3.3 70B": "Llama-3.3-70B",
           "DeepSeek V3.2": "DeepSeek-V3.2"}
ARM = {"Original_oct": "original_prompt_october", "Humanlike": "role_play_instruction", "Fullscale": "full_scale_administration"}


def instrument_strings():
    v = json.loads((REPO / "vignettes.json").read_text(encoding="utf-8"))
    it = json.loads((REPO / "items.json").read_text(encoding="utf-8"))
    out = []
    for k, x in v.items():
        if k.startswith("_"):
            continue
        out += [x.get("text_en", ""), x.get("text_zh", "")]
    for key in ("social_distance_items", "prejudice_items"):
        for x in it[key]:
            if not any(k.startswith("_") for k in x):
                out += [x["en"], x["zh"]]
    # sentence-level fragments of the vignettes as well (a response could quote one sentence)
    frags = []
    for s in out:
        for part in s.replace("。", ".").split("."):
            if len(part.strip()) >= 25:
                frags.append(part.strip())
    return [s for s in out if len(s) >= 25] + frags


REDACT = "[instrument text removed]"
REDACTED = []


def export(src, dst, drop=("item_text",), article_names=True, needles=()):
    with open(src, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    cols = [c for c in rows[0].keys() if c not in drop]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            if article_names and "model" in r:
                r["model"] = DISPLAY.get(r["model"], r["model"])
            raw = r.get("raw_response") or ""
            for s in sorted(needles, key=len, reverse=True):  # wording a model quoted back in its response
                if s in raw:
                    raw = raw.replace(s, REDACT)
            if raw != (r.get("raw_response") or ""):
                REDACTED.append((dst.name, r.get("model"), r.get("vignette"), r.get("item_id")))
                r["raw_response"] = raw
            w.writerow(r)
    return len(rows), cols


def main():
    plan = []
    for lang in ("en", "zh"):
        plan.append((AN / lang / f"results_14models_{lang}.csv", OUT / f"item_level_responses_14models_{lang}.csv", True))
        plan.append((AN / lang / "run_level_scale_scores.csv", OUT / f"run_level_scale_scores_14models_{lang}.csv", True))
    plan.append((REPO / "outputs" / "figures_tables" / "eTable6_pairwise_full.csv",
                 OUT / "supplementary_data_1_pairwise_14models.csv", False))
    for arm, name in ARM.items():
        plan.append((REPO / "results_20260930_4models" / f"{arm}.csv", SENS / f"elicitation_4models_{name}.csv", True))
    plan.append((AN / "robust_temperature" / "raw_collection" / "results_0508_tempsens_t1p0.csv",
                 SENS / "temperature_claude_sonnet_4_5_t1p0.csv", True))

    expected = {"item_level_responses_14models_en.csv": 67200, "item_level_responses_14models_zh.csv": 67200,
                "run_level_scale_scores_14models_en.csv": 3360, "run_level_scale_scores_14models_zh.csv": 3360,
                "supplementary_data_1_pairwise_14models.csv": 1456,
                "elicitation_4models_original_prompt_october.csv": 12800,
                "elicitation_4models_role_play_instruction.csv": 38400,
                "elicitation_4models_full_scale_administration.csv": 38400,
                "temperature_claude_sonnet_4_5_t1p0.csv": 3200}
    manifest = []
    needles = instrument_strings()
    for src, dst, disp in plan:
        n, cols = export(src, dst, article_names=disp, needles=needles)
        assert n == expected[dst.name], (dst.name, n)
        assert "item_text" not in cols
        manifest.append(dict(file=str(dst.relative_to(REPO)), rows=n, columns=len(cols),
                             sha256=hashlib.sha256(dst.read_bytes()).hexdigest(), source=str(src.relative_to(REPO))))
    old = OUT / "eTable6_pairwise_full.csv"
    if old.exists():
        old.unlink()  # 13-model version, replaced by supplementary_data_1_pairwise_14models.csv
    # verbatim instrument text must not appear anywhere in the public files
    hits = {}
    for m in manifest:
        txt = (REPO / m["file"]).read_text(encoding="utf-8")
        found = [s for s in needles if s in txt]
        if found:
            hits[m["file"]] = found[:3]
    with open(OUT / "MANIFEST.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)
    for m in manifest:
        print(f"{m['file']}: {m['rows']} rows, {m['columns']} columns")
    print("responses in which quoted instrument wording was replaced:", REDACTED)
    print("verbatim instrument text found after redaction:", hits if hits else "none")
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main())

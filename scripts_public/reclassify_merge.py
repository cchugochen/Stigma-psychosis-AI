#!/usr/bin/env python3
"""
Rebuild analysis_13models_20260419 merged CSVs with corrected response classifications.

Applies:
  - Bug 5 fix: smart-quote normalization in classify_response()
  - Bug 6 note: Claude Sonnet 4.5 EN truncated responses now uniformly -> unparseable
  - Fix 7: GPT-3.5 ZH SD12×PLE context refusal patterns
  - Fix 8: digit-before-TRUNCATED parseable as valid
  - Deduplication for GPT-OSS-120B ZH (two background processes wrote same CSV)

13 models (v0419 protocol, Qwen3.5 35B removed due to Novita billing issues):
  GPT-3.5, GPT-4o, GPT-OSS-120B, GPT-5.4, GPT-5.4 Mini,
  Claude Sonnet 4.5, Claude Opus 4.6,
  Gemini 2.5 Flash, Gemini 3.1 Pro Preview, Gemini 3.1 Flash-Lite Preview, Gemma 4 31B IT,
  Llama 3.3 70B, DeepSeek V3.2

Sources (in merge order):
  EN:
    5 models:       analysis_5models_20260401/en/results_5models_en.csv
    GPT-OSS-120B:   results_20260410_gpt_oss_120b_novita/results_en.csv
    DeepSeek:       results_20260410_deepseek_novita/results_en.csv
    Gemma:          results_20260411_gemma_novita/results_en.csv
    GPT-4o:         results_20260417_gpt4o/results_0417_en.csv
    GPT-3.5:        results_20260417_gpt35/results_en.csv
    Gemini 3.1 Pro Preview: results_20260417_gemini_pro/results_en.csv
    Llama 3.3 70B:  results_20260417_llama/results_en.csv
    Gemini 2.5 Flash: results_20260417_gemini_flash/results_en.csv
  ZH:
    5 models:       analysis_5models_20260401/zh/results_5models_zh.csv
    GPT-OSS-120B:   results_20260410_gpt_oss_120b_novita/results_zh.csv  (deduplicate)
    DeepSeek:       results_20260410_deepseek_novita/results_zh.csv
    Gemma:          results_20260411_gemma_novita/results_zh.csv
    GPT-4o:         results_20260417_gpt4o/results_0417_zh.csv
    GPT-3.5:        results_20260417_gpt35/results_zh.csv
    Gemini 3.1 Pro Preview: results_20260417_gemini_pro/results_zh.csv
    Llama 3.3 70B:  results_20260417_llama/results_zh.csv
    Gemini 2.5 Flash: results_20260417_gemini_flash/results_zh.csv
"""
import sys, csv
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from run_stigma_study import (
    classify_response, parse_response, score_item,
    SOCIAL_DISTANCE_ITEMS, PREJUDICE_ITEMS, HIGH_SENSITIVITY_ITEMS,
    _CSV_FIELDNAMES,
)

item_lookup = {it["id"]: it for it in SOCIAL_DISTANCE_ITEMS + PREJUDICE_ITEMS}

SOURCES = {
    "en": [
        "analysis_5models_20260401/en/results_5models_en.csv",
        "results_20260410_gpt_oss_120b_novita/results_en.csv",
        "results_20260410_deepseek_novita/results_en.csv",
        "results_20260411_gemma_novita/results_en.csv",
        "results_20260417_gpt4o/results_0417_en.csv",
        "results_20260417_gpt35/results_en.csv",
        "results_20260417_gemini_pro/results_en.csv",
        "results_20260417_llama/results_en.csv",
        "results_20260417_gemini_flash/results_en.csv",
    ],
    "zh": [
        "analysis_5models_20260401/zh/results_5models_zh.csv",
        "results_20260410_gpt_oss_120b_novita/results_zh.csv",
        "results_20260410_deepseek_novita/results_zh.csv",
        "results_20260411_gemma_novita/results_zh.csv",
        "results_20260417_gpt4o/results_0417_zh.csv",
        "results_20260417_gpt35/results_zh.csv",
        "results_20260417_gemini_pro/results_zh.csv",
        "results_20260417_llama/results_zh.csv",
        "results_20260417_gemini_flash/results_zh.csv",
    ],
}

OUT_DIR = Path("analysis_13models_20260419")
OUT_FILES = {
    "en": OUT_DIR / "en" / "results_13models_en.csv",
    "zh": OUT_DIR / "zh" / "results_13models_zh.csv",
}


def reclassify_row(row):
    """Re-run classification + scoring on raw_response using fixed classify_response()."""
    raw = row["raw_response"]
    rt = classify_response(raw)
    parsed = scored = None
    if rt in ("valid", "hedged"):
        parsed = parse_response(raw)
        if parsed is not None:
            item = item_lookup.get(row["item_id"])
            if item:
                scale_type = row["scale_type"]
                scored = score_item(parsed, item["reverse"], scale_type)
    row["response_type"] = rt
    row["parsed_value"]  = "" if parsed is None else parsed
    row["scored_value"]  = "" if scored is None else scored
    return row


def load_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dedup_rows(rows, key_fields):
    """Keep newest timestamp per composite key."""
    best = {}
    for r in rows:
        k = tuple(r.get(f, "") for f in key_fields)
        if k not in best or r.get("timestamp", "") > best[k].get("timestamp", ""):
            best[k] = r
    return list(best.values())


DEDUP_KEY = ("model_id", "run", "vignette", "scale_type", "item_id")


def merge_language(lang):
    sources = SOURCES[lang]
    all_rows = []
    for src in sources:
        p = Path(src)
        if not p.exists():
            print(f"  WARNING: missing {src}, skipping")
            continue
        rows = load_csv(p)
        print(f"  {lang} {p.name}: {len(rows)} rows, models: "
              f"{sorted({r['model'] for r in rows})}")
        all_rows.extend(rows)

    before = len(all_rows)
    all_rows = dedup_rows(all_rows, DEDUP_KEY)
    if len(all_rows) < before:
        print(f"  Deduplication: {before} -> {len(all_rows)} rows (removed {before - len(all_rows)} dupes)")

    # Reclassify every row
    old_types = defaultdict(int)
    new_types = defaultdict(int)
    changed = 0
    for row in all_rows:
        old_rt = row["response_type"]
        reclassify_row(row)
        new_rt = row["response_type"]
        old_types[old_rt] += 1
        new_types[new_rt] += 1
        if old_rt != new_rt:
            changed += 1

    print(f"  Reclassification: {changed} rows changed")
    print(f"  Old types: {dict(sorted(old_types.items()))}")
    print(f"  New types: {dict(sorted(new_types.items()))}")

    # Sort
    vig_order = {"PLE": 0, "DEP": 1, "APS": 2, "SCZ": 3}
    all_rows.sort(key=lambda r: (
        r["model"],
        int(r["run"]) if r["run"].isdigit() else 0,
        vig_order.get(r["vignette"], 9),
        r["scale_type"],
        r["item_id"],
    ))

    out_path = OUT_FILES[lang]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)

    models = sorted({r["model"] for r in all_rows})
    print(f"  Wrote {len(all_rows)} rows to {out_path}")
    print(f"  Models ({len(models)}): {models}")
    return all_rows


def main():
    for lang in ("en", "zh"):
        print(f"\n{'='*60}")
        print(f" Building {lang.upper()} merged file")
        print(f"{'='*60}")
        rows = merge_language(lang)

        # Per-model summary
        by_model = defaultdict(list)
        for r in rows:
            by_model[r["model"]].append(r)
        print(f"\n  Per-model row counts and response types:")
        for m in sorted(by_model):
            rs = by_model[m]
            valid = sum(1 for r in rs if r["response_type"] == "valid")
            hedged = sum(1 for r in rs if r["response_type"] == "hedged")
            ref = sum(1 for r in rs if "refusal" in r["response_type"])
            unp = sum(1 for r in rs if r["response_type"] == "unparseable")
            saf = sum(1 for r in rs if r["response_type"] == "safety")
            print(f"    {m:<30} n={len(rs):5d}  valid={valid}  hedged={hedged}  "
                  f"refusal={ref}  unparseable={unp}  safety={saf}")

    print("\nDone.")


if __name__ == "__main__":
    main()

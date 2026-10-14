#!/usr/bin/env python3
"""Build per-arm merged CSVs for the 4-model elicitation sensitivity study.

Output: analysis_sen_20260930/<arm>/<lang>/results_4models_<arm>_<lang>.csv  (one file per
language folder, as analyze_stage1.R expects), plus audit listings.

Arms
  Humanlike, Original_oct, Fullscale   from results_20260930_4models/<arm>/<model>/<lang>/
                                     (also written combined as results_20260930_4models/<arm>.csv)
  Original_pub                       published 14-model data, 4-model subset
                                     ("Gemini 3.5 Flash" renamed "Gemini-3.5-Flash" to match the R script)
  Humanlike_rescored, Original_oct_rescored
                                     pre-specified sensitivity: non-valid replies containing exactly one
                                     distinct digit 1-4 are re-scored as valid (applied AFTER reclassification)

Every arm goes through the same locked classifier, the original dedup key and the original sort order
(merge_14models_20260614.py).
"""
import argparse, csv, json, random, re, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts_public"))
from merge_14models_20260614 import reclassify_row, dedup_rows, DEDUP_KEY, item_lookup  # noqa: E402
from run_stigma_study import score_item, _CSV_FIELDNAMES  # noqa: E402

RAW = REPO / "results_20260930_4models"
OUT = REPO / "analysis_sen_20260930"
PUB = REPO / "analysis_14models_20260614"
MODEL_IDS = {"claude-sonnet-4-5-20250929", "gpt-5.4", "gemini-3.5-flash", "openai/gpt-oss-120b"}
RENAME = {"Gemini 3.5 Flash": "Gemini-3.5-Flash"}
VIG_ORDER = {"PLE": 0, "DEP": 1, "APS": 2, "SCZ": 3}
NONVALID = {"refusal", "refusal_identity", "refusal_ethical", "unparseable"}
DIGIT_RE = re.compile(r"(?<![0-9])([1-4])(?![0-9])")


def load(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sort_key(r):
    return (r["model"], int(r["run"]) if str(r["run"]).isdigit() else 0,
            VIG_ORDER.get(r["vignette"], 9), r["scale_type"], r["item_id"])


def finish(rows):
    rows = dedup_rows(rows, DEDUP_KEY)
    for r in rows:
        r["model"] = RENAME.get(r["model"], r["model"])
        reclassify_row(r)
    rows.sort(key=sort_key)
    return rows


def rescore(rows):
    """Pre-specified caveat re-scoring. Returns (rows, n_changed)."""
    n = 0
    for r in rows:
        raw = r.get("raw_response") or ""
        if r["response_type"] not in NONVALID or raw.startswith("[API_ERROR]") or raw.startswith("[SAFETY_BLOCK"):
            continue
        digits = set(DIGIT_RE.findall(raw))
        if len(digits) != 1:
            continue
        d = int(digits.pop())
        item = item_lookup[r["item_id"]]
        r["response_type"] = "valid"
        r["parsed_value"] = d
        r["scored_value"] = score_item(d, item["reverse"], r["scale_type"])
        n += 1
    assert all(r["scored_value"] not in ("", None) for r in rows if r["response_type"] == "valid")
    return rows, n


def write(arm, lang, rows):
    p = OUT / arm / lang / f"results_4models_{arm}_{lang}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    for old in p.parent.glob("results_*.csv"):   # exactly one results_* per folder for R
        if old != p:
            old.unlink()
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    return p


def collected(arm, lang, raw_root):
    rows = []
    for p in sorted((raw_root / arm).glob(f"*/{lang}/results_{arm}_{lang}.csv")):
        rows += load(p)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="merge _smoke/ into analysis_sen_20260930/_smoke/")
    a = ap.parse_args()
    global OUT
    raw_root = RAW / "_smoke" if a.smoke else RAW
    OUT = OUT / "_smoke" if a.smoke else OUT
    summary = {}
    audit_dir = OUT / "audit"; audit_dir.mkdir(parents=True, exist_ok=True)
    combined = {"Humanlike": [], "Original_oct": [], "Fullscale": []}
    for lang in ("en", "zh"):
        arms = {arm: finish(collected(arm, lang, raw_root)) for arm in ("Humanlike", "Original_oct", "Fullscale")}
        for arm in combined:
            combined[arm] += arms[arm]
        if not a.smoke:
            pub = [r for r in load(PUB / lang / f"results_14models_{lang}.csv") if r["model_id"] in MODEL_IDS]
            arms["Original_pub"] = finish(pub)
        for base in ("Humanlike", "Original_oct"):
            rows, n = rescore([dict(r) for r in arms[base]])
            arms[f"{base}_rescored"] = rows
            summary[f"{base}_rescored_{lang}_n_changed"] = n
        for arm, rows in arms.items():
            if not rows:
                continue
            write(arm, lang, rows)
            summary[f"{arm}_{lang}"] = {"rows": len(rows), "types": dict(Counter(r["response_type"] for r in rows)),
                                        "models": sorted({r["model"] for r in rows})}
            if not arm.endswith("_rescored") and arm != "Original_pub":
                nv = [r for r in rows if r["response_type"] != "valid" or not re.fullmatch(r"\s*[1-4]\.?\s*", r["raw_response"] or "")]
                with open(audit_dir / f"nonvalid_or_extra_text_{arm}_{lang}.csv", "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=["model", "run", "vignette", "scale_type", "item_id",
                                                      "response_type", "parsed_value", "raw_response"], extrasaction="ignore")
                    w.writeheader(); w.writerows(nv)
    # One CSV per collected arm (4 models, EN + ZH), in results_20260930_4models/: the exact rows the analysis uses.
    for arm, rows in combined.items():
        if not rows:
            continue
        p_out = raw_root / f"{arm}.csv"
        with open(p_out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)
        summary[f"{arm}_combined_csv"] = {"path": str(p_out.relative_to(REPO)), "rows": len(rows)}
    # F7 parser audit sample: stratified 40 full-scale calls (5 per model x language)
    calls = []
    for p in sorted(raw_root.glob("Fullscale_calls_*.jsonl")):
        calls += [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    rng = random.Random("20260930-audit"); sample = []
    for key in sorted({(c["model_key"], c["lang"]) for c in calls}):
        pool = [c for c in calls if (c["model_key"], c["lang"]) == key]
        sample += rng.sample(pool, min(5, len(pool)))
    with open(audit_dir / "Fullscale_parser_sample.jsonl", "w", encoding="utf-8") as f:
        for c in sample:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    # Human-review form: one row per item; reviewer fills reviewer_agrees (Y/N) and note.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import fullscale_lib as fs
    from run_stigma_study import classify_response, parse_response, SOCIAL_DISTANCE_ITEMS, PREJUDICE_ITEMS
    ids = [i["id"] for i in SOCIAL_DISTANCE_ITEMS + PREJUDICE_ITEMS]
    with open(audit_dir / "Fullscale_parser_audit_form.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["call_no", "model_key", "lang", "run", "vignette", "item_id", "fragment_given_to_classifier",
                    "response_type", "parsed_value", "full_reply", "reviewer_agrees", "reviewer_note"])
        for n, cl in enumerate(sample, 1):
            frags, _ = fs.split_fullscale_reply(cl["raw_response"], ids)
            for k, iid in enumerate(ids):
                fr = frags[iid]; rt = classify_response(fr)
                w.writerow([n, cl["model_key"], cl["lang"], cl["run"], cl["vignette"], iid, fr, rt,
                            parse_response(fr) if rt in ("valid", "hedged") else "",
                            cl["raw_response"] if k == 0 else "", "", ""])
    summary["Fullscale_parser_sample_n"] = len(sample)
    (OUT / "merge_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

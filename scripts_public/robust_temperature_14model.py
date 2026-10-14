#!/usr/bin/env python3
"""Temperature-sensitivity comparison on the 14-model dataset of record (Reviewer 1, Comment 11).

Wraps robust_temperature.py (functions unchanged) with three fixes needed for the 14-model data:
  1. Primary input = analysis_14models_20260614/{en,zh}/results_14models_{lang}.csv.
     That file names the small GPT-5.4 model "GPT-5.4 Mini"; robust_temperature.py expects
     "GPT-5.4-Mini" (13-model naming), so the name is mapped before scoring. Without this the
     model would be dropped and its effective temperature (1.0) not applied.
  2. The Claude Sonnet 4.5 T = 1.0 responses (collected 2026-05-08) are re-classified with the
     same locked classifier that produced the 14-model dataset (merge_14models_20260614.reclassify_row),
     so that every reported analysis uses the rule set finalized on 20 April 2026. The number of
     rows whose classification changes is logged.
  3. Outputs go to analysis_14models_20260614/robust_temperature/. The files previously there were a
     byte-identical copy of the 13-model run and are kept in _pre1007_copy_from_13model/.

Usage: python scripts_public/robust_temperature_14model.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import robust_temperature as rt  # noqa: E402
from merge_14models_20260614 import reclassify_row  # noqa: E402

AN = REPO / "analysis_14models_20260614"
OUT = AN / "robust_temperature"
T1_CSV = OUT / "raw_collection" / "results_0508_tempsens_t1p0.csv"
NAME_MAP = {"GPT-5.4 Mini": "GPT-5.4-Mini"}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    backup = OUT / "_pre1007_copy_from_13model"
    if not backup.exists():
        backup.mkdir()
        for f in OUT.glob("*.csv"):
            shutil.copy2(f, backup / f.name)

    rows_t1 = rt.load_rows(T1_CSV)
    changed = 0
    for r in rows_t1:
        before = (r["response_type"], str(r["parsed_value"]), str(r["scored_value"]))
        reclassify_row(r)
        r["parsed_value"], r["scored_value"] = str(r["parsed_value"]), str(r["scored_value"])
        after = (r["response_type"], r["parsed_value"], r["scored_value"])
        changed += before != after
    print(f"T=1.0 rows: {len(rows_t1)}; re-classification changed {changed} rows")

    rows_primary = []
    for lang in ("en", "zh"):
        for r in rt.load_rows(AN / lang / f"results_14models_{lang}.csv"):
            r["model"] = NAME_MAP.get(r["model"], r["model"])
            if r["model"] in rt.T1_TARGET_MODELS:
                rows_primary.append(r)
    print(f"Primary rows for {rt.T1_TARGET_MODELS}: {len(rows_primary)}")

    scores = rt.prorated_scale_scores(rows_t1 + rows_primary)
    rt.write_csv(scores, OUT / "run_level_scale_scores.csv")
    rt.write_csv(rt.cell_summary(scores), OUT / "cell_summary.csv")
    rt.write_csv(rt.within_model_temperature(scores), OUT / "within_model_temperature_effect.csv")
    rt.write_csv(rt.cross_model_t1p0(scores), OUT / "cross_model_t1p0_comparison.csv")

    log = dict(run_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               script="scripts_public/robust_temperature_14model.py",
               script_sha256=sha256(Path(__file__)), wrapped=sha256(HERE / "robust_temperature.py"),
               t1p0_rows=len(rows_t1), t1p0_rows_reclassification_changed=changed,
               inputs={str(p.relative_to(REPO)): sha256(p) for p in
                       [T1_CSV, AN / "en/results_14models_en.csv", AN / "zh/results_14models_zh.csv"]})
    (OUT / "run_log_1007.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

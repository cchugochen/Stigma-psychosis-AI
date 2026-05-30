#!/usr/bin/env python3
"""
robust_refusal.py — Refusal-imputation sensitivity analysis (Section 2.5).

The primary analysis drops items where the model itself refused to answer
(response_type in {refusal, refusal_ethical, refusal_identity}) before
computing prorated scale scores under a >=80% completeness filter. This
risks under-estimating the stigma scores of safety-tuned models if their
refusals are systematically concentrated on the most stigma-laden items
(e.g., GPT-OSS-120B on parenting / marriage / dangerousness items).

This script produces three imputed copies of the merged dataset:

    S1_lowest    refusals -> scored_value = 1   (least-stigma; analytically
                                                  most permissive scenario
                                                  for safety-tuned models)
    S2_midpoint  refusals -> scored_value = 2.5 (scale midpoint)
    S3_highest   refusals -> scored_value = 4   (worst-case bound)

Plus the unmodified primary (S0_complete_case). For each scenario, the
script writes a self-contained analysis directory and (optionally) re-
runs scripts_public/analyze_stage1.R + item_level_profile.R so the
sensitivity comparison reproduces every Table and Figure of the main
analysis under that imputation rule.

Infrastructure-level missingness (HTTP 4xx/5xx, DNS errors, max_tokens
truncation, and provider-side `safety` blocks) is preserved as NA in
every scenario; we treat those as missing data rather than refusals.

Usage:
  python3 scripts_public/robust_refusal.py \
      --source analysis_13models_20260419/ \
      --output analysis_13models_20260508/robust_refusal/

  # Skip the R re-run (just produce the imputed CSVs):
  python3 scripts_public/robust_refusal.py \
      --source analysis_13models_20260419/ \
      --output analysis_13models_20260508/robust_refusal/ \
      --no-r
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

# Response-type categories that count as model-level refusal (i.e., the model
# CHOSE not to answer). Other empty scored_value rows (unparseable, safety,
# infrastructure errors) are treated as missing in every scenario.
REFUSAL_TYPES: set[str] = {
    "refusal",
    "refusal_ethical",
    "refusal_identity",
}

# Imputation scenarios. S0 is the unmodified primary (refusals stay NA).
SCENARIOS: dict[str, float | None] = {
    "S0_complete_case": None,
    "S1_lowest":        1.0,
    "S2_midpoint":      2.5,
    "S3_highest":       4.0,
}


def impute_csv(src_path: Path, dst_path: Path, fill_value: float | None) -> dict:
    """Copy src_path → dst_path, replacing scored_value for refusal rows.

    fill_value=None preserves the original (S0_complete_case).
    """
    n_total = 0
    n_refusal_rows = 0
    n_imputed = 0
    n_other_na = 0

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with src_path.open(newline="", encoding="utf-8") as fin, \
         dst_path.open("w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            n_total += 1
            scored = row["scored_value"].strip()
            rtype = row["response_type"]
            if not scored:
                if rtype in REFUSAL_TYPES:
                    n_refusal_rows += 1
                    if fill_value is not None:
                        # Score in the "higher = more stigma" direction
                        # (the column is already direction-corrected upstream
                        # via score_item() in run_stigma_study.py, so reverse
                        # items are accounted for).
                        row["scored_value"] = (
                            f"{int(fill_value)}"
                            if fill_value.is_integer()
                            else f"{fill_value}"
                        )
                        n_imputed += 1
                else:
                    n_other_na += 1
            writer.writerow(row)

    return dict(
        n_total=n_total,
        n_refusal_rows=n_refusal_rows,
        n_imputed=n_imputed,
        n_other_na=n_other_na,
    )


def run_r_pipeline(scenario_dir: Path, repo_root: Path) -> tuple[bool, str]:
    """Call analyze_stage1.R + item_level_profile.R on the imputed dir."""
    log_lines: list[str] = []
    for script_name in ("analyze_stage1.R", "item_level_profile.R"):
        script_path = repo_root / "scripts_public" / script_name
        cmd = ["Rscript", str(script_path), str(scenario_dir) + "/"]
        log_lines.append(f"\n$ {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=900
            )
        except subprocess.TimeoutExpired:
            log_lines.append("  -> TIMEOUT (>15 min)")
            return False, "\n".join(log_lines)
        log_lines.append(proc.stdout[-1500:] if proc.stdout else "")
        if proc.returncode != 0:
            log_lines.append(f"  STDERR:\n{proc.stderr[-2000:]}")
            return False, "\n".join(log_lines)
    return True, "\n".join(log_lines)


def collate_summary(output_dir: Path) -> Path:
    """Collate the per-scenario tableS2_descriptive_stats.csv into one file."""
    rows: list[dict] = []
    for scenario in SCENARIOS:
        for lang in ("en", "zh"):
            desc = output_dir / scenario / lang / "tableS2_descriptive_stats.csv"
            if not desc.is_file():
                continue
            with desc.open(newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    r["scenario"] = scenario
                    r["language"] = lang
                    rows.append(r)
    if not rows:
        return output_dir / "sensitivity_summary.csv"

    # Reorder columns: scenario + language first, then everything else.
    base_cols = ["scenario", "language"]
    other_cols = [c for c in rows[0].keys() if c not in base_cols]
    out_path = output_dir / "sensitivity_summary.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=base_cols + other_cols)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default="analysis_13models_20260419/",
                   help="Source analysis directory containing en/, zh/.")
    p.add_argument("--output", default="analysis_13models_20260508/robust_refusal/",
                   help="Output directory for the four imputed scenarios.")
    p.add_argument("--no-r", action="store_true",
                   help="Skip analyze_stage1.R / item_level_profile.R re-run.")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    src_dir = (repo_root / args.source).resolve()
    out_dir = (repo_root / args.output).resolve()

    en_src = src_dir / "en" / "results_13models_en.csv"
    zh_src = src_dir / "zh" / "results_13models_zh.csv"
    for path in (en_src, zh_src):
        if not path.is_file():
            print(f"ERROR: missing source file {path}", file=sys.stderr)
            return 1

    print(f"Source: {src_dir}")
    print(f"Output: {out_dir}")
    print()

    # 1. Build per-scenario imputed CSVs.
    audit_rows: list[dict] = []
    for scenario, fill in SCENARIOS.items():
        s_dir = out_dir / scenario
        for lang_csv, lang in ((en_src, "en"), (zh_src, "zh")):
            dst = s_dir / lang / lang_csv.name
            stats = impute_csv(lang_csv, dst, fill)
            audit_rows.append(dict(
                scenario=scenario,
                language=lang,
                fill_value="" if fill is None else f"{fill}",
                **stats,
            ))
            print(f"  [{scenario}/{lang}] rows={stats['n_total']:6d}  "
                  f"refusals={stats['n_refusal_rows']:4d}  "
                  f"imputed={stats['n_imputed']:4d}  "
                  f"other_NA={stats['n_other_na']:4d}")

    # 2. Write imputation audit log.
    audit_path = out_dir / "imputation_audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as f:
        cols = ["scenario", "language", "fill_value",
                "n_total", "n_refusal_rows", "n_imputed", "n_other_na"]
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(audit_rows)
    print(f"\nWrote: {audit_path}")

    # 3. Optionally re-run the R analysis pipeline per scenario.
    if not args.no_r:
        print("\nRunning R analysis pipeline per scenario...")
        for scenario in SCENARIOS:
            s_dir = out_dir / scenario
            print(f"\n=== {scenario} ===")
            ok, log = run_r_pipeline(s_dir, repo_root)
            log_path = s_dir / "_pipeline.log"
            log_path.write_text(log, encoding="utf-8")
            print(f"  log -> {log_path}")
            if not ok:
                print(f"  WARNING: pipeline failed for {scenario}; "
                      f"continuing with remaining scenarios.")

        # 4. Collate the sensitivity summary.
        summary = collate_summary(out_dir)
        if summary.is_file():
            print(f"\nWrote: {summary}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

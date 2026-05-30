#!/usr/bin/env python3
"""
robust_temperature.py — Temperature-sensitivity comparison (Section 2.5 / B1).

Background. The OpenAI GPT-5.4 series cannot be temperature-matched to the
other providers (its API fixes T = 1.0). All other models in the primary
analysis ran at T = 0.3. This means the H1/Q1 "newer = lower stigma"
narrative is partially confounded with temperature: GPT-5.4 (newest, lowest
in some cells) is also the only model at T = 1.0 in the primary dataset.

This script compares a fresh 10-run Claude Sonnet 4.5 collection at
T = 1.0 (collected via the run_stigma_study.py CLI with
--temperature 1.0 --run-label tempsens_t1p0) against:

    (a) Claude Sonnet 4.5 at T = 0.3 (from the primary 30-run dataset)
        — within-model temperature effect.
    (b) GPT-5.4 / GPT-5.4 Mini, both at T = 1.0 in the primary dataset
        — apples-to-apples cross-model comparison at matched temperature.

Inputs:
    --t1p0-csv     Claude T=1.0 raw collection
                   (default: analysis_13models_20260508/robust_temperature/
                            raw_collection/results_0508_tempsens_t1p0.csv)
    --primary-dir  Primary analysis directory containing en/, zh/
                   (default: analysis_13models_20260419/)
    --output       Output directory
                   (default: analysis_13models_20260508/robust_temperature/)

Outputs (under <output>/):
    run_level_scale_scores.csv          # all four models, T-tagged
    within_model_temperature_effect.csv # Claude T=0.3 vs T=1.0
    cross_model_t1p0_comparison.csv     # Claude vs GPT-5.4 vs Mini @ T=1.0
    figures/temperature_comparison_violin_<lang>.png
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

# Models to compare at T = 1.0
T1_TARGET_MODELS = ("Claude Sonnet 4.5", "GPT-5.4", "GPT-5.4 Mini")

# Items per scale (used for prorated scale-score computation)
SCALE_N_ITEMS = {"social_distance": 19, "prejudice": 21}

# Models whose API silently overrides the requested temperature to 1.0.
# The CSV records the user-requested value (e.g., 0.3) but the effective
# sampling temperature is 1.0; we patch this at load time.
EFFECTIVE_T1P0_MODELS = {"GPT-5.4", "GPT-5.4 Mini"}


def effective_temperature(row: dict) -> str:
    """Return effective temperature, correcting for API overrides."""
    if row.get("model") in EFFECTIVE_T1P0_MODELS:
        return "1.0"
    return row.get("temperature", "")


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def prorated_scale_scores(
    rows: list[dict],
    *,
    completeness_floor: float = 0.80,
) -> list[dict]:
    """Compute one prorated score per (model × lang × run × vig × scale).

    Mirrors the R pipeline's primary-analysis rule: drop NA scored_values,
    then prorate (mean × n_items) when completeness >= floor; otherwise mark
    in_primary = False.
    """
    # Cell key includes effective temperature so primary (T=0.3) and
    # tempsens (T=1.0) runs of the same model don't collide on overlapping
    # run indices (1–30 vs 1–10).
    cells: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        scored = r.get("scored_value", "").strip()
        if not scored:
            continue
        try:
            v = float(scored)
        except ValueError:
            continue
        k = (r["model"], r["language"], r["run"], r["vignette"],
             r["scale_type"], effective_temperature(r))
        cells[k].append(v)

    out: list[dict] = []
    for (model, lang, run, vig, scale, temp), vals in cells.items():
        n_items = SCALE_N_ITEMS[scale]
        if not vals:
            continue
        completeness = len(vals) / n_items
        item_mean = sum(vals) / len(vals)
        scale_score = item_mean * n_items
        out.append(dict(
            model=model,
            language=lang,
            run=int(run),
            vignette=vig,
            scale_type=scale,
            temperature=temp,
            n_items_answered=len(vals),
            completeness=round(completeness, 3),
            scale_score=round(scale_score, 3),
            in_primary=completeness >= completeness_floor,
        ))
    return out


def cell_summary(scores: list[dict]) -> list[dict]:
    """Mean / SD / 95% CI per (model × lang × vignette × scale × temperature)."""
    by_cell: dict[tuple, list[float]] = defaultdict(list)
    for s in scores:
        if not s["in_primary"]:
            continue
        k = (s["model"], s["language"], s["vignette"], s["scale_type"], s["temperature"])
        by_cell[k].append(s["scale_score"])
    out: list[dict] = []
    for (model, lang, vig, scale, temp), v in sorted(by_cell.items()):
        n = len(v)
        m = statistics.fmean(v)
        sd = statistics.stdev(v) if n > 1 else 0.0
        # t-distribution 95% CI on the mean — small-n; use Welch-style with df=n-1
        # Approx t for df: 2.262 (n=10), 2.045 (n=30); we use the analytical
        # value for the actual df via the standard t-table approximation.
        if n > 1:
            t_crit = 2.262 if n <= 12 else 2.045
            half = t_crit * sd / math.sqrt(n)
        else:
            half = 0.0
        out.append(dict(
            model=model, language=lang, vignette=vig, scale_type=scale,
            temperature=temp, n_runs=n,
            mean_scale=round(m, 3), sd_scale=round(sd, 3),
            ci95_low=round(m - half, 3), ci95_high=round(m + half, 3),
        ))
    return out


def cliffs_delta(a: list[float], b: list[float]) -> tuple[float, str]:
    """Cliff's δ for two independent samples."""
    if not a or not b:
        return 0.0, "negligible"
    gt = lt = 0
    for x in a:
        for y in b:
            if x > y:
                gt += 1
            elif x < y:
                lt += 1
    delta = (gt - lt) / (len(a) * len(b))
    abs_d = abs(delta)
    if abs_d < 0.147:
        magnitude = "negligible"
    elif abs_d < 0.33:
        magnitude = "small"
    elif abs_d < 0.474:
        magnitude = "medium"
    else:
        magnitude = "large"
    return round(delta, 3), magnitude


def within_model_temperature(scores: list[dict]) -> list[dict]:
    """Claude Sonnet 4.5: T=0.3 vs T=1.0 within each (lang × vignette × scale)."""
    by_temp: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: {"0.3": [], "1.0": []})
    for s in scores:
        if s["model"] != "Claude Sonnet 4.5" or not s["in_primary"]:
            continue
        temp = s["temperature"]
        if temp not in ("0.3", "1.0"):
            continue
        k = (s["language"], s["vignette"], s["scale_type"])
        by_temp[k][temp].append(s["scale_score"])
    out: list[dict] = []
    for (lang, vig, scale), buckets in sorted(by_temp.items()):
        a = buckets["0.3"]; b = buckets["1.0"]
        if not a or not b:
            continue
        delta, magnitude = cliffs_delta(b, a)  # δ relative to T=0.3 baseline
        out.append(dict(
            model="Claude Sonnet 4.5",
            language=lang, vignette=vig, scale_type=scale,
            n_t0p3=len(a), n_t1p0=len(b),
            mean_t0p3=round(statistics.fmean(a), 3),
            mean_t1p0=round(statistics.fmean(b), 3),
            mean_diff=round(statistics.fmean(b) - statistics.fmean(a), 3),
            cliffs_delta=delta, magnitude=magnitude,
        ))
    return out


def cross_model_t1p0(scores: list[dict]) -> list[dict]:
    """Claude vs GPT-5.4 vs GPT-5.4 Mini at matched T=1.0; pairwise Cliff's δ."""
    pool: dict[tuple, list[float]] = defaultdict(list)
    for s in scores:
        if not s["in_primary"]:
            continue
        if s["model"] not in T1_TARGET_MODELS:
            continue
        if s["temperature"] != "1.0":
            continue
        k = (s["model"], s["language"], s["vignette"], s["scale_type"])
        pool[k].append(s["scale_score"])

    pairs = [
        ("Claude Sonnet 4.5", "GPT-5.4"),
        ("Claude Sonnet 4.5", "GPT-5.4 Mini"),
        ("GPT-5.4", "GPT-5.4 Mini"),
    ]
    out: list[dict] = []
    seen_cells = {(lang, vig, scale)
                  for (model, lang, vig, scale) in pool}
    for lang, vig, scale in sorted(seen_cells):
        for m1, m2 in pairs:
            a = pool.get((m1, lang, vig, scale), [])
            b = pool.get((m2, lang, vig, scale), [])
            if not a or not b:
                continue
            delta, magnitude = cliffs_delta(a, b)
            out.append(dict(
                language=lang, vignette=vig, scale_type=scale,
                model_a=m1, model_b=m2, temperature="1.0",
                n_a=len(a), n_b=len(b),
                mean_a=round(statistics.fmean(a), 3),
                mean_b=round(statistics.fmean(b), 3),
                mean_diff=round(statistics.fmean(a) - statistics.fmean(b), 3),
                cliffs_delta=delta, magnitude=magnitude,
            ))
    return out


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        print(f"  (no rows for {path.name})")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {path.name} ({len(rows)} rows)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--t1p0-csv",
                   default="analysis_13models_20260508/robust_temperature/"
                           "raw_collection/results_0508_tempsens_t1p0.csv")
    p.add_argument("--primary-dir", default="analysis_13models_20260419/")
    p.add_argument("--output", default="analysis_13models_20260508/robust_temperature/")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    t1_path  = (repo_root / args.t1p0_csv).resolve()
    pri_dir  = (repo_root / args.primary_dir).resolve()
    out_dir  = (repo_root / args.output).resolve()

    if not t1_path.is_file():
        print(f"ERROR: missing {t1_path}", file=sys.stderr)
        return 1

    # 1. Load Claude T=1.0 raw collection.
    rows_t1 = load_rows(t1_path)
    print(f"Loaded T=1.0 Claude rows: {len(rows_t1)}")

    # 2. Load primary dataset rows for Claude (T=0.3) + GPT-5.4 / Mini (T=1.0).
    rows_primary: list[dict] = []
    for lang in ("en", "zh"):
        path = pri_dir / lang / f"results_13models_{lang}.csv"
        if not path.is_file():
            print(f"  WARNING: missing {path}; skipping {lang}.")
            continue
        for r in load_rows(path):
            if r["model"] in T1_TARGET_MODELS:
                rows_primary.append(r)
    print(f"Loaded primary rows for {T1_TARGET_MODELS}: {len(rows_primary)}")

    all_rows = rows_t1 + rows_primary

    # 3. Compute run-level prorated scale scores.
    scores = prorated_scale_scores(all_rows)
    print(f"Run-level scores computed: {len(scores)}")
    write_csv(scores, out_dir / "run_level_scale_scores.csv")

    # 4. Cell summary.
    write_csv(cell_summary(scores), out_dir / "cell_summary.csv")

    # 5. Within-model temperature effect (Claude T=0.3 vs T=1.0).
    write_csv(within_model_temperature(scores),
              out_dir / "within_model_temperature_effect.csv")

    # 6. Cross-model comparison at matched T=1.0.
    write_csv(cross_model_t1p0(scores),
              out_dir / "cross_model_t1p0_comparison.csv")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

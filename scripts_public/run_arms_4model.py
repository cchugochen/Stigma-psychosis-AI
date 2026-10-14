#!/usr/bin/env python3
"""Run the unmodified main-study R pipeline once per arm (pattern of robust_refusal.run_r_pipeline).

  Rscript scripts_public/analyze_stage1.R analysis_sen_20260930/<arm>/

item_level_profile.R is not run: it filters on spaced model names and would drop Gemini-3.5-Flash.
"""
import argparse, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
R_SCRIPT = REPO / "scripts_public" / "analyze_stage1.R"
ARMS = ["Original_pub", "Original_oct", "Humanlike", "Fullscale", "Humanlike_rescored", "Original_oct_rescored"]


def run(arm_dir):
    p = subprocess.run(["Rscript", str(R_SCRIPT), str(arm_dir) + "/"], cwd=REPO,
                       capture_output=True, text=True, timeout=1800)
    (arm_dir / "_pipeline.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr, encoding="utf-8")
    return p.returncode == 0, p.stderr[-1500:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(REPO / "analysis_sen_20260930"))
    ap.add_argument("--arms", nargs="*", default=ARMS)
    a = ap.parse_args()
    root = Path(a.root); failed = []
    for arm in a.arms:
        d = root / arm
        if not (d / "en").is_dir() or not (d / "zh").is_dir():
            print(f"skip {arm}: missing en/ or zh/"); continue
        ok, err = run(d)
        print(f"{arm}: {'OK' if ok else 'FAILED'}")
        if not ok:
            failed.append(arm); print(err)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Export Analysis Results for LLM Chat Interfaces (e.g., ChatGPT, Gemini Pro).

This script consolidates dozens of fragmented statistical CSVs from the
analysis directory into a maximum of 6 cleanly structured CSV files.
It injects 'table_name' and 'language' columns to preserve context, and
generates a '01_Master_Summary.csv' that describes each consolidated file,
its source tables, row counts, and column definitions so an LLM can read
the schema without having to guess.

Raw run-level CSV (results_NNmodels_*.csv, 60k+ rows) is NOT exported —
it is too large for typical LLM context windows and does not add value
for discussion. Only aggregated / inferential outputs are included.

Usage:
  python scripts/export_for_llm.py analysis_13models_20260419/
  python scripts/export_for_llm.py analysis_13models_20260419/ --output LLM_Chat_Export/
"""

import csv
import argparse
import sys
import re
from pathlib import Path
from datetime import datetime

# Grouping: target merged file -> list of source CSV filenames
# Note: "_no_gpt_oss" sensitivity outputs are merged into the same files
# as their primary counterparts (with table_name carrying the distinction).
FILE_GROUPS = {
    "02_Descriptive_Stats.csv": [
        "tableS2_descriptive_stats.csv",
        "tableS10_sensitivity_descriptive.csv",
        "tableS1_missingness.csv",
    ],
    "03_Statistical_Inference.csv": [
        "tableS5_vignette_omnibus.csv",
        "tableS6_vignette_pairwise.csv",
        "tableS7_model_omnibus.csv",
        "tableS11_sensitivity_omnibus.csv",
        "tableS8_model_pairwise.csv",
    ],
    "04_Model_Diagnostics.csv": [
        "tableS3_reliability.csv",
        "tableS4_gradient_check.csv",
        "tableS9_ai_vs_human.csv",
    ],
    "05_Cross_Language.csv": [
        "tableS12_language_descriptives.csv",
        "tableS13_language_comparison.csv",
        "tableS14_language_by_model.csv",
        "tableS15_language_by_vignette.csv",
    ],
    "06_Item_Level_Profile.csv": [
        "Table5_item_stigma_profile.csv",
    ],
}

FILE_DESCRIPTIONS = {
    # TableS1-S11: from analyze_results.R (in en/ or zh/ subfolder)
    "tableS1_missingness.csv":
        "資料完整性檢查：n_primary 為通過 >=80% completeness 門檻的 run 數，供判斷納入 primary analysis 的樣本量。",
    "tableS2_descriptive_stats.csv":
        "各模型 x vignette x scale 的基本描述性統計 (n_runs, mean, sd, median, IQR, item-level mean, completeness)。",
    "tableS3_reliability.csv":
        "Run-level 信度：ICC(2,k) + mean pairwise Spearman rho。reliability_flag 'ok' / 'insufficient_complete_runs' / 'perfect_agreement'。",
    "tableS4_gradient_check.csv":
        "污名梯度 PLE < APS ≈ DEP < SCZ 符合度檢查 (observed_order + matches_human_pattern)。",
    "tableS5_vignette_omnibus.csv":
        "同一模型內四個 vignette (PLE/DEP/APS/SCZ) 的整體差異檢定 (Friedman matched-run test)。",
    "tableS6_vignette_pairwise.csv":
        "同一模型內 vignette 之間的成對比較 (Wilcoxon signed-rank, Holm 調整)。正值 median_difference 代表 vignette_1 > vignette_2。",
    "tableS7_model_omnibus.csv":
        "同一 vignette 內跨模型整體差異檢定 (Kruskal-Wallis)。",
    "tableS8_model_pairwise.csv":
        "同一 vignette 內跨模型成對比較 (Wilcoxon rank-sum + Cliff's delta, Holm 調整)。cliffs_delta 正值代表 model_1 > model_2。",
    "tableS9_ai_vs_human.csv":
        "AI 分數 vs Wang 2020 Taiwan 人類常模之描述性差距 (human_sd_units = (AI_mean - human_mean)/human_sd)。language_match 'matched' / 'instrument_language_mismatch'。",
    "tableS10_sensitivity_descriptive.csv":
        "Sensitivity 版本：排除 GPT-OSS-120B 後重算的描述統計 (檢驗該模型對整體結果的影響)。",
    "tableS11_sensitivity_omnibus.csv":
        "Sensitivity 版本：排除 GPT-OSS-120B 後的跨模型 omnibus 檢定。",
    # TableS12-S15: from compare_language_results.R (at analysis root)
    "tableS12_language_descriptives.csv":
        "跨語言比較：每個 model x vignette x scale cell 在 EN / ZH 的描述統計。",
    "tableS13_language_comparison.csv":
        "跨語言 Cell-level 檢定：ZH vs EN 的 Wilcoxon rank-sum + Cliff's delta + mean_diff_zh_minus_en (正值=ZH 較高)。",
    "tableS14_language_by_model.csv":
        "按模型彙整的跨語言差異 (每個 model x scale: mean_cell_diff_zh_minus_en, max_abs_shift, 計數 cells_zh_higher)。",
    "tableS15_language_by_vignette.csv":
        "按 vignette 彙整的跨語言差異 (每個 vignette x scale: mean_cell_diff_zh_minus_en, 計數 models_zh_higher)。",
    # Table 5: from scripts/item_level_profile.R (at analysis root)
    "Table5_item_stigma_profile.csv":
        "微結構分析：每個 Model x Item_ID 在 PLE/DEP/APS/SCZ 的 item-level mean score (EN + ZH 雙語列)。"
        "APS_Spike = Mean_APS - Mean_DEP；APS_ZH_minus_EN = APS 中英差距。"
        "Scale: social_distance (SD01-SD19) | prejudice (PJ01-PJ21)。",
}

KEY_COLUMN_GLOSSARY = {
    "model": "模型名稱 (例: GPT-4o, Claude Sonnet 4.5, DeepSeek V3.2)。",
    "vignette": "臨床情境代碼：PLE (Psychotic-Like Experiences) | DEP (Major Depression) | APS (Attenuated Psychosis Syndrome) | SCZ (Schizophrenia)。",
    "scale_type": "量表類型：social_distance (19 題, 19-76) | prejudice (21 題, 21-84)。higher = more stigma。",
    "language": "en = English / zh = 繁體中文 / cross_language = 從根目錄跨語言彙整檔來。",
    "table_name": "這筆 row 來自哪一個原始 CSV (用於 filter)。",
    "mean_scale": "Run-level 量表分數平均 (higher = more stigma)。",
    "cliffs_delta": "Cliff's delta effect size: |d|<0.147 negligible, <0.33 small, <0.474 medium, else large。",
    "human_sd_units": "(AI_mean - human_mean) / human_sd。正值 = AI 比人類更高污名。",
    "p_adjusted": "Holm-Bonferroni 調整後 p-value (family-wise control 於同一 scale x vignette 家族內)。",
    "icc2k": "Intraclass Correlation (two-way random, k raters=runs)。0.5 poor / 0.75 good / 0.9 excellent。",
    "mean_pairwise_spearman": "Run 之間題目分數的平均 Spearman rho (補 ICC，對 degenerate 情況更穩健)。",
    "matches_human_pattern": "observed_order 是否符合 PLE 最低、SCZ 最高之預期梯度。",
    "APS_Spike": "Mean_APS - Mean_DEP (同語言)。正值 = APS 情境比 DEP 情境更高污名。",
    "APS_ZH_minus_EN": "ZH APS 分數 - EN APS 分數。正值 = 中文提示在 APS 情境有更高污名。",
    "Item_Domain": "prejudice 題目的語義子領域 (dangerousness / disclosure / exclusionary / negative_affect / traditional_prejudice / treatment_carryover)；social_distance 為 NA。",
}


def _read_csv_rows(path):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    return fields, rows


def _format_row_for_llm(row, precision=8):
    """Truncate long floats to save LLM context tokens."""
    for k, v in row.items():
        if isinstance(v, str) and v.strip():
            # Check if it's a number that could be a float.
            if '.' in v or 'e' in v.lower():
                try:
                    float_val = float(v)
                    # Use 'g' format for significant digits.
                    row[k] = f"{float_val:.{precision}g}"
                except (ValueError, TypeError):
                    pass  # Not a float, leave as is.
    return row


def _locate_sources(input_path: Path, target_file: str):
    """Dynamically locate source files in root (for cross-language) and language subdirectories."""
    found = []
    # 1. Check root for cross-language files
    if (input_path / target_file).exists():
        found.append(("cross_language", input_path / target_file))
    # 2. Scan subdirectories for language-specific files
    for sub_dir in input_path.iterdir():
        if sub_dir.is_dir() and (sub_dir / target_file).exists():
            found.append((sub_dir.name, sub_dir / target_file))
    return found


def _infer_model_count(input_path: Path):
    m = re.search(r"analysis_(\d+)models_", input_path.name)
    return int(m.group(1)) if m else None


def process_directory(input_dir, output_dir):
    input_path = Path(input_dir).resolve()
    if not input_path.is_dir():
        sys.exit(f"Error: Input directory not found or is not a directory: {input_path}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    master_rows = []
    group_totals = {}

    for group_name, target_files in FILE_GROUPS.items():
        all_rows = []
        fieldnames_ordered = ["table_name", "language"]
        fieldnames_set = set(fieldnames_ordered)

        for target_file in target_files:
            sources = _locate_sources(input_path, target_file)
            if not sources:
                continue

            source_row_count = 0
            file_columns = []

            for lang_label, path in sources:
                fields, rows = _read_csv_rows(path)
                for col in fields:
                    if col not in fieldnames_set:
                        fieldnames_set.add(col)
                        fieldnames_ordered.append(col)
                    if col not in file_columns:
                        file_columns.append(col)
                for row in rows:
                    row["table_name"] = target_file
                    row["language"] = lang_label
                    all_rows.append(_format_row_for_llm(row))
                source_row_count += len(rows)

            master_rows.append({
                "Merged_File": group_name,
                "Source_Table": target_file,
                "Languages_Present": " | ".join(lang for lang, _ in sources),
                "Rows": source_row_count,
                "Description": FILE_DESCRIPTIONS.get(target_file, "(no description)"),
                "Columns": ", ".join(file_columns),
            })

        if all_rows:
            out_csv = output_path / group_name
            with open(out_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames_ordered)
                writer.writeheader()
                writer.writerows(all_rows)
            group_totals[group_name] = len(all_rows)
            print(f"Created {out_csv.name:32s} ({len(all_rows):>6d} rows, {len(fieldnames_ordered)} cols)")

    # Master summary file
    summary_csv = output_path / "01_Master_Summary.csv"
    with open(summary_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Section 1: analysis metadata
        model_count = _infer_model_count(input_path)
        writer.writerow(["# SECTION", "META", "", "", "", ""])
        writer.writerow(["Key", "Value", "", "", "", ""])
        writer.writerow(["source_directory", str(input_path), "", "", "", ""])
        writer.writerow(["model_count", model_count if model_count else "unknown", "", "", "", ""])
        writer.writerow(["generated_at", datetime.now().isoformat(timespec="seconds"), "", "", "", ""])
        writer.writerow(["total_merged_files", len(group_totals), "", "", "", ""])
        for g, n in group_totals.items():
            writer.writerow([f"rows_in_{g}", n, "", "", "", ""])
        writer.writerow([""] * 6)

        # Section 2: file / source table index
        writer.writerow(["# SECTION", "FILE_INDEX", "", "", "", ""])
        writer.writerow(["Merged_File", "Source_Table", "Languages_Present", "Rows", "Description", "Columns"])
        for r in master_rows:
            writer.writerow([
                r["Merged_File"], r["Source_Table"], r["Languages_Present"],
                r["Rows"], r["Description"], r["Columns"]
            ])
        writer.writerow([""] * 6)

        # Section 3: key column glossary
        writer.writerow(["# SECTION", "COLUMN_GLOSSARY", "", "", "", ""])
        writer.writerow(["Column", "Meaning", "", "", "", ""])
        for col, meaning in KEY_COLUMN_GLOSSARY.items():
            writer.writerow([col, meaning, "", "", "", ""])

    print(f"Created {summary_csv.name:32s} (meta + {len(master_rows)} source tables + glossary)")
    print(f"\nAll LLM-ready files exported to: {output_path.resolve()}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Consolidate analysis CSVs for LLM chat interfaces (ChatGPT, Gemini Pro)."
    )
    parser.add_argument(
        "input_dir",
        help="Target analysis directory (e.g., analysis_13models_20260419).")
    parser.add_argument(
        "--output", default=None,
        help="Output directory. Default: LLM_Chat_Export_<input_dir_name>/")
    args = parser.parse_args()

    out = args.output or f"LLM_Chat_{Path(args.input_dir).name.rstrip('/')}"
    process_directory(args.input_dir, out)

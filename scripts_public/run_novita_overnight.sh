#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env in $ROOT_DIR"
  exit 1
fi

set -a
source .env
set +a

if [[ -z "${NOVITA_API_KEY:-}" ]]; then
  echo "Missing NOVITA_API_KEY in .env"
  exit 1
fi

mkdir -p logs

LOG_FILE="logs/novita_overnight_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

run_optional() {
  echo
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Optional step: $*"
  if "$@"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Optional step finished"
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Optional step failed; continuing"
  fi
}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Novita overnight run starting"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log file: $LOG_FILE"

python3 -u scripts_public/run_stigma_study.py \
  --provider novita \
  --runs 30 \
  --language en \
  --output results_20260402_novita_en \
  --yes \
  --delay 0.1

python3 -u scripts_public/run_stigma_study.py \
  --provider novita \
  --runs 30 \
  --language zh \
  --output results_20260402_novita_zh \
  --yes \
  --delay 0.1

python3 scripts/merge_results_csv.py \
  results_20260402_en_7models/results_0402_7models_en.csv \
  results_20260401_en/results_0401_successful_5models.csv \
  results_20260402_novita_en/results_0402.csv

python3 scripts/merge_results_csv.py \
  results_20260402_zh_7models/results_0402_7models_zh.csv \
  results_20260402_zh/results_0402.csv \
  results_20260402_novita_zh/results_0402.csv

run_optional Rscript analyze_results.R results_20260402_en_7models/results_0402_7models_en.csv
run_optional Rscript analyze_results.R results_20260402_zh_7models/results_0402_7models_zh.csv
run_optional Rscript compare_languages.R \
  results_20260402_en_7models/results_0402_7models_en.csv \
  results_20260402_zh_7models/results_0402_7models_zh.csv \
  results_en_vs_zh_20260402_7models

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Novita overnight run finished"

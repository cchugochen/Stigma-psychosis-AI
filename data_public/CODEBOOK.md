# CODEBOOK — Mental-Illness Stigma Across Large Language Models

Data dictionary for the data released with the study *Mental-illness stigma
across large language models* (13 models × 2 languages).

## Scope of this release

The publicly released data file is the **between-model pairwise comparison
table** that underlies the study's between-model statistics:

- **`data_public/eTable6_pairwise_full.csv`** — every pairwise model contrast, within
  each language × vignette × scale, with effect sizes and adjusted p-values.

**Not released (third-party copyright):** the item-level response records contain
the verbatim Wang et al. (2020) vignette and item wording, which is copyrighted
and cannot be redistributed. Item-level analysis can be reproduced with the code
in `scripts_public/` once the user supplies their own licensed copy of the
instrument (see `items.example.json` / `vignettes.example.json` for the required
schema).

- **Companion code:** `scripts_public/` (collection + analysis pipeline)
- **Measurement scale:** 1–4 Likert; **all scores are stigma-directional,
  higher = more stigma** (reverse-keyed items recoded before scoring).

---

## 1. Study design constants

| Dimension | Value |
|-----------|-------|
| Models | 13 (see §3) |
| Languages | English, Mandarin Chinese |
| Vignettes | 4 — `PLE`, `DEP`, `APS`, `SCZ` |
| Scales | 2 — `social_distance` (19 items), `prejudice` (21 items) |
| Runs per cell | 30 (independent repetitions) |
| Inclusion | run-level scale scores with completeness ≥ 0.80 |
| Default temperature | 0.3 (GPT-5.4 / GPT-5.4 Mini fixed at 1.0 — not configurable) |

Expected human gradient (Wang 2020): `PLE < APS ≈ DEP < SCZ`.

---

## 2. File: `data_public/eTable6_pairwise_full.csv`

One row per ordered model pair, within each language × vignette × scale.
**1,248 rows, 17 columns.** Comparison statistic = Wilcoxon rank-sum
(Mann–Whitney); effect size = Cliff's delta; multiplicity = Holm within family.

| # | Variable | Type | Coding / values | Notes |
|---|----------|------|-----------------|-------|
| 1 | `language` | categorical | `English`, `Mandarin Chinese` | Prompt language |
| 2 | `vignette` | categorical | `PLE`, `DEP`, `APS`, `SCZ` | Clinical scenario (see §4) |
| 3 | `scale_type` | categorical | `social_distance`, `prejudice` | Instrument subscale |
| 4 | `model_1` | string | display name | First model in the contrast (see §3) |
| 5 | `model_2` | string | display name | Second model in the contrast |
| 6 | `n_1` | integer | run count | Qualifying runs (completeness ≥ 0.80) for `model_1` |
| 7 | `n_2` | integer | run count | Qualifying runs for `model_2` |
| 8 | `statistic` | numeric | Wilcoxon W | Rank-sum (Mann–Whitney) statistic for `model_1` vs `model_2` |
| 9 | `median_difference` | numeric | scale-score units | Median(`model_1`) − Median(`model_2`); **positive = `model_1` more stigmatizing** |
| 10 | `p_raw` | numeric | 0–1 | Unadjusted two-sided Wilcoxon p-value |
| 11 | `note` | string | `NA` or flag | Reserved annotation (all `NA` in this release) |
| 12 | `cliffs_delta` | numeric | −1 … 1 | Cliff's delta, direction `model_1` vs `model_2` (positive = `model_1` higher) |
| 13 | `cliffs_delta_low` | numeric | −1 … 1 | Lower bound, 95% CI of Cliff's delta |
| 14 | `cliffs_delta_high` | numeric | −1 … 1 | Upper bound, 95% CI of Cliff's delta |
| 15 | `magnitude` | categorical | `negligible`, `small`, `medium`, `large` | Cliff's delta magnitude (\|δ\|: <0.147 negligible, <0.33 small, <0.474 medium, ≥0.474 large) |
| 16 | `p_adjusted` | numeric | 0–1 | Holm-adjusted p-value (within language × vignette × scale family) |
| 17 | `significant` | boolean | `TRUE` / `FALSE` | `p_adjusted < 0.05` |

**Reading a row:** within one `language × vignette × scale` cell, `model_1` and
`model_2` are compared; `median_difference` and `cliffs_delta` are signed so that
positive values mean `model_1` showed *more* stigma than `model_2`.

---

## 3. Model roster (display order: developer family → release date)

| Order | Model | API id | Provider | Notes |
|-------|-------|--------|----------|-------|
| 1 | GPT-3.5 | `gpt-3.5-turbo-0125` | OpenAI | Historical baseline (2022-11) |
| 2 | GPT-4o | `gpt-4o` | OpenAI | |
| 3 | GPT-OSS-120B | `openai/gpt-oss-120b` | Novita | Open weights |
| 4 | GPT-5.4 | `gpt-5.4` | OpenAI | temperature fixed 1.0 |
| 5 | GPT-5.4 Mini | `gpt-5.4-mini` | OpenAI | temperature fixed 1.0 |
| 6 | Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | Anthropic | |
| 7 | Claude Opus 4.6 | `claude-opus-4-6` | Anthropic | |
| 8 | Gemini 2.5 Flash | `gemini-2.5-flash` | Google | |
| 9 | Gemini 3.1 Pro Preview | `gemini-3.1-pro-preview` | Google | Preview model |
| 10 | Gemini 3.1 Flash-Lite Preview | `gemini-3.1-flash-lite-preview` | Google | Preview model |
| 11 | Gemma 4 31B IT | `google/gemma-4-31b-it` | Novita | Open weights |
| 12 | Llama 3.3 70B | `meta-llama/llama-3.3-70b-instruct` | Novita | Open weights |
| 13 | DeepSeek V3.2 | `deepseek/deepseek-v3.2` | Novita | Cross-cultural focus |

---

## 4. Vignette and scale coding

| Code | Vignette |
|------|----------|
| `PLE` | Psychotic-Like Experiences |
| `DEP` | Depression |
| `APS` | Attenuated Psychosis Syndrome |
| `SCZ` | Schizophrenia |

| Code | Scale | Items |
|------|-------|-------|
| `social_distance` | Social distance | 19 (`SD01`–`SD19`) |
| `prejudice` | Prejudice / attitudes | 21 (`PJ01`–`PJ21`) |

Scale scores are scale-level (summed across items after reverse-keying), the same
unit used for the human baseline comparison in Wang (2020) — never item means.

---

## 5. Statistical methods (as implemented in `scripts_public/analyze_stage1.R`)

- Primary analysis = run-level scale scores with completeness ≥ 0.80.
- Between-model omnibus: Kruskal–Wallis; pairwise: Wilcoxon rank-sum (this table).
- Effect size: Cliff's delta with 95% CI.
- Multiplicity: Holm correction applied **within** each language × vignette ×
  scale family (not across the whole table).

---

## 6. Reproduction

```bash
# Full Stage 1 pipeline (regenerates pairwise tables, figures, cross-language outputs)
Rscript scripts_public/analyze_stage1.R <analysis_dir>/
```

Re-running from raw model responses requires your own licensed `items.json` and
`vignettes.json` (schema in `items.example.json` / `vignettes.example.json`) and
API keys in `.env` (template in `.env.example`).

---

## 7. Citation

If you use this dataset or code, please cite the accompanying article and the
source instrument (Wang K, et al., 2020; see article references).

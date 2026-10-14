# CODEBOOK: data released with the LLM psychiatric-stigma study

Data dictionary for the data that accompany the manuscript *Large language models reproduce human-like
stigma-related response patterns toward psychiatric vignettes across models and languages* (14 models × English
and Mandarin Chinese prompts). File sizes, row counts and SHA-256 checksums are listed in
[MANIFEST.csv](MANIFEST.csv).

## Scope of this release

| File | Rows | Content |
|---|---|---|
| `item_level_responses_14models_en.csv`, `item_level_responses_14models_zh.csv` | 67,200 each | Every item-level API call of the main study: raw model output, classification and score |
| `run_level_scale_scores_14models_en.csv`, `run_level_scale_scores_14models_zh.csv` | 3,360 each | Run-level scale scores (model × vignette × scale × run), with completeness and inclusion flags |
| `supplementary_data_1_pairwise_14models.csv` | 1,456 | Supplementary Data 1: all 91 between-model contrasts in each of 16 language × vignette × scale families |
| `sensitivity_analyses/elicitation_4models_original_prompt_october.csv` | 12,800 | Original prompt re-run on 1 October 2026 (4 models, 10 runs) |
| `sensitivity_analyses/elicitation_4models_role_play_instruction.csv` | 38,400 | Role-play instruction (4 models, 30 runs) |
| `sensitivity_analyses/elicitation_4models_full_scale_administration.csv` | 38,400 | Full-scale administration (4 models, 30 runs), one row per item |
| `sensitivity_analyses/temperature_claude_sonnet_4_5_t1p0.csv` | 3,200 | Claude Sonnet 4.5 at temperature 1.0 (8 May 2026; 10 runs) |

**Instrument wording is not redistributed.** The vignette and item text (Lee et al., 2016; Wang et al., 2020) is
replaced by identifiers: vignettes `PLE`, `DEP`, `APS`, `SCZ`; items `SD01`–`SD19` and `PJ01`–`PJ21`. One
model response quoted an item's wording back (GPT-OSS-120B, Mandarin Chinese, SCZ, PJ09); the quoted wording
was replaced by `[instrument text removed]`. A worked example with one vignette (PLE) and one item (SD01) in
both languages is given in [PROMPTS.md](../PROMPTS.md) and in Supplementary Text 1 of the article.

All scores are stigma-directional: higher = more stigma; reverse-keyed items are recoded before scoring.

---

## 1. Study design constants

| Dimension | Value |
|---|---|
| Models | 14 (see §5) |
| Languages | English (`en`), Mandarin Chinese (`zh`; Taiwanese version, Traditional Chinese characters) |
| Vignettes | `PLE` psychotic-like experiences, `DEP` major depression, `APS` attenuated psychosis syndrome, `SCZ` schizophrenia |
| Scales | `social_distance` (19 items, range 19–76), `prejudice` (21 items, range 21–84) |
| Runs per cell | 30 |
| Administration | one stateless API call per item; 4,800 calls per model and language |
| Inclusion (primary analysis) | run-level scale scores with ≥ 80% of items valid |
| Temperature | 0.3; the GPT-5.4 series does not accept a custom value and ran at its default of 1.0 |
| Query period | 1–18 April 2026; Gemini-3.5-Flash on 14 June 2026 |

---

## 2. Item-level files (main study and sensitivity analyses)

One row per item-level response. The four sensitivity files have the same columns.

| Variable | Coding / values | Notes |
|---|---|---|
| `model` | model name used in the article | e.g. `Gemini-3.5-Flash` (see §5; the authors' collection files spell it `Gemini 3.5 Flash`) |
| `model_id` | identifier sent to the provider API | e.g. `gemini-3.5-flash` |
| `provider` | `openai`, `anthropic`, `google`, `novita` | `novita` = Novita.AI (open-weight models) |
| `run` | 1–30 | Run index as recorded at collection; the analysis code reconstructs `analysis_run` from it |
| `vignette` | `PLE`, `DEP`, `APS`, `SCZ` | |
| `vignette_label` | full vignette name | e.g. `Psychotic-Like Experiences` |
| `scale_type` | `social_distance`, `prejudice` | |
| `item_id` | `SD01`–`SD19`, `PJ01`–`PJ21` | Item identifier (wording not released) |
| `item_domain` | Prejudice domain: `disclosure`, `treatment_carryover`, `traditional_prejudice`, `exclusionary`, `negative_affect`, `dangerousness`; empty for Social Distance items | The article calls `traditional_prejudice` "prejudice stereotypes" |
| `is_reverse` | `True` / `False` | Reverse-keyed item (score = 5 − rating) |
| `is_sensitive` | `True` / `False` | Item flagged in advance as high-sensitivity |
| `raw_response` | text | Verbatim model output. API failures start with `[API_ERROR]`; outputs cut at the token limit end with `[TRUNCATED:…]`. In the full-scale file this is the answer fragment for the item, split from the one-call reply |
| `response_type` | `valid`, `refusal`, `refusal_identity`, `unparseable` | Classification by the rule-based classifier (Supplementary Table 3b); in the article `refusal_identity` is counted as refusal, and API errors as unparseable/error |
| `parsed_value` | 1–4, or empty | Rating given by the model (1 = strongly agree … 4 = strongly disagree); empty when not valid |
| `scored_value` | 1–4, or empty | Stigma-directional score after reverse keying |
| `temperature` | configured value | 0.3 in the main study (the GPT-5.4 series ignores it; effective 1.0); 1.0 in the temperature file |
| `language` | `en`, `zh` | Prompt language |
| `timestamp` | ISO 8601, UTC | Time the response was recorded. GPT-3.5, GPT-4o and Gemini-3.1-Pro-Preview were queried through batch APIs and have batch-level times (Supplementary Table 2, Part B) |

---

## 3. Run-level files

One row per model × vignette × scale × run, as produced by the analysis code from the item-level files.

| Variable | Coding / values | Notes |
|---|---|---|
| `model` | as in §2 | |
| `vignette`, `scale_type` | as in §2 | |
| `analysis_run` | text | Run identifier reconstructed by the analysis code; unique within model × vignette × scale |
| `expected_items` | 19 or 21 | Items in the scale |
| `items_answered` | integer | Valid items in the run |
| `item_mean` | 1–4 | Mean stigma-directional score of the valid items |
| `scale_score_complete` | scale points, or empty | Sum of scores when all items are valid |
| `completeness` | 0–1 | `items_answered / expected_items` |
| `scale_score_primary` | scale points | `item_mean × expected_items` (prorated); used when completeness ≥ 0.80 |
| `in_primary_analysis` | `TRUE` / `FALSE` | Completeness ≥ 0.80 |
| `in_complete_case_analysis` | `TRUE` / `FALSE` | All items valid |

---

## 4. Supplementary Data 1: `supplementary_data_1_pairwise_14models.csv`

One row per model pair within each language × vignette × scale family (91 pairs × 16 families). Comparison
statistic = Wilcoxon rank-sum; effect size = Cliff's δ (unbiased variance estimator, asymmetric 95% CI, computed
with the exact dominance-matrix algorithm: `effsize::cliff.delta(..., return.dm = TRUE)`);
multiplicity = Holm within each family.

| Variable | Coding / values | Notes |
|---|---|---|
| `language` | `English`, `Mandarin Chinese` | |
| `vignette` | `PLE`, `DEP`, `APS`, `SCZ` | |
| `scale_type` | `social_distance`, `prejudice` | |
| `model_1`, `model_2` | display names | |
| `n_1`, `n_2` | integer | Qualifying runs (completeness ≥ 0.80) |
| `statistic` | Wilcoxon W | |
| `median_difference` | scale points | Median(`model_1`) − Median(`model_2`); positive = `model_1` higher |
| `p_raw` | 0–1 | Unadjusted two-sided p value |
| `note` | `NA` or flag | Reserved annotation |
| `cliffs_delta`, `cliffs_delta_low`, `cliffs_delta_high` | −1 to 1 | Cliff's δ and 95% CI; positive = `model_1` higher |
| `magnitude` | `negligible`, `small`, `medium`, `large` | \|δ\| < 0.147, < 0.33, < 0.474, ≥ 0.474 |
| `p_adjusted` | 0–1 | Holm-adjusted within the family |
| `significant` | `TRUE` / `FALSE` | `p_adjusted < 0.05` |

---

## 5. Model roster

| Name in the article (`model` in the data) | Name in the authors' collection files | API identifier | Provider | Notes |
|---|---|---|---|---|
| GPT-3.5 | GPT-3.5 | `gpt-3.5-turbo-0125` | OpenAI | Batch API |
| GPT-4o | GPT-4o | `gpt-4o` | OpenAI | Batch API |
| GPT-OSS-120B | GPT-OSS-120B | `openai/gpt-oss-120b` | Novita.AI | Open weights |
| GPT-5.4 | GPT-5.4 | `gpt-5.4` | OpenAI | Temperature fixed at 1.0 |
| GPT-5.4-Mini | GPT-5.4 Mini | `gpt-5.4-mini` | OpenAI | Temperature fixed at 1.0 |
| Claude Sonnet 4.5 | Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | Anthropic | |
| Claude Opus 4.6 | Claude Opus 4.6 | `claude-opus-4-6` | Anthropic | |
| Gemini-2.5-Flash | Gemini 2.5 Flash | `gemini-2.5-flash` | Google | |
| Gemini-3.1-Pro-Preview | Gemini 3.1 Pro Preview | `gemini-3.1-pro-preview` | Google | Preview model; batch API |
| Gemini-3.1-Flash-Lite-Preview | Gemini 3.1 Flash-Lite Preview | `gemini-3.1-flash-lite-preview` | Google | Preview model |
| Gemini-3.5-Flash | Gemini 3.5 Flash | `gemini-3.5-flash` | Google | Queried 14 June 2026 |
| Gemma-4-31B-IT | Gemma 4 31B IT | `google/gemma-4-31b-it` | Novita.AI | Open weights |
| Llama-3.3-70B | Llama 3.3 70B | `meta-llama/llama-3.3-70b-instruct` | Novita.AI | Open weights |
| DeepSeek-V3.2 | DeepSeek V3.2 | `deepseek/deepseek-v3.2` | Novita.AI | Open weights |

The sensitivity files contain Claude Sonnet 4.5, GPT-5.4, Gemini-3.5-Flash and GPT-OSS-120B (elicitation formats)
and Claude Sonnet 4.5 (temperature).

---

## 6. Citation

If you use these data, please cite the accompanying article and the source instruments (Lee et al., 2016;
Wang et al., 2020; full references in the article and in the repository README).

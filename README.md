# LLM Mental-Illness Stigma Study — Code and Data Repository

This repository contains the **analysis pipeline and the released data** for the manuscript:

> **Large language models reproduce human-like stigma-related response
> patterns toward psychiatric vignettes across models and languages.**
> *Status: under review.*

It administers the validated vignette and questionnaire methodology
of Wang et al. (2020) to fourteen frontier and open-weight LLMs from
five developers (OpenAI, Anthropic, Google, Meta, DeepSeek) in English
and Mandarin Chinese (the Taiwanese version, in Traditional Chinese
characters).

The repository holds the scripts behind the article, the study data,
and examples of the vignettes and items (one vignette and one item, in
both languages, in [PROMPTS.md](PROMPTS.md)). The full vignette and
item wording is not redistributed.

The repository is intended for two audiences:

* **Reviewers** verifying methodological transparency and the
  reproducibility of the reported analyses.
* **Researchers** wishing to replicate or extend the pipeline against
  newer models or additional languages.

---

## What is and is not included in this repository

To respect third-party copyright, the repository omits the following
classes of material. Each item is excluded by `.gitignore`; the
instrument files must be supplied locally before the pipeline can run
end-to-end.

| Excluded artefact | Reason | How to obtain |
|---|---|---|
| Full vignette and item wording (`vignettes.json`, `items.json`) | Copyright in the wording remains with the original authors (Lee et al., 2016; Wang et al., 2020). | Obtain from the source publications or the corresponding author; the expected structure is shown in [vignettes.example.json](vignettes.example.json) and [items.example.json](items.example.json). One vignette and one item are reproduced in [PROMPTS.md](PROMPTS.md). |
| All analysis outputs (`analysis_*/`, `LLM_Chat_analysis_*/`) | Several derived files (e.g., heatmap labels) embed copyrighted item wording. | Re-run [scripts_public/analyze_stage1.R](scripts_public/analyze_stage1.R) and [scripts_public/item_level_profile.R](scripts_public/item_level_profile.R) on your own data; outputs land in `analysis_<n>models_<date>/`. |
| Reference PDFs (`papers/`) | Third-party copyright. | Cited references are listed at the end of this README; obtain through your institutional library or the publishers. |

What **is** included:

* The scripts behind the article (`scripts_public/`): data collection
  and the response classifier, merging, the statistical analyses, the
  robustness and sensitivity analyses, the classifier validation, and
  the scripts that produce Table 1, Figures 1–3 and the Supplementary
  Tables and Figures. They are copies of the authors' working scripts;
  only file paths were changed.
* [PROMPTS.md](PROMPTS.md): the verbatim system prompts, user-message
  template and scale stems; the role-play and full-scale prompts of the
  sensitivity analyses; and one complete API call in each language
  (the PLE vignette with Social Distance item SD01).
* [data_public/](data_public/): the item-level responses of all 14
  models in both languages (134,400 rows), the run-level scale scores,
  the full pairwise model-comparison dataset (Supplementary Data 1 of
  the article), and the responses of the sensitivity analyses. Vignette
  and item wording is replaced by identifiers (`PLE`–`SCZ`,
  `SD01`–`SD19`, `PJ01`–`PJ21`). Variables are defined in
  [data_public/CODEBOOK.md](data_public/CODEBOOK.md); row counts and
  checksums are in [data_public/MANIFEST.csv](data_public/MANIFEST.csv).
* Schema-only example files (`vignettes.example.json`,
  `items.example.json`) so you can see the expected structure without
  copying any copyrighted text.
* This README and the `.gitignore` policy that documents what stays
  private.

---

## Repository layout

```
.
├── scripts_public/                       # the scripts behind the article (14 models)
│   ├── run_stigma_study.py               # data collection (provider APIs) + response classifier
│   ├── merge_14models_20260614.py        # merge collection files, re-apply the classifier
│   ├── analyze_stage1.R                  # statistical pipeline (English, Mandarin Chinese, cross-language)
│   ├── item_level_profile.R              # item-level profile
│   ├── robust_refusal.py                 # refusal-imputation sensitivity analysis
│   ├── robust_temperature.py             # temperature sensitivity analysis (functions)
│   ├── robust_temperature_14model.py     # temperature analysis on the 14-model dataset
│   ├── supp_tables_9_10_14model.R        # concordance rules; temperature table
│   ├── within_cell_independent_14model.R # within-cell vignette tests (Kruskal-Wallis, rank-sum, Cliff's δ)
│   ├── psychometric_domain_structure_14model.py   # Prejudice domain structure
│   ├── figure_metadata_14model.py        # model metadata shared by the figure scripts
│   ├── build_table1_main_stigma_0622.py  # Table 1
│   ├── build_etables_0622.py             # Supplementary Tables 1–7, Supplementary Data 1
│   ├── figure1_*.R, figure2_*.R, figure3_*.py      # Figures 1–3
│   ├── efigure1_*.R … efigure4_*.py      # Supplementary Figures 1–4
│   ├── collect_frames_4model*.py, fullscale_lib.py, merge_frames_4model.py,
│   │   run_arms_4model.py, compare_frames_4model.R,
│   │   supp_table11_4model.py, efigure5_*.R           # elicitation-format sensitivity analysis
│   ├── build_validation_set.py, analyze_agreement.py  # classifier validation
│   ├── export_public_data_1007.py        # builds data_public/
│   ├── install_r_deps.R, run_novita_overnight.sh, Models_name.md
├── data_public/                          # released data (no instrument wording)
│   ├── CODEBOOK.md                       # data dictionary
│   ├── MANIFEST.csv                      # rows, columns, SHA-256 per file
│   ├── item_level_responses_14models_{en,zh}.csv
│   ├── run_level_scale_scores_14models_{en,zh}.csv
│   ├── supplementary_data_1_pairwise_14models.csv
│   └── sensitivity_analyses/             # elicitation formats (4 models); temperature 1.0
├── PROMPTS.md                            # verbatim prompts + one worked example per language
├── vignettes.example.json, items.example.json  # schema only
├── requirements.txt, .env.example, .gitignore, README.md
```

Running the scripts creates the following local, `.gitignore`-protected
folders:

```
vignettes.json, items.json          # instrument wording, supplied locally
results_<date>_<provider>/          # raw collection files
analysis_14models_20260614/         # merged dataset and analysis outputs
analysis_sen_20260930/              # elicitation-format sensitivity analysis
analysis_psychometric_20261003/     # Prejudice domain-structure analysis
resp_valid_14model_0622/            # classifier-validation forms and labels (contain instrument text)
outputs/figures_tables/             # Table 1, Figures 1–3, Supplementary Tables 1–7 and Figures
```

---

## Software requirements

### Python

* **Python 3.12** was used (3.10+ should work).
* Install dependencies with:

  ```bash
  python3 -m pip install -r requirements.txt
  ```

  See [requirements.txt](requirements.txt). The provider SDKs
  (`openai`, `anthropic`, `google-genai`) are listed individually so
  that you can comment out any line for a provider you do not query.
  Models accessed via Novita.AI use the OpenAI-compatible endpoint at
  `https://api.novita.ai/openai` and require only the `openai` SDK.

### R

* **R 4.4–4.5** was used.
* Install required CRAN packages with:

  ```bash
  Rscript scripts_public/install_r_deps.R
  ```

  This installs `dplyr`, `readr`, `tidyr`, `ggplot2`, `stringr`,
  `tibble`, `effsize`, `ggdendro`, `patchwork`, `scales`, `ggrepel`
  and `jsonlite`.

### Other

* A POSIX shell for the optional `run_novita_overnight.sh` batch
  wrapper.
* Provider API keys for the models you intend to evaluate. See
  [.env.example](.env.example) for the expected variable names; copy
  it to `.env` (which is `.gitignore`'d) and fill in your keys. The
  data-collection script will refuse to start if a required key is
  missing for any selected model. **API keys must never be committed
  to version control.**

---

## Reproducing the study

All commands are run from the repository root. Steps 1–2 are one-time
setup; steps 3–5 reproduce the main dataset and its analysis; steps
6–9 reproduce the robustness and sensitivity analyses, the tables and
figures, the classifier validation and the public data release. The
released data in `data_public/` allow the analyses to be checked
without querying any model.

### 1. Prepare the instruments

1. Obtain the source instruments (vignettes and the social-distance /
   prejudice questionnaires) from Wang et al. (2020) through your
   institutional library or by contacting the original authors. The
   reference is listed at the end of this README.
2. Create local-only `vignettes.json` and `items.json` files matching
   the schemas shown in [vignettes.example.json](vignettes.example.json)
   and [items.example.json](items.example.json), or point the
   `AI_STIGMA_VIGNETTES_PATH` / `AI_STIGMA_ITEMS_PATH` environment
   variables at them. Both files are `.gitignore`'d and will never be
   committed.

### 2. Configure provider credentials and dependencies

```bash
python3 -m pip install -r requirements.txt     # Python deps
Rscript scripts_public/install_r_deps.R          # R deps
cp .env.example .env && $EDITOR .env             # provider API keys (.env is .gitignore'd)
```

### 3. Collect data — `scripts_public/run_stigma_study.py`

```bash
# One provider and one language at a time (recommended)
python3 scripts_public/run_stigma_study.py --provider anthropic --runs 30 --language en --yes
python3 scripts_public/run_stigma_study.py --provider anthropic --runs 30 --language zh --yes

# Open-weight models served via Novita.AI: run serially (rate limits)
bash scripts_public/run_novita_overnight.sh    # optional batch wrapper
```

Each run writes incrementally and resumes automatically on restart.
The temperature is 0.3; the OpenAI GPT-5.4 series does not accept a
custom value and runs at 1.0. The response classifier
(`classify_response()`, `parse_response()`) is defined in this script.
See `python3 scripts_public/run_stigma_study.py --help` for all options.

### 4. Merge and classify — `scripts_public/merge_14models_20260614.py`

Edit the `SOURCES` lists at the top of the script so that they point
to your collection files, then run:

```bash
python3 scripts_public/merge_14models_20260614.py
```

This writes `analysis_14models_20260614/{en,zh}/results_14models_{lang}.csv`
(67,200 rows per language), re-applying the response classifier to
every response and removing duplicates (newest timestamp wins). These
files correspond to `data_public/item_level_responses_14models_{en,zh}.csv`,
which omit the item wording and give the models the names used in the
article: the merged files keep the collection names (e.g.
`Gemini 2.5 Flash` for `Gemini-2.5-Flash`; see
[scripts_public/Models_name.md](scripts_public/Models_name.md)).

### 5. Statistical analysis — `scripts_public/analyze_stage1.R`

```bash
Rscript scripts_public/analyze_stage1.R analysis_14models_20260614/
Rscript scripts_public/item_level_profile.R analysis_14models_20260614/
```

This produces the run-level scale scores, descriptive statistics,
reliability, gradient checks, within- and between-model tests,
cross-language comparisons and refusal summaries used throughout the
article.

`analyze_stage1.R` expects the article's model names. To analyse the
released data, copy `data_public/item_level_responses_14models_{en,zh}.csv`
to `<dir>/{en,zh}/results_14models_{en,zh}.csv` and run the script on
`<dir>`; this reproduces all 34 of its output tables. Newly merged files
must first be renamed (see the comment at the top of the script).
`item_level_profile.R` and several table and figure scripts of step 7
key their model tables to the collection names, as in the analysis
behind the article; each of them says so at the top.

### 6. Robustness and sensitivity analyses

```bash
python3 scripts_public/robust_refusal.py                 # refusal imputation (Supplementary Table 7)
python3 scripts_public/robust_temperature_14model.py     # temperature 1.0 vs 0.3
Rscript scripts_public/supp_tables_9_10_14model.R        # Supplementary Tables 9 and 10
Rscript scripts_public/within_cell_independent_14model.R # Supplementary Table 4, Parts A and B
python3 scripts_public/psychometric_domain_structure_14model.py   # Supplementary Table 12, Fig. 6

# Elicitation-format sensitivity analysis (four models; Supplementary Table 11, Fig. 5)
python3 scripts_public/collect_frames_4model.py --help   # collection (one process per model)
python3 scripts_public/merge_frames_4model.py
python3 scripts_public/run_arms_4model.py
Rscript scripts_public/compare_frames_4model.R analysis_sen_20260930
python3 scripts_public/supp_table11_4model.py
Rscript scripts_public/efigure5_elicitation_sensitivity_4model.R
```

`collect_frames_4model_AS_RUN_20261001.py` is the collector exactly as
it ran on 1 October 2026; it used the earlier condition names
`persona`, `original_oct` and `fullscale`, which were later renamed
`Humanlike`, `Original_oct` and `Fullscale` (the names used by the
current collector and the downstream scripts).

### 7. Tables and figures

```bash
python3 scripts_public/build_table1_main_stigma_0622.py          # Table 1
Rscript scripts_public/figure1_stigma_profile_dual_lang_1002.R   # Figure 1
Rscript scripts_public/figure2_cross_language_forest_1002.R      # Figure 2
python3 scripts_public/figure3_trend_dual_lang_2x2_1002.py       # Figure 3
python3 scripts_public/build_etables_0622.py                     # Supplementary Tables 1–7, Supplementary Data 1
Rscript scripts_public/efigure1_reliability_refusal_1002.R       # Supplementary Fig. 1
Rscript scripts_public/efigure2_run_level_distributions_1002.R   # Supplementary Fig. 2
Rscript scripts_public/efigure3_item_profile_heatmaps_1002.R     # Supplementary Fig. 3
python3 scripts_public/efigure4_flow_diagram_1007.py             # Supplementary Fig. 4
```

Outputs are written to `outputs/figures_tables/`. The wording of the
table notes was edited further in the manuscript and Supplementary
Information documents.

### 8. Classifier validation (Supplementary Table 8)

```bash
python3 scripts_public/build_validation_set.py   # stratified 160-response subsample (seed 20260621), blinded forms
python3 scripts_public/analyze_agreement.py      # agreement statistics against the adjudicated reference standard
```

The forms and the per-response labels contain verbatim instrument text
and raw model responses, so they are kept in the local
`resp_valid_14model_0622/` folder and are available from the
corresponding author on reasonable request.

### 9. Public data release

```bash
python3 scripts_public/export_public_data_1007.py   # builds data_public/ and MANIFEST.csv
```

The script removes the item wording, replaces any wording a model
quoted back with `[instrument text removed]`, and checks every released
cell against the vignette and item text.

#### Article item ↔ script

| Article item | Script |
|---|---|
| Table 1 | `build_table1_main_stigma_0622.py` |
| Figures 1, 2, 3 | `figure1_stigma_profile_dual_lang_1002.R`, `figure2_cross_language_forest_1002.R`, `figure3_trend_dual_lang_2x2_1002.py` |
| Supplementary Tables 1–7, Supplementary Data 1 | `build_etables_0622.py` (numbers from `analyze_stage1.R` and `robust_refusal.py`); Supplementary Table 2, Part B, from the timestamps in the item-level files; Supplementary Table 4, Parts A and B (within-cell vignette tests), from `within_cell_independent_14model.R` |
| Supplementary Table 8 | `analyze_agreement.py` |
| Supplementary Tables 9, 10 | `supp_tables_9_10_14model.R` (temperature inputs from `robust_temperature_14model.py`) |
| Supplementary Table 11, Supplementary Fig. 5 | `compare_frames_4model.R`, `supp_table11_4model.py`, `efigure5_elicitation_sensitivity_4model.R` |
| Supplementary Table 12, Supplementary Fig. 6 | `psychometric_domain_structure_14model.py` |
| Supplementary Figs 1–4 | `efigure1_…`, `efigure2_…`, `efigure3_…` (R), `efigure4_flow_diagram_1007.py` |
| Supplementary Text 1 | [PROMPTS.md](PROMPTS.md) |

---

## Methodological overview

The full methodological specification is given in the Methods of the
article. The headline parameters are:

* 14 LLMs × 30 runs × 4 vignettes × 40 items × 2 languages =
  134,400 item-level API calls.
* Vignettes: psychotic-like experiences (PLE), major depression (DEP),
  attenuated psychosis syndrome (APS), schizophrenia (SCZ).
* Scales: 19-item Social Distance Scale (range 19–76); 21-item
  Prejudice Questionnaire (range 21–84). Higher scores indicate more
  stigma in both scales.
* Run-level scale scores are prorated and retained when ≥80% of items
  are valid.
* Effect sizes with 95% CIs are the primary quantities (Cliff's δ,
  Kendall's W); Friedman, Wilcoxon and Kruskal–Wallis tests are
  supporting descriptive indices, with Holm–Bonferroni correction
  within each test family.

---

## Privacy and copyright policy at a glance

* The repository contains the scripts, the verbatim prompts with
  examples of one vignette and one item in each language (`PROMPTS.md`),
  and the study data in `data_public/`. The full vignette and item
  wording and copyrighted PDFs are not committed; in the released data
  the wording is replaced by identifiers.
* Manuscript drafts and document-assembly code are kept in private
  folders that `.gitignore` excludes.
* The released model outputs are research data generated through each
  provider's API under its terms of service; the internal collection
  files, which still contain item wording, remain excluded.

---

## References

Source PDFs that informed this study live in the local `papers/`
directory (private). The complete bibliographic information, in APA
7th edition style, is reproduced below.

Baba, Y., Nemoto, T., Tsujino, N., Yamaguchi, T., Katagiri, N., &
Mizuno, M. (2017). Stigma toward psychosis and its formulation
process: Prejudice and discrimination against early stages of
schizophrenia. *Comprehensive Psychiatry*, *73*, 181–186.
https://doi.org/10.1016/j.comppsych.2016.11.005

Lee, E. H.-M., Hui, C. L.-M., Ching, E. Y.-N., Lin, J., Chang, W.-C.,
Chan, S. K.-W., & Chen, E. Y.-H. (2016). Public stigma in China
associated with schizophrenia, depression, attenuated psychosis
syndrome, and psychosis-like experiences. *Psychiatric Services*,
*67*(7), 766–770.
https://doi.org/10.1176/appi.ps.201500156

Wang, Y.-C., Lin, Y.-T., Liu, C.-M., Hwang, T.-J., Hsieh, M. H., Chien,
Y.-L., Hwu, H.-G., & Liu, C.-C. (2020). Stigmas toward psychosis-related
clinical features among the general public in Taiwan. *Asia-Pacific
Psychiatry*, *12*(1), e12370.
https://doi.org/10.1111/appy.12370

Yang, L. H., Wonpat-Borja, A. J., Opler, M. G., & Corcoran, C. M.
(2010). Potential stigma associated with inclusion of the psychosis
risk syndrome in the DSM-V: An empirical question. *Schizophrenia
Research*, *120*(1–3), 42–48.
https://doi.org/10.1016/j.schres.2010.03.012

The instrument-specific Wang et al. (2020) supplementary documents
(case vignettes in English and Mandarin Chinese, Traditional Chinese
characters; the social-distance and prejudice questionnaires) are companion files to the
main 2020 article cited above and are not separate publications.

---

## Citing this work

The accompanying manuscript is currently under review; a formal
citation (with DOI) will be added on acceptance. In the interim,
please cite this code repository together with the underlying
instruments (Wang et al., 2020).

Provisional BibTeX (please update the year, journal, DOI, and any
co-author list once the manuscript is accepted):

```bibtex
@misc{llm_stigma_2026,
  author       = {Author, A. and Co-author, B.},
  title        = {Large language models reproduce human-like
                  stigma-related response patterns toward psychiatric
                  vignettes across models and languages},
  year         = {2026},
  note         = {Manuscript under review. Code repository:
                  \url{https://github.com/<owner>/<repo>}},
}

@article{wang2020stigmas,
  author  = {Wang, Yen-Chin and Lin, Yi-Ting and Liu, Chih-Min
             and Hwang, Tzung-Jeng and Hsieh, Ming H. and Chien, Yi-Ling
             and Hwu, Hai-Gwo and Liu, Chen-Chung},
  title   = {Stigmas toward psychosis-related clinical features
             among the general public in {Taiwan}},
  journal = {Asia-Pacific Psychiatry},
  volume  = {12},
  number  = {1},
  pages   = {e12370},
  year    = {2020},
  doi     = {10.1111/appy.12370},
}
```

## Contact

For questions about reproduction, instrument access, or extension to
additional models or languages, please open an issue in this
repository.

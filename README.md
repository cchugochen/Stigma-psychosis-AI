# LLM Mental-Illness Stigma Study — Code Repository

This repository contains the **analysis pipeline** for the manuscript:

> **Large Language Models demonstrate Human-like Stigmatizing Responses
> to Mental Illness Scenarios? A Cross-Model, Cross-Language Comparison
> Using Validated Vignette Methodology.**
> *Status: Under review (preprint link to be added on submission).*

It operationalises the validated vignette and questionnaire methodology
of Wang et al. (2020) and tests thirteen frontier and open-weight LLMs
from five providers (OpenAI, Anthropic, Google, Meta, DeepSeek AI) in
English and Traditional Chinese.

The repository is intended for two audiences:

* **Reviewers** verifying methodological transparency and the
  reproducibility of the reported analyses.
* **Researchers** wishing to replicate or extend the pipeline against
  newer models or additional languages.

---

## What is and is not included in this repository

To respect third-party copyright and the privacy of generated model
outputs, the repository deliberately omits the following classes of
material. Each item is excluded by `.gitignore` and must be supplied
locally before the pipeline can run end-to-end.

| Excluded artefact | Reason | How to obtain |
|---|---|---|
| Case vignettes (`vignettes.json`) | Verbatim wording is the property of Wang et al. (2020). | Reproduce from Wang et al. (2020) or contact the original authors. The expected JSON schema is shown in [vignettes.example.json](vignettes.example.json). |
| Scale items (`items.json`) — 19 social-distance + 21 prejudice items | Verbatim wording is the property of Wang et al. (2020). | Reproduce from Wang et al. (2020). The expected JSON schema is shown in [items.example.json](items.example.json). |
| Raw LLM responses (`results_*models_*.csv`, ~62k rows × 2 languages) | Generated content is bound by each provider's terms of service. | Re-run [scripts_public/run_stigma_study.py](scripts_public/run_stigma_study.py) under your own provider API keys. |
| All analysis outputs (`analysis_*/`, `LLM_Chat_analysis_*/`) | Several derived files (e.g., heatmap labels) embed copyrighted item wording. | Re-run [scripts_public/analyze_stage1.R](scripts_public/analyze_stage1.R) and [scripts_public/item_level_profile.R](scripts_public/item_level_profile.R) on your own data; outputs land in `analysis_<n>models_<date>/`. |
| Reference PDFs (`papers/`) | Third-party copyright. | Cited references are listed at the end of this README; obtain through your institutional library or the publishers. |

What **is** included:

* The complete data-collection and analysis source code
  (`scripts_public/`).
* Schema-only example files (`vignettes.example.json`,
  `items.example.json`) so you can see the expected structure without
  copying any copyrighted text.
* This README and the `.gitignore` policy that documents what stays
  private.

---

## Repository layout

```
.
├── scripts_public/                 # the entire reproducible pipeline
│   ├── run_stigma_study.py         # data collection (CLI; provider APIs)
│   ├── reclassify_merge.py         # merge per-stage CSVs; reapply classifier
│   ├── analyze_stage1.R            # Stage 1 statistical pipeline (EN + ZH)
│   ├── item_level_profile.R        # item-level profile + heatmaps
│   ├── export_for_llm.py           # consolidate outputs into ≤6 tidy CSVs
│   ├── generate_dashboard.py       # interactive HTML dashboard
│   └── run_novita_overnight.sh     # batch wrapper for Novita.AI models
├── vignettes.example.json          # schema only — populate locally
├── items.example.json              # schema only — populate locally
├── .env.example                    # required provider API keys
├── .gitignore                      # privacy / copyright policy
└── README.md                       # this file
```

After running the pipeline locally, the following private
(`.gitignore`-protected) directories will appear:

```
vignettes.json, items.json          # populated from Wang et al. (2020)
results_<date>_<provider>/          # per-stage raw CSVs
analysis_<n>models_<date>/          # merged dataset + analysis outputs
LLM_Chat_analysis_<n>models_<date>/ # consolidated LLM-friendly CSVs
papers/                             # source PDFs
```

---

## Software requirements

### Python

* **Python 3.10+**.
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

* **R 4.3+**.
* Install required CRAN packages with:

  ```bash
  Rscript scripts_public/install_r_deps.R
  ```

  This installs `dplyr`, `readr`, `tidyr`, `ggplot2`, `stringr`,
  `tibble`, `effsize`, `ggdendro`, `patchwork`, and `scales`.

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

The pipeline is six steps; steps 1–2 are one-time setup, steps 3–5
correspond to data collection → merge → statistical analysis, and step
6 is optional dashboarding.

### 1. Prepare the instruments

1. Obtain the source instruments (vignettes and the social-distance /
   prejudice questionnaires) from Wang et al. (2020) through your
   institutional library or by contacting the original authors. The
   reference is listed at the end of this README.
2. Create local-only `vignettes.json` and `items.json` files matching
   the schemas shown in [vignettes.example.json](vignettes.example.json)
   and [items.example.json](items.example.json). Both files are
   `.gitignore`'d and will never be committed.

### 2. Configure provider credentials and dependencies

```bash
# Python deps
python3 -m pip install -r requirements.txt

# R deps
Rscript scripts_public/install_r_deps.R

# Provider API keys (fill in your own; .env is .gitignore'd)
cp .env.example .env
$EDITOR .env
```

### 3. Collect data — `scripts_public/run_stigma_study.py`

```bash
# Full primary study, one provider at a time (recommended)
python3 scripts_public/run_stigma_study.py \
  --provider anthropic --runs 30 --language en --yes

python3 scripts_public/run_stigma_study.py \
  --provider anthropic --runs 30 --language zh --yes

# Open-weight models served via Novita.AI: serial execution (rate-limit safety)
bash scripts_public/run_novita_overnight.sh    # optional batch wrapper
```

Each run writes incrementally to `results/results_<MMDD>.csv`; resume
is automatic on restart. The default temperature is 0.3 (the OpenAI
GPT-5.4 family is fixed at 1.0 by the API and cannot be overridden).
Repeat for every (provider × language) combination you intend to
include. See `python3 scripts_public/run_stigma_study.py --help` for
the full CLI surface (`--models`, `--runs`, `--language`,
`--temperature`, `--run-label`, `--vignettes`, `--dry-run`,
`--analyze`, ...).

### 4. Merge per-stage data — `scripts_public/reclassify_merge.py`

Once all providers and languages are collected, edit the `SOURCES`
dictionary at the top of `scripts_public/reclassify_merge.py` so that
the per-stage CSV paths it lists match your local layout, then run:

```bash
python3 scripts_public/reclassify_merge.py
```

This produces
`analysis_<n>models_<date>/{en,zh}/results_<n>models_<lang>.csv`,
the merged item-level master files used by the R pipeline. The merge
also re-runs the response classifier so that every model and language
is subject to the same logic (response-type categories defined in
`run_stigma_study.py`).

### 5. Statistical analysis — `scripts_public/analyze_stage1.R`

```bash
# Primary statistics, figures, and Stage 1A–1C tables (all language pairs)
Rscript scripts_public/analyze_stage1.R analysis_<n>models_<date>/

# Item-level profile (Table 5 and companion heatmaps)
Rscript scripts_public/item_level_profile.R analysis_<n>models_<date>/
```

The two scripts collectively produce every numbered Table and Figure
in the manuscript; the headers of `analyze_stage1.R` and
`item_level_profile.R` map each output filename to the corresponding
manuscript reference (see also the *Output map* table below).

#### Output map (manuscript ↔ file)

| Manuscript ref | File | Generated by |
|---|---|---|
| Table 1 (response classification) | `analysis_<…>/table1_response_classification.csv` | `analyze_stage1.R` (Stage 1C) |
| Table 2 (EN scores) | `analysis_<…>/en/table2_en_stigma_scores.csv` | `analyze_stage1.R` (Stage 1A, EN) |
| Table 3 (ZH scores) | `analysis_<…>/zh/table3_zh_stigma_scores.csv` | `analyze_stage1.R` (Stage 1A, ZH) |
| Table 4 (cross-language Δ) | `analysis_<…>/table4_cross_language_shift.csv` | `analyze_stage1.R` (Stage 1C) |
| Table 5 (item-level profile) | `analysis_<…>/Table5_item_stigma_profile.csv` | `item_level_profile.R` |
| Tables S1–S11 (per language) | `analysis_<…>/{en,zh}/tableS1…tableS11_*.csv` | `analyze_stage1.R` (Stage 1A) |
| Tables S12–S15 (cross-language) | `analysis_<…>/tableS12…tableS15_*.csv` | `analyze_stage1.R` (Stage 1B) |
| Figure 1 (timeline) | `analysis_<…>/{en,zh}/figures/fig1_timeline_scatter_*` | `analyze_stage1.R` (Stage 1A) |
| Figures 2–4 (violins, heatmap) | `analysis_<…>/{en,zh}/figures/fig{2,2a,2b,3,3a,3b,4}_*` | `analyze_stage1.R` (Stage 1A) |
| Figure 5 (forest plot) | `analysis_<…>/fig5_cross_language_forest_plot.{pdf,png}` | `analyze_stage1.R` (Stage 1B) |
| Figure 6 (heatmap) | `analysis_<…>/fig6_cross_language_heatmap.{pdf,png}` | `analyze_stage1.R` (Stage 1B) |
| Figure 7 (response classes) | `analysis_<…>/fig7_response_classification.{pdf,png}` | `analyze_stage1.R` (Stage 1C) |
| Figures A–B (item profile, APS spike) | `analysis_<…>/Fig{A,B}_*` | `item_level_profile.R` |

### 6. Optional consolidated outputs

```bash
# Pack the analysis directory into ≤6 tidy CSVs (good for LLM-aided review)
python3 scripts_public/export_for_llm.py analysis_<n>models_<date>/

# Build a self-contained interactive HTML dashboard
python3 scripts_public/generate_dashboard.py analysis_<n>models_<date>/
```

Both consumer scripts have been hardened to omit verbatim scale wording
from their public outputs; only `Item_ID` and `Item_Domain` propagate
into the released artefacts.

---

## Methodological overview

The full methodological specification, including statistical models,
sample-size justification, classifier rules, errata, and known
limitations, is described in the manuscript draft (kept private
under `submit/`). The headline parameters are:

* 13 LLMs × 30 runs × 4 vignettes × 40 items × 2 languages =
  124,800 item-level API calls.
* Vignettes: psychotic-like experiences (PLE), major depression (DEP),
  attenuated psychosis syndrome (APS), schizophrenia (SCZ).
* Scales: 19-item Social Distance Scale (range 19–76); 21-item
  Prejudice Questionnaire (range 21–84). Higher scores indicate more
  stigma in both scales.
* Run-level scale scores are prorated and retained when ≥80% of items
  are answered.
* Non-parametric inference: Friedman + paired Wilcoxon (within-model
  vignette contrasts); Kruskal–Wallis + Wilcoxon rank-sum with Cliff's
  δ (between-model comparisons); Holm–Bonferroni correction within
  each test family.

---

## Privacy and copyright policy at a glance

* The repository is **code-only**. No vignette text, no scale items,
  no raw model responses, and no copyrighted PDFs are committed.
* Two private directories (`scripts_authors/`, `submit/`) hold
  manuscript-drafting code and Word documents and are excluded from
  version control by `.gitignore`.
* Researchers re-running the pipeline must source Wang et al. (2020)
  through legitimate channels and populate `vignettes.json` and
  `items.json` locally.
* Provider terms of service govern the storage and redistribution of
  generated outputs; raw `results_*models_*.csv` files are excluded
  from the repository accordingly.

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

Lee, E. H. M., Hui, C. L. M., Chan, K. P. K., Chan, P. Y., Law,
E. Y. L., Chong, C. S. Y., Chang, W. C., & Chen, E. Y. H. (2016).
Public stigma in China associated with schizophrenia, depression,
attenuated psychosis syndrome, and psychotic-like experiences.
*Psychiatric Services*, *67*(7), 766–770.
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
(case vignettes in English and Traditional Chinese; the social-
distance and prejudice questionnaires) are companion files to the
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
  title        = {Large Language Models demonstrate Human-like
                  Stigmatizing Responses to Mental Illness Scenarios?
                  A Cross-Model, Cross-Language Comparison Using
                  Validated Vignette Methodology},
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

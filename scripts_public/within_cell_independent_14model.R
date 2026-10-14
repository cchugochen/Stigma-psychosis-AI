#!/usr/bin/env Rscript
# Within-cell vignette comparisons as independent samples (Reviewer 3, Comment 4; editorial audit item E03, plan A;
# corresponding author, 2026-10-12). Replaces the matched-run Friedman and paired signed-rank tests and Kendall's W:
# each item was administered in a separate stateless call, so runs with the same index share nothing across vignettes.
#   omnibus  : Kruskal-Wallis across the four vignettes in each model x scale x language cell, on all qualifying runs;
#              epsilon^2 = H / (N - 1) (as for the between-model tests); Holm within each model x language family
#              (2 tests), as for the former Part A
#   pairwise : Wilcoxon rank-sum for the 6 vignette pairs (exact = FALSE, continuity correction: the settings of the
#              between-model contrasts in analyze_stage1.R); Holm within each cell (6 tests); Cliff's delta with 95% CI
#              (effsize::cliff.delta, conf.level = 0.95, default unbiased variance and Student-t interval). The CI is
#              computed with the exact dominance-matrix algorithm (return.dm = TRUE): in effsize 0.8.1 the default
#              "row partitioning" algorithm can give a wrong interval with many ties (e.g. Claude Sonnet 4.5, English
#              Prejudice, PLE vs DEP: [-0.998, 0.043] against the exact [-0.983, -0.782]); estimates are identical.
# Input : analysis_14models_20260614/{en,zh}/run_level_scale_scores.csv (in_primary_analysis == TRUE)
# Output: analysis_14models_20260614/within_cell_independent/within_cell_{omnibus,pairwise}.csv
# Usage : Rscript scripts_public/within_cell_independent_14model.R
suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(effsize)
})

file_arg <- sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE))
root <- normalizePath(file.path(dirname(file_arg), ".."))
an <- file.path(root, "analysis_14models_20260614")
out_dir <- file.path(an, "within_cell_independent")
dir.create(out_dir, showWarnings = FALSE)

vignettes <- c("PLE", "DEP", "APS", "SCZ")
min_runs <- 5  # min_runs_for_inference in analyze_stage1.R
omnibus <- list()
pairwise <- list()

for (lang in c("en", "zh")) {
  d <- read_csv(file.path(an, lang, "run_level_scale_scores.csv"), show_col_types = FALSE) %>%
    filter(in_primary_analysis, vignette %in% vignettes)
  for (m in sort(unique(d$model))) {
    for (st in c("social_distance", "prejudice")) {
      a <- d %>% filter(model == m, scale_type == st)
      g <- lapply(vignettes, function(v) a$scale_score_primary[a$vignette == v])
      names(g) <- vignettes
      stopifnot(all(lengths(g) >= min_runs))  # every cell has all four vignettes with enough qualifying runs
      kw <- kruskal.test(scale_score_primary ~ factor(vignette), data = a)
      n <- nrow(a)
      omnibus[[length(omnibus) + 1]] <- tibble(
        language = lang, model = m, scale_type = st, n_runs = n,
        n_PLE = length(g$PLE), n_DEP = length(g$DEP), n_APS = length(g$APS), n_SCZ = length(g$SCZ),
        statistic = unname(kw$statistic), df = unname(kw$parameter), p_value = kw$p.value,
        epsilon_sq = unname(kw$statistic) / (n - 1)
      )
      rows <- lapply(combn(vignettes, 2, simplify = FALSE), function(pr) {
        x <- g[[pr[1]]]
        y <- g[[pr[2]]]
        wt <- suppressWarnings(wilcox.test(x, y, exact = FALSE))
        cd <- suppressWarnings(effsize::cliff.delta(x, y, conf.level = 0.95, return.dm = TRUE))
        tibble(
          language = lang, model = m, scale_type = st, vignette_1 = pr[1], vignette_2 = pr[2],
          n_1 = length(x), n_2 = length(y), statistic = unname(wt$statistic),
          median_difference = median(x) - median(y), p_raw = wt$p.value,
          cliffs_delta = unname(cd$estimate), cliffs_delta_low = unname(cd$conf.int[1]),
          cliffs_delta_high = unname(cd$conf.int[2])
        )
      })
      pairwise[[length(pairwise) + 1]] <- bind_rows(rows) %>%
        mutate(p_adjusted = p.adjust(p_raw, method = "holm"), significant = p_adjusted < 0.05)
    }
  }
}

omnibus <- bind_rows(omnibus) %>%
  group_by(language, model) %>%
  mutate(p_holm = p.adjust(p_value, method = "holm")) %>%
  ungroup()
pairwise <- bind_rows(pairwise)
stopifnot(nrow(omnibus) == 56, nrow(pairwise) == 336)
write_csv(omnibus, file.path(out_dir, "within_cell_omnibus.csv"))
write_csv(pairwise, file.path(out_dir, "within_cell_pairwise.csv"))
cat(sprintf("wrote %s (56 cells) and %s (336 contrasts) [R %s, effsize %s]\n",
            file.path(out_dir, "within_cell_omnibus.csv"), file.path(out_dir, "within_cell_pairwise.csv"),
            getRversion(), packageVersion("effsize")))

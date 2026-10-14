# supp_tables_9_10_14model.R  (2026-10-07)
#
# Supplementary Table 9  (Reviewer 1, Comment 3; Reviewer 3, Minor 1): gradient concordance
#   under (a) the primary rule, (b) an uncertainty-aware rule, (c) restriction to reliable cells.
# Supplementary Table 10 (Reviewer 1, Comment 11): Claude Sonnet 4.5 at temperature 1.0 vs 0.3.
#
# Rules (as stated in the revised Methods):
#   primary     : mean(PLE) < min[mean(DEP), mean(APS)] and mean(SCZ) > max[mean(DEP), mean(APS)];
#                 unrounded means; an exact tie at either boundary counts as non-concordant.
#   uncertainty : primary rule met AND both boundary contrasts have a Cliff's delta whose 95% CI
#                 excludes zero in the concordant direction. Lower boundary = the lower of DEP/APS
#                 vs PLE; upper boundary = SCZ vs the higher of DEP/APS. Independent-samples
#                 estimator (effsize::cliff.delta: default unbiased variance, asymmetric CI; return.dm = TRUE,
#                 2026-10-12, because the default row-partitioning algorithm of effsize 0.8.1 can give a wrong
#                 CI when many values are tied), as in analyze_stage1.R safe_cliff_delta().
#   reliable    : (model x scale x language) cells in which all four vignettes have mean pairwise
#                 Spearman rho > 0.70 (tableS3_reliability.csv); non-evaluable vignettes exclude the cell.
# Inputs : analysis_14models_20260614/{en,zh}/run_level_scale_scores.csv, tableS3, tableS4;
#          analysis_14models_20260614/robust_temperature/run_level_scale_scores.csv (1007 re-run)
# Outputs: analysis_14models_20260614/concordance_sensitivity/{cells,summary}.csv
#          analysis_14models_20260614/robust_temperature/supp_table10_{cells,gradient}.csv
#
# Usage: Rscript scripts_public/supp_tables_9_10_14model.R

suppressPackageStartupMessages({
  library(dplyr); library(readr); library(tidyr); library(effsize)
})
args <- commandArgs(trailingOnly = FALSE)
sf   <- args[startsWith(args, "--file=")]
root <- normalizePath(if (length(sf) > 0) file.path(dirname(sub("--file=", "", sf)), "..") else ".")
an   <- file.path(root, "analysis_14models_20260614")
out9 <- file.path(an, "concordance_sensitivity"); dir.create(out9, showWarnings = FALSE)
V    <- c("PLE", "DEP", "APS", "SCZ")

cd <- function(x, y) {
  r <- suppressWarnings(effsize::cliff.delta(x, y, conf.level = 0.95, return.dm = TRUE))
  c(d = unname(r$estimate), lo = r$conf.int[[1]], hi = r$conf.int[[2]])
}
strict <- function(m) m[["PLE"]] < min(m[["DEP"]], m[["APS"]]) && m[["SCZ"]] > max(m[["DEP"]], m[["APS"]])

# ── Supplementary Table 9 ───────────────────────────────────────────────────
cells <- list()
for (lang in c("en", "zh")) {
  rl  <- read_csv(file.path(an, lang, "run_level_scale_scores.csv"), show_col_types = FALSE) %>%
           filter(in_primary_analysis == "TRUE" | in_primary_analysis == TRUE)
  rel <- read_csv(file.path(an, lang, "tableS3_reliability.csv"), show_col_types = FALSE)
  s4  <- read_csv(file.path(an, lang, "tableS4_gradient_check.csv"), show_col_types = FALSE)
  for (key in split(rl, list(rl$model, rl$scale_type), drop = TRUE)) {
    mdl <- key$model[1]; sc <- key$scale_type[1]
    vals <- lapply(setNames(V, V), function(v) key$scale_score_primary[key$vignette == v])
    m    <- sapply(vals, mean)
    lowv <- if (m[["DEP"]] <= m[["APS"]]) "DEP" else "APS"
    higv <- if (m[["DEP"]] <= m[["APS"]]) "APS" else "DEP"
    lo   <- cd(vals[[lowv]], vals[["PLE"]])          # > 0: lower intermediate above PLE
    hi   <- cd(vals[["SCZ"]], vals[[higv]])          # > 0: SCZ above higher intermediate
    rr   <- rel %>% filter(model == mdl, scale_type == sc)
    rho  <- setNames(rr$mean_pairwise_spearman, rr$vignette)[V]
    prim <- strict(m)
    cells[[length(cells) + 1]] <- tibble(
      language = lang, model = mdl, scale_type = sc,
      n_PLE = length(vals$PLE), n_DEP = length(vals$DEP), n_APS = length(vals$APS), n_SCZ = length(vals$SCZ),
      mean_PLE = m[["PLE"]], mean_DEP = m[["DEP"]], mean_APS = m[["APS"]], mean_SCZ = m[["SCZ"]],
      lower_intermediate = lowv, delta_lower = lo[["d"]], delta_lower_lo = lo[["lo"]], delta_lower_hi = lo[["hi"]],
      higher_intermediate = higv, delta_upper = hi[["d"]], delta_upper_lo = hi[["lo"]], delta_upper_hi = hi[["hi"]],
      concordant_primary = prim,
      concordant_uncertainty = prim && lo[["lo"]] > 0 && hi[["lo"]] > 0,
      rho_min = suppressWarnings(min(rho)), rho_all_gt_070 = all(!is.na(rho) & rho > 0.70),
      tableS4_matches = s4$matches_human_pattern[s4$model == mdl & s4$scale_type == sc]
    )
  }
}
cells <- bind_rows(cells) %>% arrange(language, scale_type, model)
stopifnot(nrow(cells) == 56, all(cells$concordant_primary == as.logical(cells$tableS4_matches)))
write_csv(cells, file.path(out9, "concordance_sensitivity_cells.csv"))
summ <- cells %>% group_by(language) %>% summarise(
  cells = n(), primary = sum(concordant_primary), uncertainty = sum(concordant_uncertainty),
  reliable_cells = sum(rho_all_gt_070), reliable_concordant = sum(rho_all_gt_070 & concordant_primary),
  reliable_concordant_uncertainty = sum(rho_all_gt_070 & concordant_uncertainty), .groups = "drop")
write_csv(summ, file.path(out9, "concordance_sensitivity_summary.csv"))
print(as.data.frame(summ))
cat("\nCells concordant under the primary rule but not under the uncertainty rule:\n")
print(as.data.frame(cells %>% filter(concordant_primary, !concordant_uncertainty) %>%
  transmute(language, model, scale_type, lower_intermediate, delta_lower = round(delta_lower, 3),
            lower_ci = sprintf("[%.3f, %.3f]", delta_lower_lo, delta_lower_hi),
            delta_upper = round(delta_upper, 3), upper_ci = sprintf("[%.3f, %.3f]", delta_upper_lo, delta_upper_hi))))

# ── Supplementary Table 10 ──────────────────────────────────────────────────
rt <- read_csv(file.path(an, "robust_temperature", "run_level_scale_scores.csv"), show_col_types = FALSE) %>%
        filter(model == "Claude Sonnet 4.5", in_primary == TRUE | in_primary == "True")
rt$temperature <- sprintf("%.1f", as.numeric(rt$temperature))
t10 <- list(); grad <- list()
for (lang in c("en", "zh")) for (sc in c("social_distance", "prejudice")) {
  mm <- list()
  for (tt in c("0.3", "1.0")) mm[[tt]] <- sapply(V, function(v) mean(rt$scale_score[rt$language == lang & rt$scale_type == sc & rt$vignette == v & rt$temperature == tt]))
  for (v in V) {
    a <- rt$scale_score[rt$language == lang & rt$scale_type == sc & rt$vignette == v & rt$temperature == "0.3"]
    b <- rt$scale_score[rt$language == lang & rt$scale_type == sc & rt$vignette == v & rt$temperature == "1.0"]
    d <- cd(b, a)
    t10[[length(t10) + 1]] <- tibble(language = lang, scale_type = sc, vignette = v,
      n_t03 = length(a), mean_t03 = mean(a), n_t10 = length(b), mean_t10 = mean(b),
      diff = mean(b) - mean(a), cliffs_delta = d[["d"]], delta_lo = d[["lo"]], delta_hi = d[["hi"]])
  }
  for (tt in c("0.3", "1.0")) {
    m <- mm[[tt]]
    grad[[length(grad) + 1]] <- tibble(language = lang, scale_type = sc, temperature = tt,
      concordant = strict(m), lower_margin = min(m[["DEP"]], m[["APS"]]) - m[["PLE"]],
      upper_margin = m[["SCZ"]] - max(m[["DEP"]], m[["APS"]]))
  }
}
t10 <- bind_rows(t10); grad <- bind_rows(grad)
write_csv(t10,  file.path(an, "robust_temperature", "supp_table10_cells.csv"))
write_csv(grad, file.path(an, "robust_temperature", "supp_table10_gradient.csv"))
cat("\nTemperature: max |diff| =", round(max(abs(t10$diff)), 3), "\n")
print(as.data.frame(grad %>% mutate(across(where(is.numeric), ~round(.x, 3)))))

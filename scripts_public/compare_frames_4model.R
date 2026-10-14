#!/usr/bin/env Rscript
# Elicitation sensitivity comparisons, 4 models (npj Digital Medicine revision).
# Reads the per-arm outputs of the unmodified analyze_stage1.R and writes
# analysis_sen_20260930/comparison/*.csv + fig_frame_delta_4model.{pdf,png}.
#
# Primary contrasts (comparator = concurrent item-by-item original prompt):
#   Humanlike - Original_oct     (R2-1, R1-4)
#   Fullscale - Original_oct     (R1-4 full-scale administration)
# Secondary: original_oct - original_pub (drift, R1-m3/R3-m2);
#            persona / fullscale - original_pub (time-confounded, always reported);
#            persona_rescored - original_oct_rescored (caveat re-scoring sensitivity).
# Runs in different arms are independent realisations: unpaired statistics only (R3-4).
#
# Usage: Rscript compare_frames_4model.R [analysis_sen_20260930]

suppressPackageStartupMessages({
  library(dplyr); library(readr); library(tidyr); library(ggplot2); library(effsize)
})
args <- commandArgs(trailingOnly = TRUE)
root <- if (length(args)) args[1] else "analysis_sen_20260930"
raw_root <- file.path(dirname(normalizePath(root)), "results_20260930_4models")
out <- file.path(root, "comparison"); dir.create(out, showWarnings = FALSE, recursive = TRUE)
ARMS <- c("Original_pub", "Original_oct", "Humanlike", "Fullscale", "Humanlike_rescored", "Original_oct_rescored")
arms <- ARMS[dir.exists(file.path(root, ARMS))]
langs <- c("en", "zh")
vig_order <- c("PLE", "DEP", "APS", "SCZ")
rd <- function(arm, f, lang = NULL) {
  p <- if (is.null(lang)) file.path(root, arm, f) else file.path(root, arm, lang, f)
  if (!file.exists(p)) return(NULL)
  d <- suppressMessages(read_csv(p, show_col_types = FALSE, guess_max = 1e5))
  d$arm <- arm; if (!is.null(lang)) d$language <- lang; d
}
stack <- function(f, per_lang = TRUE) bind_rows(lapply(arms, function(a)
  if (per_lang) bind_rows(lapply(langs, function(l) rd(a, f, l))) else rd(a, f)))

scores <- stack("run_level_scale_scores.csv") %>% filter(in_primary_analysis) %>%
  select(arm, language, model, vignette, scale_type, analysis_run, score = scale_score_primary)
write_csv(scores, file.path(out, "run_level_scores_all_arms.csv"))

# ---- cell summaries (n, mean, sd, t CI) ------------------------------------------
cells <- scores %>% group_by(arm, language, model, vignette, scale_type) %>%
  summarise(n = n(), mean = mean(score), sd = sd(score),
            ci_low = mean - qt(.975, pmax(n - 1, 1)) * sd / sqrt(n),
            ci_high = mean + qt(.975, pmax(n - 1, 1)) * sd / sqrt(n), .groups = "drop")
write_csv(cells, file.path(out, "cell_summary_by_arm.csv"))

# ---- contrasts: Welch mean difference + Cliff's delta (independent) -------------
welch <- function(x, y) {
  d <- mean(x) - mean(y)
  if (length(x) < 2 || length(y) < 2) return(c(d, NA, NA))
  if (sd(x) == 0 && sd(y) == 0) return(c(d, d, d))
  ci <- tryCatch(t.test(x, y, var.equal = FALSE)$conf.int, error = function(e) c(NA, NA))
  c(d, ci)
}
contrast <- function(a, b, family) {
  sa <- scores %>% filter(arm == a); sb <- scores %>% filter(arm == b)
  if (!nrow(sa) || !nrow(sb)) return(NULL)
  keys <- inner_join(distinct(sa, language, model, vignette, scale_type),
                     distinct(sb, language, model, vignette, scale_type),
                     by = c("language", "model", "vignette", "scale_type"))
  res <- lapply(seq_len(nrow(keys)), function(i) {
    k <- keys[i, ]
    x <- sa %>% semi_join(k, by = names(k)) %>% pull(score)
    y <- sb %>% semi_join(k, by = names(k)) %>% pull(score)
    w <- welch(x, y)
    cd <- tryCatch(effsize::cliff.delta(x, y, conf.level = 0.95, return.dm = TRUE), error = function(e) NULL)  # exact CI (2026-10-12)
    p <- tryCatch(suppressWarnings(wilcox.test(x, y, exact = FALSE)$p.value), error = function(e) NA)
    tibble(k, arm_a = a, arm_b = b, family = family, n_a = length(x), n_b = length(y),
           mean_a = mean(x), mean_b = mean(y), diff = w[1], diff_ci_low = w[2], diff_ci_high = w[3],
           cliffs_delta = if (is.null(cd)) NA else unname(cd$estimate),
           cliffs_low = if (is.null(cd)) NA else unname(cd$conf.int[1]),
           cliffs_high = if (is.null(cd)) NA else unname(cd$conf.int[2]),
           magnitude = if (is.null(cd)) NA else as.character(cd$magnitude), wilcox_p = p)
  })
  bind_rows(res) %>% mutate(wilcox_p_holm = p.adjust(wilcox_p, "holm"))
}
pairs <- list(c("Humanlike", "Original_oct", "Humanlike_vs_Original_oct"),
              c("Fullscale", "Original_oct", "Fullscale_vs_Original_oct"),
              c("Original_oct", "Original_pub", "Original_oct_vs_Original_pub"),
              c("Humanlike", "Original_pub", "Humanlike_vs_Original_pub"),
              c("Fullscale", "Original_pub", "Fullscale_vs_Original_pub"),
              c("Humanlike_rescored", "Original_oct_rescored", "Humanlike_rescored_vs_Original_oct_rescored"))
con <- bind_rows(lapply(pairs, function(p) contrast(p[1], p[2], p[3])))
write_csv(con, file.path(out, "contrasts_all.csv"))

# ---- P1/F1 gradient concordance (tableS4 = same code as published 13/28, 25/28) --
grad <- stack("tableS4_gradient_check.csv") %>%
  mutate(boundary_tie = (PLE == pmin(DEP, APS)) | (SCZ == pmax(DEP, APS)),
         strict_rule = (PLE < pmin(DEP, APS)) & (SCZ > pmax(DEP, APS)))
write_csv(grad, file.path(out, "gradient_by_arm.csv"))
grad_wide <- grad %>% select(language, model, scale_type, arm, matches_human_pattern) %>%
  pivot_wider(names_from = arm, values_from = matches_human_pattern)
write_csv(grad_wide, file.path(out, "gradient_agreement_wide.csv"))
grad_counts <- grad %>% group_by(arm, language) %>%
  summarise(cells = n(), concordant = sum(matches_human_pattern), strict_rule = sum(strict_rule),
            ties = sum(boundary_tie), .groups = "drop")
write_csv(grad_counts, file.path(out, "gradient_counts_by_arm.csv"))
agree <- function(a, b) if (all(c(a, b) %in% names(grad_wide)))
  grad_wide %>% filter(!is.na(.data[[a]]), !is.na(.data[[b]])) %>% group_by(language) %>%
  summarise(arm_a = a, arm_b = b, cells = n(), same_classification = sum(.data[[a]] == .data[[b]]), .groups = "drop")
write_csv(bind_rows(agree("Humanlike", "Original_oct"), agree("Fullscale", "Original_oct"),
                    agree("Original_oct", "Original_pub"), agree("Humanlike", "Original_pub"),
                    agree("Fullscale", "Original_pub")),
          file.path(out, "gradient_agreement_counts.csv"))

# ---- P3/F3 PLE - DEP gap within each arm ----------------------------------------
gap <- scores %>% filter(vignette %in% c("PLE", "DEP")) %>%
  group_by(arm, language, model, scale_type) %>%
  group_modify(function(d, k) {
    w <- welch(d$score[d$vignette == "PLE"], d$score[d$vignette == "DEP"])
    tibble(ple_minus_dep = w[1], ci_low = w[2], ci_high = w[3])
  }) %>% ungroup()
write_csv(gap, file.path(out, "ple_dep_gap_by_arm.csv"))

# ---- P4/F4 cross-language direction (tableS13 within each arm) --------------------
s13 <- stack("tableS13_language_comparison.csv", per_lang = FALSE)
xl <- s13 %>% group_by(arm) %>%
  summarise(dep_aps_scz_cells = sum(vignette != "PLE"),
            zh_higher_dep_aps_scz = sum(vignette != "PLE" & mean_diff_zh_minus_en > 0),
            ple_cells = sum(vignette == "PLE"),
            en_higher_ple = sum(vignette == "PLE" & mean_diff_zh_minus_en < 0),
            min_diff = min(mean_diff_zh_minus_en), max_diff = max(mean_diff_zh_minus_en), .groups = "drop")
write_csv(s13 %>% select(arm, model, vignette, scale_type, n_runs_en, n_runs_zh, mean_scale_en, mean_scale_zh,
                         mean_diff_zh_minus_en, cliffs_delta_zh_vs_en, direction),
          file.path(out, "crosslanguage_by_arm.csv"))
write_csv(xl, file.path(out, "crosslanguage_counts_by_arm.csv"))

# ---- P5/F5/F6 response types, API errors apart; format compliance; straightlining -
items <- bind_rows(lapply(arms, function(a) bind_rows(lapply(langs, function(l) {
  f <- list.files(file.path(root, a, l), pattern = "^results_.*\\.csv$", full.names = TRUE)
  if (!length(f)) return(NULL)
  d <- suppressMessages(read_csv(f[1], show_col_types = FALSE, col_types = cols(.default = "c")))
  d$arm <- a; d
}))))
items <- items %>% mutate(is_api = startsWith(raw_response, "[API_ERROR]"),
                          extra_text = response_type == "valid" & !grepl("^\\s*[1-4]\\.?\\s*$", raw_response))
resp <- items %>% group_by(arm, language, model) %>%
  summarise(items = n(), api_error = sum(is_api),
            valid = sum(response_type == "valid"),
            refusal_any = sum(grepl("^refusal", response_type)),
            refusal_identity = sum(response_type == "refusal_identity"),
            unparseable_excl_api = sum(response_type == "unparseable" & !is_api),
            valid_with_extra_text = sum(extra_text), .groups = "drop") %>%
  mutate(nonvalid_rate_excl_api = (items - api_error - valid) / (items - api_error))
write_csv(resp, file.path(out, "response_types_by_arm.csv"))

straight <- items %>% filter(response_type == "valid") %>%
  group_by(arm, language, model, run, vignette, scale_type) %>%
  summarise(n_valid = n(), n_distinct_answers = n_distinct(parsed_value), .groups = "drop") %>%
  mutate(full = (scale_type == "social_distance" & n_valid == 19) | (scale_type == "prejudice" & n_valid == 21)) %>%
  filter(full) %>% group_by(arm, language, model, scale_type) %>%
  summarise(complete_blocks = n(), straightlined = sum(n_distinct_answers == 1),
            straightline_rate = straightlined / complete_blocks, .groups = "drop")
write_csv(straight, file.path(out, "straightlining_by_arm.csv"))

if ("Fullscale" %in% arms) {
  fs_calls <- items %>% filter(arm == "Fullscale") %>% group_by(language, model, run, vignette) %>%
    summarise(items_valid = sum(response_type == "valid"), api_error = any(is_api),
              whole_call_refusal = all(grepl("^refusal", response_type)), .groups = "drop")
  calls_files <- list.files(raw_root, pattern = "^Fullscale_calls_.*\\.jsonl$", full.names = TRUE)
  trunc <- if (length(calls_files)) bind_rows(lapply(calls_files, function(f) {
    L <- readLines(f, warn = FALSE); L <- L[nzchar(L)]
    bind_rows(lapply(L, function(x) { j <- jsonlite::fromJSON(x)
      tibble(model_key = j$model_key, language = j$lang, run = as.character(j$run), vignette = j$vignette,
             truncated = isTRUE(j$parse_info$truncated)) }))
  })) else NULL
  fs_summary <- fs_calls %>% group_by(language, model) %>%
    summarise(calls = n(), all_40_valid = sum(items_valid == 40), mean_items_valid = mean(items_valid),
              whole_call_refusal = sum(whole_call_refusal), api_error_calls = sum(api_error), .groups = "drop")
  if (!is.null(trunc)) {
    tsum <- trunc %>% group_by(model_key, language) %>% summarise(truncated_calls = sum(truncated), .groups = "drop")
    write_csv(tsum, file.path(out, "Fullscale_truncation.csv"))
  }
  write_csv(fs_summary, file.path(out, "Fullscale_completeness.csv"))
}

# ---- S3 reliability, S4 human distance (ZH, descriptive only), S5 flow --------
rel <- stack("tableS3_reliability.csv")
write_csv(rel %>% select(arm, language, model, vignette, scale_type, n_complete_runs,
                         mean_pairwise_spearman, icc2k, reliability_flag),
          file.path(out, "reliability_by_arm.csv"))
s9 <- stack("tableS9_ai_vs_human.csv") %>% filter(language_match == "matched")
write_csv(s9 %>% select(arm, language, model, vignette, scale_type, ai_mean, human_mean, human_sd, human_sd_units),
          file.path(out, "human_distance_zh_by_arm.csv"))
flow <- items %>% group_by(arm, language) %>%
  summarise(item_rows = n(), api_error = sum(is_api), valid = sum(response_type == "valid"),
            refusal_any = sum(grepl("^refusal", response_type)),
            unparseable_excl_api = sum(response_type == "unparseable" & !is_api), .groups = "drop") %>%
  left_join(stack("run_level_scale_scores.csv") %>% group_by(arm, language) %>%
              summarise(run_cells = n(), run_cells_primary = sum(in_primary_analysis), .groups = "drop"),
            by = c("arm", "language"))
write_csv(flow, file.path(out, "flow_counts_by_arm.csv"))

# ---- figure: primary contrasts ---------------------------------------------------
if (!nrow(con) || !"family" %in% names(con)) con <- tibble(family = character(), scale_type = character(),
  vignette = character(), language = character(), model = character(), diff = numeric(),
  diff_ci_low = numeric(), diff_ci_high = numeric())
fig <- con %>% filter(.data$family %in% c("Humanlike_vs_Original_oct", "Fullscale_vs_Original_oct")) %>%
  mutate(contrast = recode(family, Humanlike_vs_Original_oct = "Humanlike − Original_oct",
                           Fullscale_vs_Original_oct = "Fullscale − Original_oct"),
         contrast = factor(contrast, levels = c("Humanlike − Original_oct", "Fullscale − Original_oct")),
         vignette = factor(vignette, levels = vig_order),
         scale = recode(scale_type, social_distance = "Social Distance", prejudice = "Prejudice"),
         language = recode(language, en = "English", zh = "Mandarin Chinese"))
if (nrow(fig)) {
  g <- ggplot(fig, aes(x = diff, y = model, colour = language)) +
    geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50") +
    geom_errorbarh(aes(xmin = diff_ci_low, xmax = diff_ci_high), height = 0,
                   position = position_dodge(width = 0.5)) +
    geom_point(position = position_dodge(width = 0.5), size = 1.8) +
    facet_grid(contrast + scale ~ vignette) +
    scale_colour_manual(values = c("English" = "#1F77B4", "Mandarin Chinese" = "#D62728")) +
    labs(x = "Difference in scale score (95% CI)", y = NULL, colour = NULL) +
    theme_bw(base_family = "Helvetica", base_size = 9) + theme(legend.position = "bottom")
  ggsave(file.path(out, "fig_frame_delta_4model.pdf"), g, width = 9, height = 8)
  ggsave(file.path(out, "fig_frame_delta_4model.png"), g, width = 9, height = 8, dpi = 300)
}
cat("comparison written to", out, "\n")
print(as.data.frame(grad_counts)); print(as.data.frame(xl))

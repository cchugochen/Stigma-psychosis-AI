#!/usr/bin/env Rscript
# =============================================================================
# AI Mental Illness Stigma Study — Stage 1 Analysis Pipeline (v0419)
# Merges: analyze_results.R + compare_language_results.R + generate_tables.R
#
# Usage:
#   Rscript scripts/analyze_stage1.R <analysis_dir>
#   e.g.: Rscript scripts/analyze_stage1.R analysis_13models_20260419/
#
# Expected layout of <analysis_dir>:
#   en/results_NNmodels_en.csv
#   zh/results_NNmodels_zh.csv
#
# Outputs per language subfolder (en/ and zh/):
#   run_level_scale_scores.csv
#   tableS1_missingness.csv           tableS2_descriptive_stats.csv
#   tableS3_reliability.csv           tableS4_gradient_check.csv
#   tableS5_vignette_omnibus.csv      tableS6_vignette_pairwise.csv
#   tableS7_model_omnibus.csv         tableS8_model_pairwise.csv
#   tableS9_ai_vs_human.csv           tableS10_sensitivity_descriptive.csv
#   tableS11_sensitivity_omnibus.csv
#   table2_en_stigma_scores.csv  (EN only)
#   table3_zh_stigma_scores.csv  (ZH only)
#   figures/
#
# Outputs at analysis root:
#   tableS12_language_descriptives.csv  tableS13_language_comparison.csv
#   tableS14_language_by_model.csv      tableS15_language_by_vignette.csv
#   table1_response_classification.csv  table4_cross_language_shift.csv
#   fig5_cross_language_forest_plot.{pdf,png}
#   fig6_cross_language_heatmap.{pdf,png}
#   fig7_response_classification.{pdf,png}
#
# Table 5 (item-level profile) is generated separately:
#   Rscript scripts/item_level_profile.R <analysis_dir>
# =============================================================================

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tidyr)
  library(ggplot2)
  library(effsize)
  library(ggdendro)
  library(patchwork)
  library(tibble)
})

# =============================================================================
# SHARED CONSTANTS — 13-model v0419 protocol (Qwen3.5 35B removed)
# =============================================================================

min_scale_completeness      <- 0.80
min_runs_for_inference      <- 5
min_complete_runs_for_alpha <- 10
vignette_order <- c("PLE", "DEP", "APS", "SCZ")
scale_order    <- c("social_distance", "prejudice")

model_order <- c(
  "GPT-3.5",
  "GPT-4o",
  "GPT-OSS-120B",
  "GPT-5.4",
  "GPT-5.4 Mini",
  "Claude Sonnet 4.5",
  "Claude Opus 4.6",
  "Gemini 2.5 Flash",
  "Gemini 3.1 Pro Preview",
  "Gemini 3.1 Flash-Lite Preview",
  "Gemma 4 31B IT",
  "Llama 3.3 70B",
  "DeepSeek V3.2"
)

model_labels <- c(
  "GPT-3.5"               = "GPT-3.5 (2022/11)",
  "GPT-4o"                = "GPT-4o (2024/05)",
  "Llama 3.3 70B"         = "Llama 3.3 70B (2024/12)",
  "Gemini 2.5 Flash"      = "Gemini 2.5 Flash (2025/03)",
  "GPT-OSS-120B"          = "GPT-OSS-120B (2025/08)",
  "Claude Sonnet 4.5"     = "Claude Sonnet 4.5 (2025/09)",
  "DeepSeek V3.2"         = "DeepSeek V3.2 (2025/12)",
  "Claude Opus 4.6"       = "Claude Opus 4.6 (2026/02)",
  "Gemini 3.1 Pro Preview"        = "Gemini 3.1 Pro Preview (2026/03)",
  "Gemini 3.1 Flash-Lite Preview" = "Gemini 3.1 Flash-Lite Preview (2026/03)",
  "GPT-5.4"               = "GPT-5.4 (2026/03)",
  "GPT-5.4 Mini"          = "GPT-5.4 Mini (2026/03)",
  "Gemma 4 31B IT"        = "Gemma 4 31B IT (2026/04)"
)

model_family <- c(
  "GPT-3.5"               = "GPT",
  "GPT-4o"                = "GPT",
  "GPT-OSS-120B"          = "GPT",
  "GPT-5.4"               = "GPT",
  "GPT-5.4 Mini"          = "GPT",
  "Claude Sonnet 4.5"     = "Claude",
  "Claude Opus 4.6"       = "Claude",
  "Gemini 2.5 Flash"      = "Gemini",
  "Gemini 3.1 Pro Preview"        = "Gemini Pro",
  "Gemini 3.1 Flash-Lite Preview" = "Gemini",
  "Gemma 4 31B IT"        = "Gemini",
  "Llama 3.3 70B"         = "Llama",
  "DeepSeek V3.2"         = "DeepSeek"
)

model_deployment <- c(
  "GPT-3.5"               = "API",
  "GPT-4o"                = "API",
  "GPT-OSS-120B"          = "Open-source",
  "GPT-5.4"               = "API",
  "GPT-5.4 Mini"          = "API",
  "Claude Sonnet 4.5"     = "API",
  "Claude Opus 4.6"       = "API",
  "Gemini 2.5 Flash"      = "API",
  "Gemini 3.1 Pro Preview"        = "API",
  "Gemini 3.1 Flash-Lite Preview" = "API",
  "Gemma 4 31B IT"        = "Open-source",
  "Llama 3.3 70B"         = "Open-source",
  "DeepSeek V3.2"         = "Open-source"
)

family_colors <- c(
  "GPT-3.5"               = "#1B5E20",
  "GPT-4o"                = "#2E7D32",
  "GPT-OSS-120B"          = "#A5D6A7",
  "GPT-5.4"               = "#388E3C",
  "GPT-5.4 Mini"          = "#66BB6A",
  "Claude Sonnet 4.5"     = "#FF9800",
  "Claude Opus 4.6"       = "#E65100",
  "Gemini 2.5 Flash"      = "#0D47A1",
  "Gemini 3.1 Pro Preview"        = "#1565C0",
  "Gemini 3.1 Flash-Lite Preview" = "#42A5F5",
  "Gemma 4 31B IT"        = "#90CAF9",
  "Llama 3.3 70B"         = "#6A1B9A",
  "DeepSeek V3.2"         = "#C62828"
)

family_group_colors <- c(
  "GPT"        = "#2E7D32",
  "Claude"     = "#E65100",
  "Gemini"     = "#1565C0",
  "Gemini Pro" = "#1565C0",
  "Llama"      = "#6A1B9A",
  "DeepSeek"   = "#C62828"
)

deployment_shapes <- c("API" = 16, "Open-source" = 5)

model_release_dates <- c(
  "GPT-3.5"               = "2022-11-30",
  "GPT-4o"                = "2024-05-13",
  "Llama 3.3 70B"         = "2024-12-06",
  "Gemini 2.5 Flash"      = "2025-03-25",
  "GPT-OSS-120B"          = "2025-08-01",
  "Claude Sonnet 4.5"     = "2025-09-29",
  "DeepSeek V3.2"         = "2025-12-01",
  "Claude Opus 4.6"       = "2026-02-01",
  "Gemini 3.1 Pro Preview"        = "2026-03-01",
  "Gemini 3.1 Flash-Lite Preview" = "2026-03-01",
  "GPT-5.4"               = "2026-03-01",
  "GPT-5.4 Mini"          = "2026-03-01",
  "Gemma 4 31B IT"        = "2026-04-01"
)

# Plot order: GPT-3.5 baseline first, then GPT > Claude > Gemini > Other
# DeepSeek last as cross-cultural focus
model_plot_order <- c(
  "GPT-3.5",
  "GPT-4o",
  "GPT-OSS-120B",
  "GPT-5.4",
  "GPT-5.4 Mini",
  "Claude Sonnet 4.5",
  "Claude Opus 4.6",
  "Gemini 2.5 Flash",
  "Gemini 3.1 Pro Preview",
  "Gemini 3.1 Flash-Lite Preview",
  "Gemma 4 31B IT",
  "Llama 3.3 70B",
  "DeepSeek V3.2"
)

model_short_labels <- c(
  "GPT-3.5"               = "GPT-3.5",
  "GPT-4o"                = "GPT-4o",
  "GPT-OSS-120B"          = "GPT-OSS",
  "GPT-5.4"               = "GPT-5.4",
  "GPT-5.4 Mini"          = "GPT-5.4m",
  "Claude Sonnet 4.5"     = "Sonnet\n4.5",
  "Claude Opus 4.6"       = "Opus\n4.6",
  "Gemini 2.5 Flash"      = "G2.5\nFlash",
  "Gemini 3.1 Pro Preview"        = "G3.1 Pro",
  "Gemini 3.1 Flash-Lite Preview" = "G3.1\nF-Lite",
  "Gemma 4 31B IT"        = "Gemma 4",
  "Llama 3.3 70B"         = "Llama\n3.3",
  "DeepSeek V3.2"         = "DeepSeek"
)

human_baselines <- tribble(
  ~vignette, ~scale_type,       ~human_mean, ~human_sd, ~human_n, ~human_language,
  "SCZ",     "social_distance", 53.55,       9.10,      268,      "zh",
  "APS",     "social_distance", 47.98,       8.86,      268,      "zh",
  "DEP",     "social_distance", 48.10,       9.46,      268,      "zh",
  "PLE",     "social_distance", 38.78,       9.17,      268,      "zh",
  "SCZ",     "prejudice",       52.62,       7.21,      268,      "zh",
  "APS",     "prejudice",       48.13,       6.94,      268,      "zh",
  "DEP",     "prejudice",       48.56,       7.56,      268,      "zh",
  "PLE",     "prejudice",       42.25,       9.32,      268,      "zh"
)

# =============================================================================
# SHARED HELPER FUNCTIONS
# =============================================================================

run_reliability_metrics <- function(items_matrix, min_complete_runs = 10) {
  complete_matrix <- items_matrix[stats::complete.cases(items_matrix), , drop = FALSE]
  n_complete_runs <- nrow(complete_matrix)
  k <- ncol(complete_matrix)

  base <- tibble(
    n_complete_runs        = n_complete_runs,
    n_items                = k,
    icc2k                  = NA_real_,
    icc2k_low              = NA_real_,
    icc2k_high             = NA_real_,
    mean_pairwise_spearman = NA_real_,
    zero_variance_items    = NA_integer_,
    reliability_flag       = NA_character_
  )

  if (k < 2) {
    base$reliability_flag <- "fewer_than_two_items"
    return(base)
  }
  if (n_complete_runs < min_complete_runs) {
    base$n_items <- k
    base$reliability_flag <- "insufficient_complete_runs"
    return(base)
  }

  item_vars <- apply(complete_matrix, 2, stats::var)
  base$zero_variance_items <- sum(item_vars == 0, na.rm = TRUE)

  long_df <- data.frame(
    run   = factor(rep(seq_len(n_complete_runs), times = k)),
    item  = factor(rep(seq_len(k), each = n_complete_runs)),
    value = as.numeric(complete_matrix)
  )

  icc_result <- tryCatch({
    fit  <- stats::aov(value ~ run + item, data = long_df)
    ms   <- summary(fit)[[1]][, "Mean Sq"]
    MSR  <- ms[1]; MSC <- ms[2]; MSE <- ms[3]
    n_r  <- n_complete_runs; n_c <- k
    denom <- MSR + (MSC - MSE) / n_r
    if (!is.finite(denom) || denom <= 0) {
      list(est = NA_real_, low = NA_real_, high = NA_real_)
    } else {
      est   <- (MSR - MSE) / denom
      F_obs <- MSR / MSE
      df1   <- n_r - 1
      df2   <- (n_r - 1) * (n_c - 1)
      F_L   <- F_obs / stats::qf(0.975, df1, df2)
      F_U   <- F_obs * stats::qf(0.975, df2, df1)
      low   <- (F_L - 1) / (F_L - 1 + n_c * (MSC / MSE + 1) / n_r)
      high  <- (F_U - 1) / (F_U - 1 + n_c * (MSC / MSE + 1) / n_r)
      list(est = est, low = low, high = high)
    }
  }, error = function(e) list(est = NA_real_, low = NA_real_, high = NA_real_))

  base$icc2k      <- icc_result$est
  base$icc2k_low  <- icc_result$low
  base$icc2k_high <- icc_result$high

  if (n_complete_runs >= 2) {
    pair_rhos <- c()
    for (i in seq_len(n_complete_runs - 1)) {
      for (j in seq((i + 1), n_complete_runs)) {
        if (stats::sd(complete_matrix[i, ], na.rm = TRUE) > 0 &&
            stats::sd(complete_matrix[j, ], na.rm = TRUE) > 0) {
          rho <- suppressWarnings(stats::cor(
            complete_matrix[i, ], complete_matrix[j, ], method = "spearman"
          ))
          if (is.finite(rho)) pair_rhos <- c(pair_rhos, rho)
        }
      }
    }
    base$mean_pairwise_spearman <- if (length(pair_rhos) > 0) mean(pair_rhos) else NA_real_
  }

  base$reliability_flag <- if (!is.finite(base$icc2k)) {
    "unstable_icc"
  } else if (!is.na(base$zero_variance_items) && base$zero_variance_items == k &&
             !is.na(base$mean_pairwise_spearman) && base$mean_pairwise_spearman >= 0.999) {
    "perfect_agreement"
  } else {
    "ok"
  }
  base
}

# Returns a tibble with Cliff's delta + 95% CI (uses effsize package)
safe_cliff_delta <- function(x, y) {
  out <- tryCatch(
    suppressWarnings(effsize::cliff.delta(x, y, conf.level = 0.95)),
    error = function(e) NULL
  )
  if (is.null(out)) {
    return(tibble(
      cliffs_delta = NA_real_, cliffs_delta_low = NA_real_,
      cliffs_delta_high = NA_real_, magnitude = NA_character_
    ))
  }
  tibble(
    cliffs_delta      = unname(out$estimate),
    cliffs_delta_low  = if (!is.null(out$conf.int)) out$conf.int[[1]] else NA_real_,
    cliffs_delta_high = if (!is.null(out$conf.int)) out$conf.int[[2]] else NA_real_,
    magnitude         = as.character(out$magnitude)
  )
}

# Scalar Cliff's delta without CI (used in cross-language comparison)
cliff_delta_scalar <- function(x, y) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  wins <- 0; losses <- 0
  for (xi in x) { wins <- wins + sum(xi > y); losses <- losses + sum(xi < y) }
  (wins - losses) / (length(x) * length(y))
}

theme_journal <- function(base_size = 11) {
  theme_classic(base_size = base_size) +
    theme(
      text             = element_text(family = "Helvetica"),
      strip.background = element_rect(fill = "grey92", color = NA),
      strip.text       = element_text(face = "bold", size = base_size),
      axis.line        = element_line(color = "grey30"),
      panel.spacing    = unit(0.8, "lines"),
      legend.position  = "bottom",
      legend.title     = element_text(face = "bold"),
      plot.title       = element_text(face = "bold", size = base_size + 1),
      plot.subtitle    = element_text(size = base_size - 1, color = "grey40"),
      plot.caption     = element_text(size = base_size - 2, color = "grey50", hjust = 0)
    )
}

make_model_label_pub <- function(m) {
  m <- as.character(m)
  display <- dplyr::recode(m,
    "Gemini 3.1 Pro Preview"        = "Gemini 3.1 Pro Preview",
    "Gemini 3.1 Flash-Lite Preview" = "Gemini 3.1 Flash-Lite Preview",
    .default = m
  )
  dep <- unname(ifelse(m %in% names(model_deployment), model_deployment[[m]], ""))
  paste0(display, " (", dep, ")")
}

format_stigma_table <- function(comparison_df) {
  scale_abbrev <- c("social_distance" = "Social Distance", "prejudice" = "Prejudice")
  vig_order    <- c("PLE", "DEP", "APS", "SCZ")
  tbl <- comparison_df %>%
    mutate(
      ci_str = ifelse(
        !is.na(ai_ci_low),
        sprintf("%.1f [%.1f, %.1f]", ai_mean, ai_ci_low, ai_ci_high),
        NA_character_
      ),
      scale_label = scale_abbrev[scale_type],
      vignette    = factor(vignette, levels = vig_order)
    ) %>%
    filter(!is.na(ci_str)) %>%
    select(model, scale_label, vignette, ci_str) %>%
    pivot_wider(names_from = vignette, values_from = ci_str) %>%
    arrange(model, scale_label)
  present   <- model_plot_order[model_plot_order %in% unique(tbl$model)]
  extra     <- sort(setdiff(unique(tbl$model), model_plot_order))
  model_seq <- c(present, extra)
  tbl %>%
    mutate(
      model_label = sapply(model, make_model_label_pub),
      model       = factor(model, levels = model_seq)
    ) %>%
    arrange(model, scale_label) %>%
    select(model_label, Scale = scale_label, PLE, DEP, APS, SCZ)
}

# =============================================================================
# STAGE 1A: SINGLE-LANGUAGE ANALYSIS
# run_language_analysis(csv_path, results_dir, lang_tag)
#   csv_path    — path to raw results CSV
#   results_dir — output directory for this language (en/ or zh/)
#   lang_tag    — "en" or "zh"
# =============================================================================

run_language_analysis <- function(csv_path, results_dir, lang_tag) {
  lang_suffix  <- paste0("_", lang_tag)
  lang_label   <- toupper(lang_tag)
  figures_dir  <- file.path(results_dir, "figures")

  dir.create(results_dir, recursive = TRUE, showWarnings = FALSE)
  dir.create(figures_dir, showWarnings = FALSE, recursive = TRUE)

  # -- Load data ---------------------------------------------------------------
  raw_data <- read_csv(csv_path, show_col_types = FALSE) %>%
    mutate(
      row_id       = row_number(),
      run          = as.character(run),
      scored_value = as.numeric(scored_value)
    )

  present_vignettes <- vignette_order[vignette_order %in% unique(raw_data$vignette)]
  present_models    <- model_order[model_order %in% unique(raw_data$model)]

  if (length(present_vignettes) == 0) stop("No recognized vignette labels in: ", csv_path)

  raw_data <- raw_data %>%
    mutate(
      model      = factor(model, levels = present_models),
      vignette   = factor(vignette, levels = present_vignettes),
      scale_type = factor(scale_type, levels = scale_order),
      item_key   = paste(vignette, scale_type, item_id, sep = "|")
    ) %>%
    group_by(model, run) %>%
    arrange(row_id, .by_group = TRUE) %>%
    mutate(
      block_index  = cumsum(item_key == first(item_key)),
      analysis_run = paste(run, block_index, sep = "_")
    ) %>%
    ungroup() %>%
    select(-item_key, -block_index)

  valid_responses <- sum(!is.na(raw_data$scored_value))
  cat("Loaded", valid_responses, "valid responses [", lang_label, "] from", csv_path, "\n")

  # -- Scale scores ------------------------------------------------------------
  expected_items <- raw_data %>%
    distinct(scale_type, item_id) %>%
    count(scale_type, name = "expected_items")

  scale_scores <- raw_data %>%
    left_join(expected_items, by = "scale_type") %>%
    group_by(model, vignette, scale_type, analysis_run) %>%
    summarise(
      expected_items           = first(expected_items),
      items_answered           = sum(!is.na(scored_value)),
      item_mean                = ifelse(items_answered > 0, mean(scored_value, na.rm = TRUE), NA_real_),
      scale_score_complete     = ifelse(items_answered == expected_items, sum(scored_value, na.rm = TRUE), NA_real_),
      completeness             = items_answered / expected_items,
      .groups = "drop"
    ) %>%
    mutate(
      scale_score_primary         = ifelse(
        items_answered > 0 & completeness >= min_scale_completeness,
        item_mean * expected_items, NA_real_
      ),
      in_primary_analysis         = !is.na(scale_score_primary),
      in_complete_case_analysis   = !is.na(scale_score_complete)
    )

  write_csv(scale_scores, file.path(results_dir, "run_level_scale_scores.csv"))

  # -- S1: Missingness ---------------------------------------------------------
  missingness_summary <- scale_scores %>%
    group_by(model, vignette, scale_type) %>%
    summarise(
      n_run_blocks        = n(),
      n_primary           = sum(in_primary_analysis),
      n_complete          = sum(in_complete_case_analysis),
      mean_completeness   = mean(completeness),
      median_completeness = median(completeness),
      min_completeness    = min(completeness),
      .groups = "drop"
    )
  write_csv(missingness_summary, file.path(results_dir, "tableS1_missingness.csv"))

  # -- S2: Descriptive statistics ----------------------------------------------
  desc_stats <- scale_scores %>%
    filter(in_primary_analysis) %>%
    group_by(model, vignette, scale_type) %>%
    summarise(
      n_runs           = n(),
      n_complete_runs  = sum(in_complete_case_analysis),
      mean_scale       = mean(scale_score_primary),
      sd_scale         = sd(scale_score_primary),
      median_scale     = median(scale_score_primary),
      iqr_scale        = IQR(scale_score_primary),
      min_scale        = min(scale_score_primary),
      max_scale        = max(scale_score_primary),
      mean_item        = mean(item_mean),
      mean_completeness = mean(completeness),
      .groups = "drop"
    )
  write_csv(desc_stats, file.path(results_dir, "tableS2_descriptive_stats.csv"))

  # -- S5/S6: Within-model vignette comparison ---------------------------------
  cat("\n--- Within-model vignette effects [", lang_label, "] ---\n")
  within_omnibus  <- list()
  within_pairwise <- list()

  for (m in levels(raw_data$model)) {
    for (st in scale_order) {
      wide_scores <- scale_scores %>%
        filter(model == m, scale_type == st) %>%
        select(analysis_run, vignette, scale_score_primary) %>%
        pivot_wider(names_from = vignette, values_from = scale_score_primary)

      avail <- intersect(present_vignettes, names(wide_scores))
      avail <- avail[vapply(avail, function(v) any(!is.na(wide_scores[[v]])), logical(1))]
      if (length(avail) < 2) next

      omnibus_row <- tibble(
        model = m, scale_type = st, method = NA_character_,
        n_vignettes = length(avail), n_blocks = NA_integer_,
        statistic = NA_real_, df = NA_real_, p_value = NA_real_, note = NA_character_
      )

      if (length(avail) >= 3) {
        cw <- wide_scores %>% select(all_of(avail)) %>% drop_na()
        nb <- nrow(cw)
        if (nb >= min_runs_for_inference) {
          fr <- stats::friedman.test(as.matrix(cw))
          omnibus_row <- omnibus_row %>% mutate(
            method = "Friedman matched-run test", n_blocks = nb,
            statistic = unname(fr$statistic), df = unname(fr$parameter),
            p_value = fr$p.value,
            note = paste("Complete matched vignette blocks:", paste(avail, collapse = ", "))
          )
        } else {
          omnibus_row <- omnibus_row %>% mutate(
            method = "Friedman matched-run test", n_blocks = nb,
            note = "Insufficient complete matched run blocks for omnibus inference"
          )
        }
      } else {
        pb <- wide_scores %>% select(all_of(avail)) %>% drop_na()
        np <- nrow(pb)
        if (np >= min_runs_for_inference) {
          wr <- suppressWarnings(stats::wilcox.test(pb[[avail[1]]], pb[[avail[2]]], paired = TRUE, exact = FALSE))
          omnibus_row <- omnibus_row %>% mutate(
            method = "Paired Wilcoxon signed-rank test", n_blocks = np,
            statistic = unname(wr$statistic), p_value = wr$p.value,
            note = paste("Compared", paste(avail, collapse = " vs "))
          )
        } else {
          omnibus_row <- omnibus_row %>% mutate(
            method = "Paired Wilcoxon signed-rank test", n_blocks = np,
            note = "Insufficient paired runs for inference"
          )
        }
      }
      within_omnibus[[length(within_omnibus) + 1]] <- omnibus_row

      pair_rows <- list()
      for (pair in combn(avail, 2, simplify = FALSE)) {
        pb <- wide_scores %>% select(all_of(pair)) %>% drop_na()
        np <- nrow(pb)
        if (np < min_runs_for_inference) {
          pair_rows[[length(pair_rows) + 1]] <- tibble(
            model = m, scale_type = st, vignette_1 = pair[1], vignette_2 = pair[2],
            n_pairs = np, statistic = NA_real_, median_difference = NA_real_,
            p_raw = NA_real_, note = "Insufficient paired runs"
          )
          next
        }
        wr <- suppressWarnings(stats::wilcox.test(pb[[pair[1]]], pb[[pair[2]]], paired = TRUE, exact = FALSE))
        pair_rows[[length(pair_rows) + 1]] <- tibble(
          model = m, scale_type = st, vignette_1 = pair[1], vignette_2 = pair[2],
          n_pairs = np, statistic = unname(wr$statistic),
          median_difference = median(pb[[pair[1]]] - pb[[pair[2]]]),
          p_raw = wr$p.value, note = NA_character_
        )
      }
      if (length(pair_rows) > 0) {
        pairwise_df <- bind_rows(pair_rows) %>%
          mutate(
            p_adjusted  = ifelse(!is.na(p_raw), p.adjust(p_raw, method = "holm"), NA_real_),
            significant = ifelse(!is.na(p_adjusted), p_adjusted < 0.05, NA)
          )
        within_pairwise[[length(within_pairwise) + 1]] <- pairwise_df
      }
    }
  }

  write_csv(bind_rows(within_omnibus),  file.path(results_dir, "tableS5_vignette_omnibus.csv"))
  write_csv(bind_rows(within_pairwise), file.path(results_dir, "tableS6_vignette_pairwise.csv"))

  # -- S7/S8: Between-model comparison -----------------------------------------
  cat("--- Between-model comparisons [", lang_label, "] ---\n")
  between_omnibus  <- list()
  between_pairwise <- list()

  for (vig in present_vignettes) {
    for (st in scale_order) {
      run_scores_cell <- scale_scores %>%
        filter(vignette == vig, scale_type == st, in_primary_analysis) %>%
        select(model, analysis_run, scale_score_primary)

      group_sizes       <- run_scores_cell %>% count(model, name = "n_runs")
      analyzable_models <- as.character(group_sizes$model[group_sizes$n_runs >= min_runs_for_inference])
      if (length(analyzable_models) < 2) next

      run_scores_cell <- run_scores_cell %>% filter(as.character(model) %in% analyzable_models)

      omnibus_row <- tibble(
        vignette = vig, scale_type = st, method = NA_character_,
        n_models = length(analyzable_models), statistic = NA_real_,
        df = NA_real_, p_value = NA_real_, note = NA_character_
      )

      if (length(analyzable_models) >= 3) {
        kw <- stats::kruskal.test(scale_score_primary ~ model, data = run_scores_cell)
        omnibus_row <- omnibus_row %>% mutate(
          method = "Kruskal-Wallis test",
          statistic = unname(kw$statistic), df = unname(kw$parameter), p_value = kw$p.value,
          note = paste("Models:", paste(analyzable_models, collapse = ", "))
        )
      } else {
        wr <- suppressWarnings(stats::wilcox.test(scale_score_primary ~ model, data = run_scores_cell, exact = FALSE))
        omnibus_row <- omnibus_row %>% mutate(
          method = "Wilcoxon rank-sum test",
          statistic = unname(wr$statistic), p_value = wr$p.value,
          note = paste("Models:", paste(analyzable_models, collapse = " vs "))
        )
      }
      between_omnibus[[length(between_omnibus) + 1]] <- omnibus_row

      pair_rows <- list()
      for (pair in combn(analyzable_models, 2, simplify = FALSE)) {
        g1 <- run_scores_cell %>% filter(as.character(model) == pair[1]) %>% pull(scale_score_primary)
        g2 <- run_scores_cell %>% filter(as.character(model) == pair[2]) %>% pull(scale_score_primary)
        if (length(g1) < min_runs_for_inference || length(g2) < min_runs_for_inference) {
          pair_rows[[length(pair_rows) + 1]] <- tibble(
            vignette = vig, scale_type = st, model_1 = pair[1], model_2 = pair[2],
            n_1 = length(g1), n_2 = length(g2), statistic = NA_real_,
            median_difference = NA_real_, p_raw = NA_real_,
            cliffs_delta = NA_real_, cliffs_delta_low = NA_real_,
            cliffs_delta_high = NA_real_, magnitude = NA_character_,
            note = "Insufficient runs"
          )
          next
        }
        wr     <- suppressWarnings(stats::wilcox.test(g1, g2, exact = FALSE))
        cliffs <- safe_cliff_delta(g1, g2)
        pair_rows[[length(pair_rows) + 1]] <- tibble(
          vignette = vig, scale_type = st, model_1 = pair[1], model_2 = pair[2],
          n_1 = length(g1), n_2 = length(g2),
          statistic = unname(wr$statistic),
          median_difference = median(g1) - median(g2),
          p_raw = wr$p.value, note = NA_character_
        ) %>% bind_cols(cliffs)
      }
      if (length(pair_rows) > 0) {
        pairwise_df <- bind_rows(pair_rows) %>%
          mutate(
            p_adjusted  = ifelse(!is.na(p_raw), p.adjust(p_raw, method = "holm"), NA_real_),
            significant = ifelse(!is.na(p_adjusted), p_adjusted < 0.05, NA)
          )
        between_pairwise[[length(between_pairwise) + 1]] <- pairwise_df
      }
    }
  }

  write_csv(bind_rows(between_omnibus),  file.path(results_dir, "tableS7_model_omnibus.csv"))
  write_csv(bind_rows(between_pairwise), file.path(results_dir, "tableS8_model_pairwise.csv"))

  # -- S4: Stigma gradient check -----------------------------------------------
  gradient_test <- desc_stats %>%
    group_by(model, vignette, scale_type) %>%
    summarise(mean_score = mean(mean_scale), .groups = "drop") %>%
    pivot_wider(names_from = vignette, values_from = mean_score)

  gradient_rows <- list()
  for (m in unique(gradient_test$model)) {
    for (st in scale_order) {
      row <- gradient_test %>% filter(model == m, scale_type == st)
      if (nrow(row) != 1) next
      score_lookup <- stats::setNames(rep(NA_real_, length(vignette_order)), vignette_order)
      score_lookup[present_vignettes] <- as.numeric(row[present_vignettes])
      scores  <- score_lookup[!is.na(score_lookup)]
      ordered <- names(sort(scores))
      matches_human <- length(ordered) == 4 &&
        (identical(ordered, c("PLE", "DEP", "APS", "SCZ")) ||
         identical(ordered, c("PLE", "APS", "DEP", "SCZ")))
      gradient_note <- if (length(ordered) < 4) "partial dataset: full human gradient not testable" else
                       if (matches_human) "matches human pattern" else "differs"
      gradient_rows[[length(gradient_rows) + 1]] <- tibble(
        model = m, scale_type = st,
        n_vignettes_tested = length(ordered),
        observed_order = paste(ordered, collapse = " -> "),
        matches_human_pattern = if (length(ordered) == 4) matches_human else NA,
        gradient_note = gradient_note,
        PLE = score_lookup[["PLE"]], DEP = score_lookup[["DEP"]],
        APS = score_lookup[["APS"]], SCZ = score_lookup[["SCZ"]]
      )
    }
  }
  write_csv(bind_rows(gradient_rows), file.path(results_dir, "tableS4_gradient_check.csv"))

  # -- S9: AI vs human baseline + Table 2/3 ------------------------------------
  comparison <- desc_stats %>%
    transmute(
      model, vignette = as.character(vignette), scale_type = as.character(scale_type),
      ai_mean = mean_scale, ai_sd = sd_scale, ai_n = n_runs,
      n_complete_runs, mean_completeness
    ) %>%
    left_join(human_baselines, by = c("vignette", "scale_type")) %>%
    filter(!is.na(human_mean)) %>%
    mutate(
      ai_language    = lang_tag,
      language_match = dplyr::case_when(
        lang_tag == human_language ~ "matched",
        TRUE                       ~ "instrument_language_mismatch"
      ),
      ai_se      = ifelse(ai_n > 1, ai_sd / sqrt(ai_n), NA_real_),
      ai_ci_low  = ifelse(ai_n > 1, ai_mean - stats::qt(0.975, df = ai_n - 1) * ai_se, NA_real_),
      ai_ci_high = ifelse(ai_n > 1, ai_mean + stats::qt(0.975, df = ai_n - 1) * ai_se, NA_real_),
      diff           = ai_mean - human_mean,
      human_sd_units = diff / human_sd,
      direction      = ifelse(diff > 0, "AI more stigmatizing", "AI less stigmatizing"),
      comparison_note = paste0(
        "Descriptive benchmark only; human raw data unavailable. ",
        "Primary effect size = human_sd_units. Language match: ", language_match, "."
      )
    )

  write_csv(comparison, file.path(results_dir, "tableS9_ai_vs_human.csv"))

  tbl_num   <- if (lang_tag == "zh") 3L else 2L
  tbl_fname <- sprintf("table%d_%s_stigma_scores.csv", tbl_num, lang_tag)
  write_csv(format_stigma_table(comparison), file.path(results_dir, tbl_fname))
  cat("  Saved", tbl_fname, "(mean [95% CI], t-distribution)\n")

  # -- S3: Run-level reliability (ICC(2,k) + Spearman) -------------------------
  cat("--- Reliability metrics [", lang_label, "] ---\n")
  reliability_rows <- list()
  for (m in levels(raw_data$model)) {
    for (vig in present_vignettes) {
      for (st in scale_order) {
        item_matrix <- raw_data %>%
          filter(model == m, vignette == vig, scale_type == st) %>%
          select(analysis_run, item_id, scored_value) %>%
          distinct() %>%
          pivot_wider(names_from = item_id, values_from = scored_value) %>%
          select(-analysis_run) %>%
          as.matrix()
        rel_summary <- run_reliability_metrics(item_matrix, min_complete_runs = min_complete_runs_for_alpha) %>%
          mutate(model = m, vignette = vig, scale_type = st) %>%
          relocate(model, vignette, scale_type)
        reliability_rows[[length(reliability_rows) + 1]] <- rel_summary
      }
    }
  }
  write_csv(bind_rows(reliability_rows), file.path(results_dir, "tableS3_reliability.csv"))

  # -- S10/S11: Leave-GPT-OSS-out sensitivity ----------------------------------
  gpt_oss_label <- "GPT-OSS-120B"
  if (any(as.character(scale_scores$model) == gpt_oss_label)) {
    cat("--- Sensitivity: leave GPT-OSS-120B out [", lang_label, "] ---\n")
    ss_sens <- scale_scores %>%
      filter(as.character(model) != gpt_oss_label) %>%
      mutate(model = droplevels(factor(model)))

    desc_sens <- ss_sens %>%
      filter(in_primary_analysis) %>%
      group_by(model, vignette, scale_type) %>%
      summarise(
        n_runs = dplyr::n(), mean_scale = mean(scale_score_primary, na.rm = TRUE),
        sd_scale = stats::sd(scale_score_primary, na.rm = TRUE),
        median_scale = stats::median(scale_score_primary, na.rm = TRUE),
        .groups = "drop"
      )
    write_csv(desc_sens, file.path(results_dir, "tableS10_sensitivity_descriptive.csv"))

    between_omnibus_sens <- list()
    for (vig in intersect(vignette_order, unique(as.character(ss_sens$vignette)))) {
      for (st in scale_order) {
        rs <- ss_sens %>%
          filter(in_primary_analysis, as.character(vignette) == vig, as.character(scale_type) == st)
        am <- rs %>% dplyr::count(model) %>% filter(n >= min_runs_for_inference) %>% pull(model) %>% as.character()
        if (length(am) < 2) next
        groups <- lapply(am, function(mm) rs %>% filter(as.character(model) == mm) %>% pull(scale_score_primary))
        kw <- tryCatch(stats::kruskal.test(groups), error = function(e) NULL)
        if (is.null(kw)) next
        between_omnibus_sens[[length(between_omnibus_sens) + 1]] <- tibble(
          vignette = vig, scale_type = st,
          method = "Kruskal-Wallis test (leave GPT-OSS-120B out)",
          n_models = length(am), statistic = unname(kw$statistic),
          df = unname(kw$parameter), p_value = kw$p.value,
          models = paste(am, collapse = ", ")
        )
      }
    }
    if (length(between_omnibus_sens) > 0)
      write_csv(bind_rows(between_omnibus_sens), file.path(results_dir, "tableS11_sensitivity_omnibus.csv"))
  }

  # -- Figures -----------------------------------------------------------------
  ss_primary <- scale_scores %>% filter(in_primary_analysis)
  present_plot_order <- model_plot_order[model_plot_order %in% levels(ss_primary$model)]
  ss_primary <- ss_primary %>%
    mutate(
      model_plot = factor(model, levels = present_plot_order),
      family     = model_family[as.character(model)],
      deployment = model_deployment[as.character(model)]
    )

  primary_cell_counts <- ss_primary %>% count(model, vignette, scale_type, name = "n_primary_runs")
  primary_run_min <- min(primary_cell_counts$n_primary_runs)
  primary_run_max <- max(primary_cell_counts$n_primary_runs)
  figure_run_subtitle <- if (primary_run_min == primary_run_max) {
    sprintf("Run-level prorated scale scores (>=80%% item completeness), %d runs per cell", primary_run_min)
  } else {
    sprintf("Run-level prorated scale scores (>=80%% item completeness); qualifying runs %d\u2013%d per cell",
            primary_run_min, primary_run_max)
  }
  set.seed(42)

  present_colors      <- family_colors[present_plot_order]
  present_labels      <- model_labels[present_plot_order]
  present_deployments <- unique(model_deployment[present_plot_order])

  # Fig 1: Release-year bin descriptive (Q1 \u2014 descriptive only, no OLS trend)
  # \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  # Bins: 2022-23 (GPT-3.5 era), 2024-25 (GPT-4o / Claude Sonnet 4.5 era),
  # 2026 (frontier reasoning era). Per-bin median and IQR are reported as
  # an opaque band; individual model points are jittered on top with
  # within-developer-family trajectory arrows.
  bin_release_year <- function(d) {
    y <- as.integer(format(d, "%Y"))
    cut(y, breaks = c(-Inf, 2023, 2025, Inf),
        labels = c("2022\u201323", "2024\u201325", "2026"),
        right  = TRUE)
  }

  timeline_data <- desc_stats %>%
    mutate(
      release_date = as.Date(model_release_dates[as.character(model)]),
      family       = model_family[as.character(model)],
      deployment   = model_deployment[as.character(model)]
    ) %>%
    filter(!is.na(release_date)) %>%
    group_by(model, scale_type, release_date, family, deployment) %>%
    summarise(
      mean_stigma = mean(mean_scale, na.rm = TRUE),
      .groups = "drop"
    ) %>%
    mutate(
      release_year_bin = bin_release_year(release_date),
      scale_label = recode(scale_type,
        social_distance = "Social Distance (19\u201376)",
        prejudice       = "Prejudice (21\u201384)"
      )
    )

  bin_summary <- timeline_data %>%
    group_by(release_year_bin, scale_type, scale_label) %>%
    summarise(
      median_stigma = median(mean_stigma, na.rm = TRUE),
      q25 = quantile(mean_stigma, 0.25, na.rm = TRUE),
      q75 = quantile(mean_stigma, 0.75, na.rm = TRUE),
      n_models = n(),
      .groups = "drop"
    )

  family_trajectories <- timeline_data %>%
    group_by(family, scale_type, scale_label) %>%
    arrange(release_date, model, .by_group = TRUE) %>%
    mutate(x_end = lead(release_date), y_end = lead(mean_stigma)) %>%
    filter(!is.na(x_end)) %>%
    ungroup()

  bin_x_lookup <- c(
    "2022\u201323" = as.Date("2022-12-15"),
    "2024\u201325" = as.Date("2024-12-15"),
    "2026"      = as.Date("2026-03-01")
  )
  bin_summary$bin_x <- bin_x_lookup[as.character(bin_summary$release_year_bin)]

  p_timeline <- ggplot(timeline_data, aes(x = release_date, y = mean_stigma)) +
    geom_crossbar(data = bin_summary,
      aes(x = bin_x, y = median_stigma, ymin = q25, ymax = q75),
      width = 240, fill = "grey85", color = "grey45", linewidth = 0.5, alpha = 0.55,
      inherit.aes = FALSE) +
    geom_segment(data = family_trajectories,
      aes(x = release_date, y = mean_stigma, xend = x_end, yend = y_end, color = family),
      linewidth = 0.6, alpha = 0.35,
      arrow = arrow(length = unit(0.08, "inches"), type = "closed"), show.legend = FALSE) +
    geom_point(aes(color = model, shape = deployment), size = 3.5, stroke = 0.8) +
    ggrepel::geom_text_repel(aes(label = model), size = 2.8, max.overlaps = 20,
      show.legend = FALSE, family = "Helvetica", seed = 42,
      min.segment.length = 0.2, box.padding = 0.4, point.padding = 0.3) +
    facet_wrap(~ scale_label, scales = "free_y") +
    scale_color_manual(values = c(family_colors, family_group_colors),
                       labels = model_labels, name = "Model", breaks = names(family_colors)) +
    scale_shape_manual(values = deployment_shapes, name = "Deployment") +
    scale_x_date(date_breaks = "1 year", date_labels = "%Y", expand = expansion(add = c(150, 60))) +
    labs(
      title    = paste0("Stigma Scores by Release-Year Bin [", lang_label, "]"),
      subtitle = "Descriptive median + IQR per release-year bin; arrows = within-family contrast (no formal trend test).",
      x = "Model release year (binned)", y = "Mean scale score (higher = more stigma)",
      caption = paste0(
        "Each point = one model\u2019s mean across 4 vignettes. Solid circles = API; open diamonds = open-source.\n",
        "Grey crossbar = median \u00b1 IQR within each bin (2022\u201323 / 2024\u201325 / 2026). ",
        "Colored arrows connect successive models within a developer family.\n",
        "Q1 is reported descriptively; no formal trend test is conducted (n = 13 models is small relative to confounders)."
      )
    ) +
    guides(color = guide_legend(nrow = 2, order = 1), shape = guide_legend(order = 2)) +
    theme_journal() +
    theme(axis.text.x = element_text(size = 10), plot.margin = margin(5, 12, 12, 5, "mm"),
          plot.caption = element_text(size = 8, color = "grey50", hjust = 0, margin = margin(t = 6)))

  ggsave(file.path(figures_dir, paste0("fig1_release_year_bin", lang_suffix, ".pdf")), p_timeline, width = 14, height = 8)
  ggsave(file.path(figures_dir, paste0("fig1_release_year_bin", lang_suffix, ".png")), p_timeline, width = 14, height = 8, dpi = 300)

  # Companion CSV summarising the bin medians (referenced as Table S4b in the draft)
  write_csv(bin_summary %>% select(-bin_x),
            file.path(results_dir, "tableS4b_release_year_bin_summary.csv"))

  # Fig 2 & 3: Horizontal violin plots (H2)
  vignette_facet_labels <- c(
    PLE = "PLE (Psychotic-Like Experiences)", DEP = "DEP (Major Depression)",
    APS = "APS (Attenuated Psychosis Syndrome)", SCZ = "SCZ (Schizophrenia)"
  )
  model_y_order  <- rev(present_plot_order)
  model_y_labels <- model_labels[model_y_order]

  make_horizontal_violin <- function(data, scale_filter, x_label, title_scale) {
    plot_data <- data %>%
      filter(scale_type == scale_filter) %>%
      mutate(model_y = factor(model, levels = model_y_order))
    ggplot(plot_data, aes(x = scale_score_primary, y = model_y)) +
      geom_violin(aes(fill = model_y, linetype = deployment),
                  alpha = 0.22, linewidth = 0.4, trim = TRUE, scale = "width", color = "grey30") +
      geom_boxplot(aes(group = model_y), width = 0.2, outlier.shape = NA,
                   linewidth = 0.4, color = "grey25", fill = NA) +
      geom_point(aes(color = model_y, shape = deployment),
                 position = position_jitter(height = 0.08, width = 0), size = 0.7, alpha = 0.35) +
      facet_wrap(~ vignette, ncol = 2, labeller = labeller(vignette = vignette_facet_labels)) +
      scale_y_discrete(labels = model_y_labels) +
      scale_fill_manual(values = present_colors, guide = "none") +
      scale_color_manual(values = present_colors, guide = "none") +
      scale_linetype_manual(values = c("API" = "solid", "Open-source" = "dashed"), name = "Deployment") +
      scale_shape_manual(values = deployment_shapes, name = "Deployment") +
      labs(
        title    = paste0("Mental Illness Stigma: ", title_scale, " [", lang_label, "]"),
        subtitle = figure_run_subtitle, x = x_label, y = NULL,
        caption  = paste0(
          "Models grouped by family: Claude (orange), GPT (green), Gemini (blue), DeepSeek (red).\n",
          "Dashed violin outlines = open-source models (wider = less stable). Solid circles = API; open diamonds = open-source."
        )
      ) +
      guides(linetype = guide_legend(order = 1), shape = guide_legend(order = 2)) +
      theme_journal() +
      theme(strip.text = element_text(size = 10), axis.text.y = element_text(size = 9),
            panel.spacing = unit(1, "lines"))
  }

  p2 <- make_horizontal_violin(ss_primary, "social_distance",
    "Social distance scale score (range 19\u201376; higher = more stigma)", "Discrimination (Social Distance)")
  ggsave(file.path(figures_dir, paste0("fig2_social_distance", lang_suffix, ".pdf")), p2, width = 14, height = 10)
  ggsave(file.path(figures_dir, paste0("fig2_social_distance", lang_suffix, ".png")), p2, width = 14, height = 10, dpi = 300)

  p3 <- make_horizontal_violin(ss_primary, "prejudice",
    "Prejudice scale score (range 21\u201384; higher = more stigma)", "Prejudice")
  ggsave(file.path(figures_dir, paste0("fig3_prejudice", lang_suffix, ".pdf")), p3, width = 14, height = 10)
  ggsave(file.path(figures_dir, paste0("fig3_prejudice", lang_suffix, ".png")), p3, width = 14, height = 10, dpi = 300)

  # Fig 2a & 3a: Vertical violin, faceted by vignette (PLE->DEP->APS->SCZ), models on X-axis
  make_vertical_violin_faceted <- function(data, scale_filter, y_label, title_scale) {
    plot_data <- data %>%
      filter(scale_type == scale_filter) %>%
      mutate(
        model_x = factor(model, levels = present_plot_order),
        vignette = factor(vignette, levels = vignette_order)
      )
    ggplot(plot_data, aes(x = model_x, y = scale_score_primary)) +
      geom_violin(aes(fill = model_x, linetype = deployment),
                  alpha = 0.22, linewidth = 0.4, trim = TRUE, scale = "width", color = "grey30") +
      geom_boxplot(aes(group = model_x), width = 0.2, outlier.shape = NA,
                   linewidth = 0.4, color = "grey25", fill = NA) +
      geom_point(aes(color = model_x, shape = deployment),
                 position = position_jitter(width = 0.08, height = 0), size = 0.7, alpha = 0.35) +
      facet_wrap(~ vignette, nrow = 1, labeller = labeller(vignette = vignette_facet_labels)) +
      scale_x_discrete(labels = model_short_labels[present_plot_order]) +
      scale_fill_manual(values = present_colors, guide = "none") +
      scale_color_manual(values = present_colors, guide = "none") +
      scale_linetype_manual(values = c("API" = "solid", "Open-source" = "dashed"), name = "Deployment") +
      scale_shape_manual(values = deployment_shapes, name = "Deployment") +
      labs(
        title    = paste0("Mental Illness Stigma: ", title_scale, " [", lang_label, "] \u2014 by Vignette"),
        subtitle = figure_run_subtitle, y = y_label, x = NULL,
        caption  = paste0(
          "Models ordered: GPT \u2192 Claude \u2192 Gemini \u2192 Other, then release date. ",
          "Vignettes left\u2013right: PLE \u2192 DEP \u2192 APS \u2192 SCZ.\n",
          "Dashed violin outlines = open-source models. Solid circles = API; open diamonds = open-source."
        )
      ) +
      guides(linetype = guide_legend(order = 1), shape = guide_legend(order = 2)) +
      theme_journal() +
      theme(strip.text = element_text(size = 10),
            axis.text.x = element_text(size = 8, angle = 45, hjust = 1),
            panel.spacing = unit(0.8, "lines"))
  }

  p2a <- make_vertical_violin_faceted(ss_primary, "social_distance",
    "Social distance scale score (range 19\u201376; higher = more stigma)", "Discrimination (Social Distance)")
  ggsave(file.path(figures_dir, paste0("fig2a_social_distance_by_vignette", lang_suffix, ".pdf")), p2a, width = 18, height = 8)
  ggsave(file.path(figures_dir, paste0("fig2a_social_distance_by_vignette", lang_suffix, ".png")), p2a, width = 18, height = 8, dpi = 300)

  p3a <- make_vertical_violin_faceted(ss_primary, "prejudice",
    "Prejudice scale score (range 21\u201384; higher = more stigma)", "Prejudice")
  ggsave(file.path(figures_dir, paste0("fig3a_prejudice_by_vignette", lang_suffix, ".pdf")), p3a, width = 18, height = 8)
  ggsave(file.path(figures_dir, paste0("fig3a_prejudice_by_vignette", lang_suffix, ".png")), p3a, width = 18, height = 8, dpi = 300)

  # Fig 2b & 3b: Vertical grouped boxplot, models on X-axis, vignettes (PLE->DEP->APS->SCZ) dodged within each model
  make_vertical_grouped <- function(data, scale_filter, y_label, title_scale) {
    vignette_fill_colors <- c(PLE = "#43A047", DEP = "#1E88E5", APS = "#FB8C00", SCZ = "#E53935")
    plot_data <- data %>%
      filter(scale_type == scale_filter) %>%
      mutate(
        model_x = factor(model, levels = present_plot_order),
        vignette = factor(vignette, levels = vignette_order)
      )
    ggplot(plot_data, aes(x = model_x, y = scale_score_primary,
                          fill = vignette, color = vignette,
                          group = interaction(model_x, vignette))) +
      geom_boxplot(position = position_dodge(width = 0.78),
                   width = 0.65, outlier.shape = NA, alpha = 0.25, linewidth = 0.4) +
      geom_point(aes(shape = deployment),
                 position = position_jitterdodge(jitter.width = 0.1, dodge.width = 0.78),
                 size = 0.6, alpha = 0.3) +
      scale_x_discrete(labels = model_short_labels[present_plot_order]) +
      scale_fill_manual(values = vignette_fill_colors, name = "Vignette") +
      scale_color_manual(values = vignette_fill_colors, name = "Vignette") +
      scale_shape_manual(values = deployment_shapes, name = "Deployment") +
      labs(
        title    = paste0("Mental Illness Stigma: ", title_scale, " [", lang_label, "] \u2014 by Model \u00d7 Vignette"),
        subtitle = figure_run_subtitle, y = y_label, x = NULL,
        caption  = paste0(
          "Models ordered: GPT \u2192 Claude \u2192 Gemini \u2192 Other, then release date. ",
          "Within each model, vignettes left\u2013right: PLE \u2192 DEP \u2192 APS \u2192 SCZ.\n",
          "Solid circles = API; open diamonds = open-source."
        )
      ) +
      guides(
        fill  = guide_legend(order = 1, override.aes = list(alpha = 0.6, size = 3)),
        color = guide_legend(order = 1),
        shape = guide_legend(order = 2)
      ) +
      theme_journal() +
      theme(axis.text.x = element_text(size = 8, angle = 45, hjust = 1))
  }

  p2b <- make_vertical_grouped(ss_primary, "social_distance",
    "Social distance scale score (range 19\u201376; higher = more stigma)", "Discrimination (Social Distance)")
  ggsave(file.path(figures_dir, paste0("fig2b_social_distance_grouped", lang_suffix, ".pdf")), p2b, width = 18, height = 8)
  ggsave(file.path(figures_dir, paste0("fig2b_social_distance_grouped", lang_suffix, ".png")), p2b, width = 18, height = 8, dpi = 300)

  p3b <- make_vertical_grouped(ss_primary, "prejudice",
    "Prejudice scale score (range 21\u201384; higher = more stigma)", "Prejudice")
  ggsave(file.path(figures_dir, paste0("fig3b_prejudice_grouped", lang_suffix, ".pdf")), p3b, width = 18, height = 8)
  ggsave(file.path(figures_dir, paste0("fig3b_prejudice_grouped", lang_suffix, ".png")), p3b, width = 18, height = 8, dpi = 300)

  # Fig 4: Prejudice domain heatmap (H4)
  domain_scores <- raw_data %>%
    filter(scale_type == "prejudice", !is.na(item_domain)) %>%
    left_join(scale_scores %>% select(model, vignette, scale_type, analysis_run, in_primary_analysis),
              by = c("model", "vignette", "scale_type", "analysis_run")) %>%
    filter(in_primary_analysis, !is.na(scored_value)) %>%
    group_by(model, vignette, item_domain) %>%
    summarise(mean_score = mean(scored_value), .groups = "drop") %>%
    mutate(col_key = paste(vignette, item_domain, sep = "\n"))

  mat <- domain_scores %>%
    pivot_wider(id_cols = model, names_from = col_key, values_from = mean_score) %>%
    column_to_rownames("model") %>% as.matrix()
  mat[is.na(mat)] <- mean(mat, na.rm = TRUE)

  hc_col <- hclust(dist(t(mat)), method = "ward.D2")
  col_ord <- hc_col$labels[hc_col$order]
  row_ord <- rev(present_plot_order[present_plot_order %in% rownames(mat)])
  dend_col_data <- dendro_data(as.dendrogram(hc_col), type = "rectangle")
  score_min <- min(domain_scores$mean_score, na.rm = TRUE)
  score_max <- max(domain_scores$mean_score, na.rm = TRUE)
  score_mid <- mean(c(score_min, score_max))
  deepseek_y_pos <- which(row_ord %in% grep("DeepSeek", row_ord, value = TRUE))

  domain_scores_ord <- domain_scores %>%
    mutate(
      model_label = model_labels[as.character(model)],
      model_label = factor(model_label, levels = model_labels[row_ord]),
      col_key     = factor(col_key, levels = col_ord),
      is_deepseek = grepl("DeepSeek", model)
    )

  p_heat <- ggplot(domain_scores_ord, aes(x = col_key, y = model_label, fill = mean_score)) +
    geom_tile(color = "white", linewidth = 0.3) +
    geom_text(aes(label = sprintf("%.2f", mean_score)), size = 2.4) +
    {
      if (length(deepseek_y_pos) > 0)
        annotate("rect", xmin = 0.5, xmax = length(col_ord) + 0.5,
                 ymin = min(deepseek_y_pos) - 0.5, ymax = max(deepseek_y_pos) + 0.5,
                 fill = NA, color = "#C62828", linewidth = 1.2, linetype = "solid")
    } +
    scale_fill_gradient2(low = "steelblue", mid = "white", high = "firebrick",
                         midpoint = score_mid, limits = c(score_min, score_max), name = "Mean\nItem Score") +
    labs(
      title    = paste0("Prejudice Domain Scores by Model and Vignette [", lang_label, "]"),
      subtitle = "Rows: model family order (consistent with Fig 2/3); columns clustered by Ward\u2019s D2; red border = DeepSeek V3.2",
      x = "Vignette \u00d7 prejudice domain", y = NULL,
      caption  = paste0(
        "Cell values = mean item scores (1\u20134). Clustering: Ward\u2019s minimum-variance on Euclidean distances.\n",
        "PLE = psychotic-like experiences; DEP = major depression; APS = attenuated psychosis syndrome; SCZ = schizophrenia."
      )
    ) +
    theme_journal(base_size = 10) +
    theme(axis.text.x = element_text(angle = 35, hjust = 1, size = 8),
          axis.text.y = element_text(size = 9), panel.grid = element_blank())

  p_dend_col <- ggplot(segment(dend_col_data)) +
    geom_segment(aes(x = x, y = y, xend = xend, yend = yend), color = "grey40", linewidth = 0.4) +
    scale_x_continuous(expand = expansion(add = 0.5)) + theme_void()

  p4 <- (plot_spacer() + p_dend_col + plot_layout(widths = c(0, 1))) /
        (p_heat + plot_layout(widths = c(1))) + plot_layout(heights = c(1, 8))

  ggsave(file.path(figures_dir, paste0("fig4_prejudice_clustered_heatmap", lang_suffix, ".pdf")), p4, width = 14, height = 8)
  ggsave(file.path(figures_dir, paste0("fig4_prejudice_clustered_heatmap", lang_suffix, ".png")), p4, width = 14, height = 8, dpi = 300)

  cat("Figures saved to", figures_dir, "\n")
  cat("Language analysis complete [", lang_label, "]\n\n")
  invisible(list(scale_scores = scale_scores, comparison = comparison))
}

# =============================================================================
# STAGE 1B: CROSS-LANGUAGE COMPARISON
# run_cross_language(en_scores_path, zh_scores_path, output_dir)
# =============================================================================

run_cross_language <- function(en_scores_path, zh_scores_path, output_dir) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  load_lang <- function(path, lang) {
    read_csv(path, show_col_types = FALSE) %>%
      mutate(
        language                  = lang,
        completeness              = as.numeric(completeness),
        scale_score_primary       = as.numeric(scale_score_primary),
        in_primary_analysis       = toupper(in_primary_analysis) == "TRUE",
        in_complete_case_analysis = toupper(in_complete_case_analysis) == "TRUE"
      ) %>%
      filter(in_primary_analysis)
  }

  run_scores <- bind_rows(load_lang(en_scores_path, "en"), load_lang(zh_scores_path, "zh")) %>%
    mutate(
      vignette   = factor(vignette, levels = c("PLE", "DEP", "APS", "SCZ")),
      scale_type = factor(scale_type, levels = c("social_distance", "prejudice"))
    )

  present_models <- c(
    model_plot_order[model_plot_order %in% unique(run_scores$model)],
    sort(setdiff(unique(run_scores$model), model_plot_order))
  )
  plot_model_labels <- stats::setNames(present_models, present_models)
  plot_model_labels[names(model_labels)] <- model_labels

  cell_descriptives <- run_scores %>%
    group_by(language, model, vignette, scale_type) %>%
    summarise(
      n_runs = n(), mean_scale = mean(scale_score_primary, na.rm = TRUE),
      sd_scale = sd(scale_score_primary, na.rm = TRUE),
      median_scale = median(scale_score_primary, na.rm = TRUE),
      iqr_scale = IQR(scale_score_primary, na.rm = TRUE),
      mean_completeness = mean(completeness, na.rm = TRUE),
      .groups = "drop"
    )

  cell_tests <- run_scores %>%
    group_by(model, vignette, scale_type) %>%
    group_modify(~ {
      en_sc <- .x %>% filter(language == "en") %>% pull(scale_score_primary)
      zh_sc <- .x %>% filter(language == "zh") %>% pull(scale_score_primary)
      if (length(en_sc) < 5 || length(zh_sc) < 5)
        return(tibble(n_en = length(en_sc), n_zh = length(zh_sc),
                      wilcox_p = NA_real_, cliffs_delta_zh_vs_en = NA_real_))
      wt <- suppressWarnings(wilcox.test(zh_sc, en_sc, exact = FALSE))
      tibble(n_en = length(en_sc), n_zh = length(zh_sc),
             wilcox_p = wt$p.value,
             cliffs_delta_zh_vs_en = cliff_delta_scalar(zh_sc, en_sc))
    }) %>%
    ungroup() %>%
    mutate(wilcox_p_adjusted = p.adjust(wilcox_p, method = "holm"))

  cell_comparison <- cell_descriptives %>%
    select(language, model, vignette, scale_type,
           n_runs, mean_scale, sd_scale, median_scale, iqr_scale, mean_completeness) %>%
    pivot_wider(names_from = language,
                values_from = c(n_runs, mean_scale, sd_scale, median_scale, iqr_scale, mean_completeness)) %>%
    left_join(cell_tests, by = c("model", "vignette", "scale_type")) %>%
    mutate(
      mean_diff_zh_minus_en   = mean_scale_zh - mean_scale_en,
      median_diff_zh_minus_en = median_scale_zh - median_scale_en,
      direction = case_when(
        is.na(mean_diff_zh_minus_en)  ~ NA_character_,
        mean_diff_zh_minus_en > 0     ~ "ZH_higher",
        mean_diff_zh_minus_en < 0     ~ "EN_higher",
        TRUE                          ~ "equal"
      ),
      model = factor(model, levels = rev(present_models))
    ) %>%
    arrange(scale_type, vignette, model)

  model_summary <- cell_comparison %>%
    group_by(model, scale_type) %>%
    summarise(
      mean_scale_en               = mean(mean_scale_en, na.rm = TRUE),
      mean_scale_zh               = mean(mean_scale_zh, na.rm = TRUE),
      mean_cell_diff_zh_minus_en  = mean(mean_diff_zh_minus_en, na.rm = TRUE),
      n_cells_zh_higher           = sum(mean_diff_zh_minus_en > 0, na.rm = TRUE),
      n_cells_en_higher           = sum(mean_diff_zh_minus_en < 0, na.rm = TRUE),
      max_abs_shift               = max(abs(mean_diff_zh_minus_en), na.rm = TRUE),
      .groups = "drop"
    ) %>%
    arrange(scale_type, desc(mean_cell_diff_zh_minus_en))

  vignette_summary <- cell_comparison %>%
    group_by(vignette, scale_type) %>%
    summarise(
      mean_scale_en               = mean(mean_scale_en, na.rm = TRUE),
      mean_scale_zh               = mean(mean_scale_zh, na.rm = TRUE),
      mean_cell_diff_zh_minus_en  = mean(mean_diff_zh_minus_en, na.rm = TRUE),
      n_models_zh_higher          = sum(mean_diff_zh_minus_en > 0, na.rm = TRUE),
      n_models_en_higher          = sum(mean_diff_zh_minus_en < 0, na.rm = TRUE),
      .groups = "drop"
    ) %>%
    arrange(scale_type, vignette)

  write_csv(cell_descriptives, file.path(output_dir, "tableS12_language_descriptives.csv"))
  write_csv(cell_comparison,   file.path(output_dir, "tableS13_language_comparison.csv"))
  write_csv(model_summary,     file.path(output_dir, "tableS14_language_by_model.csv"))
  write_csv(vignette_summary,  file.path(output_dir, "tableS15_language_by_vignette.csv"))

  # Fig 5: Forest plot (H3)
  forest_data <- cell_comparison %>%
    mutate(
      se_diff = sqrt((sd_scale_zh^2 / n_runs_zh) + (sd_scale_en^2 / n_runs_en)),
      df_approx = ((sd_scale_zh^2 / n_runs_zh + sd_scale_en^2 / n_runs_en)^2) /
        ((sd_scale_zh^2 / n_runs_zh)^2 / (n_runs_zh - 1) +
         (sd_scale_en^2 / n_runs_en)^2 / (n_runs_en - 1)),
      ci_lo = mean_diff_zh_minus_en - qt(0.975, df_approx) * se_diff,
      ci_hi = mean_diff_zh_minus_en + qt(0.975, df_approx) * se_diff,
      sig   = !is.na(wilcox_p_adjusted) & wilcox_p_adjusted < 0.05,
      model_label = plot_model_labels[as.character(model)],
      family      = model_family[as.character(model)]
    ) %>%
    mutate(
      model_label = factor(model_label, levels = rev(unname(plot_model_labels[present_models]))),
      scale_label = recode(scale_type,
        social_distance = "Discrimination (Social Distance)", prejudice = "Prejudice")
    )

  pooled_data <- forest_data %>%
    filter(is.finite(se_diff), se_diff > 0) %>%
    group_by(vignette, scale_type, scale_label) %>%
    summarise(
      w           = sum(1 / se_diff^2),
      pooled_mean = sum(mean_diff_zh_minus_en / se_diff^2) / sum(1 / se_diff^2),
      pooled_se   = sqrt(1 / sum(1 / se_diff^2)),
      .groups = "drop"
    ) %>%
    mutate(
      pooled_lo   = pooled_mean - 1.96 * pooled_se,
      pooled_hi   = pooled_mean + 1.96 * pooled_se,
      model_label = factor("Pooled effect",
                           levels = c(levels(forest_data$model_label), "Pooled effect"))
    )

  forest_data <- forest_data %>%
    mutate(model_label = factor(model_label,
                                levels = c("Pooled effect", levels(forest_data$model_label))))

  forest_colors <- family_colors[present_models]
  names(forest_colors) <- plot_model_labels[present_models]

  forest_plot <- ggplot(forest_data, aes(x = mean_diff_zh_minus_en, y = model_label)) +
    geom_vline(xintercept = 0, linetype = "dashed", color = "grey50", linewidth = 0.6) +
    geom_errorbarh(data = pooled_data,
      aes(x = pooled_mean, xmin = pooled_lo, xmax = pooled_hi, y = model_label),
      height = 0.3, linewidth = 0.8, color = "black", inherit.aes = FALSE) +
    geom_point(data = pooled_data, aes(x = pooled_mean, y = model_label),
      shape = 18, size = 4, color = "black", inherit.aes = FALSE) +
    geom_errorbarh(aes(xmin = ci_lo, xmax = ci_hi, color = model_label),
                   height = 0.25, linewidth = 0.6) +
    geom_point(aes(color = model_label,
                   shape = ifelse(sig, "P < 0.05", "P \u2265 0.05")), size = 2.5) +
    scale_color_manual(values = forest_colors, guide = "none") +
    scale_shape_manual(values = c("P < 0.05" = 18, "P \u2265 0.05" = 16), name = "Significance") +
    facet_grid(scale_label ~ vignette, scales = "free_x") +
    labs(
      title    = "Cross-Language Differences in Mental Illness Stigma Scores",
      subtitle = "Mean difference (Chinese \u2212 English) with 95% CIs; black diamond = inverse-variance pooled effect",
      x = "Mean difference (Chinese \u2212 English)", y = NULL,
      caption  = paste0(
        "Colors: Claude (orange), GPT (green), Gemini (blue), DeepSeek (red). Diamonds = P < 0.05 (Wilcoxon, Holm-adjusted).\n",
        "Pooled effect via inverse-variance fixed-effect meta-analytic weighting. ",
        "PLE = psychotic-like experiences; DEP = major depression; APS = attenuated psychosis syndrome; SCZ = schizophrenia."
      )
    ) +
    theme_classic(base_size = 10) +
    theme(
      text = element_text(family = "Helvetica"),
      strip.background = element_rect(fill = "grey92", color = NA),
      strip.text = element_text(face = "bold"), panel.spacing = unit(0.6, "lines"),
      legend.position = "bottom", axis.text.y = element_text(size = 8),
      plot.title = element_text(face = "bold"),
      plot.subtitle = element_text(size = 9, color = "grey40"),
      plot.caption = element_text(size = 8, color = "grey50", hjust = 0)
    )

  ggsave(file.path(output_dir, "fig5_cross_language_forest_plot.pdf"), forest_plot, width = 14, height = 7.5)
  ggsave(file.path(output_dir, "fig5_cross_language_forest_plot.png"), forest_plot, width = 14, height = 7.5, dpi = 300)

  # Fig 6: Cross-language heatmap (H4)
  heatmap_data <- cell_comparison %>%
    mutate(
      sig_label = case_when(
        !is.na(wilcox_p_adjusted) & wilcox_p_adjusted < 0.05 ~
          paste0(sprintf("%.1f", mean_diff_zh_minus_en), "*"),
        TRUE ~ sprintf("%.1f", mean_diff_zh_minus_en)
      ),
      is_deepseek = grepl("DeepSeek", model)
    )
  heatmap_y_levels <- rev(present_models)
  deepseek_idx <- which(grepl("DeepSeek", heatmap_y_levels))

  heatmap_plot <- ggplot(heatmap_data, aes(x = vignette, y = model, fill = mean_diff_zh_minus_en)) +
    geom_tile(color = "white", linewidth = 0.4) +
    geom_text(aes(label = sig_label), size = 3, family = "Helvetica") +
    {
      if (length(deepseek_idx) > 0)
        annotate("rect", xmin = 0.5, xmax = length(unique(heatmap_data$vignette)) + 0.5,
                 ymin = min(deepseek_idx) - 0.5, ymax = max(deepseek_idx) + 0.5,
                 fill = NA, color = "#C62828", linewidth = 1.2, linetype = "solid")
    } +
    facet_wrap(~ scale_type, ncol = 1,
               labeller = labeller(scale_type = c(
                 social_distance = "Discrimination (Social Distance)", prejudice = "Prejudice"))) +
    scale_y_discrete(labels = plot_model_labels) +
    scale_fill_gradient2(low = "#1f4e79", mid = "#f7f5ef", high = "#b2493f",
                         midpoint = 0, name = "ZH \u2212 EN") +
    labs(
      title    = "Cross-Language Differences in Mean Stigma Scores",
      subtitle = "Positive = higher stigma in Chinese; red border highlights DeepSeek V3.2",
      x = "Clinical vignette", y = "Model",
      caption  = paste0(
        "* P < 0.05 by Wilcoxon rank-sum test (Holm-adjusted). ",
        "See tableS13_language_comparison.csv for exact P values.\n",
        "PLE = psychotic-like experiences; DEP = major depression; ",
        "APS = attenuated psychosis syndrome; SCZ = schizophrenia."
      )
    ) +
    theme_classic(base_size = 11) +
    theme(
      text = element_text(family = "Helvetica"), panel.grid = element_blank(),
      strip.background = element_rect(fill = "grey92", color = NA),
      strip.text = element_text(face = "bold"),
      axis.text.x = element_text(face = "bold"), axis.text.y = element_text(size = 9),
      plot.title = element_text(face = "bold"),
      plot.subtitle = element_text(size = 10, color = "grey40"),
      plot.caption = element_text(size = 8, color = "grey50", hjust = 0)
    )

  ggsave(file.path(output_dir, "fig6_cross_language_heatmap.pdf"), heatmap_plot, width = 9, height = 7.5)
  ggsave(file.path(output_dir, "fig6_cross_language_heatmap.png"), heatmap_plot, width = 9, height = 7.5, dpi = 300)

  cat("Cross-language comparison complete.\n")
  cat("  tableS12_language_descriptives.csv\n  tableS13_language_comparison.csv\n")
  cat("  tableS14_language_by_model.csv\n  tableS15_language_by_vignette.csv\n")
  cat("  fig5_cross_language_forest_plot.{pdf,png}\n  fig6_cross_language_heatmap.{pdf,png}\n")
  invisible(cell_comparison)
}

# =============================================================================
# STAGE 1C: PUBLICATION TABLES (Table 1, Table 4) + Fig 7
# Table 2/3 are written by run_language_analysis()
# Table 5 is generated by: Rscript scripts/item_level_profile.R <analysis_dir>
# =============================================================================

run_generate_tables <- function(en_raw_path, zh_raw_path, output_dir) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  non_valid_types <- c("refusal_ethical", "refusal_identity", "refusal", "safety", "unparseable")

  load_raw <- function(path, lang) {
    read_csv(path, show_col_types = FALSE) %>% mutate(language = lang)
  }

  # -- Table 1: Response classification ----------------------------------------
  cat("Generating Table 1: Response Classification...\n")
  raw_all <- bind_rows(load_raw(en_raw_path, "en"), load_raw(zh_raw_path, "zh"))

  table1_data <- raw_all %>%
    group_by(language, model) %>%
    summarise(
      n_total            = n(),
      n_refusal_ethical  = sum(response_type == "refusal_ethical", na.rm = TRUE),
      n_refusal_identity = sum(response_type == "refusal_identity", na.rm = TRUE),
      n_refusal_other    = sum(response_type == "refusal", na.rm = TRUE),
      n_safety           = sum(response_type == "safety", na.rm = TRUE),
      n_unparseable      = sum(response_type == "unparseable", na.rm = TRUE),
      n_non_valid        = sum(response_type %in% non_valid_types, na.rm = TRUE),
      .groups = "drop"
    ) %>%
    mutate(pct_non_valid = round(100 * n_non_valid / n_total, 1))

  table1_wide <- table1_data %>%
    pivot_wider(id_cols = model, names_from = language,
                values_from = c(n_total, n_refusal_ethical, n_refusal_identity,
                                n_refusal_other, n_safety, n_unparseable,
                                n_non_valid, pct_non_valid))

  present <- model_plot_order[model_plot_order %in% unique(raw_all$model)]
  extra   <- sort(setdiff(unique(raw_all$model), model_plot_order))
  model_seq <- c(present, extra)

  table1_out <- table1_wide %>%
    mutate(model = factor(model, levels = model_seq)) %>%
    arrange(model) %>%
    mutate(model_label = sapply(as.character(model), make_model_label_pub), model = as.character(model)) %>%
    select(model_label, everything(), -model)

  write_csv(table1_out, file.path(output_dir, "table1_response_classification.csv"))
  cat("  Saved table1_response_classification.csv\n")

  # -- Table 4: Cross-language shift -------------------------------------------
  cat("Generating Table 4: Cross-Language Shift...\n")
  lang_comp_path <- file.path(output_dir, "tableS13_language_comparison.csv")
  if (!file.exists(lang_comp_path)) {
    cat("  SKIP Table 4: tableS13_language_comparison.csv not found (run Stage 1B first)\n")
  } else {
    lang_comp <- read_csv(lang_comp_path, show_col_types = FALSE)
    scale_abbrev <- c("social_distance" = "Social Distance", "prejudice" = "Prejudice")

    table4 <- lang_comp %>%
      mutate(
        diff_str    = sprintf("%.2f", mean_diff_zh_minus_en),
        sig_flag    = ifelse(!is.na(wilcox_p_adjusted) & wilcox_p_adjusted < 0.05, "*", ""),
        diff_label  = paste0(diff_str, sig_flag),
        scale_label = scale_abbrev[scale_type],
        vignette    = factor(vignette, levels = c("PLE", "DEP", "APS", "SCZ"))
      ) %>%
      select(model, scale_label, vignette, diff_label) %>%
      pivot_wider(names_from = vignette, values_from = diff_label) %>%
      arrange(model, scale_label)

    present <- model_plot_order[model_plot_order %in% unique(table4$model)]
    extra   <- sort(setdiff(unique(table4$model), model_plot_order))

    table4_out <- table4 %>%
      mutate(
        model_label = sapply(model, make_model_label_pub),
        model       = factor(model, levels = c(present, extra))
      ) %>%
      arrange(model, scale_label) %>%
      select(model_label, Scale = scale_label, PLE, DEP, APS, SCZ)

    write_csv(table4_out, file.path(output_dir, "table4_cross_language_shift.csv"))
    cat("  Saved table4_cross_language_shift.csv\n")
    cat("  Note: * = Holm-adjusted p < .05 (Wilcoxon rank-sum). Positive values = higher Chinese stigma.\n")
  }

  # -- Fig 7: Response classification stacked bar chart -----------------------
  cat("Generating Fig 7: Response Classification Chart...\n")

  fig7_colors <- c("Refusal" = "#D55E00", "Unparseable" = "#56B4E9")

  tbl1_fig <- raw_all %>%
    mutate(
      is_refusal     = response_type %in% c("refusal", "refusal_ethical", "refusal_identity", "safety"),
      is_unparseable = response_type == "unparseable"
    ) %>%
    group_by(language, model) %>%
    summarise(
      n_total       = n(),
      n_refusal     = sum(is_refusal),
      n_unparseable = sum(is_unparseable),
      .groups       = "drop"
    ) %>%
    pivot_wider(names_from = language,
                values_from = c(n_total, n_refusal, n_unparseable)) %>%
    mutate(
      refusal_pct_en     = n_refusal_en     / n_total_en * 100,
      unparseable_pct_en = n_unparseable_en / n_total_en * 100,
      refusal_pct_zh     = n_refusal_zh     / n_total_zh * 100,
      unparseable_pct_zh = n_unparseable_zh / n_total_zh * 100,
      model = factor(model, levels = model_plot_order),
      model_label = model_labels[as.character(model)]
    ) %>%
    filter(!is.na(model))

  fig7_data <- tbl1_fig %>%
    select(model, model_label, refusal_pct_en, unparseable_pct_en, refusal_pct_zh, unparseable_pct_zh) %>%
    pivot_longer(cols = c(refusal_pct_en, unparseable_pct_en, refusal_pct_zh, unparseable_pct_zh),
                 names_to = "key", values_to = "pct") %>%
    mutate(
      language   = if_else(grepl("_en$", key), "English", "Chinese (ZH)"),
      error_type = if_else(grepl("^refusal", key), "Refusal", "Unparseable"),
      model_label = factor(model_label,
        levels = rev(model_labels[model_plot_order[model_plot_order %in% levels(tbl1_fig$model)]])),
      error_type = factor(error_type, levels = c("Refusal", "Unparseable")),
      language   = factor(language, levels = c("English", "Chinese (ZH)"))
    )

  p_fig7 <- ggplot(fig7_data, aes(x = pct, y = model_label, fill = error_type)) +
    geom_col(width = 0.65, position = "stack") +
    geom_vline(xintercept = 0, linewidth = 0.4, colour = "grey40") +
    facet_wrap(~ language, nrow = 1) +
    scale_fill_manual(values = fig7_colors, name = "Non-valid type") +
    scale_x_continuous(expand = expansion(mult = c(0, 0.04)),
                       labels = function(x) paste0(x, "%")) +
    labs(
      title    = "Fig 7. Non-valid Response Rates by Model and Language",
      subtitle = paste0(
        "Proportion of responses classified as Refusal (ethical/identity/safety) ",
        "or Unparseable (truncation, API errors) per 4,800 items per language. ",
        "Models in protocol order (GPT \u2192 Claude \u2192 Gemini \u2192 Other), same as Figs 2\u20136."
      ),
      x = "% of total responses", y = NULL,
      caption = paste0(
        "Refusal: response_type \u2208 {refusal, refusal_ethical, refusal_identity, safety}. ",
        "Unparseable: API errors, generation truncation, DNS failures.\n",
        "Valid and hedged responses not shown."
      )
    ) +
    theme_journal() +
    theme(
      strip.text = element_text(size = 11, face = "bold"), legend.position = "bottom",
      legend.key.size = unit(0.45, "cm"),
      plot.subtitle = element_text(size = 8.5, color = "grey40", margin = margin(b = 6)),
      plot.caption = element_text(size = 7.5, color = "grey50", hjust = 0, margin = margin(t = 6)),
      axis.text.y = element_text(size = 9),
      panel.grid.major.y = element_blank(),
      panel.grid.major.x = element_line(linewidth = 0.3, colour = "grey88")
    )

  ggsave(file.path(output_dir, "fig7_response_classification.pdf"), p_fig7, width = 12, height = 6)
  ggsave(file.path(output_dir, "fig7_response_classification.png"), p_fig7, width = 12, height = 6, dpi = 300)
  cat("  Saved fig7_response_classification.{pdf,png}\n")

  cat("\nPublication tables complete. Outputs written to:", output_dir, "\n")
  cat("  Note: Table 2/3 written by Stage 1A (run_language_analysis).\n")
  cat("  Note: Table 5 generated by: Rscript scripts/item_level_profile.R <analysis_dir>\n")
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript scripts/analyze_stage1.R <analysis_dir>\n",
       "  e.g.: Rscript scripts/analyze_stage1.R analysis_13models_20260419/")
}

analysis_dir <- normalizePath(args[[1]], mustWork = TRUE)

en_csv_candidates <- list.files(file.path(analysis_dir, "en"), pattern = "^results_.*\\.csv$", full.names = TRUE)
zh_csv_candidates <- list.files(file.path(analysis_dir, "zh"), pattern = "^results_.*\\.csv$", full.names = TRUE)

if (length(en_csv_candidates) == 0) stop("No results_*.csv found in ", analysis_dir, "/en/")
if (length(zh_csv_candidates) == 0) stop("No results_*.csv found in ", analysis_dir, "/zh/")

en_csv <- en_csv_candidates[[1]]
zh_csv <- zh_csv_candidates[[1]]
en_dir <- file.path(analysis_dir, "en")
zh_dir <- file.path(analysis_dir, "zh")

cat("=================================================================\n")
cat("Stage 1 Analysis Pipeline — v0419 (13-model)\n")
cat("Analysis dir:", analysis_dir, "\n")
cat("EN input:", en_csv, "\n")
cat("ZH input:", zh_csv, "\n")
cat("=================================================================\n\n")

cat("=== Stage 1A: English analysis ===\n")
run_language_analysis(en_csv, en_dir, "en")

cat("=== Stage 1A: Chinese analysis ===\n")
run_language_analysis(zh_csv, zh_dir, "zh")

cat("=== Stage 1B: Cross-language comparison ===\n")
en_scores <- file.path(en_dir, "run_level_scale_scores.csv")
zh_scores <- file.path(zh_dir, "run_level_scale_scores.csv")
run_cross_language(en_scores, zh_scores, analysis_dir)

cat("=== Stage 1C: Publication tables + Fig 7 ===\n")
run_generate_tables(en_csv, zh_csv, analysis_dir)

cat("\n=================================================================\n")
cat("All stages complete. Outputs in:", analysis_dir, "\n")
cat("Next step — Table 5:\n")
cat("  Rscript scripts/item_level_profile.R", analysis_dir, "\n")
cat("=================================================================\n")

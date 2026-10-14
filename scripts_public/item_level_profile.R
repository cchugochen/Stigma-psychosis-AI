#!/usr/bin/env Rscript
# Micro-structural item-level stigma profiling (bilingual).
#
# Reads EN and ZH raw results from an analysis directory and produces:
#   Table5_item_stigma_profile.csv               — Model × Item, EN + ZH + diff columns (Table 5)
#   eFigure3A_item_profile_social_distance.pdf   — eFigure 3A: Social Distance heatmap, EN | ZH
#   eFigure3B_item_profile_prejudice.pdf         — eFigure 3B: Prejudice heatmap, EN | ZH
#   FigB_SD_APS_Spike_Slope.pdf                  — auxiliary: SD items DEP->APS slope (EN/ZH)
#   FigB_PJ_APS_Spike_Slope.pdf                  — auxiliary: PJ items DEP->APS slope (EN/ZH)
#
# eFigure 3A/3B are the NEJM AI supplement item-level profile figures; the file
# names match the deliverables in outputs/figures_tables/.
# (.png companions are emitted for embedding via build_etables_0622.py.)
# The FigB_* slope figures are auxiliary diagnostics, not part of the submission.
#
# Usage:
#   Rscript scripts_public/item_level_profile.R analysis_14models_20260614/
#
# Output is written to the analysis directory root (alongside Fig5-7).
#
# Model names (2026-10-12): the model tables in this script use the collection names of the authors' merged files
# (e.g. "Gemini 2.5 Flash"), as in the analysis behind the article. analyze_stage1.R run on data_public/ writes the
# article names ("Gemini-2.5-Flash"; scripts_public/Models_name.md); rename them back before running this script.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tidyr)
  library(ggplot2)
  library(stringr)
  library(patchwork)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript item_level_profile.R <analysis_dir>")
}
parent_dir <- normalizePath(args[[1]])
if (!dir.exists(parent_dir)) stop("Directory not found: ", parent_dir)

# ---- Helper: locate raw results CSV in a language sub-directory --------------

find_raw_csv <- function(lang_dir) {
  if (!dir.exists(lang_dir)) return(NULL)
  f <- list.files(lang_dir, pattern = "^results_.*\\.csv$", full.names = TRUE)
  if (length(f) == 0) return(NULL)
  f[[1]]
}

en_csv <- find_raw_csv(file.path(parent_dir, "en"))
zh_csv <- find_raw_csv(file.path(parent_dir, "zh"))

if (is.null(en_csv) && is.null(zh_csv)) {
  stop("No results_*.csv found in en/ or zh/ sub-directories of: ", parent_dir)
}

# ---- Visual encoding (mirrors analyze_results.R) ----------------------------

# Data uses spaced model ids; keys here must match the data.
model_plot_order <- c(
  "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4 Mini",
  "Claude Sonnet 4.5", "Claude Opus 4.6",
  "Gemini 2.5 Flash", "Gemini 3.1 Pro Preview", "Gemini 3.1 Flash-Lite Preview",
  "Gemini 3.5 Flash", "Gemma 4 31B IT", "Llama 3.3 70B", "DeepSeek V3.2"
)

model_family <- c(
  "GPT-3.5" = "GPT", "GPT-4o" = "GPT", "GPT-OSS-120B" = "GPT",
  "GPT-5.4" = "GPT", "GPT-5.4 Mini" = "GPT",
  "Claude Sonnet 4.5" = "Claude", "Claude Opus 4.6" = "Claude",
  "Gemini 2.5 Flash" = "Gemini", "Gemini 3.1 Pro Preview" = "Gemini Pro",
  "Gemini 3.1 Flash-Lite Preview" = "Gemini", "Gemini 3.5 Flash" = "Gemini",
  "Gemma 4 31B IT" = "Gemini",
  "Llama 3.3 70B" = "Llama", "DeepSeek V3.2" = "DeepSeek"
)

# Display labels (antigravity hyphenated naming) for row labels.
model_disp <- c(
  "GPT-3.5" = "GPT-3.5", "GPT-4o" = "GPT-4o", "GPT-OSS-120B" = "GPT-OSS-120B",
  "GPT-5.4" = "GPT-5.4", "GPT-5.4 Mini" = "GPT-5.4-Mini",
  "Claude Sonnet 4.5" = "Claude Sonnet 4.5", "Claude Opus 4.6" = "Claude Opus 4.6",
  "Gemini 2.5 Flash" = "Gemini-2.5-Flash", "Gemini 3.1 Pro Preview" = "Gemini-3.1-Pro-Preview",
  "Gemini 3.1 Flash-Lite Preview" = "Gemini-3.1-Flash-Lite-Preview",
  "Gemini 3.5 Flash" = "Gemini-3.5-Flash", "Gemma 4 31B IT" = "Gemma-4-31B-IT",
  "Llama 3.3 70B" = "Llama-3.3-70B", "DeepSeek V3.2" = "DeepSeek-V3.2"
)

family_levels <- c("GPT", "Claude", "Gemini", "Gemini Pro", "Llama", "DeepSeek")

family_group_colors <- c(
  "GPT" = "#2E7D32", "Claude" = "#E65100",
  "Gemini" = "#1565C0", "Gemini Pro" = "#1565C0",
  "Llama" = "#6A1B9A", "DeepSeek" = "#C62828"
)

vignette_order <- c("PLE", "DEP", "APS", "SCZ")
vignette_labels <- c(
  "PLE" = "PLE", "DEP" = "DEP", "APS" = "APS", "SCZ" = "SCZ"
)

# ---- Load and filter both languages -----------------------------------------

load_valid <- function(csv_path, lang_label) {
  if (is.null(csv_path)) return(NULL)
  message("Reading [", lang_label, "]: ", csv_path)
  d <- read_csv(csv_path, show_col_types = FALSE)
  v <- d %>%
    filter(response_type == "valid", !is.na(scored_value),
           model %in% model_plot_order) %>%
    mutate(
      language = lang_label,
      model    = factor(model, levels = model_plot_order),
      vignette = factor(vignette, levels = vignette_order)
    )
  message(sprintf("  total rows: %d | valid kept: %d", nrow(d), nrow(v)))
  v
}

both <- bind_rows(
  load_valid(en_csv, "EN"),
  load_valid(zh_csv, "ZH")
)

# ---- Task 1: aggregate + bilingual wide table --------------------------------

# Item-level metadata. Public outputs intentionally omit `item_text`
# (Wang 2020 verbatim wording is copyrighted); only item_id and item_domain
# are exported. Internal use can still join `item_text` from the merged
# CSV if needed.
item_meta_lookup <- both %>%
  distinct(scale_type, item_id, item_domain) %>%
  group_by(scale_type, item_id) %>%
  slice(1) %>%
  ungroup()

item_means <- both %>%
  group_by(language, model, vignette, scale_type, item_id) %>%
  summarise(mean_score = mean(scored_value, na.rm = TRUE), .groups = "drop")

# Per-language wide (Mean_PLE/DEP/APS/SCZ + APS_Spike)
make_wide <- function(lang) {
  item_means %>%
    filter(language == lang) %>%
    select(model, scale_type, item_id, vignette, mean_score) %>%
    pivot_wider(names_from = vignette, values_from = mean_score,
                names_prefix = paste0("Mean_", lang, "_")) %>%
    mutate(!!paste0("APS_Spike_", lang) :=
             .data[[paste0("Mean_", lang, "_APS")]] -
             .data[[paste0("Mean_", lang, "_DEP")]])
}

langs_available <- unique(both$language)
wide_list <- lapply(langs_available, make_wide)
names(wide_list) <- langs_available

wide_tbl <- Reduce(function(a, b) full_join(a, b, by = c("model", "scale_type",
                                                          "item_id")),
                   wide_list)

# ZH - EN diff on APS score (if both present)
if (all(c("EN", "ZH") %in% langs_available)) {
  wide_tbl <- wide_tbl %>%
    mutate(APS_ZH_minus_EN = Mean_ZH_APS - Mean_EN_APS)
}

wide_tbl <- wide_tbl %>%
  left_join(item_meta_lookup, by = c("scale_type", "item_id")) %>%
  arrange(model, scale_type, item_id) %>%
  rename(Model = model, Scale = scale_type, Item_ID = item_id,
         Item_Domain = item_domain)

table_path <- file.path(parent_dir, "Table5_item_stigma_profile.csv")
write_csv(wide_tbl, table_path)
message("Wrote: ", table_path)

# ---- Heatmap helper ----------------------------------------------------------

build_heatmap <- function(scale_filter, scale_title, figure_label) {
  heat_df <- item_means %>%
    filter(scale_type == scale_filter,
           language %in% langs_available) %>%
    mutate(
      family = factor(model_family[as.character(model)],
                      levels = family_levels),
      row_label = paste0(model_disp[as.character(model)], " | ", item_id),
      language  = factor(language, levels = c("EN", "ZH"))
    )

  row_levels <- heat_df %>%
    distinct(model, item_id, row_label) %>%
    arrange(model, item_id) %>%
    pull(row_label)
  heat_df$row_label <- factor(heat_df$row_label, levels = rev(row_levels))

  ggplot(heat_df, aes(x = vignette, y = row_label, fill = mean_score)) +
    geom_tile(color = "white", linewidth = 0.15) +
    facet_grid(family ~ language, scales = "free_y", space = "free_y",
               switch = "y") +
    scale_fill_gradient2(
      name = "Mean item score\n(1 = low, 4 = high stigma)",
      low = "#2166AC", mid = "#F7F7F7", high = "#B2182B",
      midpoint = 2.5, limits = c(1, 4), oob = scales::squish
    ) +
    scale_x_discrete(labels = vignette_labels, position = "top") +
    labs(
      title    = sprintf("%s. Item-level stigma: %s scale",
                         figure_label, scale_title),
      subtitle = paste(
        "Rows = Model x Item (grouped by developer family);",
        "columns = vignette; panels = EN vs ZH.",
        "Diverging palette centred at scale midpoint (2.5)."
      ),
      x = NULL, y = NULL
    ) +
    theme_minimal(base_size = 8) +
    theme(
      panel.grid         = element_blank(),
      axis.text.y        = element_text(size = 5.5, family = "mono"),
      axis.text.x.top    = element_text(size = 9, face = "bold"),
      strip.text.y.left  = element_text(angle = 0, face = "bold", size = 9),
      strip.text.x       = element_text(face = "bold", size = 10),
      strip.placement    = "outside",
      panel.spacing.y    = unit(0.15, "lines"),
      panel.spacing.x    = unit(0.8,  "lines"),
      legend.position    = "bottom",
      legend.key.width   = unit(2.4, "cm"),
      plot.title         = element_text(face = "bold", size = 12),
      plot.subtitle      = element_text(size = 8.5, color = "grey30")
    )
}

# eFigure 3A: Social Distance heatmap (19 items × 14 models × 2 langs)
p_sd <- build_heatmap("social_distance", "Social Distance", "eFigure 3A")
efig3a <- file.path(parent_dir, "eFigure3A_item_profile_social_distance.pdf")
ggsave(efig3a, p_sd, width = 12, height = 16)
ggsave(file.path(parent_dir, "eFigure3A_item_profile_social_distance.png"),
       p_sd, width = 12, height = 16, dpi = 200)
message("Wrote: ", efig3a)

# eFigure 3B: Prejudice heatmap (21 items × 14 models × 2 langs)
p_pj <- build_heatmap("prejudice", "Prejudice", "eFigure 3B")
efig3b <- file.path(parent_dir, "eFigure3B_item_profile_prejudice.pdf")
ggsave(efig3b, p_pj, width = 12, height = 18)
ggsave(file.path(parent_dir, "eFigure3B_item_profile_prejudice.png"),
       p_pj, width = 12, height = 18, dpi = 200)
message("Wrote: ", efig3b)

# ---- APS spike slope helper --------------------------------------------------

# Anchor item subsets for each scale
sd_anchor  <- c("SD01", "SD11", "SD12", "SD15")          # marriage + childcare
pj_anchor  <- c("PJ15", "PJ20", "PJ21")                  # dangerousness

build_slope <- function(scale_filter, anchor_items, figure_label, n_topup = 2) {
  # Data-driven top-up: items with highest cross-language mean APS spike
  ranked <- wide_tbl %>%
    filter(Scale == scale_filter) %>%
    select(Item_ID, matches("^APS_Spike_")) %>%
    pivot_longer(starts_with("APS_Spike_"),
                 names_to = "lang", values_to = "spike") %>%
    group_by(Item_ID) %>%
    summarise(mean_spike = mean(spike, na.rm = TRUE), .groups = "drop") %>%
    arrange(desc(mean_spike))

  top_up <- ranked %>%
    filter(!Item_ID %in% anchor_items) %>%
    slice_head(n = n_topup) %>%
    pull(Item_ID)

  target <- c(anchor_items, top_up)

  # Long format: one row per model × item × language × vignette (DEP & APS only)
  slope_df <- item_means %>%
    filter(scale_type == scale_filter,
           item_id %in% target,
           vignette %in% c("DEP", "APS"),
           language %in% langs_available) %>%
    left_join(item_meta_lookup, by = c("scale_type", "item_id")) %>%
    mutate(
      family = factor(model_family[as.character(model)],
                      levels = family_levels),
      language = factor(language, levels = c("EN", "ZH")),
      vignette = factor(vignette, levels = c("DEP", "APS")),
      item_panel = paste0(item_id, " (", item_domain, ")")
    )

  # Order panels by mean APS spike (descending)
  panel_order <- slope_df %>%
    filter(vignette == "APS") %>%
    group_by(item_panel, item_id) %>%
    summarise(m = mean(mean_score, na.rm = TRUE), .groups = "drop") %>%
    left_join(ranked, by = c("item_id" = "Item_ID")) %>%
    arrange(desc(mean_spike)) %>%
    pull(item_panel)
  slope_df$item_panel <- factor(slope_df$item_panel, levels = panel_order)

  ncols <- min(3, length(target))

  ggplot(slope_df,
         aes(x = vignette, y = mean_score,
             group = interaction(model, language),
             color = family, linetype = language)) +
    geom_line(alpha = 0.80, linewidth = 0.65) +
    geom_point(aes(shape = language), size = 1.8) +
    facet_wrap(~ item_panel, ncol = ncols) +
    scale_color_manual(values = family_group_colors, name = "Model family",
                       drop = FALSE) +
    scale_linetype_manual(values = c("EN" = "solid", "ZH" = "dashed"),
                          name = "Language") +
    scale_shape_manual(values = c("EN" = 16, "ZH" = 1), name = "Language") +
    scale_y_continuous(limits = c(1, 4), breaks = 1:4) +
    labs(
      title = sprintf(
        "%s. APS spike: DEP -> APS score shift (%s scale)",
        figure_label, ifelse(scale_filter == "social_distance",
                             "Social Distance", "Prejudice")),
      subtitle = paste(
        "Each line = one model. Solid = English; dashed = Chinese.",
        "Upward slope = higher stigma in APS vs depression context."
      ),
      x = "Vignette", y = "Mean item score (1 = low, 4 = high stigma)"
    ) +
    theme_minimal(base_size = 10) +
    theme(
      strip.text       = element_text(face = "bold", size = 8),
      panel.grid.minor = element_blank(),
      plot.title       = element_text(face = "bold", size = 12),
      plot.subtitle    = element_text(size = 9, color = "grey30"),
      legend.position  = "bottom"
    )
}

p_slope_sd <- build_slope("social_distance", sd_anchor, "Figure B-SD", n_topup = 2)
figB_sd <- file.path(parent_dir, "FigB_SD_APS_Spike_Slope.pdf")
ggsave(figB_sd, p_slope_sd, width = 12, height = 7)
message("Wrote: ", figB_sd)

p_slope_pj <- build_slope("prejudice", pj_anchor, "Figure B-PJ", n_topup = 3)
figB_pj <- file.path(parent_dir, "FigB_PJ_APS_Spike_Slope.pdf")
ggsave(figB_pj, p_slope_pj, width = 12, height = 8)
message("Wrote: ", figB_pj)

message("\nAll outputs written to: ", parent_dir)

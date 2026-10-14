# efigure3_item_profile_heatmaps_1002.R
#
# Supplementary Fig. 3A / 3B (npj Digital Medicine revision, 2026-10-02):
# item-level mean scores, Model x Item rows, vignette columns, EN | ZH panels.
#
# The submitted heatmaps (outputs/figures_tables/
# eFigure3{A,B}_*.png) came from a 14-model variant of the heatmap section of
# scripts_public/item_level_profile.R, which is not in the repository (the public
# script lists 13 models). This script reproduces that heatmap from the
# 14-model master CSVs with one correction: the title embedded in the image
# ("Figure A-SD." / "Figure A-PJ.", a legacy label inconsistent with the SI
# numbering) is removed; the SI caption gives the title. Grouping, colours and
# row labels follow the submitted figure. Saved at 300 dpi (submitted: 200 dpi).
#
# Usage: Rscript scripts_public/efigure3_item_profile_heatmaps_1002.R
#
# Model names (2026-10-12): the model tables in this script use the collection names of the authors' merged files
# (e.g. "Gemini 2.5 Flash"), as in the analysis behind the article. analyze_stage1.R run on data_public/ writes the
# article names ("Gemini-2.5-Flash"; scripts_public/Models_name.md); rename them back before running this script.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(ggplot2)
})

args     <- commandArgs(trailingOnly = FALSE)
sf       <- args[startsWith(args, "--file=")]
root_dir <- normalizePath(
  if (length(sf) > 0) file.path(dirname(sub("--file=", "", sf)), "..") else "."
)
an_dir  <- file.path(root_dir, "analysis_14models_20260614")
out_dir <- file.path(root_dir, "outputs", "figures_tables")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# Data names (master CSV) -> display names used in all other figures and tables
display_name <- c(
  "GPT-3.5" = "GPT-3.5", "GPT-4o" = "GPT-4o", "GPT-OSS-120B" = "GPT-OSS-120B",
  "GPT-5.4" = "GPT-5.4", "GPT-5.4 Mini" = "GPT-5.4-Mini",
  "Claude Sonnet 4.5" = "Claude Sonnet 4.5", "Claude Opus 4.6" = "Claude Opus 4.6",
  "Gemini 2.5 Flash" = "Gemini-2.5-Flash", "Gemini 3.1 Pro Preview" = "Gemini-3.1-Pro-Preview",
  "Gemini 3.1 Flash-Lite Preview" = "Gemini-3.1-Flash-Lite-Preview",
  "Gemini 3.5 Flash" = "Gemini-3.5-Flash", "Gemma 4 31B IT" = "Gemma-4-31B-IT",
  "Llama 3.3 70B" = "Llama-3.3-70B", "DeepSeek V3.2" = "DeepSeek-V3.2"
)
model_plot_order <- c(
  "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4-Mini",
  "Claude Sonnet 4.5", "Claude Opus 4.6",
  "Gemini-2.5-Flash", "Gemini-3.1-Pro-Preview", "Gemini-3.1-Flash-Lite-Preview",
  "Gemini-3.5-Flash", "Gemma-4-31B-IT", "Llama-3.3-70B", "DeepSeek-V3.2"
)
# Grouping as in the submitted figure (Gemini-3.1-Pro-Preview shown as its own block)
model_family <- c(
  "GPT-3.5" = "GPT", "GPT-4o" = "GPT", "GPT-OSS-120B" = "GPT",
  "GPT-5.4" = "GPT", "GPT-5.4-Mini" = "GPT",
  "Claude Sonnet 4.5" = "Claude", "Claude Opus 4.6" = "Claude",
  "Gemini-2.5-Flash" = "Gemini", "Gemini-3.1-Pro-Preview" = "Gemini Pro",
  "Gemini-3.1-Flash-Lite-Preview" = "Gemini", "Gemini-3.5-Flash" = "Gemini",
  "Gemma-4-31B-IT" = "Gemini", "Llama-3.3-70B" = "Llama", "DeepSeek-V3.2" = "DeepSeek"
)
family_levels  <- c("GPT", "Claude", "Gemini", "Gemini Pro", "Llama", "DeepSeek")
vignette_order <- c("PLE", "DEP", "APS", "SCZ")

load_valid <- function(lang, lang_label) {
  read_csv(file.path(an_dir, lang, sprintf("results_14models_%s.csv", lang)),
           show_col_types = FALSE) %>%
    filter(response_type == "valid", !is.na(scored_value)) %>%
    mutate(model    = factor(display_name[model], levels = model_plot_order),
           language = lang_label,
           vignette = factor(vignette, levels = vignette_order))
}
both <- bind_rows(load_valid("en", "EN"), load_valid("zh", "ZH"))
stopifnot(!anyNA(both$model), nlevels(droplevels(both$model)) == 14)

item_means <- both %>%
  group_by(language, model, vignette, scale_type, item_id) %>%
  summarise(mean_score = mean(scored_value, na.rm = TRUE), .groups = "drop")

build_heatmap <- function(scale_filter) {
  heat_df <- item_means %>%
    filter(scale_type == scale_filter) %>%
    mutate(
      family    = factor(model_family[as.character(model)], levels = family_levels),
      row_label = paste0(as.character(model), " | ", item_id),
      language  = factor(language, levels = c("EN", "ZH"))
    )
  row_levels <- heat_df %>% distinct(model, item_id, row_label) %>%
    arrange(model, item_id) %>% pull(row_label)
  heat_df$row_label <- factor(heat_df$row_label, levels = rev(row_levels))

  ggplot(heat_df, aes(x = vignette, y = row_label, fill = mean_score)) +
    geom_tile(color = "white", linewidth = 0.15) +
    facet_grid(family ~ language, scales = "free_y", space = "free_y", switch = "y") +
    scale_fill_gradient2(
      name = "Mean item score\n(1 = low, 4 = high stigma)",
      low = "#2166AC", mid = "#F7F7F7", high = "#B2182B",
      midpoint = 2.5, limits = c(1, 4), oob = scales::squish
    ) +
    scale_x_discrete(position = "top") +
    labs(
      subtitle = paste(
        "Rows = Model x Item (grouped by developer family);",
        "columns = vignette; panels = EN vs ZH.",
        "Diverging palette centred at scale midpoint (2.5)."
      ),
      x = NULL, y = NULL
    ) +
    theme_minimal(base_size = 8) +
    theme(
      panel.grid        = element_blank(),
      axis.text.y       = element_text(size = 5.5, family = "mono"),
      axis.text.x.top   = element_text(size = 9, face = "bold"),
      strip.text.y.left = element_text(angle = 0, face = "bold", size = 9),
      strip.text.x      = element_text(face = "bold", size = 10),
      strip.placement   = "outside",
      panel.spacing.y   = unit(0.15, "lines"),
      panel.spacing.x   = unit(0.8,  "lines"),
      legend.position   = "bottom",
      legend.key.width  = unit(2.4, "cm"),
      plot.subtitle     = element_text(size = 8.5, color = "grey30")
    )
}

outs <- list(
  list(scale = "social_distance", stem = "eFigure3A_item_profile_social_distance_1002", h = 16),
  list(scale = "prejudice",       stem = "eFigure3B_item_profile_prejudice_1002",       h = 18)
)
for (o in outs) {
  p <- build_heatmap(o$scale)
  ggsave(file.path(out_dir, paste0(o$stem, ".pdf")), p, width = 12, height = o$h)
  ggsave(file.path(out_dir, paste0(o$stem, ".png")), p, width = 12, height = o$h, dpi = 300)
  cat("Wrote:", file.path(out_dir, paste0(o$stem, ".{pdf,png}")), "\n")
}
cat(sprintf("[OK] %d models, %d model x vignette x item x language means\n",
            nlevels(droplevels(item_means$model)), nrow(item_means)))

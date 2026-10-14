# figure2_cross_language_forest_1002.R
#
# Figure 2 (npj Digital Medicine revision, 2026-10-02). Copy of
# figure2_cross_language_forest_0622.R (which produced the submitted figure),
# with the corrections listed in the October 2026 revision notes:
#   1. The inverse-variance-weighted pooled diamonds and the pooled Cliff's delta
#      annotations are removed (Reviewer 1, Comment 6; Reviewer 3, Minor 3).
#      The bottom row of each panel now shows the median and range of the 14
#      model-level mean differences: an unweighted descriptive summary of the
#      models evaluated, not a population-level estimate.
#   2. Legend: "P < 0.05" / "P >= 0.05" formatting matched to the manuscript.
#   3. X-axis breaks no longer fall on the panel edges, so tick labels of
#      adjacent panels do not overlap.
# Model estimates, CIs, colours and layout are otherwise unchanged.
#
# Usage: Rscript scripts_public/figure2_cross_language_forest_1002.R
#
# Model names (2026-10-12): the model tables in this script use the collection names of the authors' merged files
# (e.g. "Gemini 2.5 Flash"), as in the analysis behind the article. analyze_stage1.R run on data_public/ writes the
# article names ("Gemini-2.5-Flash"; scripts_public/Models_name.md); rename them back before running this script.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tibble)
  library(ggplot2)
  library(patchwork)
  library(grid)
})

# ── Paths ─────────────────────────────────────────────────────────────────────
args    <- commandArgs(trailingOnly = FALSE)
sf      <- args[startsWith(args, "--file=")]
root    <- normalizePath(
  if (length(sf) > 0) file.path(dirname(sub("--file=", "", sf)), "..") else "."
)
an_dir  <- file.path(root, "analysis_14models_20260614")
out_dir <- file.path(root, "outputs", "figures_tables")
dir.create(out_dir, showWarnings = FALSE)

BASE_FONT <- "Helvetica"
PT_BASE   <- 10
PT_AXIS   <- 11
ALPHA_SIG <- 1.00
ALPHA_NS  <- 0.35

# ── Model metadata ─────────────────────────────────────────────────────────────
MODEL_RAW <- c(
  "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4 Mini",
  "Claude Sonnet 4.5", "Claude Opus 4.6",
  "Gemini 2.5 Flash", "Gemini 3.1 Pro Preview", "Gemini 3.1 Flash-Lite Preview", "Gemini 3.5 Flash",
  "Gemma 4 31B IT", "Llama 3.3 70B", "DeepSeek V3.2"
)
SUMMARY  <- "Median (range), 14 models"
Y_LEVELS <- c(SUMMARY, rev(MODEL_RAW))  # ggplot y: bottom → top

# Display labels (no dates; GPT-OSS-120B → GPT-OSS-120B)
Y_LABELS <- c(
  "Median (range), 14 models"     = "Median (range), 14 models",
  "GPT-3.5"                       = "GPT-3.5",
  "GPT-4o"                        = "GPT-4o",
  "GPT-OSS-120B"                  = "GPT-OSS-120B",
  "GPT-5.4"                       = "GPT-5.4",
  "GPT-5.4 Mini"                  = "GPT-5.4-Mini",
  "Claude Sonnet 4.5"             = "Claude Sonnet 4.5",
  "Claude Opus 4.6"               = "Claude Opus 4.6",
  "Gemini 2.5 Flash"              = "Gemini-2.5-Flash",
  "Gemini 3.1 Pro Preview"        = "Gemini-3.1-Pro-Preview",
  "Gemini 3.1 Flash-Lite Preview" = "Gemini-3.1-Flash-Lite-Preview",
  "Gemini 3.5 Flash"              = "Gemini-3.5-Flash",
  "Gemma 4 31B IT"                = "Gemma-4-31B-IT",
  "Llama 3.3 70B"                 = "Llama-3.3-70B",
  "DeepSeek V3.2"                 = "DeepSeek-V3.2"
)

# Family mapping → Okabe-Ito colorblind-safe palette
FAM_MAP <- c(
  "GPT-3.5"                       = "GPT",
  "GPT-4o"                        = "GPT",
  "GPT-OSS-120B"                  = "GPT",
  "GPT-5.4"                       = "GPT",
  "GPT-5.4 Mini"                  = "GPT",
  "Claude Sonnet 4.5"             = "Claude",
  "Claude Opus 4.6"               = "Claude",
  "Gemini 2.5 Flash"              = "Gemini",
  "Gemini 3.1 Pro Preview"        = "Gemini",
  "Gemini 3.1 Flash-Lite Preview" = "Gemini",
  "Gemini 3.5 Flash"              = "Gemini",
  "Gemma 4 31B IT"                = "Gemini",
  "Llama 3.3 70B"                 = "DeepSeek/other",
  "DeepSeek V3.2"                 = "DeepSeek/other",
  "Median (range), 14 models"     = "Summary"
)
FAM_PAL <- c(
  "GPT"            = "#009E73",  # Okabe-Ito bluish-green
  "Claude"         = "#E69F00",  # Okabe-Ito orange
  "Gemini"         = "#0072B2",  # Okabe-Ito deep blue
  "DeepSeek/other" = "#D55E00",  # Okabe-Ito vermillion
  "Summary"        = "#000000"
)

# ── Load & compute CIs ────────────────────────────────────────────────────────
s13 <- read_csv(file.path(an_dir, "tableS13_language_comparison.csv"),
                show_col_types = FALSE) %>%
  filter(model %in% MODEL_RAW) %>%
  mutate(
    se_diff = sqrt(sd_scale_en^2 / n_en + sd_scale_zh^2 / n_zh),
    df_w    = (sd_scale_en^2/n_en + sd_scale_zh^2/n_zh)^2 /
              ((sd_scale_en^2/n_en)^2 / (n_en - 1) +
               (sd_scale_zh^2/n_zh)^2 / (n_zh - 1)),
    ci_lo   = mean_diff_zh_minus_en - qt(0.975, df_w) * se_diff,
    ci_hi   = mean_diff_zh_minus_en + qt(0.975, df_w) * se_diff,
    sig     = wilcox_p_adjusted < 0.05
  )

# Descriptive summary per (vignette × scale): median and range of the 14
# model-level mean differences (unweighted; not a population-level estimate)
summary_df <- s13 %>%
  group_by(vignette, scale_type) %>%
  summarise(
    n_models  = n(),
    mean_diff = median(mean_diff_zh_minus_en),
    ci_lo     = min(mean_diff_zh_minus_en),    # range, stored in the CI columns
    ci_hi     = max(mean_diff_zh_minus_en),
    .groups   = "drop"
  ) %>%
  mutate(model = SUMMARY, sig = TRUE)
stopifnot(all(summary_df$n_models == 14))

# Combined plot data
plot_df <- bind_rows(
  s13 %>% transmute(
    model, vignette, scale_type, sig,
    mean_diff = mean_diff_zh_minus_en,
    ci_lo, ci_hi,
    is_pooled = FALSE
  ),
  summary_df %>% transmute(
    model, vignette, scale_type, sig,
    mean_diff, ci_lo, ci_hi,
    is_pooled = TRUE
  )
) %>%
  mutate(
    model_y  = factor(model, levels = Y_LEVELS),
    family   = factor(FAM_MAP[model], levels = names(FAM_PAL)),
    pt_alpha = if_else(sig, ALPHA_SIG, ALPHA_NS)
  )

# ── X-axis bounds ─────────────────────────────────────────────────────────────
X_LO     <- -17
X_HI     <-  20
X_BREAKS <- c(-10, -5, 0, 5, 10, 15)   # none on the panel edges (-17, 20)

# ── Base theme ────────────────────────────────────────────────────────────────
theme_forest <- function(show_y = FALSE) {
  theme_bw(base_size = PT_BASE, base_family = BASE_FONT) %+replace%
    theme(
      plot.title         = element_text(face = "bold", size = PT_BASE,
                                        hjust = 0.5, margin = margin(b = 2)),
      axis.title         = element_blank(),
      axis.text.y        = if (show_y)
                             element_text(size = 9, hjust = 1, color = "grey15")
                           else
                             element_blank(),
      axis.ticks.y       = if (show_y)
                             element_line(linewidth = 0.3)
                           else
                             element_blank(),
      axis.text.x        = element_text(size = PT_BASE - 1.5, color = "grey15"),
      axis.ticks.x       = element_line(linewidth = 0.3),
      panel.grid.major.x = element_blank(),
      panel.grid.major.y = element_line(color = "grey91", linewidth = 0.2),
      panel.grid.minor   = element_blank(),
      panel.border       = element_rect(color = "grey55", linewidth = 0.38),
      legend.position    = "none",
      plot.margin        = margin(t = 2, r = 2, b = 2,
                                  l = if (show_y) 4 else 0)
    )
}

# ── Panel factory ─────────────────────────────────────────────────────────────
make_panel <- function(vig, sc, show_y = FALSE) {

  d   <- plot_df %>% filter(vignette == vig, scale_type == sc)
  d_m <- d %>% filter(!is_pooled)
  d_p <- d %>% filter(is_pooled)   # summary row: median and range of the 14 models

  ggplot() +
    # Zero reference
    geom_vline(xintercept = 0, linewidth = 0.38, color = "grey35") +
    # Thin dashed separator above the summary row
    geom_hline(yintercept = 1.5, linewidth = 0.28, color = "grey62",
               linetype = "22") +
    # ── Model CIs (segment, no caps) ─────────────────────────────────
    geom_segment(
      data = d_m,
      aes(x     = ci_lo, xend = ci_hi,
          y     = model_y, yend = model_y,
          color = family,
          alpha = pt_alpha),
      linewidth = 0.45
    ) +
    # ── Model mean dots ───────────────────────────────────────────────
    geom_point(
      data = d_m,
      aes(x     = mean_diff,
          y     = model_y,
          color = family,
          alpha = pt_alpha),
      shape = 16, size = 2.1
    ) +
    # ── Summary row: range of the 14 model-level differences ─────────
    geom_segment(
      data      = d_p,
      aes(x = ci_lo, xend = ci_hi, y = model_y, yend = model_y),
      color = "black", linewidth = 0.6
    ) +
    annotate("segment", x = d_p$ci_lo, xend = d_p$ci_lo, y = 0.78, yend = 1.22,
             color = "black", linewidth = 0.6) +
    annotate("segment", x = d_p$ci_hi, xend = d_p$ci_hi, y = 0.78, yend = 1.22,
             color = "black", linewidth = 0.6) +
    # ── Summary row: median (filled square) ──────────────────────────
    geom_point(
      data  = d_p,
      aes(x = mean_diff, y = model_y),
      shape = 15, color = "black", size = 2.9
    ) +
    # ── Scales ────────────────────────────────────────────────────────
    scale_color_manual(values = FAM_PAL, drop = FALSE) +
    scale_alpha_identity() +
    scale_x_continuous(
      limits = c(X_LO, X_HI),
      breaks = X_BREAKS,
      expand = expansion(0)
    ) +
    scale_y_discrete(
      limits = Y_LEVELS,
      labels = if (show_y) Y_LABELS[Y_LEVELS]
               else        setNames(rep("", length(Y_LEVELS)), Y_LEVELS)
    ) +
    labs(title = vig) +
    theme_forest(show_y = show_y)
}

# ── Build 8 panels ─────────────────────────────────────────────────────────────
p_sd <- list(
  make_panel("PLE", "social_distance", show_y = TRUE),
  make_panel("DEP", "social_distance"),
  make_panel("APS", "social_distance"),
  make_panel("SCZ", "social_distance")
)
p_pj <- list(
  make_panel("PLE", "prejudice"),
  make_panel("DEP", "prejudice"),
  make_panel("APS", "prejudice"),
  make_panel("SCZ", "prejudice")
)

# ── Spanning header factory ───────────────────────────────────────────────────
# The grey band is drawn as a panel-filling rect (not plot.background), and the plot
# background is white. A larger inner-side margin therefore renders as a WHITE gap that
# separates the two block headers at the SD | PJ boundary.
mk_hdr <- function(label, inner = c("none", "left", "right")) {
  inner <- match.arg(inner)
  m_l <- if (inner == "left")  11 else 2
  m_r <- if (inner == "right") 11 else 2
  ggplot() +
    annotate("rect", xmin = 0, xmax = 1, ymin = 0, ymax = 1, fill = "#EFEFEF") +
    annotate("text", x = 0.5, y = 0.5,
             label    = label,
             fontface = "bold",
             size     = (PT_AXIS + 1) / 2.835,
             hjust    = 0.5,
             color    = "grey10",
             family   = BASE_FONT) +
    scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
    scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) +
    theme_void(base_family = BASE_FONT) +
    theme(
      plot.background = element_rect(fill = "white", color = NA),
      plot.margin     = margin(t = 6, b = 4, l = m_l, r = m_r)
    )
}

# ── Sub-blocks: header / 4-panel row ─────────────────────────────────────────
sd_panels <- p_sd[[1]] + p_sd[[2]] + p_sd[[3]] + p_sd[[4]] +
  plot_layout(nrow = 1, widths = c(1, 1, 1, 1))

pj_panels <- p_pj[[1]] + p_pj[[2]] + p_pj[[3]] + p_pj[[4]] +
  plot_layout(nrow = 1)

sd_block <- mk_hdr("Social Distance", inner = "right") / sd_panels +
  plot_layout(heights = c(0.065, 1))

pj_block <- mk_hdr("Prejudice", inner = "left") / pj_panels +
  plot_layout(heights = c(0.065, 1))

# Side-by-side with EQUAL per-panel widths across both blocks.
# Equal block widths (4:4) yield all 8 vignette panels at identical width: patchwork
# aligns the two nested panel grids and places the SD block's y-axis model-label strip
# in a shared left margin (not stolen from its panels). Verified by pixel measurement
# of the per-panel x=0 reference lines: SD pitch == PJ pitch == 677 px (diff 0.0).
SD_PJ_WIDTH_RATIO <- c(4.0, 4.0)
main_area <- (sd_block | pj_block) +
  plot_layout(widths = SD_PJ_WIDTH_RATIO)

# ── Shared X-axis label ───────────────────────────────────────────────────────
xlab_row <- ggplot() +
  annotate("text", x = 0.5, y = 0.5,
           label  = paste0("Mean Difference (Mandarin Chinese - English)",
                           " with 95% CI"),
           size   = PT_AXIS / 2.835,
           hjust  = 0.5,
           color  = "grey10",
           family = BASE_FONT) +
  theme_void(base_family = BASE_FONT) +
  theme(plot.margin = margin(t = 0, b = 3))

# ── Legend ────────────────────────────────────────────────────────────────────
leg_pts <- tibble(
  x      = c(1.1, 2.3, 3.5, 4.9,   6.5, 7.9,   9.4),
  y      = rep(1, 7),
  lbl    = c("GPT", "Claude", "Gemini", "DeepSeek/other",
             "italic(P) < 0.05", "italic(P) >= 0.05",
             "Median and range of the 14 models"),
  is_math = c(FALSE, FALSE, FALSE, FALSE, TRUE, TRUE, FALSE),
  col    = c("#009E73", "#E69F00", "#0072B2", "#D55E00",
             "#555555", "#555555", "#000000"),
  alph   = c(1, 1, 1, 1,  1, ALPHA_NS, 1),
  shp    = c(16, 16, 16, 16, 16, 16, 15),
  sz     = c(3, 3, 3, 3, 3, 3, 2.9)
)

leg_grp_hdr <- tibble(
  x   = c(0.35, 5.85),
  y   = c(1.62, 1.62),
  lbl = c("Developer family:", "Significance / summary row:")
)

leg_plot <- ggplot() +
  # Header labels
  geom_text(data = leg_grp_hdr,
            aes(x = x, y = y, label = lbl),
            hjust = 0, size = 2.65, fontface = "bold",
            color = "grey20", family = BASE_FONT) +
  # Range line for the summary-row legend item
  annotate("segment", x = 9.4 - 0.32, xend = 9.4 + 0.32, y = 1, yend = 1,
           color = "black", linewidth = 0.6) +
  # Colored dots / median square
  geom_point(data = leg_pts,
             aes(x = x, y = y),
             shape = leg_pts$shp,
             color = leg_pts$col,
             alpha = leg_pts$alph,
             size  = leg_pts$sz) +
  # Item labels (P-value labels parsed as plotmath so ">=" renders as a glyph)
  geom_text(data = filter(leg_pts, !is_math),
            aes(x = x, y = 0.38, label = lbl),
            size = 2.65, hjust = 0.5,
            color = "grey20", family = BASE_FONT) +
  geom_text(data = filter(leg_pts, is_math),
            aes(x = x, y = 0.38, label = lbl), parse = TRUE,
            size = 2.65, hjust = 0.5,
            color = "grey20", family = BASE_FONT) +
  xlim(0, 10.2) + ylim(0, 2) +
  theme_void(base_family = BASE_FONT) +
  theme(plot.margin = margin(t = 3, b = 6))

# ── Assemble ──────────────────────────────────────────────────────────────────
combined <- (main_area / xlab_row / leg_plot) +
  plot_layout(heights = c(1, 0.035, 0.10))

# ── Save ──────────────────────────────────────────────────────────────────────
FIG_W <- 20.0
FIG_H <-  8.5

pdf_path <- file.path(out_dir, "figure2_cross_language_forest_1002.pdf")
png_path <- file.path(out_dir, "figure2_cross_language_forest_1002.png")

ggsave(pdf_path, combined, width = FIG_W, height = FIG_H,
       device = "pdf", family = BASE_FONT)
ggsave(png_path, combined, width = FIG_W, height = FIG_H, dpi = 300)

pdf_kb <- round(file.size(pdf_path) / 1024)
png_kb <- round(file.size(png_path) / 1024)

cat("\n── Figure 2 outputs ──────────────────────────────────────────\n")
cat(sprintf("  PDF : %s  [%d KB]\n", pdf_path, pdf_kb))
cat(sprintf("  PNG : %s  [%d KB]\n", png_path, png_kb))
cat(sprintf("  Size: %.1f × %.1f in @ 300 dpi\n", FIG_W, FIG_H))

# Summary row values (also written to CSV for the Results text)
sum_out <- summary_df %>%
  transmute(scale_type, vignette, n_models,
            median_diff_zh_minus_en = mean_diff,
            min_diff = ci_lo, max_diff = ci_hi) %>%
  arrange(scale_type, vignette)
write_csv(sum_out, file.path(out_dir, "figure2_summary_median_range_1002.csv"))
cat("\n  Median and range of the 14 model-level differences per cell:\n")
print(as.data.frame(sum_out %>% mutate(across(where(is.numeric), \(x) round(x, 2)))))

cat(sprintf("\n  [OK] %d model×vignette×scale cells plotted\n",
            nrow(s13)))
cat(sprintf("  [OK] Significant cells: %d / %d\n",
            sum(s13$sig), nrow(s13)))
cat("  [OK] GPT-OSS-120B naming applied\n")
cat("  [OK] Colorblind-safe Okabe-Ito palette\n")
cat("  [OK] Pooled IVW estimates removed; median and range shown instead\n")

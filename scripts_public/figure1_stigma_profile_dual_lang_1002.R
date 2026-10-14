# figure1_stigma_profile_dual_lang_1002.R
#
# Figure 1 (npj Digital Medicine revision, 2026-10-02). Copy of
# figure1_stigma_profile_dual_lang_0622.R (which produced the submitted figure),
# with the reviewer-driven corrections listed in
# the October 2026 revision notes:
#   1. Access mode for Novita-served models labelled "Open-weight", not
#      "Open-source" (Reviewer 1, Comment 12).
#   2. Human baseline (Wang et al., 2020; Chinese-language Taiwanese sample)
#      drawn on the Mandarin Chinese panels only (Reviewer 2, Comment 9).
#   3. Panel labels in lower-case bold a-d (npj figure guideline).
# Data, layout and styling are otherwise unchanged.
#
# Layout (4 panels, top to bottom):
#   a  English — Social Distance  (range 19-76)
#   b  English — Prejudice        (range 21-84)
#   c  Mandarin Chinese — Social Distance
#   d  Mandarin Chinese — Prejudice
#
# Usage: Rscript scripts_public/figure1_stigma_profile_dual_lang_1002.R
#
# Model names (2026-10-12): the model tables in this script use the collection names of the authors' merged files
# (e.g. "Gemini 2.5 Flash"), as in the analysis behind the article. analyze_stage1.R run on data_public/ writes the
# article names ("Gemini-2.5-Flash"; scripts_public/Models_name.md); rename them back before running this script.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tidyr)
  library(ggplot2)
  library(patchwork)
  library(grid)
})

# ── Paths ─────────────────────────────────────────────────────────────────────
args <- commandArgs(trailingOnly = FALSE)
sf   <- args[startsWith(args, "--file=")]
root_dir <- normalizePath(
  if (length(sf) > 0) file.path(dirname(sub("--file=", "", sf)), "..") else "."
)
an_dir  <- file.path(root_dir, "analysis_14models_20260614")
out_dir <- file.path(root_dir, "outputs", "figures_tables")
dir.create(out_dir, showWarnings = FALSE)

BASE_FONT <- "Helvetica"

# ── Model order, short labels, deployment ─────────────────────────────────────
model_order <- c(
  "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4 Mini",
  "Claude Sonnet 4.5", "Claude Opus 4.6",
  "Gemini 2.5 Flash", "Gemini 3.1 Pro Preview", "Gemini 3.1 Flash-Lite Preview", "Gemini 3.5 Flash",
  "Gemma 4 31B IT", "Llama 3.3 70B", "DeepSeek V3.2"
)

# X-axis labels (short, two-line where needed)
model_xlabels <- c(
  "GPT-3.5"                       = "GPT-3.5",
  "GPT-4o"                        = "GPT-4o",
  "GPT-OSS-120B"                  = "GPT-OSS-
120B",
  "GPT-5.4"                       = "GPT-5.4",
  "GPT-5.4 Mini"                  = "GPT-5.4-
Mini",
  "Claude Sonnet 4.5"             = "Claude
Sonnet 4.5",
  "Claude Opus 4.6"               = "Claude
Opus 4.6",
  "Gemini 2.5 Flash"              = "Gemini-
2.5-Flash",
  "Gemini 3.1 Pro Preview"        = "Gemini-3.1-
Pro-Preview",
  "Gemini 3.1 Flash-Lite Preview" = "Gemini-3.1-
Flash-Lite-
Preview",
  "Gemini 3.5 Flash"              = "Gemini-
3.5-Flash",
  "Gemma 4 31B IT"                = "Gemma-4-
31B-IT",
  "Llama 3.3 70B"                 = "Llama-
3.3-70B",
  "DeepSeek V3.2"                 = "DeepSeek-
V3.2"
)

deployment_map <- c(
  "GPT-3.5"                       = "API",
  "GPT-4o"                        = "API",
  "GPT-OSS-120B"                  = "Open-weight",
  "GPT-5.4"                       = "API",
  "GPT-5.4 Mini"                  = "API",
  "Claude Sonnet 4.5"             = "API",
  "Claude Opus 4.6"               = "API",
  "Gemini 2.5 Flash"              = "API",
  "Gemini 3.1 Pro Preview"        = "API",
  "Gemini 3.1 Flash-Lite Preview" = "API",
  "Gemini 3.5 Flash"              = "API",
  "Gemma 4 31B IT"                = "Open-weight",
  "Llama 3.3 70B"                 = "Open-weight",
  "DeepSeek V3.2"                 = "Open-weight"
)

# X-axis numeric positions 1-13
# Family boundaries (between families):
#   OpenAI ends at 5, Anthropic at 7, Google at 11, Meta at 12, DeepSeek at 13
fam_sep_x  <- c(5.5, 7.5, 12.5, 13.5)   # vertical separator lines

# Background band definitions
fam_bands <- tibble(
  xmin = c(0.5, 5.5, 7.5, 12.5, 13.5),
  xmax = c(5.5, 7.5, 12.5, 13.5, 14.5),
  fill = c("#F2F2F2", "#FAFAFA", "#F2F2F2", "#FAFAFA", "#F2F2F2"),
  label = c("OpenAI", "Anthropic", "Google", "Meta", "DeepSeek"),
  lx    = c(3.0, 6.5, 10.0, 13.0, 14.0)
)

# ── Vignette colors: Okabe-Ito ────────────────────────────────────────────────
vig_colors <- c(
  PLE = "#56B4E9",   # sky blue
  DEP = "#009E73",   # bluish green
  APS = "#E69F00",   # orange
  SCZ = "#D55E00"    # vermillion
)
vig_labels <- c(
  PLE = "PLE",
  DEP = "DEP",
  APS = "APS",
  SCZ = "SCZ"
)
vig_long <- c(
  PLE = "PLE (Psychotic-Like Experiences)",
  DEP = "DEP (Major Depression)",
  APS = "APS (Attenuated Psychosis Syndrome)",
  SCZ = "SCZ (Schizophrenia)"
)

# ── Human baselines: Wang et al. (2020) Taiwan, N = 268 ──────────────────────
human_bl <- tribble(
  ~vignette, ~scale_type,       ~human_mean,
  "PLE",     "social_distance",  38.78,
  "DEP",     "social_distance",  48.10,
  "APS",     "social_distance",  47.98,
  "SCZ",     "social_distance",  53.55,
  "PLE",     "prejudice",        42.25,
  "DEP",     "prejudice",        48.56,
  "APS",     "prejudice",        48.13,
  "SCZ",     "prejudice",        52.62
) %>%
  mutate(vignette = factor(vignette, levels = c("PLE","DEP","APS","SCZ")))

# ── Load data ─────────────────────────────────────────────────────────────────
load_runs <- function(lang) {
  read_csv(file.path(an_dir, lang, "run_level_scale_scores.csv"),
           show_col_types = FALSE) %>%
    filter(in_primary_analysis == "TRUE") %>%
    mutate(language = lang)
}

compute_ci <- function(df) {
  df %>%
    group_by(language, model, vignette, scale_type) %>%
    summarise(
      n     = n(),
      mean  = mean(scale_score_primary, na.rm = TRUE),
      se    = sd(scale_score_primary,   na.rm = TRUE) / sqrt(n),
      ci_lo = mean - qt(0.975, df = n - 1) * se,
      ci_hi = mean + qt(0.975, df = n - 1) * se,
      .groups = "drop"
    ) %>%
    mutate(
      model      = factor(model, levels = model_order),
      vignette   = factor(vignette, levels = c("PLE","DEP","APS","SCZ")),
      deployment = factor(deployment_map[as.character(model)],
                          levels = c("API","Open-weight"))
    )
}

stats_all <- bind_rows(load_runs("en"), load_runs("zh")) %>% compute_ci()

# ── Shared Y-axis (covers all 4 panels + baselines) ───────────────────────────
Y_LO    <- 17
Y_HI    <- 72
Y_BREAKS <- c(20, 30, 40, 50, 60, 70)

# ── Base theme ────────────────────────────────────────────────────────────────
theme_fig1 <- function(show_x = FALSE) {
  theme_bw(base_size = 9, base_family = BASE_FONT) %+replace%
    theme(
      plot.title         = element_text(face = "bold", size = 9,
                                        hjust = 0, margin = margin(b = 2)),
      axis.title.y       = element_text(size = 8, angle = 90,
                                        margin = margin(r = 4)),
      axis.title.x       = element_blank(),
      axis.text.x        = if (show_x) {
        element_text(size = 7.2, angle = 40, hjust = 1,
                     vjust = 1, lineheight = 0.85)
      } else {
        element_blank()
      },
      axis.ticks.x       = if (show_x) element_line(linewidth = 0.3) else element_blank(),
      axis.text.y        = element_text(size = 7.5),
      panel.grid.major.x = element_blank(),
      panel.grid.minor   = element_blank(),
      panel.grid.major.y = element_line(color = "grey88", linewidth = 0.28),
      panel.border       = element_rect(color = "grey55", linewidth = 0.45),
      legend.position    = "none",
      plot.margin        = margin(t = 3, r = 6, b = 1, l = 4)
    )
}

# ── Panel factory ─────────────────────────────────────────────────────────────
make_panel <- function(data_lang, scale_filter, panel_label, show_x = FALSE) {
  d  <- data_lang %>% filter(scale_type == scale_filter)
  # Human baseline only on the Mandarin Chinese panels: Wang et al. (2020) is a
  # Chinese-language Taiwanese sample, not a comparator for English prompts.
  bl <- human_bl  %>% filter(scale_type == scale_filter,
                             unique(data_lang$language) == "zh")

  scale_title <- if (scale_filter == "social_distance")
    "Social Distance score" else "Prejudice score"
  lang_label  <- if (unique(data_lang$language) == "en")
    "English Prompts" else "Mandarin Chinese Prompts"
  y_label <- paste0(scale_title, " (higher = more stigma)")

  p <- ggplot(d, aes(x = model, y = mean,
                     color = vignette,
                     group = vignette)) +
    # ── Family background bands ───────────────────────────────────────
    geom_rect(
      data        = fam_bands,
      aes(xmin = xmin, xmax = xmax, ymin = -Inf, ymax = Inf, fill = fill),
      inherit.aes = FALSE, alpha = 0.55
    ) +
    # ── Family separator lines ─────────────────────────────────────────
    geom_vline(xintercept = fam_sep_x,
               color = "grey58", linewidth = 0.32, linetype = "solid") +
    # ── Human baseline horizontal dotted lines ────────────────────────
    geom_hline(
      data        = bl,
      aes(yintercept = human_mean, color = vignette),
      linetype    = "dotted", linewidth = 0.55, alpha = 0.65,
      inherit.aes = FALSE
    ) +
    # ── 95% CI bars ────────────────────────────────────────────────────
    geom_errorbar(
      aes(ymin = ci_lo, ymax = ci_hi),
      position = position_dodge(width = 0.72),
      width    = 0, linewidth = 0.42, alpha = 0.82
    ) +
    # ── Mean dots ─────────────────────────────────────────────────────
    geom_point(
      aes(shape = deployment),
      position = position_dodge(width = 0.72),
      size     = 2.2, alpha = 0.95
    ) +
    # ── Scales ────────────────────────────────────────────────────────
    scale_fill_identity() +
    scale_color_manual(values = vig_colors, labels = vig_long,
                       name = "Vignette") +
    scale_shape_manual(
      values = c("API" = 16, "Open-weight" = 5),
      name   = "Access",
      labels = c("API" = "API", "Open-weight" = "Open-weight (via Novita.AI)")
    ) +
    scale_x_discrete(
      limits = model_order,
      labels = model_xlabels[model_order]
    ) +
    scale_y_continuous(
      limits = c(Y_LO, Y_HI),
      breaks = Y_BREAKS,
      expand = expansion(0)
    ) +
    # ── Family labels (top of band) ───────────────────────────────────
    annotate("text",
      x     = fam_bands$lx,
      y     = Y_HI - 1.2,
      label = fam_bands$label,
      hjust = 0.5, vjust = 1,
      size  = 2.4, fontface = "italic",
      color = "grey38", family = BASE_FONT
    ) +
    labs(
      title = sprintf("%s   %s | %s", panel_label, scale_title, lang_label),
      y     = y_label
    ) +
    theme_fig1(show_x = show_x)

  p
}

# ── Build 4 panels ────────────────────────────────────────────────────────────
en_d <- stats_all %>% filter(language == "en")
zh_d <- stats_all %>% filter(language == "zh")

pA <- make_panel(en_d, "social_distance",  "a", show_x = FALSE)
pB <- make_panel(en_d, "prejudice",        "b", show_x = FALSE)
pC <- make_panel(zh_d, "social_distance",  "c", show_x = FALSE)
pD <- make_panel(zh_d, "prejudice",        "d", show_x = TRUE)

# ── Legend panel ──────────────────────────────────────────────────────────────
leg_title_vig <- paste0(
  "Vignette  (horizontal dotted lines in panels c and d = Wang et al. [2020] human baseline,\n",
  "Taiwanese general public, Chinese-language survey, N = 268 per vignette)"
)
p_leg_src <- ggplot(
  expand.grid(
    vignette   = factor(c("PLE","DEP","APS","SCZ"), levels=c("PLE","DEP","APS","SCZ")),
    deployment = factor(c("API","Open-weight"), levels=c("API","Open-weight"))
  ) %>% mutate(x = as.integer(vignette), y = as.integer(deployment)),
  aes(x = x, y = y, color = vignette, shape = deployment)
) +
  geom_point(size = 2.8) +
  scale_color_manual(values = vig_colors, labels = vig_long,
                     name = leg_title_vig) +
  scale_shape_manual(
    values = c("API" = 16, "Open-weight" = 5),
    name   = "Access mode",
    labels = c("API" = "Developer primary API",
               "Open-weight" = "Open-weight model via Novita.AI")
  ) +
  guides(
    color = guide_legend(nrow = 2, order = 1,
                         override.aes = list(size = 3, shape = 16)),
    shape = guide_legend(nrow = 1, order = 2,
                         override.aes = list(size = 3,
                           color = "grey30"))
  ) +
  theme_void(base_family = BASE_FONT) +
  theme(
    legend.position  = "bottom",
    legend.direction = "horizontal",
    legend.box       = "vertical",
    legend.text      = element_text(size = 7.5, family = BASE_FONT),
    legend.title     = element_text(size = 8, face = "bold",
                                    family = BASE_FONT),
    legend.key.size  = unit(0.38, "cm"),
    legend.key.width = unit(0.55, "cm"),
    legend.spacing.y = unit(0.15, "cm"),
    legend.box.margin = margin(t = 2)
  )

legend_grob <- ggplotGrob(p_leg_src)
leg_idx     <- which(legend_grob$layout$name == "guide-box-bottom")
legend_only <- legend_grob$grobs[[leg_idx]]
p_legend_row <- wrap_elements(legend_only)

# ── Assemble ──────────────────────────────────────────────────────────────────
combined <- pA / pB / pC / pD / p_legend_row +
  plot_layout(heights = c(1, 1, 1, 1.28, 0.22))

# ── Save ──────────────────────────────────────────────────────────────────────
FIG_W <- 14.0
FIG_H <- 16.0
pdf_path <- file.path(out_dir, "figure1_stigma_profile_dual_lang_1002.pdf")
png_path <- file.path(out_dir, "figure1_stigma_profile_dual_lang_1002.png")

ggsave(pdf_path, combined, width = FIG_W, height = FIG_H,
       device = "pdf", family = BASE_FONT)
ggsave(png_path, combined, width = FIG_W, height = FIG_H, dpi = 300)

pdf_kb <- round(file.size(pdf_path) / 1024)
png_kb <- round(file.size(png_path) / 1024)

cat("\n── Figure 1 outputs ─────────────────────────────────────────\n")
cat(sprintf("  PDF: %s  [%d KB]\n", pdf_path, pdf_kb))
cat(sprintf("  PNG: %s  [%d KB]\n", png_path, png_kb))
cat(sprintf("  Dimensions: %.1f x %.1f in,  shared Y: %d-%d\n",
            FIG_W, FIG_H, Y_LO, Y_HI))

n_ok <- stats_all %>% distinct(language, model, vignette, scale_type) %>% nrow()
cat(sprintf("  [OK] %d / 224 cells plotted\n", n_ok))
cat("  [OK] Human baseline: Wang et al. (2020) Taiwan (N=268), Mandarin Chinese panels only\n")
cat("  [OK] Model label: GPT-OSS-120B (with hyphens)\n")

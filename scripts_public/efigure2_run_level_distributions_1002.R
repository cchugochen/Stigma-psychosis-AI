# efigure2_run_level_distributions_1002.R — revision copy (2026-10-02) of
# efigure2_run_level_distributions_0622.R. Only change: Novita-served models are
# labelled "Open-weight" rather than "Open-source" (Reviewer 1, Comment 12);
# output goes to outputs/figures_tables.
#
# efigure2_run_level_distributions.R
#
# eFigure 2. Run-Level Stigma Score Distributions by
# (Model x Vignette x Scale x Language).
#
# Layout (4 panels, top to bottom), mirroring figure1_stigma_profile_dual_lang.R:
#   A  English — Social Distance
#   B  English — Prejudice
#   C  Mandarin Chinese — Social Distance
#   D  Mandarin Chinese — Prejudice
#
# Each point = one qualifying run (>=80% item completeness; primary-analysis
# runs), jittered within vignette dodge. Within each model, vignettes appear
# left-to-right as PLE -> DEP -> APS -> SCZ. Shape: solid circle = API,
# open diamond = open-weight via Novita.AI.
#
# Usage: Rscript scripts_public/efigure2_run_level_distributions_0529.R
#
# Model names (2026-10-12): the model tables in this script use the collection names of the authors' merged files
# (e.g. "Gemini 2.5 Flash"), as in the analysis behind the article. analyze_stage1.R run on data_public/ writes the
# article names ("Gemini-2.5-Flash"; scripts_public/Models_name.md); rename them back before running this script.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
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

BASE_FONT <- "Helvetica"

model_order <- c(
  "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4 Mini",
  "Claude Sonnet 4.5", "Claude Opus 4.6",
  "Gemini 2.5 Flash", "Gemini 3.1 Pro Preview", "Gemini 3.1 Flash-Lite Preview", "Gemini 3.5 Flash",
  "Gemma 4 31B IT", "Llama 3.3 70B", "DeepSeek V3.2"
)

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

fam_sep_x  <- c(5.5, 7.5, 12.5, 13.5)
fam_bands <- tibble(
  xmin = c(0.5, 5.5, 7.5, 12.5, 13.5),
  xmax = c(5.5, 7.5, 12.5, 13.5, 14.5),
  fill = c("#F2F2F2", "#FAFAFA", "#F2F2F2", "#FAFAFA", "#F2F2F2"),
  label = c("OpenAI", "Anthropic", "Google", "Meta", "DeepSeek"),
  lx    = c(3.0, 6.5, 10.0, 13.0, 14.0)
)

vig_colors <- c(
  PLE = "#56B4E9",
  DEP = "#009E73",
  APS = "#E69F00",
  SCZ = "#D55E00"
)
vig_long <- c(
  PLE = "PLE (Psychotic-Like Experiences)",
  DEP = "DEP (Major Depression)",
  APS = "APS (Attenuated Psychosis Syndrome)",
  SCZ = "SCZ (Schizophrenia)"
)

# ── Load data ─────────────────────────────────────────────────────────────────
load_runs <- function(lang) {
  read_csv(file.path(an_dir, lang, "run_level_scale_scores.csv"),
           show_col_types = FALSE) %>%
    filter(in_primary_analysis == "TRUE" | in_primary_analysis == TRUE) %>%
    mutate(language = lang)
}

runs_all <- bind_rows(load_runs("en"), load_runs("zh")) %>%
  mutate(
    model      = factor(model, levels = model_order),
    vignette   = factor(vignette, levels = c("PLE","DEP","APS","SCZ")),
    deployment = factor(deployment_map[as.character(model)],
                        levels = c("API","Open-weight"))
  )

# qualifying-run range audit (legend cross-check)
qr <- runs_all %>%
  count(language, model, vignette, scale_type) %>%
  group_by(language) %>%
  summarise(min_n = min(n), max_n = max(n), .groups = "drop")
print(qr)

rng <- range(runs_all$scale_score_primary, na.rm = TRUE)
cat(sprintf("run-level score range: %.1f - %.1f\n", rng[1], rng[2]))

Y_LO <- floor(rng[1] / 5) * 5 - 1
Y_HI <- ceiling(rng[2] / 5) * 5 + 1
Y_BREAKS <- seq(20, Y_HI - 1, by = 10)

theme_efig2 <- function(show_x = FALSE) {
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

make_panel <- function(lang_code, scale_filter, panel_label, show_x = FALSE) {
  d <- runs_all %>%
    filter(language == lang_code, scale_type == scale_filter)

  scale_title <- if (scale_filter == "social_distance")
    "Social Distance score" else "Prejudice score"
  lang_label  <- if (lang_code == "en")
    "English Prompts" else "Mandarin Chinese Prompts"
  y_label <- paste0(scale_title, " (higher = more stigma)")

  ggplot(d, aes(x = model, y = scale_score_primary,
                color = vignette, group = vignette)) +
    geom_rect(
      data        = fam_bands,
      aes(xmin = xmin, xmax = xmax, ymin = -Inf, ymax = Inf, fill = fill),
      inherit.aes = FALSE, alpha = 0.55
    ) +
    geom_vline(xintercept = fam_sep_x,
               color = "grey58", linewidth = 0.32, linetype = "solid") +
    geom_point(
      aes(shape = deployment),
      position = position_jitterdodge(jitter.width = 0.12,
                                      jitter.height = 0,
                                      dodge.width = 0.72, seed = 42),
      size = 0.75, alpha = 0.55, stroke = 0.45
    ) +
    scale_fill_identity() +
    scale_color_manual(values = vig_colors, labels = vig_long,
                       name = "Vignette") +
    scale_shape_manual(
      values = c("API" = 16, "Open-weight" = 5),
      name   = "Access"
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
    theme_efig2(show_x = show_x)
}

pA <- make_panel("en", "social_distance", "A", show_x = FALSE)
pB <- make_panel("en", "prejudice",       "B", show_x = FALSE)
pC <- make_panel("zh", "social_distance", "C", show_x = FALSE)
pD <- make_panel("zh", "prejudice",       "D", show_x = TRUE)

leg_title_vig <- "Vignette  (each point = one qualifying run; 30 runs per cell administered)"
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
                         override.aes = list(size = 3, color = "grey30"))
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

combined <- pA / pB / pC / pD / p_legend_row +
  plot_layout(heights = c(1, 1, 1, 1.28, 0.22))

FIG_W <- 14.0
FIG_H <- 16.0
pdf_path <- file.path(out_dir, "efigure2_run_level_distributions_1002.pdf")
png_path <- file.path(out_dir, "efigure2_run_level_distributions_1002.png")

ggsave(pdf_path, combined, width = FIG_W, height = FIG_H,
       device = "pdf", family = BASE_FONT)
ggsave(png_path, combined, width = FIG_W, height = FIG_H, dpi = 300)

cat("\n── eFigure 2 outputs ───────────────────────────────────────\n")
cat(sprintf("  PDF: %s  [%d KB]\n", pdf_path, round(file.size(pdf_path) / 1024)))
cat(sprintf("  PNG: %s  [%d KB]\n", png_path, round(file.size(png_path) / 1024)))
n_cells <- runs_all %>% distinct(language, model, vignette, scale_type) %>% nrow()
cat(sprintf("  [OK] %d / 224 cells plotted; %d run-level points\n",
            n_cells, nrow(runs_all)))

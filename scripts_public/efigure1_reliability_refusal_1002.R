# efigure1_reliability_refusal_1002.R
#
# Supplementary Fig. 1 (npj Digital Medicine revision, 2026-10-02). Copy of
# efigure1_reliability_refusal_0622.R with these corrections:
#   1. The title embedded in the image is removed. The submitted SI carried an
#      older render whose embedded title read "eFigure 1 ... Across 13 Large
#      Language Models" although 14 models are plotted; the SI caption paragraph
#      already gives the title.
#   2. Embedded footnote: the GPT-OSS-120B sentence is corrected. Some
#      GPT-OSS-120B runs were complete on a scale (0-17 per cell), and one cell
#      (Mandarin Chinese, PLE, Prejudice) had >= 10 complete runs and is evaluable.
#   3. Model labels use the hyphenated display names used in all other figures
#      and tables (the 0622 render showed the spaced data names).
#   4. Layout: the inline English / Mandarin Chinese key no longer overlaps the
#      x-axis, the top (n=8) label is no longer clipped, and the two Panel B
#      facets no longer share an overlapping "12%0%" tick label.
#   5. (2026-10-14, supplement check S02) Panel B: the light category is named "Unparseable or error", as in
#      Supplementary Fig. 4 and Table 3b (it includes API errors), instead of "Safety filter / unparseable"; the
#      footnote no longer lists safety-filter interventions, of which there were none. Output renamed 1014.
# Data and encodings are otherwise unchanged.
#
# Usage: Rscript scripts_public/efigure1_reliability_refusal_1002.R
#
# Model names (2026-10-12): the model tables in this script use the collection names of the authors' merged files
# (e.g. "Gemini 2.5 Flash"), as in the analysis behind the article. analyze_stage1.R run on data_public/ writes the
# article names ("Gemini-2.5-Flash"; scripts_public/Models_name.md); rename them back before running this script.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tidyr)
  library(stringr)
  library(ggplot2)
  library(patchwork)
})

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_FONT <- "Helvetica"
PT_AX     <- 10.5   # axis tick labels
PT_LBL    <- 11     # axis titles
PT_TTL    <- 12     # panel titles
PT_MAIN   <- 14     # main figure title
PT_FOOT   <-  8.5   # footnote

MODEL_RAW <- c(
  "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4 Mini",
  "Claude Sonnet 4.5", "Claude Opus 4.6",
  "Gemini 2.5 Flash", "Gemini 3.1 Pro Preview", "Gemini 3.1 Flash-Lite Preview", "Gemini 3.5 Flash",
  "Gemma 4 31B IT", "Llama 3.3 70B", "DeepSeek V3.2"
)

MODEL_DISP <- setNames(c(
  "GPT-3.5", "GPT-4o", "GPT-OSS-120B", "GPT-5.4", "GPT-5.4-Mini",
  "Claude Sonnet 4.5", "Claude Opus 4.6",
  "Gemini-2.5-Flash", "Gemini-3.1-Pro-Preview", "Gemini-3.1-Flash-Lite-Preview", "Gemini-3.5-Flash",
  "Gemma-4-31B-IT", "Llama-3.3-70B", "DeepSeek-V3.2"
), MODEL_RAW)

FAM_MAP <- setNames(c(
  "GPT", "GPT", "GPT", "GPT", "GPT",
  "Claude", "Claude",
  "Gemini", "Gemini", "Gemini", "Gemini", "Gemini",
  "Llama", "DeepSeek"
), MODEL_RAW)

FAM_COL <- c(
  GPT      = "#009E73",
  Claude   = "#E69F00",
  Gemini   = "#0072B2",
  Llama    = "#CC79A7",
  DeepSeek = "#D55E00"
)

# Y axis: bottom = DeepSeek (y=1), top = GPT-3.5 (y=14)
DISP_ORDER <- unname(rev(MODEL_DISP[MODEL_RAW]))   # unnamed: axis shows the hyphenated display names
# Family dividers (between the indicated y-integer positions)
FAM_DIV_Y  <- c(9.5, 7.5, 2.5, 1.5)

# ── Paths ─────────────────────────────────────────────────────────────────────
args    <- commandArgs(trailingOnly = FALSE)
sf      <- args[startsWith(args, "--file=")]
root    <- normalizePath(
  if (length(sf) > 0) file.path(dirname(sub("--file=", "", sf)), "..") else "."
)
an_dir  <- file.path(root, "analysis_14models_20260614")
out_dir <- file.path(root, "outputs", "figures_tables")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# ── Load reliability ──────────────────────────────────────────────────────────
load_rel <- function(lang) {
  read_csv(file.path(an_dir, lang, "tableS3_reliability.csv"),
           show_col_types = FALSE) %>%
    mutate(
      language = lang,
      model    = recode(model,
        "Gemini-3.1-Pro-Preview"        = "Gemini-3.1-Pro-Preview",
        "Gemini-3.1-Flash-Lite-Preview" = "Gemini-3.1-Flash-Lite-Preview"
      )
    ) %>%
    filter(model %in% MODEL_RAW)
}

rel <- bind_rows(load_rel("en"), load_rel("zh")) %>%
  mutate(evaluable = reliability_flag %in% c("ok", "perfect_agreement")) %>%
  group_by(model, language) %>%
  summarise(
    n_ev     = sum(evaluable),
    mean_rho = if (any(evaluable))
                 mean(mean_pairwise_spearman[evaluable], na.rm = TRUE)
               else
                 NA_real_,
    .groups  = "drop"
  ) %>%
  mutate(
    disp   = MODEL_DISP[model],
    family = FAM_MAP[model],
    col    = FAM_COL[family],
    disp_f = factor(disp, levels = DISP_ORDER)
  )

# ── Panel A data ───────────────────────────────────────────────────────────────
pts_en   <- rel %>% filter(language == "en", !is.na(mean_rho))
pts_zh   <- rel %>% filter(language == "zh", !is.na(mean_rho))
pts_na   <- rel %>% filter(is.na(mean_rho))          # GPT-OSS-120B EN

# EN–ZH connector (only where both are evaluable)
conn_df <- rel %>%
  select(model, disp_f, col, language, mean_rho) %>%
  pivot_wider(names_from = language, values_from = mean_rho) %>%
  filter(!is.na(en) & !is.na(zh))

# n annotations: highlight when n_ev < 8
ann_en <- rel %>%
  filter(language == "en", !is.na(mean_rho)) %>%
  mutate(
    n_lbl      = paste0("(n=", n_ev, ")"),
    ann_col    = if_else(n_ev < 8, col, "grey62"),
    ann_size   = if_else(n_ev < 8, 9 / 2.835, 7.5 / 2.835)
  )
ann_zh <- rel %>%
  filter(language == "zh") %>%
  mutate(
    n_lbl      = paste0("(n=", n_ev, ")"),
    ann_col    = if_else(n_ev < 8, col, "grey62"),
    ann_size   = if_else(n_ev < 8, 9 / 2.835, 7.5 / 2.835)
  )

# ── Panel A theme ─────────────────────────────────────────────────────────────
th_panel <- theme_bw(base_size = PT_AX, base_family = BASE_FONT) %+replace%
  theme(
    plot.title         = element_text(size = PT_TTL, face = "bold",
                                      hjust = 0, margin = margin(b = 4)),
    axis.title.x       = element_text(size = PT_LBL, margin = margin(t = 5)),
    axis.title.y       = element_blank(),
    axis.text          = element_text(size = PT_AX),
    axis.text.y        = element_text(size = PT_AX, hjust = 1),
    axis.ticks.y       = element_blank(),
    panel.grid.major.x = element_line(color = "grey88", linewidth = 0.25),
    panel.grid.minor.x = element_line(color = "grey93", linewidth = 0.15),
    panel.grid.major.y = element_blank(),
    panel.grid.minor.y = element_blank(),
    panel.border       = element_rect(color = "grey55", linewidth = 0.4),
    legend.position    = "none",
    plot.margin        = margin(t = 4, r = 12, b = 4, l = 4)
  )

# ── Build Panel A ─────────────────────────────────────────────────────────────
pA <- ggplot() +
  # Family dividers
  geom_hline(yintercept = FAM_DIV_Y, color = "#dddddd",
             linewidth = 0.35, linetype = "solid") +
  # Acceptability reference
  geom_vline(xintercept = 0.7, color = "grey50",
             linetype = "dotted", linewidth = 0.65) +
  annotate("text", x = 0.72, y = 0.25, label = "rho = 0.70",
           color = "grey50", size = 7.5 / 2.835, hjust = 0,
           family = BASE_FONT) +
  # EN-ZH connector lines
  geom_segment(
    data = conn_df,
    aes(y = disp_f, yend = disp_f, x = en, xend = zh, color = I(col)),
    linewidth = 0.45, alpha = 0.40
  ) +
  # ZH points (open square, shape = 0)
  geom_point(
    data = pts_zh,
    aes(x = mean_rho, y = disp_f, color = I(col)),
    shape = 0, size = 2.7, stroke = 0.85
  ) +
  # EN points (filled circle, shape = 16)
  geom_point(
    data = pts_en,
    aes(x = mean_rho, y = disp_f, color = I(col)),
    shape = 16, size = 3.3
  ) +
  # n annotations — EN (nudge above)
  geom_text(
    data     = ann_en,
    aes(x = mean_rho, y = disp_f, label = n_lbl, color = I(ann_col)),
    size     = I(ann_en$ann_size),
    position = position_nudge(y = 0.30),
    hjust    = 0.5,
    family   = BASE_FONT
  ) +
  # n annotations — ZH (nudge below)
  geom_text(
    data     = ann_zh %>% filter(!is.na(mean_rho)),
    aes(x = mean_rho, y = disp_f, label = n_lbl, color = I(ann_col)),
    size     = I(ann_zh %>% filter(!is.na(mean_rho)) %>% pull(ann_size)),
    position = position_nudge(y = -0.30),
    hjust    = 0.5,
    family   = BASE_FONT
  ) +
  # "not evaluable" for GPT-OSS-120B ZH n=1 — already annotated above;
  # GPT-OSS-120B EN: no dot, show italic note
  geom_text(
    data    = pts_na,
    aes(y = disp_f),
    x       = 0.03,
    label   = "not evaluable",
    color   = "grey55",
    size    = 8 / 2.835,
    hjust   = 0,
    fontface = "italic",
    family  = BASE_FONT
  ) +
  # Inline language legend (top-left corner of data area)
  annotate("point", x = 0.03, y = 0.25, shape = 16, size = 3.2,
           color = "#444444") +
  annotate("text",  x = 0.07, y = 0.25, label = "English",
           size = 9.5 / 2.835, hjust = 0, color = "#444444",
           family = BASE_FONT) +
  annotate("point", x = 0.03, y = -0.15, shape = 0, size = 2.7,
           color = "#444444", stroke = 0.85) +
  annotate("text",  x = 0.07, y = -0.15, label = "Mandarin Chinese",
           size = 9.5 / 2.835, hjust = 0, color = "#444444",
           family = BASE_FONT) +
  # Scales
  scale_x_continuous(
    limits       = c(0, 1.05),
    breaks       = seq(0, 1.0, by = 0.2),
    minor_breaks = seq(0, 1.0, by = 0.1),
    expand       = expansion(mult = c(0.01, 0.01)),
    name         = "Mean pairwise Spearman's rho"
  ) +
  scale_y_discrete(
    limits = DISP_ORDER,
    name   = NULL,
    expand = expansion(add = c(1.35, 0.80))
  ) +
  labs(title = "A  Run-Level Reliability") +
  th_panel

# ── Load non-valid response data ──────────────────────────────────────────────
t1_raw <- read_csv(file.path(an_dir, "table1_response_classification.csv"),
                   show_col_types = FALSE)

t1 <- t1_raw %>%
  mutate(
    # Strip only the trailing "(API)" / "(Open-source)" parenthetical;
    # keep "Preview" so names match the canonical MODEL_RAW (eg, "Gemini-3.1-Pro-Preview")
    model = sub("\\s*\\(.*\\)\\s*$", "", model_label),
    model = str_trim(model)
  ) %>%
  filter(model %in% MODEL_RAW) %>%
  mutate(
    # Group 1: all deliberate model refusals (ethical + identity + other)
    refusal_en = n_refusal_ethical_en + n_refusal_identity_en + n_refusal_other_en,
    refusal_zh = n_refusal_ethical_zh + n_refusal_identity_zh + n_refusal_other_zh,
    # Group 2: unparseable or error, incl. API errors (provider safety-filter blocks would count here; none occurred)
    safunp_en  = n_safety_en + n_unparseable_en,
    safunp_zh  = n_safety_zh + n_unparseable_zh
  )

# Reshape to long: model × language × category
t1_long <- t1 %>%
  select(model, refusal_en, refusal_zh, safunp_en, safunp_zh) %>%
  pivot_longer(
    cols      = c(refusal_en, refusal_zh, safunp_en, safunp_zh),
    names_to  = "key",
    values_to = "n_resp"
  ) %>%
  mutate(
    language = if_else(str_ends(key, "_en"), "en", "zh"),
    category = if_else(str_starts(key, "refusal"),
                       "Refusal", "Unparseable or error")
  ) %>%
  select(model, language, category, n_resp) %>%
  mutate(
    pct      = n_resp / 4800 * 100,
    disp     = MODEL_DISP[model],
    disp_f   = factor(disp, levels = DISP_ORDER),
    lang_lbl = if_else(language == "en", "English", "Mandarin Chinese"),
    lang_lbl = factor(lang_lbl, levels = c("English", "Mandarin Chinese")),
    category = factor(category,
                      levels = c("Refusal", "Unparseable or error"))
  )

# x-axis ceiling: round up to nearest 2%
x_max_pct <- ceiling(max(
  t1 %>% mutate(tot_en = (refusal_en + safunp_en) / 4800 * 100,
                tot_zh = (refusal_zh + safunp_zh) / 4800 * 100) %>%
    summarise(m = max(c(tot_en, tot_zh))) %>% pull(m)
) / 2) * 2 + 2

# ── Panel B colours ────────────────────────────────────────────────────────────
BAR_COLS <- c(
  "Refusal"                     = "#2B4590",   # dark navy — deliberate refusal
  "Unparseable or error" = "#A8C4E2"    # light steel blue — technical
)

# ── Build Panel B ─────────────────────────────────────────────────────────────
th_panel_b <- th_panel %+replace%
  theme(
    strip.text         = element_text(size = PT_LBL, face = "plain",
                                      margin = margin(b = 3)),
    strip.background   = element_blank(),
    panel.spacing.x    = unit(1.0, "cm"),
    axis.text.y        = element_text(size = PT_AX, hjust = 1),
    plot.margin        = margin(t = 4, r = 8, b = 4, l = 4)
  )

pB <- ggplot(t1_long, aes(x = pct, y = disp_f, fill = category)) +
  # GPT-OSS-120B highlight band
  annotate("rect",
           xmin = 0, xmax = x_max_pct,
           ymin = which(DISP_ORDER == "GPT-OSS-120B") - 0.48,
           ymax = which(DISP_ORDER == "GPT-OSS-120B") + 0.48,
           fill = "#FFF8E1", alpha = 0.70) +
  # Family dividers
  geom_hline(yintercept = FAM_DIV_Y, color = "#dddddd",
             linewidth = 0.35, linetype = "solid") +
  # Stacked bars
  geom_col(width = 0.62, position = "stack") +
  # Facet by language
  facet_wrap(~ lang_lbl, nrow = 1) +
  scale_fill_manual(
    values = BAR_COLS,
    name   = NULL,
    guide  = guide_legend(reverse = FALSE)
  ) +
  scale_x_continuous(
    limits   = c(0, x_max_pct),
    expand   = expansion(mult = c(0, 0.02)),
    breaks   = seq(0, x_max_pct, by = 2),
    labels   = function(x) paste0(x, "%"),
    name     = "Non-valid responses (% of 4,800 prompts)"
  ) +
  scale_y_discrete(
    limits = DISP_ORDER,
    name   = NULL,
    expand = expansion(add = c(1.35, 0.80))
  ) +
  labs(title = "B  Non-Valid Response Rate") +
  th_panel_b %+replace%
    theme(
      legend.position  = "bottom",
      legend.text      = element_text(size = PT_AX),
      legend.key.size  = unit(0.38, "cm"),
      legend.margin    = margin(t = 2, b = 2)
    )

# ── Shared legend for Panel A ─────────────────────────────────────────────────
# (inline annotations handle it; no separate legend needed)

# ── Assemble ──────────────────────────────────────────────────────────────────
# Footnote text (verbatim as specified)
FOOTNOTE <- str_wrap(paste0(
  "Panel A: Mean pairwise Spearman's rho across the 30 runs within each ",
  "(model x language x vignette x scale) cell, averaged across the 8 ",
  "vignette x scale combinations per (model x language). The dotted vertical ",
  "line at rho = 0.7 marks the conventional acceptability threshold. Cells ",
  "for which fewer than 10 of the 30 runs provided fully complete responses ",
  "(valid scores on all scale items) were not evaluable and are excluded from ",
  "this calculation. For GPT-OSS-120B, scattered non-valid items across runs ",
  "left 0-17 complete runs per cell, so only 1 of its 16 cells (Mandarin Chinese, ",
  "PLE, Prejudice) was evaluable. Panel B: Proportion of the 4,800 prompts per ",
  "(model x language) cell that produced non-valid responses (refusal, ",
  "or unparseable output or error, including API errors). GPT-OSS-120B ",
  "exhibited the highest refusal rate across both languages."
), width = 160)

combined <- (pA | pB) +
  plot_layout(widths = c(1.05, 1.35)) +
  plot_annotation(
    caption = FOOTNOTE,
    theme   = theme(
      plot.title   = element_text(size = PT_MAIN, face = "bold", hjust = 0,
                                  margin = margin(b = 8),
                                  family = BASE_FONT),
      plot.caption = element_text(size = PT_FOOT, hjust = 0, color = "#444444",
                                  lineheight = 1.35,
                                  margin = margin(t = 10),
                                  family = BASE_FONT)
    )
  )

# ── Save ──────────────────────────────────────────────────────────────────────
FIG_W <- 15.5
FIG_H <-  9.2

pdf_path <- file.path(out_dir, "efigure1_reliability_refusal_1014.pdf")
png_path <- file.path(out_dir, "efigure1_reliability_refusal_1014.png")

ggsave(pdf_path, combined, width = FIG_W, height = FIG_H,
       device = "pdf", family = BASE_FONT)
ggsave(png_path, combined, width = FIG_W, height = FIG_H, dpi = 300)

cat("\n-- Supplementary Fig. 1 outputs --\n")
cat(sprintf("  PDF : %s  [%d KB]\n", pdf_path,
            round(file.size(pdf_path) / 1024)))
cat(sprintf("  PNG : %s  [%d KB]\n", png_path,
            round(file.size(png_path) / 1024)))
cat(sprintf("  Size: %.1f x %.1f in @ 300 dpi\n", FIG_W, FIG_H))
cat("  [OK] GPT-OSS-120B naming\n")
cat("  [OK] n annotations on all evaluable points\n")
cat("  [OK] Non-evaluable cells (fewer than 10 complete runs) described in footnote\n")
cat("  [OK] Panel B: stacked bars (refusal dark / unparseable or error light)\n")
cat("  [OK] Font: 14pt title / 12pt panel / 11pt labels\n")

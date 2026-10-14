# efigure5_elicitation_sensitivity_4model.R  (2026-10-07)
#
# Supplementary Fig. 5 (Reviewer 1, Comment 4): score differences between each alternative
# elicitation format and the same-session original prompt, for the four re-queried models.
# Same data and estimates as compare_frames_4model.R (fig_frame_delta_4model), relabelled for
# publication: "Humanlike" = role-play instruction, "Fullscale" = full-scale administration,
# "Original_oct" = original prompt re-run in the same session.
#
# Input : analysis_sen_20260930/comparison/contrasts_all.csv
# Output: outputs/figures_tables/efigure5_elicitation_sensitivity_1007.{pdf,png}
# Usage : Rscript scripts_public/efigure5_elicitation_sensitivity_4model.R

suppressPackageStartupMessages({ library(dplyr); library(readr); library(ggplot2) })
args <- commandArgs(trailingOnly = FALSE)
sf   <- args[startsWith(args, "--file=")]
root <- normalizePath(if (length(sf) > 0) file.path(dirname(sub("--file=", "", sf)), "..") else ".")
out  <- file.path(root, "outputs", "figures_tables")

con <- read_csv(file.path(root, "analysis_sen_20260930", "comparison", "contrasts_all.csv"), show_col_types = FALSE) %>%
  filter(family %in% c("Humanlike_vs_Original_oct", "Fullscale_vs_Original_oct")) %>%
  mutate(
    contrast = factor(recode(family,
                             Humanlike_vs_Original_oct = "Role-play instruction\nminus original prompt",
                             Fullscale_vs_Original_oct = "Full-scale administration\nminus original prompt"),
                      levels = c("Role-play instruction\nminus original prompt",
                                 "Full-scale administration\nminus original prompt")),
    scale    = factor(recode(scale_type, social_distance = "Social Distance", prejudice = "Prejudice"),
                      levels = c("Social Distance", "Prejudice")),
    vignette = factor(vignette, levels = c("PLE", "DEP", "APS", "SCZ")),
    model    = factor(model, levels = rev(c("GPT-5.4", "GPT-OSS-120B", "Claude Sonnet 4.5", "Gemini-3.5-Flash"))),
    language = factor(recode(language, en = "English", zh = "Mandarin Chinese"),
                      levels = c("English", "Mandarin Chinese"))
  )
stopifnot(nrow(con) == 128, !anyNA(con$model))

g <- ggplot(con, aes(x = diff, y = model, colour = language)) +
  geom_vline(xintercept = 0, linetype = "dashed", colour = "grey45", linewidth = 0.4) +
  geom_errorbar(aes(xmin = diff_ci_low, xmax = diff_ci_high), width = 0, orientation = "y",
                position = position_dodge(width = 0.55), linewidth = 0.5) +
  geom_point(position = position_dodge(width = 0.55), size = 1.9) +
  facet_grid(contrast + scale ~ vignette) +
  scale_colour_manual(values = c("English" = "#2166AC", "Mandarin Chinese" = "#B2182B")) +
  labs(x = "Difference in scale score (95% CI)", y = NULL, colour = NULL) +
  theme_bw(base_size = 10, base_family = "Helvetica") +
  theme(legend.position = "bottom", strip.text.y = element_text(size = 8.5),
        panel.grid.minor = element_blank(), strip.background = element_rect(fill = "grey92"))

ggsave(file.path(out, "efigure5_elicitation_sensitivity_1007.pdf"), g, width = 9, height = 9)
ggsave(file.path(out, "efigure5_elicitation_sensitivity_1007.png"), g, width = 9, height = 9, dpi = 300)
cat("Wrote efigure5_elicitation_sensitivity_1007.{pdf,png}; rows:", nrow(con), "\n")

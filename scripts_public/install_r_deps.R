#!/usr/bin/env Rscript
# Install R packages required by analyze_stage1.R and item_level_profile.R.
# Tested with R 4.3+. Run once before the pipeline:
#   Rscript scripts_public/install_r_deps.R

required <- c(
  "dplyr",      # data manipulation
  "readr",      # CSV I/O
  "tidyr",      # pivoting
  "ggplot2",    # all figures
  "stringr",    # string handling (item_level_profile.R)
  "tibble",     # tibble construction
  "effsize",    # Cliff's delta, Cohen's d
  "ggdendro",   # hierarchical clustering dendrograms (Fig 4)
  "patchwork",  # multi-panel layouts
  "scales"     # axis label helpers
)

missing <- required[!vapply(required, requireNamespace, logical(1),
                            quietly = TRUE)]
if (length(missing) == 0L) {
  message("All required packages are already installed.")
} else {
  message("Installing missing packages: ", paste(missing, collapse = ", "))
  install.packages(missing, repos = "https://cloud.r-project.org")
}

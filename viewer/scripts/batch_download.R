#!/usr/bin/env Rscript
#
# Batch download of herbarium images.
#
# Usage:
#   Rscript batch_download.R ids.txt --base-url URL [--out DIR]
#
# ids.txt should contain one GB-ID per line, e.g.:
#   GB-0500017
#   GB-0500018
#
# Options:
#   --base-url  Base URL of the IIIF viewer (required),
#               e.g. https://botmus.gu.se
#   --out       Output directory (default: ./downloads)
#
# To run interactively in RStudio, set the variables below and
# source the file (no need to use the terminal).

# --- RStudio: set these values -----------------------------------------------

ids_file <- "ids.txt"
base_url <- NULL   # e.g. "https://botmus.gu.se"
out_dir  <- "downloads"

# --- Argument parsing (terminal only) ----------------------------------------

args <- commandArgs(trailingOnly = TRUE)

if (length(args) > 0) {
  if (args[1] %in% c("-h", "--help")) {
    cat("Usage: Rscript batch_download.R ids.txt --base-url URL [--out DIR]\n")
    quit(status = 0)
  }

  ids_file <- args[1]
  base_url <- NULL
  out_dir  <- "downloads"

  i <- 2
  while (i <= length(args)) {
    switch(args[i],
      "--base-url" = { base_url <- args[i + 1]; i <- i + 2 },
      "--out"      = { out_dir  <- args[i + 1]; i <- i + 2 },
      { stop("Unknown argument: ", args[i]) }
    )
  }
}

if (is.null(base_url)) {
  stop("base_url is required. Set it at the top of the script or pass --base-url.")
}

# --- Load and validate IDs ---------------------------------------------------

raw_lines <- readLines(ids_file, warn = FALSE)
raw_lines <- trimws(raw_lines)
raw_lines <- raw_lines[nchar(raw_lines) > 0 & !startsWith(raw_lines, "#")]

ids <- regmatches(raw_lines, regexpr("GB-\\d{7}", raw_lines))
no_match <- raw_lines[!grepl("GB-\\d{7}", raw_lines)]
if (length(no_match) > 0) {
  cat("Skipping lines with no GB-ID:\n")
  cat(paste0("  ", no_match, "\n"))
}

if (length(ids) == 0) stop("No valid GB-IDs found in file.")

# --- Download ----------------------------------------------------------------

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

cat(sprintf("Downloading %d image(s) -> %s/\n", length(ids), out_dir))
cat(sprintf("Base URL: %s\n\n", base_url))

ok   <- 0
fail <- 0

for (image_id in ids) {
  dest <- file.path(out_dir, sprintf("%s.jpg", image_id))

  if (file.exists(dest)) {
    cat(sprintf("  [ok]  %s  ->  already exists\n", image_id))
    ok <- ok + 1
    next
  }

  url <- sprintf("%s/%s.jpg", base_url, image_id)
  result <- tryCatch({
    download.file(url, destfile = dest, mode = "wb", quiet = TRUE)
    sprintf("  [ok]  %s  ->  %s\n", image_id, dest)
  }, error = function(e) {
    sprintf("  [err] %s  --  %s\n", image_id, e$message)
  })

  if (startsWith(result, "  [ok]")) ok <- ok + 1 else fail <- fail + 1
  cat(result)
}

cat(sprintf("\nDone: %d succeeded, %d failed.\n", ok, fail))
if (fail > 0) quit(status = 1)

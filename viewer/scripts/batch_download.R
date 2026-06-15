#!/usr/bin/env Rscript
#
# Batch download of herbarium images from the IIIF server.
#
# Usage:
#   Rscript batch_download.R ids.txt [options]
#
# ids.txt should contain one GB-ID per line, e.g.:
#   GB-0500017
#   GB-0500018
#
# Options (all optional):
#   --base-url  Base URL of the IIIF viewer (required)
#   --size      'small' (1200px wide JPEG) or 'full' (original resolution JPEG)
#               (default: full)
#   --out       Output directory (default: ./downloads)
#
# Example:
#   Rscript batch_download.R ids.txt --size small --out ./my_images
#
# Requires: jsonlite (install.packages("jsonlite"))

ids_file <- "ids.txt"
base_url <- "https://botmus.gu.se"
size     <- "full"
out_dir  <- "downloads"

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  stop("Package 'jsonlite' is required. Install it with: install.packages(\"jsonlite\")")
}

# --- Argument parsing (terminal only) ----------------------------------------
# When run interactively in RStudio the block below is skipped and the
# values set above are used instead.

args <- commandArgs(trailingOnly = TRUE)

if (length(args) > 0) {
  if (args[1] %in% c("-h", "--help")) {
    cat("Usage: Rscript batch_download.R ids.txt --base-url URL [--size small|full] [--out DIR]\n")
    quit(status = 0)
  }

  ids_file <- args[1]
  base_url <- NULL
  size     <- "full"
  out_dir  <- "downloads"

  i <- 2
  while (i <= length(args)) {
    switch(args[i],
      "--base-url" = { base_url <- args[i + 1]; i <- i + 2 },
      "--size"     = { size     <- args[i + 1]; i <- i + 2 },
      "--out"      = { out_dir  <- args[i + 1]; i <- i + 2 },
      { stop("Unknown argument: ", args[i]) }
    )
  }
}

if (is.null(base_url)) {
  stop("--base-url is required, e.g.: Rscript batch_download.R ids.txt --base-url https://example.org")
}

if (!size %in% c("small", "full")) {
  stop("--size must be 'small' or 'full'")
}

# --- Load and validate IDs ---------------------------------------------------

raw_lines <- readLines(ids_file, warn = FALSE)
raw_lines <- trimws(raw_lines)
raw_lines <- raw_lines[nchar(raw_lines) > 0 & !startsWith(raw_lines, "#")]

valid <- grepl("^GB-\\d{7}$", raw_lines)
if (any(!valid)) {
  cat("Skipping invalid IDs:\n")
  cat(paste0("  ", raw_lines[!valid], "\n"))
}
ids <- raw_lines[valid]

if (length(ids) == 0) {
  stop("No valid GB-IDs found in file.")
}

# --- Setup -------------------------------------------------------------------

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
shard_cache <- list()

cat(sprintf("Downloading %d image(s) [%s] -> %s/\n", length(ids), size, out_dir))
cat(sprintf("Base URL: %s\n\n", base_url))

# --- Helper functions --------------------------------------------------------

get_shard <- function(shard) {
  if (!is.null(shard_cache[[shard]])) return(shard_cache[[shard]])
  url <- sprintf("%s/idx/%s.json", base_url, shard)
  result <- tryCatch(
    jsonlite::fromJSON(url),
    error = function(e) stop(sprintf("Could not fetch shard index %s: %s", url, e$message))
  )
  shard_cache[[shard]] <<- result
  result
}

image_url <- function(rel, image_id, size) {
  jp2_base <- sprintf("%s/iiif/%s/%s.jp2", base_url, rel, image_id)
  if (size == "small") {
    sprintf("%s/full/1200,/0/default.jpg", jp2_base)
  } else {
    sprintf("%s/full/full/0/default.jpg", jp2_base)
  }
}

# --- Download loop -----------------------------------------------------------

ok   <- 0
fail <- 0

for (image_id in ids) {
  suffix <- if (size == "small") "small" else "large"
  dest   <- file.path(out_dir, sprintf("%s-%s.jpg", image_id, suffix))

  if (file.exists(dest)) {
    cat(sprintf("  [ok]  %s  ->  already exists\n", image_id))
    ok <- ok + 1
    next
  }

  result <- tryCatch({
    shard <- substr(image_id, 1, 7)
    index <- get_shard(shard)
    rel   <- index[[image_id]]

    if (is.null(rel)) stop("not found in index")

    url <- image_url(rel, image_id, size)
    download.file(url, destfile = dest, mode = "wb", quiet = TRUE)
    sprintf("  [ok]  %s  ->  %s\n", image_id, dest)
  }, error = function(e) {
    sprintf("  [err] %s  --  %s\n", image_id, e$message)
  })

  if (startsWith(trimws(result), "[ok]") || startsWith(result, "  [ok]")) {
    ok <- ok + 1
  } else {
    fail <- fail + 1
  }
  cat(result)
}

cat(sprintf("\nDone: %d succeeded, %d failed.\n", ok, fail))
if (fail > 0) quit(status = 1)

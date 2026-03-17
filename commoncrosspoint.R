# Requirements for the crosspoint function:
# 1. Takes `db.cables` (an R dataframe of `data/uac_cables.xlsx`) as input.
# 2. Uses the `gt` package to depict crosspoint routings.
# 3. Restricts routings to rows where `type == 'route'`.
# 4. Supports optional parameters to restrict sources or destinations to a specific list of assets.
# 5. Row headers: "source asset tag and port", with SrcTag spanning rows (implemented using dplyr::group_by before passing to gt, and rowname_col for SrcPort and optional Usage on a new line, interpreted as markdown).
# 6. Column headers: "destination asset tag and port", with DstTag spanning columns (implemented using gt::tab_spanner, and individual DstPort labels). All column text is also centered.

crosspoint <- function(db.cables, source_assets = NULL, dest_assets = NULL, includeusage = TRUE) {
  # Load necessary packages
  if (!requireNamespace("gt", quietly = TRUE)) {
    stop('Package "gt" needed for this function to work. Please install it.', call. = FALSE)
  }
  if (!requireNamespace("dplyr", quietly = TRUE)) {
    stop('Package "dplyr" needed for this function to work. Please install it.', call. = FALSE)
  }

  # Filter for 'route' type cables
  routes <- db.cables %>%
    dplyr::filter(Type == 'route')

  # Apply source asset filtering if specified
  if (!is.null(source_assets)) {
    routes <- routes %>%
      dplyr::filter(SrcTag %in% source_assets)
  }

  # Apply destination asset filtering if specified
  if (!is.null(dest_assets)) {
    routes <- routes %>%
      dplyr::filter(DstTag %in% dest_assets)
  }

  # Prepare data for gt table with separate identifiers for spanners
  crosspoint_data_long <- routes %>%
    dplyr::select(SrcTag, SrcPort, DstTag, DstPort, Usage) %>%
    dplyr::mutate(Connected = "X") # Mark connections with 'X'

  crosspoint_data_wide <- crosspoint_data_long %>%
    tidyr::pivot_wider(
      id_cols = c(SrcTag, SrcPort, Usage), # Keep Usage here to re-incorporate into row label
      names_from = c(DstTag, DstPort),
      values_from = Connected,
      values_fill = ""
    )

  crosspoint_data_final <- crosspoint_data_wide %>%
    dplyr::mutate(
      # Ensure Usage is character and handle potential NA/NULL consistently
      usage_clean = as.character(Usage), # Convert to character
      usage_clean = ifelse(is.na(usage_clean) | trimws(usage_clean) == "", "", usage_clean), # Replace NA or empty/whitespace with empty string
      RowLabel_base =   SrcPort,  # Label for the row within the SrcTag group
      RowLabel = ifelse(
        includeusage & usage_clean != "", # Use cleaned Usage directly
        paste0(RowLabel_base, "<br>", usage_clean),
        RowLabel_base
      )
    ) %>%
    dplyr::select(SrcTag, RowLabel, tidyselect::starts_with(unique(routes$DstTag))) %>% # Select only SrcTag, RowLabel, and actual DstTag_DstPort columns
    dplyr::relocate(SrcTag, RowLabel) %>% # Ensure SrcTag and RowLabel are the first two columns
    dplyr::group_by(SrcTag) %>% # Group by SrcTag for row spanners
    dplyr::arrange(SrcTag, RowLabel) # Order rows for consistency

  # If no routes are found after filtering, return an empty gt table or a message
  if (nrow(crosspoint_data_final) == 0) {
    return(gt::gt(data.frame(Message = "No routes found matching criteria.")))
  }
  
  # Create the gt table
  gt_table <- crosspoint_data_final %>%
    gt::gt(rowname_col = "RowLabel") %>% # Use RowLabel as the row name column
    gt::tab_header(
      title = "Crosspoint Routings"
    ) %>%
    gt::cols_align(columns = gt::everything(), align = "center") %>%
    gt::fmt_markdown(columns = RowLabel) %>% # Apply markdown to RowLabel
    # Extract unique DstTags from column names for spanners
    # Column names look like "DstTag_DstPort"
    gt::tab_options(
        column_labels.background.color = "#d9d9d9", # Optional: grey background for spanners
        column_labels.font.weight = "bold"
    )

  dst_col_names <- setdiff(names(crosspoint_data_final), c("SrcTag", "RowLabel"))
  
  # Get unique DstTags from these column names
  # Example: "DstTag_DstPort" -> "DstTag"
  unique_dst_spanners <- unique(sub("^(.*?)_.*", "\\1", dst_col_names)) # Extract everything before the first '_'

  # Apply column spanners
  for (spanner_tag in unique_dst_spanners) {
    # Find all columns under this spanner_tag
    cols_to_span <- dst_col_names[grepl(paste0("^", spanner_tag, "_"), dst_col_names)]
    if (length(cols_to_span) > 0) {
      gt_table <- gt_table %>%
        gt::tab_spanner(
          label = gt::md(spanner_tag),
          columns = tidyselect::all_of(cols_to_span),
          id = paste0("spanner_", spanner_tag) # Explicitly set a unique ID
        )
    }
  }

  # Prepare labels for DstPort columns
  current_dst_cols <- setdiff(names(crosspoint_data_final), c("SrcTag", "RowLabel"))
  
  new_labels_list <- list()
  for (col_name in current_dst_cols) {
    # col_name is "DstTag_DstPort", we want "DstPort"
    port_label <- sub(".*_", "", col_name) # Get everything after the last underscore
    new_labels_list[[col_name]] <- gt::md(port_label)
  }

  gt_table <- gt_table %>%
    gt::cols_label(.list = new_labels_list) %>%
    gt::tab_stubhead(label = gt::md("Source")) # Label for the stubhead (where SrcTag group names go)  

  return(gt_table)
}

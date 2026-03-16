# Requirements for the crosspoint function:
# 1. Takes `db.cables` (an R dataframe of `data/uac_cables.xlsx`) as input.
# 2. Uses the `gt` package to depict crosspoint routings.
# 3. Restricts routings to rows where `type == 'route'`.
# 4. Supports optional parameters to restrict sources or destinations to a specific list of assets.
# 5. Row headers: "source asset tag and port" (with optional usage on a new line, interpreted as markdown).
# 6. Column headers: "destination asset tag and port". Due to limitations in directly implementing vertical text within `gt`, line breaks (`<br>`) are used in conjunction with `gt::md()` to separate the asset tag and port for improved readability. All column text is also centered.

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

  # Prepare data for gt table
  # Assuming 'SourceAssetTag', 'SourcePort', 'DestinationAssetTag', 'DestinationPort' exist
  # Create unique identifiers for rows and columns
  routes <- routes %>%
    dplyr::mutate(
      SourceIdentifier_base = paste0(SrcTag, " (", SrcPort, ")"),
      SourceIdentifier = ifelse(
        includeusage & !is.na(Usage) & Usage != "",
        paste0(SourceIdentifier_base, "<br>", Usage),
        SourceIdentifier_base
      ),
      DestinationIdentifier = paste0(DstTag, " (", DstPort, ")")
    )

  # Create a matrix or data frame suitable for gt, indicating connections
  # This part needs careful construction to get the row/column structure right.
  # Let's create a wide format table where rows are SourceIdentifiers and columns are DestinationIdentifiers
  crosspoint_data <- routes %>%
    dplyr::select(SourceIdentifier, DestinationIdentifier) %>%
    dplyr::mutate(Connected = "X") %>% # Mark connections with 'X'
    tidyr::pivot_wider(
      names_from = DestinationIdentifier,
      values_from = Connected,
      values_fill = ""
    )

  # If no routes are found after filtering, return an empty gt table or a message
  if (nrow(crosspoint_data) == 0) {
    return(gt::gt(data.frame(Message = "No routes found matching criteria.")))
  }
  
  # Ensure all possible source identifiers are present as rows, even if they have no routes
  all_source_ids <- unique(routes$SourceIdentifier)
  missing_source_rows <- setdiff(all_source_ids, crosspoint_data$SourceIdentifier)
  
  if (length(missing_source_rows) > 0) {
    # Create empty rows for missing sources
    empty_rows <- data.frame(SourceIdentifier = missing_source_rows)
    # Add columns for all destination identifiers, filled with ""
    for (col_name in setdiff(names(crosspoint_data), "SourceIdentifier")) {
      empty_rows[[col_name]] <- ""
    }
    crosspoint_data <- dplyr::bind_rows(crosspoint_data, empty_rows)
  }

  # Order rows by SourceIdentifier for consistency
  crosspoint_data <- crosspoint_data %>%
    dplyr::arrange(SourceIdentifier)
  
  # Create the gt table
  gt_table <- crosspoint_data %>%
    gt::gt() %>%
    gt::tab_header(
      title = "Crosspoint Routings"
    ) %>%
    gt::cols_align(columns = gt::everything(), align = "center") %>%
    gt::fmt_markdown(columns = SourceIdentifier)

  # Get all column names that correspond to DestinationIdentifiers
  # These are all columns except 'SourceIdentifier'
  dest_cols <- setdiff(names(crosspoint_data), "SourceIdentifier")

  # Create a named list of new labels with markdown line breaks for destination columns
  new_dest_labels <- lapply(dest_cols, function(col_name) {
    # col_name will be in format "DstTag (DstPort)"
    # We want "DstTag<br>(DstPort)"
    # Need to split the string to insert <br>
    parts <- strsplit(col_name, " \\(")[[1]] # split by " ("
    tag <- parts[1]
    # Re-add the opening parenthesis for the port if it was removed by split
    port_part <- if (length(parts) > 1) paste0("(", parts[2]) else ""
    gt::md(paste0(tag, "<br>", port_part))
  })
  names(new_dest_labels) <- dest_cols

  # Combine with the SourceIdentifier label
  all_labels <- c(
    list(SourceIdentifier = "Source"),
    new_dest_labels
  )

  # Apply all labels
  gt_table <- gt_table %>%
    gt::cols_label(.list = all_labels)  

  return(gt_table)
}

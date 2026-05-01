# Requirements for the plot_rack_profile function:
# 1. Takes `rack_asset_tag` (string), `inventory_df` (dataframe), and optional `range` (numeric vector c(min_u, max_u)) as input.
# 2. `inventory_df` contains device information from `data/uac_assets.xlsx`.
# 3. `Rack` column specifies the rack's AssetTag.
# 4. `RackU` column specifies U position and front/rear face, with optional division suffix. Items without a `RackU` value will be excluded.
# 5. `RackU` format: 'Fnn' or 'Rnn' for U position from bottom (e.g., F23, R10).
# 6. `RackU` suffix format: '-x-yy-zz' where 'x' is divisions, 'yy' is start, 'zz' is end position.
#    (e.g., F23-3-2-2 means Front, U23, 1/3 width, middle section).
# 7. `RackHeight` column in `inventory_df` specifies device height. If `RackHeight` is NA, assume 1U. Devices with `RackHeight = 0` are excluded from depiction.
# 8. Depiction should include AssetTag and Usage within each device's representation.
# 9. Plotting library: ggplot2 for rectangles and text labels.
# 10. If multiple items have the same `RackU`, only the highest cost item is depicted. If costs are tied or unavailable, one is chosen at random.
# 11. The rack profile is rendered vertically with 1U at the bottom, and blank U positions are depicted.
# 12. If `range` is provided (e.g., c(min_u, max_u)), only that U-portion of the rack is depicted. `min_u` is capped at 1, `max_u` is capped by the highest actual device in the rack. If a device straddles the range, the depicted range is extended to include the entire device.

# Load necessary packages
library(dplyr)
library(ggplot2)
library(stringr)
library(glue)
library(tidyr) # For separate_wider_delim if needed

plot_rack_profile <- function(rack_asset_tag, inventory_df, range = NULL) {
  # --- 1. Filter inventory for the specific rack ---
  rack_devices <- inventory_df %>%
    filter(Rack == rack_asset_tag, !is.na(RackU), RackHeight != 0) %>% # Exclude if RackHeight is 0
    # Resolve RackU conflicts: keep highest cost item, random if ties/no cost
    group_by(RackU) %>%
    mutate(
      Cost_numeric = suppressWarnings(as.numeric(AcqValue)), # Convert to numeric, non-convertible to NA
      Cost_for_selection = ifelse(is.na(Cost_numeric), -Inf, Cost_numeric) # Treat NA costs as lowest priority
    ) %>%
    # Use slice_max to pick rows with the highest Cost_for_selection.
    # If all are -Inf, it will pick all of them.
    # n=1 to pick just one. If multiple have max, then ties="random" handles it.
    slice_max(order_by = Cost_for_selection, n = 1, with_ties = TRUE) %>% # Keep all highest cost items
    slice_sample(n = 1) %>% # Randomly pick one if there are ties
    ungroup() %>%
    select(-Cost_numeric, -Cost_for_selection) # Clean up temporary columns

  if (nrow(rack_devices) == 0) {
    message(glue("No devices found for rack: {rack_asset_tag}"))
    return(NULL)
  }

  # --- 2. Parse RackU and prepare plotting data ---
  # First, parse existing devices
  parsed_devices <- rack_devices %>%
    # Extract face and U position
    mutate(
      face_char = str_sub(toupper(RackU), 1, 1),
      u_position_str = str_extract(RackU, "\\d+"),
      u_start = coalesce(as.integer(u_position_str), 1L) # Default to 1 if parsing fails
    ) %>%
    # Handle suffixes for divisions
    mutate(
      racku_suffix = str_extract(RackU, "-\\d+-\\d+-\\d+"),
      # If no suffix, assume full width (1 division, 1-1 position)
      num_divisions = coalesce(as.integer(str_extract(racku_suffix, "(?<=-)\\d+(?=-)")), 1L), # Default to 1
      div_start = coalesce(as.integer(str_extract(racku_suffix, "(?<=-)(\\d+)(?=-\\d+$)")), 1L), # Default to 1
      div_end = coalesce(as.integer(str_extract(racku_suffix, "\\d+$")), 1L) # Simplified regex to avoid nested parentheses error # Default to 1
    ) %>%
    mutate(
      face = case_when(
        face_char == "F" ~ "Front",
        face_char == "R" ~ "Rear",
        TRUE ~ "Unknown"
      ),
      u_height = coalesce(suppressWarnings(as.integer(RackHeight)), 1L),
      u_end = u_start + u_height
    ) %>%
    # Calculate x-coordinates for divided units (0 to 1 for full width)
    mutate(
        x_start_norm = (div_start - 1) / num_divisions,
        x_end_norm = div_end / num_divisions
    ) %>%
    mutate(
        label_text = glue("{AssetTag}\n{Usage}")
    )

  # --- 3. Determine effective plotting range and create full_plot_data ---
  # Extract standard rack height from rack_asset_tag's description
  rack_description_row <- inventory_df %>%
    filter(AssetTag == rack_asset_tag)

  standard_rack_height <- NA_integer_ # Default to NA
  if (nrow(rack_description_row) > 0) {
    rack_description <- rack_description_row %>% pull(Desc)
    standard_rack_height_match <- str_match(rack_description, "(\\d+)U")
    if (!is.na(standard_rack_height_match[1,2])) {
      standard_rack_height <- as.integer(standard_rack_height_match[1,2])
    }
  }

  # Calculate overall max_u_for_rack before range filtering
  overall_max_u_for_rack <- max(parsed_devices$u_end, 1, na.rm = TRUE)

  # Default effective range to cover all devices
  effective_min_u <- 1
  effective_max_u <- overall_max_u_for_rack # Cap at overall_max_u_for_rack if no range.

  # Apply range filtering if specified
  if (!is.null(range) && length(range) == 2 && is.numeric(range)) {
    initial_min_u <- max(1, min(range)) # Cap initial_min_u at 1
    initial_max_u <- min(overall_max_u_for_rack, max(range)) # Cap initial_max_u at overall_max_u_for_rack

    # Find devices that touch or are within the initial range
    relevant_devices_in_range <- parsed_devices %>%
      filter(u_start < initial_max_u & u_end > initial_min_u)

    if (nrow(relevant_devices_in_range) > 0) {
      # Extend range to include full devices that straddle the initial range
      # Ensure effective_min_u doesn't go below 1
      effective_min_u <- max(1, min(initial_min_u, relevant_devices_in_range$u_start))
      # Ensure effective_max_u doesn't exceed overall_max_u_for_rack
      effective_max_u <- min(overall_max_u_for_rack, max(initial_max_u, relevant_devices_in_range$u_end))
      
      # Now, filter parsed_devices to only include devices within this *extended* effective range
      parsed_devices <- parsed_devices %>%
        filter(u_start < effective_max_u & u_end > effective_min_u)

      if (nrow(parsed_devices) == 0) {
        # If after extension and re-filtering, parsed_devices becomes empty, fall back to initial range (capped)
        effective_min_u <- initial_min_u
        effective_max_u <- initial_max_u
      }

    } else {
      # No devices explicitly within the initial range. Depict empty range.
      effective_min_u <- initial_min_u
      effective_max_u <- initial_max_u
      parsed_devices <- parsed_devices[FALSE, ] # Keep empty dataframe with structure
    }
  }

  # Use effective_max_u as the top of the rack for plotting (for grid lines and labels)
  total_rack_height_u = effective_max_u

  # --- Generate plot subtitle ---
  plot_subtitle <- ""
  if (!is.null(range)) {
    plot_subtitle <- glue("U-Range: {effective_min_u}-{total_rack_height_u}")
  } else {
    plot_subtitle <- "Entire Rack"
  }

  # Create all possible U positions for front and rear within the effective range
  all_u_positions <- expand_grid(
    face = c("Front", "Rear"),
    u_start = effective_min_u:(total_rack_height_u - 1) # Corrected to highest U number
  ) %>%
  mutate(u_end = u_start + 1) # All empty slots are 1U high

  # Combine all U positions with actual devices
  full_plot_data <- full_join(all_u_positions, parsed_devices, by = c("face", "u_start", "u_end")) %>%
    mutate(
      label_text = coalesce(label_text, ""),
      x_start_norm = coalesce(x_start_norm, 0),
      x_end_norm = coalesce(x_end_norm, 1),
      fill_color = case_when(
        is.na(AssetTag) ~ "grey95", # Empty slot
        !is.na(standard_rack_height) & (u_start > standard_rack_height) ~ "lightcoral", # Above standard height
        TRUE ~ face # Normal device (Front/Rear)
      )
    ) %>%
    select(face, u_start, u_end, x_start_norm, x_end_norm, label_text, fill_color, AssetTag)


  # --- 4. Plotting using ggplot2 ---
  p <- ggplot(data = full_plot_data, aes(fill = fill_color)) + # Fill by fill_color
    # Rack outline - draw for each facet
    annotate("rect", xmin = 0, xmax = 1, ymin = effective_min_u - 1, ymax = total_rack_height_u - 1, # Adjusted ymax for range
             fill = "white", color = "black", linewidth = 0.5) + # Background rect

    # U-unit demarcation lines
    geom_hline(yintercept = seq(effective_min_u, total_rack_height_u - 1, by = 1), color = "lightgrey", linetype = "dotted") + # Adjusted for range

    # Devices as rectangles
    geom_rect(aes(xmin = x_start_norm, xmax = x_end_norm,
                  ymin = u_start - 1, ymax = u_end - 1),
              color = "black", linewidth = 0.5, alpha = 0.8) + # Devices

    # Device labels (only for non-empty slots)
    geom_text(data = full_plot_data %>% filter(!is.na(AssetTag)), # Filter out empty slots for text
              aes(x = (x_start_norm + x_end_norm) / 2, y = (u_start - 1 + u_end - 1) / 2, label = label_text),
              size = 2.0, color = "black", lineheight = 0.8) + # Labels within devices

    # Scales and labels
    # U-positions are on the Y-axis, width is on the X-axis (standard ggplot orientation)
    scale_y_continuous(name = "U Position (from bottom)", # For U-positions (on Y axis)
                       breaks = seq(effective_min_u - 0.5, total_rack_height_u - 1 - 0.5, by = 1), # Labels centered in each U slot
                       labels = seq(effective_min_u, total_rack_height_u - 1, by = 1), # Labels to match U number
                       expand = c(0, 0),
                       limits = c(effective_min_u - 1, total_rack_height_u - 1)) + # Set limits for the displayed range
    scale_x_continuous(name = NULL, # For width (on X axis)
                       breaks = NULL,
                       labels = NULL,
                       expand = c(0, 0)) +
    # No coord_flip() needed for vertical orientation.
    # The ymin=u_start-1, ymax=u_end-1 already ensure 1U is at the bottom.
    scale_fill_manual(values = c("Front" = "lightblue", "Rear" = "lightgreen", "grey95" = "grey95", "lightcoral" = "lightcoral")) + # Manual fill for faces, empty slots, and above rack

    labs(title = glue("Rack Profile: {rack_asset_tag}"), subtitle = plot_subtitle) +
    theme_minimal() +
    theme(
      axis.text.x = element_blank(), # Hide x-axis text (as it's just 0-1 range)
      axis.ticks.x = element_blank(),
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_blank(),
      legend.position = "none" # Hide fill legend for face
    ) +
    # Facet by face (Front/Rear) to show both sides side-by-side
    facet_wrap(~ face, ncol = 2, strip.position = "bottom")

  return(p)
}

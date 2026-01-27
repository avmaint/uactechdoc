# Functions for generating focused connectivity diagrams.
# This script provides tools to create diagrams for a specific device,
# showing its inbound, outbound, or all connections.

library(dplyr)
library(glue)
library(stringr)

# Defines the color for cables based on their type for connectivity diagrams.
# This function applies specific colors for major categories.
# - Video-related cables are rendered in violet.
# - Network-related cables are rendered in green.
# - Audio cables are rendered in orange.
# - All other cable types are rendered in black.
connectivity_cable_color <- function(type) {
	case_when(
		type %in% c("sdi", "sdi_din", "hdmi", "vga", "video") ~ "violet",
		type %in% c("cat", "cat6e", "sw", "ndi", "network")  ~ "green",
		type == "audio"                                     ~ "orange",
		TRUE                                            ~ "black"
	)
}


# Generates the Mrecord port string for inbound ports on a device.
# It uses natural sorting to ensure port numbers are ordered correctly (e.g., 2 before 10).
# The 'cables' dataframe passed to this function should be pre-filtered
# to only contain the connections relevant to the desired diagram.
connectivity_inports <- function(dev, cables) {
	text <- cables |>
		filter(DstTag == dev) |>
		# Use slice() with str_order() to perform a natural sort on the port names
	slice(stringr::str_order(DstPort, numeric = TRUE)) |>
		mutate(text = glue("<{DstPort}>{DstPort}")) |>
		pull(text) |>
		paste(collapse = "|")
	
	return(paste("{ ", text, " }"))
}

# Generates the Mrecord port string for outbound ports on a device.
# It uses natural sorting for correct port order.
# The 'cables' dataframe should be pre-filtered for relevance.
connectivity_outports <- function(dev, cables) {
	text <- cables |>
		filter(SrcTag == dev) |>
		# Use slice() with str_order() to perform a natural sort on the port names
	slice(stringr::str_order(SrcPort, numeric = TRUE)) |>
		mutate(text = glue("<{SrcPort}>{SrcPort}")) |>
		pull(text) |>
		paste(collapse = "|")
	
	return(paste("{ ", text, " }"))
}

# Generates the 'dot' code for device nodes in the diagram.
# For each device, it constructs an Mrecord shape showing its inbound and outbound ports.
# Because it uses the 'relevant_cables' dataframe, for peripheral devices,
# it will only list the ports that are connected to the central target device.
get_connectivity_device_code <- function(targets, inventory, relevant_cables) {
	
	devices_data <- inventory |>
		filter(AssetTag %in%  targets) |>
		filter(!is.na(AssetTag))  |>
		mutate(tag = tolower(str_replace(AssetTag, "-", ""))) |>
		rowwise() |>
		mutate(inports  =   connectivity_inports( AssetTag, relevant_cables ) ) |>
		mutate(outports =  connectivity_outports( AssetTag, relevant_cables ) ) |>
		mutate(mm = glue(" {Manufacturer}/{Model} ")) |>
		mutate(label = glue('[ label= "{{
			{inports}
			| {{  {Desc}|{mm}|{AssetTag} }}
			|{outports} 
			}}"]' ))  |>
		mutate(code = paste(tag, label)) |>
		select(AssetTag, Desc, tag, label,  code)
	
	return( paste(devices_data$code, collapse="\n") )
}


# Generates the 'dot' code for the cables (edges) in the diagram.
# It applies colors based on the 'connectivity_cable_color' function.
get_connectivity_cable_code <- function(target_cables) {
	
	cable_code <- target_cables |>
		filter(! (SrcIsCable | DstIsCable)) |> # extensions handled separately
		mutate(cc = connectivity_cable_color(Type)) |>
		mutate(label = glue('[label= "{Tag}\n{Usage2}{Type}" color={cc} ]' )) |> 
		mutate(code = glue( 
			"{SrcTag2}{SrcPort2} -> {DstTag2}{DstPort2} {label} "
		))
	
	return( paste(cable_code$code , collapse = "\n")	)	
}

# --- Functions for handling cable extensions (e.g., wall plates) ---

connectivity_get_extension_node <- function(tcables) {
	set1 <- tcables |>
		filter(  DstIsCable) |> 
		mutate(code = glue('{Tag2}{DstTag2} [label="" shape=point]\n'))
	return( paste(set1$code , collapse = "\n")	)	
}

connectivity_get_extension_edge <- function(tcables) {
	edge1 <- tcables |>
		filter(  DstIsCable) |> 
		mutate(code = glue('{SrcTag2}{SrcPort2} -> {Tag2}{DstTag2} [label="{Tag}\n{Usage2}"]\n'))
	
	edge2 <- tcables |>
		filter(  SrcIsCable) |> 
		mutate(code = glue('{SrcTag2}{Tag2} -> {DstTag2}{DstPort2} [label="{Tag}\n{Usage2}"]\n'))
	
	edges <- c(edge1$code, edge2$code)
	return( paste(edges , collapse = "\n")	)	
}


#' Generate a focused connectivity diagram for a single device.
#
# This function creates a 'dot' language string for DiagrammeR to render.
# The diagram shows the connections to or from a specified 'target_device'.
#
# @param target_device The AssetTag of the central device for the diagram.
# @param direction A string specifying which connections to show:
#        'in' for only inbound connections to the target.
#        'out' for only outbound connections from the target.
#        'both' for all connections to and from the target.
# @param inventory A dataframe of all devices (assets) from the inventory spreadsheet.
# @param cables A dataframe of all cable connections from the cables spreadsheet.
# @param types An optional character vector of cable 'Type's to include in the diagram.
#        If NULL (the default), all types of connections are shown.
#        Example: `types = c("video", "network")`
# @param label An optional custom label for the diagram. If NA, a default is created.
# @param rankdir The direction for the graph layout (e.g., "LR" for left-to-right).
# @return A string containing the 'dot' code for the diagram, ready for rendering.
get_connectivity_diagram <- function(target_device, direction, inventory, cables, types = NULL, label = NA, rankdir = "LR") {
	
	# --- 1. Filter cables based on direction and type ---
	
	# Filter for connections involving the target device based on the specified direction
	if (direction == 'in') {
		target_cables <- cables |> filter(DstTag == target_device)
	} else if (direction == 'out') {
		target_cables <- cables |> filter(SrcTag == target_device)
	} else if (direction == 'both') {
		target_cables <- cables |> filter(SrcTag == target_device | DstTag == target_device)
	} else {
		stop("Direction must be one of 'in', 'out', or 'both'.")
	}
	
	# If the 'types' parameter is provided, further filter the cables.
	if (!is.null(types)) {
		target_cables <- target_cables |> filter(Type %in% types)
	}
	
	# --- 2. Identify all devices and prepare cable data for diagramming ---
	
	# Get a unique list of all devices that need to be drawn in the diagram
	all_target_devices <- unique(c(target_cables$SrcTag, target_cables$DstTag))
	
	# Add helper columns to the cable data for generating the 'dot' code
	target_cables_prepped <- target_cables |>
		mutate(SrcIsCable = SrcTag %in% cables$Tag) |>
		mutate(DstIsCable = DstTag %in% cables$Tag) |>
		mutate(SrcTag2 = tolower(str_replace(SrcTag, "-", ""))) |>
		mutate(DstTag2 = tolower(str_replace(DstTag, "-", ""))) |>
		mutate(SrcPort2 = str_replace(SrcPort, ' ', '')) |>
		mutate(DstPort2 = str_replace(DstPort, ' ', '')) |>
		mutate(SrcPort2 = ifelse(is.na(SrcPort), "", glue(": {SrcPort2}"))) |>
		mutate(DstPort2 = ifelse(is.na(DstPort), "", glue(": {DstPort2}"))) |>
		mutate(Tag2 = tolower(str_replace(Tag, "-", "")))  |>
		mutate(Usage2 = ifelse(is.na(Usage), "",  glue("{Usage} ")) )
	
	# --- 3. Generate the diagram components ---
	
	# Generate a default label for the diagram if a custom one isn't provided
	my_label <- ifelse(is.na(label),
			   glue("\"Connectivity for {target_device} ({direction})\nAs of {Sys.Date()}\""),
			   label)
	
	# Generate the 'dot' code for all devices, cables, and extensions
	device_code <- get_connectivity_device_code(all_target_devices, inventory, target_cables_prepped)
	cable_code  <- get_connectivity_cable_code(target_cables_prepped)
	extension_nodes <- connectivity_get_extension_node(target_cables_prepped)
	extension_edges <- connectivity_get_extension_edge(target_cables_prepped)
	
	
	# --- 4. Assemble the final 'dot' code string ---

diag <- paste(
		"digraph outputs {",
		paste0("graph [overlap = true, fontsize = 20, rankdir=", rankdir, ", fontname = arial, label=", my_label, "]"),
		"node [shape=Mrecord, tooltip=\"\", fontsize = 10, fontname = arial, fillcolor=\"white:beige\", style=filled, gradientangle=270]",
		"edge [fontsize=8]",
		device_code,
		cable_code,
		extension_nodes,
		extension_edges,
		"}",
		sep = "\n"
	)
	
	return(diag)
}

test_get_connectivity_diagram <- function() { 

a <- get_connectivity_diagram ( "2507-0700", "in", db.inventory
						   , db.cables, types = NULL
						   , label = NA, rankdir = "LR") 
DiagrammeR::grViz(a)
}


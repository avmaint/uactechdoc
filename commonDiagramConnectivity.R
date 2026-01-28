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
		mutate(port_id = paste0("p", str_replace_all(DstPort, "[^A-Za-z0-9_]", ""))) |>
		mutate(text = glue("<{port_id}>{DstPort}")) |>
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
		mutate(port_id = paste0("p", str_replace_all(SrcPort, "[^A-Za-z0-9_]", ""))) |>
		mutate(text = glue("<{port_id}>{SrcPort}")) |>
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
		mutate(code = paste0('"', tag, '" ', label)) |>
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
			'"{SrcTag2}"{SrcPort2} -> "{DstTag2}"{DstPort2} {label} '
		))
	
	return( paste(cable_code$code , collapse = "\n")	)	
}

# --- Functions for handling cable extensions (e.g., wall plates) ---

connectivity_get_extension_node <- function(tcables) {
	set1 <- tcables |>
		filter(  DstIsCable) |> 
		mutate(code = glue('"{Tag2}{DstTag2}" [label="", shape=point]\n'))
	return( paste(set1$code , collapse = "\n")	)	
}

connectivity_get_extension_edge <- function(tcables) {
	edge1 <- tcables |>
		filter(  DstIsCable) |> 
		mutate(code = glue('"{SrcTag2}"{SrcPort2} -> "{Tag2}{DstTag2}" [label="{Tag}\n{Usage2}"]\n'))
	
	edge2 <- tcables |>
		filter(  SrcIsCable) |> 
		mutate(code = glue('"{SrcTag2}{Tag2}" -> "{DstTag2}"{DstPort2} [label="{Tag}\n{Usage2}"]\n'))
	
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
get_connectivity_diagram <- function(target_device, direction, inventory, cables, 						types = NULL, label = NA, rankdir = "LR",
						 partners = NULL, exclude = NULL) {
	
	# Filter initial cables by type (if specified)
	filtered_cables_by_type <- cables
	if (!is.null(types)) {
		filtered_cables_by_type <- cables |> filter(Type %in% types)
	}
	
	# Define the universe of nodes for exploration
	# If partners is provided, restrict to target_device + partners
	# Otherwise, consider all nodes present in the cables dataframe
	if (!is.null(partners) && length(partners) > 0) {
		allowed_nodes_for_traversal <- unique(c(target_device, partners))
	} else {
		allowed_nodes_for_traversal <- unique(c(filtered_cables_by_type$SrcTag, filtered_cables_by_type$DstTag))
	}
	
	# Initialize BFS: queue for nodes to visit, set for visited nodes, list for collected cables
	queue <- c(target_device)
	visited_nodes_for_diagram <- c(target_device)
	collected_cables <- data.frame()
	
	# Perform BFS traversal
	head_ptr <- 1
	while(head_ptr <= length(queue)) {
		current_node <- queue[head_ptr]
		
		# Find all direct connections from current_node using the type-filtered cables
		current_node_connections <- filtered_cables_by_type |>
			filter((SrcTag == current_node & DstTag %in% allowed_nodes_for_traversal) |
				   (DstTag == current_node & SrcTag %in% allowed_nodes_for_traversal))
		
		# Add these connections to our collection
		if(nrow(current_node_connections) > 0) {
			collected_cables <- bind_rows(collected_cables, current_node_connections)
		}
		
		# Identify new nodes to visit that are within the allowed_nodes_for_traversal
		new_dst_nodes <- current_node_connections$DstTag[current_node_connections$SrcTag == current_node]
		new_src_nodes <- current_node_connections$SrcTag[current_node_connections$DstTag == current_node]
		
		new_nodes_to_add <- unique(c(new_dst_nodes, new_src_nodes))
		new_nodes_to_add <- new_nodes_to_add[new_nodes_to_add %in% allowed_nodes_for_traversal]
		
		for (node in new_nodes_to_add) {
			if (!(node %in% visited_nodes_for_diagram)) {
				queue <- c(queue, node)
				visited_nodes_for_diagram <- c(visited_nodes_for_diagram, node)
			}
		}
		
		head_ptr <- head_ptr + 1
	}
	
	# Remove duplicates from collected_cables (can happen due to bind_rows and cycles)
	collected_cables <- collected_cables |> distinct()
	
	# Apply 'exclude' filter to nodes and cables (takes precedence)
	if (!is.null(exclude) && length(exclude) > 0) {
		visited_nodes_for_diagram <- setdiff(visited_nodes_for_diagram, exclude)
		collected_cables <- collected_cables |>
			filter(SrcTag %in% visited_nodes_for_diagram & DstTag %in% visited_nodes_for_diagram)
	}
	
	# Filter 'collected_cables' by 'direction' relative to 'target_device'
	# This filter is applied *after* the subgraph generation to ensure only relevant direction is shown.
	# If partners are used for multi-hop, this filter is skipped for the subgraph edges
	# as 'direction' is assumed to have influenced the traversal, not the final edge set.
	if (is.null(partners) || length(partners) == 0) {
		if (direction == 'in') {
			collected_cables <- collected_cables |> filter(DstTag == target_device)
		} else if (direction == 'out') {
			collected_cables <- collected_cables |> filter(SrcTag == target_device)
		}
	}
	
	# Ensure the target_device is always in the final list of devices, unless it was excluded
	final_nodes_to_draw <- unique(c(collected_cables$SrcTag, collected_cables$DstTag))
	
	# Add any nodes from 'visited_nodes_for_diagram' that might be isolated (no cables in collected_cables
	# after filtering by direction/exclude), but were part of the valid traversal.
	if (length(final_nodes_to_draw) == 0 && (target_device %in% visited_nodes_for_diagram) && !(target_device %in% exclude)) {
		final_nodes_to_draw <- c(target_device)
	} else {
		final_nodes_to_draw <- unique(c(final_nodes_to_draw, visited_nodes_for_diagram[!(visited_nodes_for_diagram %in% final_nodes_to_draw)]))
	}
	
	# After traversal, 'final_nodes_to_draw' holds all nodes that should appear in the diagram.
	# 'collected_cables' holds the set of edges that should be drawn.
	
	# --- 3. Prepare cable data for diagramming ---
	
	# Define cables for populating ports (all connections between final_nodes_to_draw, respecting type filter)
	cables_for_port_listing <- filtered_cables_by_type |>
		filter(SrcTag %in% final_nodes_to_draw & DstTag %in% final_nodes_to_draw)
	
	target_cables_prepped <- collected_cables |>
		mutate(SrcIsCable = SrcTag %in% cables$Tag) |> # Use original 'cables' for SrcIsCable/DstIsCable check
		mutate(DstIsCable = DstTag %in% cables$Tag) |>
		mutate(SrcTag2 = tolower(str_replace(SrcTag, "-", ""))) |>
		mutate(DstTag2 = tolower(str_replace(DstTag, "-", ""))) |>
		mutate(SrcPort2 = str_replace_all(SrcPort, "[^A-Za-z0-9_]", "")) |>
		mutate(DstPort2 = str_replace_all(DstPort, "[^A-Za-z0-9_]", "")) |>
		mutate(SrcPort2 = ifelse(is.na(SrcPort), "", glue(":p{SrcPort2}"))) |>
		mutate(DstPort2 = ifelse(is.na(DstPort), "", glue(":p{DstPort2}"))) |>
		mutate(Tag2 = tolower(str_replace(Tag, "-", "")))  |>
		mutate(Usage2 = ifelse(is.na(Usage), "",  glue("{Usage} ")) )
	
	my_label <- ifelse(is.na(label),
					   glue("\"Connectivity for {target_device} ({direction})\nAs of {Sys.Date()}\""),
					   label)
	
	device_code <- get_connectivity_device_code(final_nodes_to_draw, inventory, cables_for_port_listing)
	cable_code  <- get_connectivity_cable_code(target_cables_prepped)
	extension_nodes <- connectivity_get_extension_node(target_cables_prepped)
	extension_edges <- connectivity_get_extension_edge(target_cables_prepped)
	
	diag <- paste(
		"digraph G {",
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

test_gcd_1 <- function() { 

a <- get_connectivity_diagram ( "2507-0700", "in", db.inventory
						   , db.cables, types = NULL
						   , label = '"Connectivity from Decklink into VideoHub"' 
								, rankdir = "LR",
								partners = c("ZVIU-E004")) 
DiagrammeR::grViz(a)
}

test_gcd_2 <- function() { 
	
	a <- get_connectivity_diagram ( "2507-0700", "in", db.inventory
									, db.cables, types = NULL
									, label = '"Connectivity from Decklink into VideoHub"' 
									, rankdir = "LR",
									partners = c("Constellation")) 
	DiagrammeR::grViz(a)
}

test_gcd_3 <- function() { 
	
	a <- get_connectivity_diagram ( "Constellation", "in", db.inventory
									, db.cables, types = NULL
									, label = '"Connectivity from Decklink into VideoHub"' 
									, rankdir = "LR",
									partners = c("2507-0700")) 
	DiagrammeR::grViz(a)
}

test_gcd_4 <- function() { 
	
	a <- get_connectivity_diagram ( "Constellation", "out", db.inventory
									, db.cables, types = NULL
									, label = '"Connectivity from Decklink into VideoHub"' 
									, rankdir = "LR",
									partners = c("2507-0700")) 
	DiagrammeR::grViz(a)
}


test_gcd_5 <- function() { 
	
	ps <- c("ZVCU-A001"
			,"ZVCU-A002"
			,"ZVCU-A003"
			,"ZVVU-C001")
	
	a <- get_connectivity_diagram ( "2507-0700", "in", db.inventory
									, db.cables, types = NULL
									, label = '"Connectivity from Decklink into VideoHub"' 
									, rankdir = "LR",
									partners = ps) 
	DiagrammeR::grViz(a)
}


test_gcd_6 <- function() { 
	target <- "ZVIU-E004"
	ps <- c("2507-0700", "2601-1304", "2601-1305",  "2601-1306"
		, "ZVVU-A001", "ZVVU-A002" , "ZVVU-A003"
	)

	dot_code <- get_connectivity_diagram ( target, "out"
									   , db.inventory
									   , db.cables, types = NULL
									   , label = '"Connectivity Diagram Test "' 
									   , rankdir = "LR",
									   partners = ps)
	DiagrammeR::grViz(a)
	}

# test_gcd_1()
# test_gcd_2()
# test_gcd_3()
# test_gcd_4()
# test_gcd_5()
# test_gcd_6()

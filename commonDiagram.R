# Functinos used to draw a diagram from the config spreadsheets

cable_color <- function(type) {
	cc <- case_when(
		type == "sdi"     ~ "blue"  ,
		type == "sdi_din" ~ "blue"  ,
		type == "usb"     ~ "red"   ,
		type == "hdmi"    ~ "cyan"  ,
		type == "vga"     ~ "green" ,
		type == "cat"     ~ "purple",
		type == "cat6e"   ~ "purple",
		type == "sw"      ~ "magenta",
		type == "audio"   ~ "orange",
		type == "ndi"     ~ "cornflowerblue",
		.default          = "black"
	) 
	q = "BuPu"
	x="webgreen"
	y = "webmaroon" 
	z="teallightcoral"
	return( cc )
}



#   Sort ports using a natural sort to handle mixed numbers and strings (e.g., "2", "10", "MV1")
#	inputs <- inputs[stringr::str_order(inputs$Port, numeric = TRUE),]

# modify this function to use natural sort of DstPort to handle mixed numbers and strings	

inports_old <- function(dev, cables) {
	text <- cables |>
		filter(DstTag == dev) |>
		arrange(DstPort) |>
		mutate(text = glue( "<{DstPort}>{DstPort}"  )) |>
		pull(text) |> paste(    collapse="|")
	
	return( paste("{", text, "}")   )
}

inports <- function(dev, cables_subset) { # Changed 'cables' to 'cables_subset'

	text <- cables_subset |> # Used 'cables_subset'

		      filter(DstTag == dev) |>

		      # Use slice() with str_order() to perform a natural sort on the port names

	          slice(stringr::str_order(DstPort, numeric = TRUE)) |>

		      mutate(port_id = paste0("p", stringr::str_replace_all(DstPort, "[^A-Za-z0-9_]", ""))) |>

		      mutate(text = glue("<{port_id}>{DstPort}")) |>

		      pull(text) |>

		      paste(collapse = "|")

	  

	 return(paste("{", text, "}"))

}


outports <- function(dev, cables_subset) { # Changed 'cables' to 'cables_subset'
	text <- cables_subset |> # Used 'cables_subset'
		filter(SrcTag == dev) |>
		# Use slice() with str_order() to perform a natural sort on the port names
		slice(stringr::str_order(SrcPort, numeric = TRUE)) |>
		#arrange(SrcPort) |>
		mutate(port_id = paste0("p", stringr::str_replace_all(SrcPort, "[^A-Za-z0-9_]", ""))) |>
		mutate(text = glue( "<{port_id}>{SrcPort}"  )) |>
		pull(text) |> paste(    collapse="|")
	
	return( paste("{", text, "}")   )
}

get_device_code <- function(targets, inventory, cables_for_ports) {

	devices_data <- inventory |>
	filter(AssetTag %in%  targets) |>
	filter(!is.na(AssetTag))  |>
	mutate(tag = tolower(stringr::str_replace_all(AssetTag, "-", ""))) |>
	rowwise() |>
	mutate(inports  =   inports( AssetTag, cables_for_ports ) ) |>
	mutate(outports =  outports( AssetTag, cables_for_ports ) ) |>
	mutate(mm = glue(" {Manufacturer}-{Model} ")) |>
	mutate(label = glue('[ label= "{{
						{inports}
						| {{  {Desc}|{mm}|{AssetTag} }}
						|{outports} 
						}}"]' ))  |>
	mutate(code = paste(tag, label)) |>
	select(AssetTag, Desc, tag, label,  code)

	return( paste(devices_data$code, collapse="\n") )
}

get_cable_code <- function(target_cables, cables) {

	cable_code <- target_cables |>
		filter(! (SrcIsCable | DstIsCable)) |> # extensions handle separately	
		mutate(cc = cable_color(Type)) |>
		mutate(label = glue('[label= "{Tag}\n{Usage2}{Type}" color={cc} ]' )) |> 
		mutate(code = glue( 
			"'{SrcTag2}' {SrcPort2} -> '{DstTag2}' {DstPort2} {label} "
		))
	
	return( paste(cable_code$code , collapse = "\n")	)	
}

get_extension_node <- function(tcables) {
	set1 <- tcables |>
		filter(  DstIsCable) |> 
		mutate(code = glue("{Tag2}{DstTag2} [label=\"\" shape=point]\n"))
	return( paste(set1$code , collapse = "\n")	)	
}

get_extension_edge <- function(tcables) {
	edge1 <- tcables |>
		filter(  DstIsCable) |> 
		mutate(code = glue("'{SrcTag2}'{SrcPort2} -> {Tag2}{DstTag2} [label=\"{Tag}\n{Usage2}\"]\n"))

	edge2 <- tcables |>
		filter(  SrcIsCable) |> 
		mutate(code = glue("'{SrcTag2}'{Tag2} -> {DstTag2}{DstPort2} [label=\"{Tag}\n{Usage2}\"]\n"))

	edges <- c(edge1$code, edge2$code)
	return( paste(edges , collapse = "\n")	)	
}

get_diagram <- function(targets, inventory, cables, label=NA
						, exc_dev
						, rankdir="LR") {
	
# exc_dev : devices to exclude
	
	labeltxt <- paste(targets, collapse= ', ' )
	my_label = glue(' "Connectivity for {labeltxt}\nAs of {Sys.Date()}"')

	label <- ifelse(is.na(label) , my_label, label)  
	
	target_cables <- cables |>
		filter(SrcTag %in% targets | DstTag %in% targets)  |>
		mutate(SrcIsCable = SrcTag %in% cables$Tag) |>
		mutate(DstIsCable = DstTag %in% cables$Tag) |>
		mutate(SrcTag2 = tolower(stringr::str_replace_all(SrcTag, "-", ""))) |>
		mutate(DstTag2 = tolower(stringr::str_replace_all(DstTag, "-", ""))) |>
		mutate(SrcPort2 = str_replace(SrcPort, ' ' , '')) |>
		mutate(DstPort2 = str_replace(DstPort, ' ' , '')) |>
		mutate(SrcPort2 = ifelse(is.na(SrcPort), "", glue(": {SrcPort2}"))) |>
		mutate(DstPort2 = ifelse(is.na(DstPort), "", glue(": {DstPort2}"))) |>
		mutate(Tag2 = tolower(stringr::str_replace_all(Tag, "-", "")))  |>
		mutate(Usage2 = ifelse( is.na(Usage), "",  glue("{Usage} ")) ) 
	
	if ( !missing(exc_dev) )  {
		target_cables <- target_cables |> filter(!(SrcTag %in% exc_dev) & !(DstTag %in% exc_dev) )
	}
	
	target_devices <- unique(c(target_cables$SrcTag ,
						target_cables$DstTag ,
						targets ))
 	if ( !missing(exc_dev) )  {
 							   target_devices <- setdiff(target_devices, exc_dev)
 							   } 

# todo consider using qreport::makegraphviz	

	diag <- paste( 
		"digraph outputs { 
			graph [overlap = true, fontsize = 20,
			rankdir="
		,rankdir
		 ,", fontname = arial ,"
		, "label=", 
		label ,  
		"]
      
node [shape=Mrecord, tooltip=\"\" 
	,  fontsize = 10 fontname = arial
    	  fillcolor=\"white:beige\" , style=filled  
		  gradientangle=270]  

edge [fontsize=8]
		"  
	, get_device_code(target_devices, inventory, target_cables)
	, get_cable_code(target_cables, cables)
	, get_extension_node(target_cables)
	, get_extension_edge(target_cables)
	, "}") 
	
	return( diag )
}

get_diagram_aux <- function (dot_code, width = 1200, height = NULL) {
	
temp_png <- tempfile(fileext=".png", tmpdir="_work")
	
	grViz(dot_code) |> 
		export_svg() |> 
		charToRaw() |> 
		rsvg_png(temp_png, width = width, height = height) 
	
	out_str <- case_when(
		knitr::is_latex_output() 
			~ sprintf("\\includegraphics[width=\\linewidth]{%s}", temp_png) ,
		knitr::is_html_output() 
			~ sprintf("![](%s)", temp_png),
		knitr::pandoc_to("docx") 
			~  "word is unsupported for dynamic diagrams.",
		TRUE 
			~ "unsupported output type for diagram"
	)	
	return(out_str)
}
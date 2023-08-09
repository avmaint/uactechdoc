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

inports <- function(dev, cables) {
	text <- cables |>
		filter(DstTag == dev) |>
		arrange(DstPort) |>
		mutate(text = glue( "<{DstPort}>{DstPort}"  )) |>
		pull(text) |> paste(    collapse="|")
	
	return( paste("{", text, "}")   )
}

outports <- function(dev, cables) {
	text <- cables |>
		filter(SrcTag == dev) |>
		arrange(SrcPort) |>
		mutate(text = glue( "<{SrcPort}>{SrcPort}"  )) |>
		pull(text) |> paste(    collapse="|")
	
	return( paste("{", text, "}")   )
}

get_device_code <- function(targets, inventory, cables) {

	devices_data <- inventory |>
	filter(AssetTag %in%  targets) |>
	filter(!is.na(AssetTag))  |>
	mutate(tag = tolower(str_replace(AssetTag, "-", ""))) |>
	rowwise() |>
	mutate(inports  =   inports( AssetTag, cables ) ) |>
	mutate(outports =  outports( AssetTag, cables ) ) |>
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

get_cable_code <- function(target_cables, cables) {

	cable_code <- target_cables |>
		mutate(SrcTag2 = tolower(str_replace(SrcTag, "-", ""))) |>
		mutate(DstTag2 = tolower(str_replace(DstTag, "-", ""))) |>
		mutate(SrcPort = str_replace(SrcPort, ' ' , '')) |>
		mutate(DstPort = str_replace(DstPort, ' ' , '')) |>
		mutate(SrcPort2 = ifelse(is.na(SrcPort), "", glue(": {SrcPort}"))) |>
		mutate(DstPort2 = ifelse(is.na(DstPort), "", glue(": {DstPort}"))) |>
		mutate(cc = cable_color(Type)) |>
		mutate(label = glue('[label= "{Tag}\n{Type}" color={cc} ]' )) |> 
		mutate(code = glue( 
			"{SrcTag2} {SrcPort2} -> {DstTag2} : {DstPort} {label} "
		))
	
	return( paste(cable_code$code , collapse = "\n")	)	
}

get_diagram <- function(targets, inventory, cables, label="" ) {
	
	labeltxt <- paste(targets, collapse= ', ' )
	my_label = glue(' label="Connectivity for {labeltxt}\nAs of {Sys.Date()}"')

	label <- ifelse(label == "", my_label, label)  
	
	target_cables <- cables |>
		filter(SrcTag %in% targets | DstTag %in% targets)  
	
	target_devices <- c(target_cables$SrcTag ,
						target_cables$DstTag ,
						targets )

	diag <- paste( 
		"digraph outputs { 
			graph [overlap = true, fontsize = 20,
			rankdir=LR, fontname = 'Helvetica' ,"
		, label ,  
		"]
      
	node [shape=Mrecord, tooltip='' ,  fontsize = 10,
    	  fillcolor='white:beige'  , style=filled  
		  gradientangle=270]  

	edge [fontsize=8]"  
	, get_device_code(target_devices, inventory, cables)
	, get_cable_code(target_cables, cables)
	, "}")
	
	return( DiagrammeR::grViz(diag) )
}

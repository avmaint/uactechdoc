# Common code for SystemOperationsAudio and SystemDesignAudio 
library(here)

#fname <- here("data", "uac_audio_config.xlsx")
#fname <- "/Users/donert/Documents/UACTech/SystemDocumentation/github/uactechdoc/data/uac_audio_config.xlsx"
#fnamedlive <- here('data', "uac_dlive_config.xlsx")

fname <- here('data', "cables.xlsx")
db.cables <- read_excel(fname,  sheet = "Cables" )

get_monitors <- function() { 
  data <- tribble(
    ~Monitor, ~Name, ~Description,
    
    1, "Vocal C",    "Front Centre",
    2, "Vocal LR",   "Front Left and Right",
    3, "Sz",         "Synthesizer", 
    4, "Pn",         "Piano",
    5, "Backline",   "Guitars and Bass",
    6, "Drums",      "Drums",
    7, "Unassigned", "Unassigned",
    8, "Unassigned", "Unassigned"
  )
  return(data)
}

get_inputs <- function( device ) {

	if ( ! (device   %in% db.cables$DstTag ) )
		stop(paste("Input Edit Error: Unknown device-", device))
		
  res <- db.cables |>
		filter(device == DstTag)
  # |>
  # 	    filter(!is.na(Name))
  # 			 	
  return(res)
}

get_outputs <- function( device ) {

	if ( ! (device   %in% db.cables$SrcTag ) )
		stop(paste("Output Edit Error: Unknown device-", device))
		
	res <- db.cables |>
		filter(device == SrcTag) 
# 	|>
#   	    filter(!is.na(Name))
  			 	
  return(res)
}
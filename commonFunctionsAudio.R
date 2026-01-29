# Common code for SystemOperationsAudio and SystemDesignAudio 
library(here)

fname <- here("data", "uac_audio_config.xlsx")
#fname <- "/Users/donert/Documents/UACTech/SystemDocumentation/github/uactechdoc/data/uac_audio_config.xlsx"

fnamedlive <- here('data', "uac_dlive_config.xlsx")

db.sources <- read_excel(fname,  sheet = "Sources" )
db.outputs <- read_excel(fname,  sheet = "Outputs" )

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

	if ( ! (device   %in% db.sources$Device ) )
		stop(paste("Input Edit Error: Unknown device-", device))
		
  res <- db.sources |>
		filter(Device == device) |>
  	    filter(!is.na(Name))
  			 	
  return(res)
}

get_outputs <- function( device ) {

	if ( ! (device   %in% db.outputs$Device ) )
		stop(paste("Output Edit Error: Unknown device-", device))
		
  res <- db.outputs |>
		filter(Device == device) |>
  	    filter(!is.na(Name))
  			 	
  return(res)
}
	

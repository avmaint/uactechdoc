# Common code for SystemOperationsAudio and SystemDesignAudio 

fname <- here("data", "uac_audio_config.xlsx")

work.config.consoleinputs <- read_excel(fname, 
                                     sheet = "ConsoleInputs" )



work.config.dantepatch <- read_excel(fname, 
                                       sheet = "DantePatch" )

work.config.consoleoutputs <- read_excel(fname, 
                                     sheet = "ConsoleOutputs" )

get_monitors <- function() { 
  data <- tribble(
    ~Monitor, ~Name, ~Description,
    
    1, "Vocal 1",   "Front vocal line - Left and Right",
    2, "Vocal 2",   "Front vocal line - Centre",
    
    3, "Synth",     "Used for Synth", 
    4, "Backline",  "Guitars and Bass",
    
    5, "Drums",     "Drums",
    6, "Piano",      "Piano"
    
  )
  return(data)
}

#TODO - Hardcoded assumption about scene 002

m7in.002 <- work.config.consoleinputs %>%
             filter(Device == "ZAKU-0001") %>% select(-Device)

dmin.002 <- work.config.consoleinputs %>%
             filter(Device == "ZAKU-0002") %>% select(-Device)

get_inputs <- function(console, scene) {
  if (scene == "002") {
    if (console == "M7CL") 
      {res <- m7in.002 }
    else if (console == "DM1K") 
      {res <- dmin.002} 
    else 
      stop(paste("Unknown console:", console))
    }
  else 
      stop(paste("Unknown Scene:", scene))
  
  return(res)
}

get_dante_outputs <- function() {
	data <- read_excel(fname
					   , sheet="dante_outputs")
	return(data)
}

get_dante_devices <- function() {
	db <- read_excel(fname, sheet = "DanteDevices" )
	return(db)
}
	
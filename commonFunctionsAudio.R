# Common code for SystemOperationsAudio and SystemDesignAudio 

# for testing: 
#fname <- file.path("/", "Users","donert","Documents","UACTech", "SystemDocumentation", "data", "AudioConfig.xlsx")
 
fname <- here("..","..","data", "AudioConfig.xlsx")

work.config.consoleinputs <- read_excel(fname, 
                                     sheet = "ConsoleInputs" )

work.config.dantedevices <- read_excel(fname, 
                                       sheet = "DanteDevices" )

work.config.dantepatch <- read_excel(fname, 
                                       sheet = "DantePatch" )

work.config.consoleoutputs <- read_excel(fname, 
                                     sheet = "ConsoleOutputs" )

get_monitors <- function() { 
  data <- tribble(
    ~Monitor, ~Name, ~Description,
    
    1, "Vocal 1",   "Typically used for the very front vocal line",
    2, "Vocal 2",   "",
    
    3, "Spare",     "If needed, used for Synth/B3", 
    4, "Backline",  "Guitars and Bass",
    
    5, "Drums",     "",
    6, "Keys",      "Piano and Keys"
    
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
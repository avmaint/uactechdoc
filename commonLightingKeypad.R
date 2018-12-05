# Common code for SystemDesignLighting and SystemOperationsLighting 
# main focus is the keypad configuration. 

get_keypad_buttons <- function() { 
  keypad <- tribble(
    ~Button, ~Name, ~B_Description,
    
    1, ".", "",  
    2, "Rehearse", "For Rehearsal - Stage Pots and Sconce",
    
    3, "Ambience", "Use for walkin - intermission", 
    4, "Basic Event", "Front centre lit bright, house medium, plus accents",
    
    5, "BSF 1", "Similar to Basic Event, plus Cross",
    6, "BSF 2", "Low levels for Video",
    
    7, "Maintenance", "House and Stage Ketras on full white",
    8, "OFF", "Night Light Mode: Sconce only." 
  )
return(keypad)
}

get_keypad2preset <- function() {
  keypad2preset <- data.frame(Button=seq(1:8), Preset=seq(1:8))
  return(keypad2preset)
}

get_preset2zone <- function() {
  preset2zone <- tribble(
    ~Preset, ~Zone, ~Details,
    7,           2, "100% Cool White",
    7,           1, "100% Cool White",
    7,           3, "100% Cool White",
    7,           4, "100% Cool White",
    
    8,           1, "80% Warm White",
    
    3,           1, "75% Blue",
    3,           5, "75% Blue",
    3,           2, "80% Warm White",
    3,           4, "80% Warm White",
    3,           3, "80% Warm White",
    3,          7, "75% Blue",
    3,          12, "75% Blue",
    3,          13, "100% Blue",
    3,          8, "100% Magenta",
    3,          10, "100%",
    3,          15, "75% Blue",
    
    4,           1, "75% Warm White",
    4,           5, "75% Warm White",
    4,           2, "80% Warm White",
    4,           4, "80% Warm White",
    4,           3, "80% Warm White",
    4,          6, "70% Warm White",
    4,          7, "75% L.Pink",
    4,          12, "75% L.Pink",
    4,          13, "100% Blue",
    4,          8, "100% Pink",   
    4,          15, "100% Blue",
    
    5,           1, "75% Warm White",
    5,           5, "75% Warm White",
    5,           2, "80% Warm White",
    5,           4, "80% Warm White",
    5,           3, "80% Warm White",
    5,          6, "80% Warm White",
    5,          7, "75% L.Pink",
    5,          12, "75% L.Pink",
    5,          13, "100% Blue",
    5,          8, "100% Pink",
    5,          10, "100%",
    
    6,           1, "75% Warm White",
    6,           2, "30% Warm White",
    6,           4, "30% Warm White",
    6,           3, "30% Warm White",
    6,           7, "25% L.Pink",
    6,          12, "75% L.Pink",
    6,          13, "50% Blue",
    6,           8,  "50% Pink",
    6,          10, "100%" ,
    6,           6,  "30%"
  )
return(preset2zone)
}

get_zones2dmx <- function() {
  
#plus_n : 
#input:  takes a string of space delimited numbers, and an integer n
#returns: a string with n added to each of the original numbers.
#usage: The ADJ Ultrabar12s have been programmed in 12 channel model (RGBWAU..I...). 
#There is no Echo profile to support that so we have split the control into a colour and an intensity zone.     

  plus_n <- function(nums, n) { 
    nums <- strsplit(nums,"[[:space:]]") %>% 
      unlist() %>% 
      as.integer() 
    
      as.character(nums + n) %>%
      paste(collapse=" ")  
  }
  
  zones <- tribble(
    ~Zone, ~Z_Description,     ~Profile, ~DMX, 
    1,  "Sconce",              "RGB",    "163",
    2,  "House Pendants Wide", "RGB",    "503 506",
    3,  "Upper Balcony",       "RGB",    "509 166",
    4,  "Under Balcony",       "RGB",    "500",
    5,  "Stage pots",          "RGB",    "151 154 157 160",
    6, "All Thrust",             "I",    "1 2 3 9 10 11",
    7, "All Vocals",         "IRGBS",    "22 27 32 37 42 47",
    8, "Floor Flares",       "IRGBS",    "172 177 182 187 192 197 202",
    9, "Floor Bars",           "RGB",    "470", # not used?
    10, "Cross",                 "I",    "458", #wont work due to DMX path
    
    12, "Wall Colour",        "RGBW", t<-"219 231 243 255 267 279 291 303 315 327 339 351 363 375",
    11, "Wall Intensity",        "I",     plus_n(t,9),
    
    14, "Bulkhead Colour",    "RGBW",    "0 0 0 0", # not sure of the profile for bulkhead.
    13, "Bulkhead Intensity",    "I",    "", #BH Colour +9",
    
    15, "Towers",             "RGBW",    "62 68 74 80"  #Amber and UV missed

    ) %>% arrange(Zone)
  return(zones)
}
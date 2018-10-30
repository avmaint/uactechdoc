# Common code for SystemDesignLighting and SystemOperationsLighting 
# main focus is the keypad configuration. 

get_keypad_buttons <- function() { 
  keypad <- tribble(
    ~Button, ~Name, ~B_Description,
    
    1, "-", "",  
    2, "-", "",
    
    3, "Ambience", "Use for walkin - intermission", 
    4, "Basic Event", "Front centre lit bright, house medium, plus accents",
    
    5, "BSF 1", "Similar to Basic Event, plus Cross",
    6, "BSF 2", "Low levels for Video",
    
    7, "On", "Maintenance: House and Stage Ketras on full white",
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
    7      ,     7, "100% Cool White",
    7      ,     5, "100% Cool White",
    
    8      ,     5, "80% Warm White",
    
    3,           5, "75% Blue",
    3,           6, "75% Blue",
    3,           7, "80% Warm White",
    3,           8, "80% Warm White",
    3,           9, "80% Warm White",
    3,          11, "75% Blue",
    3,          12, "75% Blue",
    3,          13, "100% Blue",
    3,          14, "100% Magenta",
    3,          16, "100%",
    
    4,           5, "75% Warm White",
    4,           6, "75% Warm White",
    4,           7, "80% Warm White",
    4,           8, "80% Warm White",
    4,           9, "80% Warm White",
    4,          10, "80% Warm White",
    4,          11, "75% L.Pink",
    4,          12, "75% L.Pink",
    4,          13, "100% Blue",
    4,          14, "100% Pink",   
    
    5,           5, "75% Warm White",
    5,           6, "75% Warm White",
    5,           7, "80% Warm White",
    5,           8, "80% Warm White",
    5,           9, "80% Warm White",
    5,          10, "80% Warm White",
    5,          11, "75% L.Pink",
    5,          12, "75% L.Pink",
    5,          13, "100% Blue",
    5,          14, "100% Pink",
    5,          16, "100%",
    
    6,           5, "75% Warm White",
    6,           7, "30% Warm White",
    6,           8, "30% Warm White",
    6,           9, "30% Warm White",
    6,          11, "75% L.Pink",
    6,          12, "75% L.Pink",
    6,          13, "50% Blue",
    6,          14, "50% Pink",
    6,          16, "100%" 
  )
return(preset2zone)
}

get_zones2dmx <- function() {
  zones <- tribble(
    ~Zone, ~Z_Description,        ~DMX, 
    5,  "Sconce",              "160" ,
    6,  "Stage pots",          "151 154 157",
    7,  "House pendants wide", "163 166 169",
    8,  "Under Balcony",       "500",
    9,  "Upper Balcony",       "503",
    10, "All thrust",          "1 2 3 5 6 7",
    11, "All vocals",          "22 27 32 37 42 47",
    12, "Walls",               "219 231 243 255 267 279 291 303 315 327 339 351 363 375",
    13, "Towers",              "62 68 74 80",
    14, "Floor flares",        "172 177 182 187 192 197 202",
    15, "Floor bars",          "470",
    16, "Cross",               "458"
  )
  return(zones)
}
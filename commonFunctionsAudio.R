# Common code for SystemOperationsAudio and SystemDesignAudio 

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

m7in.002 <- tribble(
  ~Channel, ~Usage, ~Type, ~Notes,
  1,       "Kick",  "Beyer M88", "Drum Snake",
  2,       "Snare", "CAD",       "Drum Snake",
  3,       "Tom 1", "CAD",       "Drum Snake",
  4,       "Tom 2", "CAD",       "Drum Snake",
  5,       "Tom 3", "CAD",       "Drum Snake",
  6,       "Tom 4 (floor)", "CAD", "Drum Snake",
  7,       "OH L","AKG 418",     "Drum Snake",
  8,       "OH R","AKG 418",     "Drum Snake",
  9,       "Hat", "AKG 418",     "Drum Snake",
  10,       "Djembe","SM 57",     "Drum Snake",
  11,       "perc 1","",          "Drum Snake",
  12,       "perc 2","",          "Drum Snake",
  13,       "Bass 1",  "JDI DI",  "",
  14,       "Bass 2",  "",        "",
  15,       "EG 1",   "SM 57",    "",
  16,       "EG 2",   "",         "",
  17,       "AG 1",   "Pro DI",   "",
  18,       "AG 2",   "",         "",
  19,       "B3 lo",   "SM57"  ,   "",
  20,       "B3 hi",    "SM57" ,   "",
  21,       "Pno lo",   "",        "Condenser",
  22,       "Pno hi",    "",       "Condenser",
  23,       "syn 1",     "Pro DI",  "",
  24,       "syn 2",     "",        "",
  25,       "syn 3",      "",       "",
  26,       "syn 4",      "",       "",
  27,       "Str 1",      "",       "",
  28,       "Str 2",      "",       "",
  29,       "Choir 1", "AT 853","Set up as required",
  30,       "Choir 2", "AT 853", "Set up as required",
  31,       "Choir 3", "AT 853", "Set up as required",
  32,       "Choir 4", "",       "",
  33,       "Vox HH01",  "Beta 87a", "Dante ZAMU-A001 ch01",
  34,       "Vox HH02",  "Beta 87a", "Dante ZAMU-A001 ch02",
  35,       "Vox HH03",  "Beta 87a", "Dante ZAMU-A001 ch03",
  36,       "Vox HH04",  "Beta 87a", "Dante ZAMU-A001 ch04",
  37,       "Vox HH05",  "Beta 87a", "Dante ZAMU-B001 ch01",
  38,       "Vox HH06",  "Beta 87a", "Dante ZAMU-B001 ch02",
  39,       "Vox HH07",  "Beta 87a", "Dante ZAMU-B001 ch03",
  40,       "Vox HH08",  "Beta 87a", "Dante ZAMU-B001 ch04",
  41,       "Front Floor Pocket", "","",
  42,       "Front Floor Pocket", "","",
  43,       "Front Floor Pocket", "","",
  44,       "Front Floor Pocket", "","",
  45,       "Front Floor Pocket", "","",
  46,       "Front Floor Pocket", "","",
  47,      "Vox HH09",  "Beta 87a", "Dante ZAMU-B002 ch01",
  48,      "Vox HH10",  "Beta 87a", "Dante ZAMU-B002 ch02",
  "STR1",    "Effect 1 Return","Rev Plate", "",
  "STR2",    "Effect 2 Return","Rev Hall",  "",
  "STR3",    "Effect 3 Return","Mono Delay","",
  "STR4",    "Effect 4 Return","Chorus",    ""
)

dmin.002 <- tribble(
  ~Channel, ~Usage, ~Type,            ~Notes,
  1,        "BP 01", "Shure Wireless", "Dante ZAMU-B002 ch03",
  2,        "BP 02", "Shure Wireless", "Dante ZAMU-B002 ch04",
  3,        "BP 03", "Shure Wireless", "Dante ZAMU-B003 ch01",
  4,        "BP 04", "Shure Wireless", "Dante ZAMU-B003 ch02",
  5,        "BP 05", "Shure Wireless", "Dante ZAMU-B003 ch03",
  6,        "BP 06", "Shure Wireless", "Dante ZAMU-B003 ch04",
  7,        "unused", "" ,             "" ,
  8,        "unused", "" ,             "" ,
  9,        "unused", "" ,             "" ,
  10,       "unused", "" ,             "" ,
  11,       "CD L",   "",              "Tascam CD-01U",
  12,       "CD R",   "",              "Tascam CD-01U",
  13,       "Computer L", "",              "CDMU-A001" ,
  14,       "Computer R", ""  ,            "CDMU-A001" ,
  15,       "Guest ⅛ᵗʰ L", "", "",
  16,       "Guest ⅛ᵗʰ R", "", "" 
)

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
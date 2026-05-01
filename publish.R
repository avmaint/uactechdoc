# Update all tech documents  
# If the source has been updated since last publication, 
# then render create a pdf and put the results in the publication directory 

publish.all <- FALSE

#It doesn't consider dependencies so if a jpg, gv or common function is changed it will not be published.
#TODO: add modification time dependency check on jpg, png and gv files (base it on a prefix)
#TODO: add dependency on common code, including furtherinformation (which should be renamed to be common...)

require(tidyverse)
require(gt)
require(quarto)

srcdir <-  "~/Documents/UACTech/SystemDocumentation/github/uactechdoc"
trgdir <- file.path(srcdir, "_output")
sog    <- "~/Documents/UACTech/SystemDocumentation/data/SystemOperationsGuide.xlsx"
ti     <- "~/Documents/UACTech/SystemDocumentation/TechInventory.xlsx"

# chromecmd <- "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome"
# chromeopt <- "--headless --disable-gpu --print-to-pdf "

files <- tribble( # The file to process and whether is depends on the inventory or Rundown data.
  ~File,                    ~Inventory,  ~Rundown,
  "SystemDesignAudio",              TRUE,   FALSE,
  "SystemDesignLighting" ,          TRUE,   FALSE,
  "SystemDesignNetwork",            TRUE,   FALSE,
  "SystemDesignProjection",         TRUE,   FALSE,
  "SystemDesignVideo",              TRUE,   FALSE,
  "SystemDesignYouth",              TRUE,   FALSE,
  
  "SystemOperationsAudio",          TRUE,   TRUE,
  "SystemOperationsLighting",       TRUE,   TRUE,
  "SystemOperationsProjection",     TRUE,   TRUE,
  "SystemOperationsVideo",          TRUE,   TRUE,
  
  "TroubleShooting",                TRUE,   TRUE,
  
  "SystemAdministrationGuide",      TRUE,   FALSE, 
  

  #"TechHomePage",                   TRUE,   FALSE,

  #"TeamDesign",                     FALSE,  FALSE,
  #"TechTeamIntro",                  FALSE,  FALSE,
  
  #"ElectricalGuide",                FALSE,  FALSE,
  #"InventoryManagement",            TRUE,   FALSE,
  #"SystemAdministrationGuide",      TRUE,   FALSE,
          
  #"index",                          FALSE,  FALSE,
  #"SystemOperationsGuide",          FALSE,  TRUE 
)

needs.updating <- function(file) {
  qmd.file   <- paste0(srcdir, "/", f, '.qmd' )
  html2.file <- paste0(trgdir, "/", f, ".html" )
  #get modification times
  qmd.mt   <- file.info(qmd.file)$mtime
  html2.mt <- file.info(html2.file)$mtime

  # Output file doesn't exist yet — always needs publishing
  if (is.na(html2.mt)) return(TRUE)

  sog.mt   <- file.info(sog)$mtime
  ti.mt    <- file.info(ti)$mtime

  qmd.newer <- (qmd.mt > html2.mt)
  sog.newer <- (sog.mt > html2.mt) & files[files$File==f,"Rundown"]
  ti.newer  <- (ti.mt > html2.mt)  & files[files$File==f,"Inventory"]

  return.value <- qmd.newer | sog.newer | ti.newer

  return(return.value)
}

#files <- c("SystemAdministrationGuide") # For Testing
results <- data.frame()

for (f in files$File) {
  
  print(paste("Processing:", f))
  
  qmd.file   <- paste0(srcdir, "/", f, '.qmd' )
  html2.file <- paste0(trgdir, "/", f, ".html" )
  html1.file <- paste0(srcdir, "/", f, '.html' )
  pdf.file   <- paste0(trgdir, "/", f, ".pdf"  )
  
  #get modification times
  qmd.mt <- file.info(qmd.file)$mtime
  html2.mt <- file.info(html2.file)$mtime
  
  if (publish.all | needs.updating(f) ) {
  	
    quarto::quarto_render(qmd.file, output_format = "html", quiet = FALSE)
  
    quarto::quarto_render(qmd.file, output_format = "titlepage-pdf", quiet = FALSE)
    
    results <- rbind(results, data.frame(File=f, Action="Updated"))
    } else {
      print(paste(f, "Update not required.")) 
      results <- rbind(results, data.frame(File=f, Action="Not updated"))
    }
}

results |>
	gt() |>
	opt_stylize(style=5)  |> print()

print(results)
print("Complete.")
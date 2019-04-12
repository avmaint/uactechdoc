# Update all tech documents  
# If the source has been updated since last publication, 
# then render create a pdf and put the results in the publication directory 

#It doesn't consider dependencies so if a jpg, gv or common function is changed it wil lnot be published.
#TODO: add modification time dependency check on jpg, png and gv files (base it on  a prefix)
#TODO: add dependency on common code, includeing furtherinformation (which should be renamed to be common...)

require(dplyr)
require(kableExtra)

srcdir <-  "~/Documents/UACTech/SystemDocumentation/github/uactechdoc"
trgdir <- "~/Dropbox/UAC_Tech_Docs"
sog    <- "~/Documents/UACTech/SystemDocumentation/data/SystemOperationsGuide.xlsx"
ti     <- "~/Documents/UACTech/SystemDocumentation/TechInventory.xlsx"

chromecmd <- "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome"
chromeopt <- "--headless --disable-gpu --print-to-pdf "

files <- tribble( # The file to process and whether is depends on the inventory or Rundown data.
  ~File,                    ~Inventory,  ~Rundown,
  "SystemDesignAudio",              TRUE,   FALSE,
  "SystemDesignLighting" ,          TRUE,   FALSE,
  "SystemDesignNetwork",            TRUE,   FALSE,
  "SystemDesignProjection",         TRUE,   FALSE,
  "SystemDesignVideo",              TRUE,   FALSE,

  "SystemOperationsAudio",          TRUE,   TRUE,
  "SystemOperationsLighting",       TRUE,   TRUE,
  "SystemOperationsProjection",     TRUE,   TRUE,
  "SystemOperationsVideo",          TRUE,   TRUE,

  "TechHomePage",                   TRUE,   FALSE,

  "TeamDesign",                     FALSE,  FALSE,
  "TechTeamIntro",                  FALSE,  FALSE,
  
  "ElectricalGuide",                FALSE,  FALSE,
  "InventoryManagement",            TRUE,   FALSE,
  "SystemAdministrationGuide",      TRUE,   FALSE,
          
  "index",                          FALSE,  FALSE,
  "SystemOperationsGuide",          FALSE,  TRUE 
)

needs.updating <- function(file) {
  rmd.file   <- paste0(srcdir, "/", f, '.Rmd' )
  html2.file <- paste0(trgdir, "/", f, ".html" )
  #get modification times
  rmd.mt <- file.info(rmd.file)$mtime
  html2.mt <- file.info(html2.file)$mtime
  sog.mt   <- file.info(sog)$mtime
  ti.mt   <- file.info(ti)$mtime
  
  rmd.newer <- (rmd.mt > html2.mt) 
  sog.newer <- (sog.mt > html2.mt) & files[files$File==f,"Rundown"]
  ti.newer  <- (ti.mt > html2.mt)  & files[files$File==f,"Inventory"]
  
  return.value <- rmd.newer | sog.newer | ti.newer
  
  return(return.value)
}

#files <- c("SystemAdministrationGuide") # For Testing
results <- data.frame()

for (f in files$File) {
  
  print(paste("Processing:", f))
  
  rmd.file   <- paste0(srcdir, "/", f, '.Rmd' )
  html2.file <- paste0(trgdir, "/", f, ".html" )
  html1.file <- paste0(srcdir, "/", f, '.html' )
  pdf.file   <- paste0(trgdir, "/", f, ".pdf"  )
  
  #get modification times
  rmd.mt <- file.info(rmd.file)$mtime
  html2.mt <- file.info(html2.file)$mtime
  
  if (needs.updating(f)) {  
    #render
    rmarkdown::render(rmd.file, output_format = "html_document")
  
    #move it to target
    cmd <- paste("mv", html1.file, trgdir)
    system(cmd)
  
    #make pdf
    cmd <- paste(chromecmd, chromeopt, html2.file)
    system(cmd)  
  
    #rename it
    system2("mv", args=paste("output.pdf", pdf.file) )
    
    results <- rbind(results, data.frame(File=f, Action="Updated"))
    } else {
      print(paste(f, "Update not required.")) 
      results <- rbind(results, data.frame(File=f, Action="Not updated"))
    }
}

results %>%
  kable(format="html") %>%
  column_spec( 1,  bold = TRUE ) %>%
  kable_styling("striped", full_width = TRUE) %>% print()

#files %>% group_by(File) %>% summarise(N = nth()) %>% filter(N > 1)

print(results)
print("Complete.")

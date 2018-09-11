# Update all tech documents  
# If the source has been updated since last publication, 
# then render create a pdf and put the results in the publication directory 

#It doesn't consider dependencies so if a jpg, gv or common function is changed it wil lnot be published.
#It doesn't consider database changes either

#TODO: also consider the inventory or rundown data in the publication decision

srcdir <-  "~/Documents/UACTech/SystemDocumentation/github/uactechdoc"
trgdir <- "~/Dropbox/UAC_Tech_Docs"

chromecmd <- "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome"
chromeopt <- "--headless --disable-gpu --print-to-pdf "

results <- data.frame()

files <- c( 
  "SystemDesignAudio",
  "SystemDesignLighting" ,
  "SystemDesignNetwork",
  "SystemDesignProjection",
  "SystemDesignVideo",

  "SystemOperationsAudio",
  "SystemOperationsLighting",
  "SystemOperationsProjection",
  "SystemOperationsVideo",

  "TechHomePage",

  "TeamDesign",
  "ElectricalGuide",
          
  "index",
          "SystemOperationsGuide"
          #"InventoryManagement",
          #", "TechTeamIntro"
)

#files <- c("SystemAdministrationGuide") # For Testing

for (f in files) {
  
  print(paste("Processing:", f))
  
  rmd.file   <- paste0(srcdir, "/", f, '.Rmd' )
  html2.file <- paste0(trgdir, "/", f, ".html" )
  html1.file <- paste0(srcdir, "/", f, '.html' )
  pdf.file   <- paste0(trgdir, "/", f, ".pdf"  )
  
  #get modification times
  rmd.mt <- file.info(rmd.file)$mtime
  html2.mt <- file.info(html2.file)$mtime
  
  if (rmd.mt > html2.mt) {  
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
    
    results <- rbind(results, data.frame(file=f, action="updated"))
    } else {
      print(paste(f, "Update not required.")) 
      results <- rbind(results, data.frame(file=f, action="not updated"))
    }
}

print(results)
print("Complete.")
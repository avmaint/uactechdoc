# Render all tech documents  
# and
# move to published documents folder.

srcdir <-  "~/Documents/UACTech/SystemDocumentation/github/uactechdoc/"
trgdir <- "~/Dropbox/UAC_Tech_Docs"

files <- c( 
  "SystemDesignAudio",
  "SystemDesignLighting" ,
  "SystemDesignNetwork",
  "SystemDesignProjection",
  "TeamDesign.Rmd",

  "SystemOperationsAudio",
  "SystemOperationsLighting",
  "SystemOperationsProjection",
  "SystemOperationsVideo",
  
  "TeamDesign",
  
  "index"
          
          #"SystemOperationsGuide"
          #"InventoryManagement",
          #"TechTeamIntro",
          #"index",
          #"SystemAdministrationGuide",
           )

for (f in files) {
  print(paste("Processing:", f))
  
  rmd <- paste0(srcdir, f, '.Rmd')
  rmarkdown::render(rmd, output_format = "html_document")
  
  html <- paste0(srcdir, f, '.html')
  cmd <- paste("mv", html, trgdir)
  
  cat(cmd)
  
  system(cmd)
}
  
print("Complete.")
# Render all team documents  
# and
# copy to published documents folder.

srcdir <-  "~/Documents/UACTech/SystemDocumentation/github/uactechdoc/"
trgdir <- "~/Dropbox/UAC_Tech_Docs"

files <- c( "SystemDesignLighting" ,
            "SystemDesignVideo",
            "SystemDesignAudio",
            "SystemDesignVideo",
            "SystemDesignNetwork",
       
            "SystemOperationsAudio",
            "SystemOperationsProjection",
            "SystemOperationsLighting",
            "SystemOperationsVideo"
          
          #"SystemOperationsGuide"
          #"InventoryManagement",
          #"TechTeamOrg",
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
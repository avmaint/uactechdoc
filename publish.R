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

  "SystemOperationsAudio",
  "SystemOperationsLighting",
  "SystemOperationsProjection",
  "SystemOperationsVideo",
  
  "TechHomePage",
  
  "TeamDesign", 
          
  "index"
          #"SystemOperationsGuide"
          #"InventoryManagement",
          #"

            #"SystemAdministrationGuide",
           )

files <- c("TechTeamIntro", "ElectricalGuide")

print(paste("files:", files))

for (f in files) {
  
  print(paste("Processing:", f))
  
  rmd <- paste0(srcdir, f, '.Rmd')
  print(paste("Rendering", rmd))
  rmarkdown::render(rmd, output_format = "html_document")
  
  html <- paste0(srcdir, f, '.html')
  cmd <- paste("mv", html, trgdir)
  
  print(paste("Moving:", cmd))
  
  system(cmd)
}
  
print("Complete.")
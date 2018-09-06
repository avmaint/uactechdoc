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
  "SystemDesignVideo",

  "SystemOperationsAudio",
  "SystemOperationsLighting",
  "SystemOperationsProjection",
  "SystemOperationsVideo",

  "TechHomePage",

  "TeamDesign",
  "ElectricalGuide",
          
  "index"
          #"SystemOperationsGuide"
          #"InventoryManagement",
          #", "TechTeamIntro"
)

#files <- c("SystemAdministrationGuide")

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

chromecmd <- "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome"
chromeopt <- "--headless --disable-gpu --print-to-pdf "

for (f in files) {

  sfile <- paste0(trgdir, "/", f, ".html"  )

  cmd <- paste(chromecmd, chromeopt, sfile)
  print(cmd)
  #system(cmd)
}
  
print("Complete.")

# TODO Explore ways to also produce PDF
#  Option 1  - use chrome headless for the conversion
# alias chromeX="/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome" 
# /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --headless --disable-gpu --print-to-pdf  file:///Users/donert/Dropbox/UAC_Tech_Docs/SystemOperationsVideo.html
# chromeX 

#TODO: Add change log report to each document:
#git log --date=local --pretty=format:"%h%x09%an%x09%ad%x09%s" -- SystemOperationsLighting.Rmd

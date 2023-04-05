# Makefile for building and publishing x.qmd

# Define variables for the file dependencies and the output file
C_FUNCTIONS_R = commonFunctions.R
C_PACKAGES_R = commonPackages.R
SD_Dante_QMD = SystemDesignDante.qmd
SD_Dante_HTML = SystemDesignDante.html
QUARTO = "/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto"  


# Define the build target and its dependencies
build: $(SD_Dante_HTML)
	echo "building"
	
$(SD_Dante_HTML): $(SD_Dante_QMD ) $(C_FUNCTIONS_R) $(C_PACKAGES_R)
	$(QUARTO) render $(SD_Dante_QMD)	

# Define the publish target and its dependencies
publish: $(SD_Dante_QMD)
    # Add commands here to publish the output file

# Specify that the targets are not actual files
.PHONY: build publish

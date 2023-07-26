# Makefile for building and publishing uac tech docs

# Define variables for the file dependencies and the output files
 
SDD_QMD = SystemDesignDante.qmd
SDD_HTML = SystemDesignDante.html

SDV_QMD = SystemDesignVideo.qmd
SDV_HTML= SystemDesignVideo.html

QUARTO = "/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto"  
QUARTO = "/Applications/quarto/bin/quarto"

#####
all:  $(SDV_HTML) $(SDD_HTML)
#####

$(SDV_HTML): $(SDV_QMD ) commonFunctions.R commonPackages.R data/cables.xlsx
	$(QUARTO) render $(SDV_QMD)	
	
$(SDD_HTML): $(SDD_QMD ) commonFunctions.R commonPackages.R commonFunctionsAudio.R
	$(QUARTO) render $(SDD_QMD)	

tinytex:
	$(QUARTO) install tool tinytex

# Specify that the targets are not actual files
.PHONY: build publish

clean:
	rm -f $(SDV_HTML) $(SDD_HTML)
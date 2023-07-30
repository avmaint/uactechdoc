# Makefile for building and publishing uac tech docs

# Define variables for the file dependencies and the output files
 
SDD_QMD = SystemDesignDante.qmd
SDD_HTML = SystemDesignDante.html

SDV_QMD = SystemDesignVideo.qmd
SDV_HTML= SystemDesignVideo.html
SDV_PDF = SystemDesignVideo.pdf

SOV_QMD = SystemOperationsVideo.qmd
SOV_HTML= SystemOperationsVideo.html

QUARTO = "/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto"  
QUARTO = "/Applications/quarto/bin/quarto"

#####
all:  $(SDV_HTML) $(SDD_HTML) $(SOV_HTML) $(SDV_PDF)
#####

sdv: $(SDV_HTML) $(SDV_PDF)
	echo making sdv

$(SDV_HTML): $(SDV_QMD ) commonFunctions.R commonPackages.R data/cables.xlsx
	$(QUARTO) render $(SDV_QMD)	--to html
	$(QUARTO) render $(SDV_QMD)	--to pdf

$(SOV_HTML): $(SOV_QMD ) commonFunctions.R commonPackages.R 
	$(QUARTO) render $(SOV_QMD)	--to html
	$(QUARTO) render $(SOV_QMD)	--to pdf
	echo "line 27"
	
	
$(SDD_HTML): $(SDD_QMD ) commonFunctions.R commonPackages.R commonFunctionsAudio.R
	$(QUARTO) render $(SDD_QMD)	--to html 
	
$%.html: %.qmd	
	$(QUARTO) render %.qmd	--to html  
	echo "line 35"
	
$%.pdf: %.qmd	
	$(QUARTO) render %.qmd	--to pdf  	
	echo "line 39"

tinytex:
	$(QUARTO) install tool tinytex

# Specify that the targets are not actual files
.PHONY: build publish

clean:
	rm -f  *.aux *.log *.tex *.toc
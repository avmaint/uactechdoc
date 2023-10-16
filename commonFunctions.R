## A library of common functions used within this collection of Rmds.

#Globals
#tODO - use of globals, cache_assets and cache_network is subject to bugs.

path         <- file.path("~", "Documents", "UACTech", "SystemDocumentation")
data_dir     <- file.path(path, "github", "uactechdoc", "data")
asset_file   <- "uac_assets.xlsx"
network_file <- "uac_network.xlsx"
cables_file  <- "uac_cables.xlsx"
glossary_file <- "uac_glossary.xlsx"
lighting_file <- "uac_lighting.xlsx"
training_file <- "training_videos.xlsx"

#' This function takes a list of asset tags and the inventory 
#' returns a formatted kable table of the results. 
#' It will force a stop if there is a mismatch.
#' The inventory must have certain columns of data within it.
#' 
#' @param items a list of asset tags which will be used to select items from the inventory
#' @param inventory A data frame containing the full list of items. It is expected to be the result of get.inventory()
#' @return returns formatted html of the selected items.
#' 
print_inv_kable <- function(items, inventory) {
  
  selected <- items %>% 
    data.frame(AssetTag=.)
  
  merged <- merge( inventory, selected) 
  
  if(length(items) != nrow(merged) ) {
    diff <- setdiff(selected$AssetTag, inventory$AssetTag)
    # ToDO: the next line of code has issues. 
    #1) if it is executed it will likley fail as the error msg is not a file name
    #2) It doesn't handle duplicate asset tags.
    #fundamentlly I don't know how to expose the error condition 
    system2("cat",  paste('"Undefined in Inventory ', diff,  '"') )
  }
  
  stopifnot(length(items) == nrow(merged) )
  
  merged %>% 
    select(AssetTag, Manufacturer, Model, Location, Desc ) %>%
    arrange( AssetTag ) %>%
    kable(align="l") %>%
    column_spec( 1,  bold = TRUE ) %>%
    kable_styling("striped", full_width = TRUE)
}

print_inv <- function(items, inventory) {
	
	selected <- items %>% 
		data.frame(AssetTag=.)
	
	merged <- merge( inventory, selected) 
	
	if(length(items) != nrow(merged) ) {
		diff <- setdiff(selected$AssetTag, inventory$AssetTag)
		# ToDO: the next line of code has issues. 
		#1) if it is executed it will likley fail as the error msg is not a file name
		#2) It doesn't handle duplicate asset tags.
		#fundamentlly I don't know how to expose the error condition 
		system2("cat",  paste('"Undefined in Inventory ', diff,  '"') )
	}
	
	stopifnot(length(items) == nrow(merged) )
	
	merged |>
		select(AssetTag, Manufacturer, Model, Location, Desc ) |>
		arrange( AssetTag ) |>
		gt() |>  
		opt_stylize(style = 3) |>
		tab_style(
			style = cell_text(
				weight = "bold", 
				),
			locations = cells_body(
				columns = "AssetTag")
		) |>
		tab_options(table.font.size="50%")
}


#' Function to retrieve and format the git commit history for a file. 
#' Meant to tack on to the end of the each document.
#'
#' @param file.name the name of a source file name to be found in git
#' @return html formatted history of commits.
#' @examples 
#'  commit.log.html( knitr::current_input() )
#'  
commit.log.html <- function(file.name) {
  
  cmd <- "git"
  opt <- 'log --date=local --pretty=format:"%h,%an,%ad,%s" --'
  
  args <- paste( opt, file.name)
  
  o <- system2(cmd, args=args, stdout=TRUE)
  
  df <- read.csv(text=o, col.names=c("id", "user", "date", "message"), header=FALSE)
  
  # formatted <- df %>% 
  # 	select(user, date, message) %>%
  # 	kable(align="l", caption="git Commit Log") %>%
  # 	column_spec( 1,  bold = TRUE ) %>%
  # 	kable_styling("striped", full_width = TRUE)
  # 
  require(gt)
  formatted <- df |> 
  	select(user, date, message) |>
  	gt() |>
  	opt_stylize(style=3) |>
  	tab_header("Change History")
  
  return( formatted )
 
}

# Functions to get data used by most of the reports.



fname.cf <- file.path(path, "TechInventory.xlsx" )
fname.people <- file.path(path, "db-people.xlsx" )

cache_network <- read_excel(file.path(data_dir, network_file), 
                           sheet = "network")

ct <- c( rep("text",2),    # AssetTag, Category
         rep("numeric",3), # Qty UnitValue AcqValue
         rep("text",10),   # Manufacturer	Model	Building	Floor	Room	Location	Type	Desc	SN	InService
         "date",           # PurcDate
         rep("text",2),    # PurcFrom Invoice
         "text",           # Comments	
         rep("numeric",2), #  AcqYear	EolYear
         "text",    #Disposed Y/N
         "numeric", #DisposedYear
         "numeric", #DisposedValue
         rep("text",2)     #DisposedComment, Destination
)

cache_assets <- read_excel(file.path(data_dir, asset_file), 
                             sheet = "assets", col_types=ct) 

get.network <- function() {
  return(cache_network)
}

get.cables <- function () {
	cables <- read_excel(file.path(data_dir, cables_file), 
					     sheet = "Cables")
	return(cables)
}

get.glossary <- function () {
	cables <- read_excel(file.path(data_dir, glossary_file), 
						 sheet = "glossary")
	return(cables)
}

get.playbacks <- function () {
	playback <- read_excel(file.path(data_dir, lighting_file), 
						   sheet = "CS40.Playback")
}	

#' retrieves the inventory database
#' @return a data frame containing the inventory database
get.assets <- function() {
  return( cache_assets )
}

get.inventory <- get.assets

#' retrieves the dmx details
#' @return a data frame containing the dmx details
get.dmxdetails <- function() {
  return( read_excel(file.path(data_dir, lighting_file)
  				   , sheet = "DMX.Details" ))
}

#' retrieves the further information list
#' @return a data frame containing the further information items
get.further <- function() {
  return( read_excel(fname.cf, sheet = "Further")
          )
}

get.credentials <- function() {
  return( read_excel(fname.cf, sheet = "Credentials"))
}

get.software <- function() {
  return( read_excel(fname.cf, sheet = "Software"))
}

#' Converts a excel formatted time value to string
#' used by get.activities()
#' @param s an excel time value
#' @return a string representation of the time
#' 
num2time  <- function(s) {
  hr <- floor(24 * s)
  mi <- round((24*s - hr ) * 60)
  
  if (nchar(hr) == 1) {
    hr <-paste0("0",hr)
  }
  
  if (nchar(mi) == 1) {
    mi <- paste0("0", mi)
  }
  
  return( paste0( hr, ":", mi ) )
}

#' retrieves the activities list from the systems operations guide data
#' @return a data frame containing the activities
get.activities <- function() {
  f <- file.path(path, "data", "SystemOperationsGuide.xlsx")
  ct <- c("numeric" ,"numeric", "text", "numeric",rep("text",7) )
  
  activities <- read_excel(f, 
                   sheet = "linear",
                   col_types=ct)  %>% 
        rowwise() %>%
        mutate(Time = num2time(Time1) )
  
  return(activities)
}

#' retrieves the event list
#' @return a data frame containing the events
get.events <- function() {
  events <- get.activities() %>%
    select(Time1, Time, Event ) %>%
    unique()
  return(events)
} 

printCurrency <- function(value, currency.sym="$", digits=2, sep=",", decimal=".") {
  paste(
    currency.sym,
    formatC(value, 
            format = "f", 
            big.mark = sep, 
            digits=digits, 
            decimal.mark=decimal),
    sep=""
  )
}

#Team Data
get.teamstructure <- function() {
  return(read_excel(fname.people, 
                    sheet = "TeamStructure")
  )
}

get.teamskill <- function() {
  return(read_excel(fname.people, 
                    sheet = "TeamSkill")
  )
}

get.people <- function() {
  return(read_excel(fname.people
                   , sheet = "People")
  )
}

get.peopleskill <- function() {
  return(read_excel(fname.people  
                   , sheet = "PeopleSkill"))
}

calc_duration <- function(dur) {
	ss <- str_split(dur ,':')[[1]]
	h <- as.numeric(ss[1])*60
	m <- as.numeric(ss[2])
	s <- as.numeric(ss[3])/60
	return(h+m+s)
}

get.training <- function() {
	data <- read_excel(file.path(data_dir, training_file)
					   , sheet="training") |>
		mutate(Episode = as.numeric(Episode)) |>
		rowwise() |>
		mutate(Duration = round(calc_duration(Duration),1) )  
  return(data)
}

print_gt_table <- function(gt_table) {
	temp_png <- tempfile(fileext=".png", tmpdir="_work")
	gtsave(gt_table, filename=temp_png)
	out_str <- case_when(
		knitr::is_latex_output() 
		~ sprintf("\\includegraphics {%s}", temp_png) , 
		knitr::is_html_output() 
		~ sprintf("![](%s)", temp_png),
		knitr::pandoc_to("docx") ~  "word is unsupported for dynamic tables",
		TRUE ~ "unsupported output type for table"
	)	
	return(out_str)
}
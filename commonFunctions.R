## A library of common functions used within this collection of Rmds.

#' This function takes a list of asset tags and the inventory  returns a formatted kable table of the results. 
#' It will force a stop if there is a mismatch.
#' The inventory must have certain columns of data within it.
#' 
#' @param items a list of asset tags which will be used to select items from the inventory
#' @param inventory A data frame containing the full list of items. It is expected to be the result of get.inventory()
#' @return returns formatted html of the selected items.
#' 
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
  
  merged %>% 
    select(AssetTag, Manufacturer, Model, Location, Desc ) %>%
    arrange( AssetTag ) %>%
    kable(align="l") %>%
    column_spec( 1,  bold = TRUE ) %>%
    kable_styling("striped", full_width = TRUE)
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
  	gt()
  
  return( formatted )
 
}

# Functions to get data used by most of the reports.

#globals
#tODO - use of globals, work.inventory and work.network is subject to bugs.

path <- file.path("~", "Documents", "UACTech", "SystemDocumentation")
fname.cf <- file.path(path, "TechInventory.xlsx" )
fname.people <- file.path(path, "db-people.xlsx" )

work.network <- read_excel(fname.cf, 
                           sheet = "Network")

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

work.inventory <- read_excel(fname.cf, 
                             sheet = "TechInventory", col_types=ct) 


get.network <- function() {
  return(work.network)
}

#' retrieves the inventory database
#' @return a data frame containing the inventory database
get.inventory <- function() {
  return( work.inventory )
}

#' retrieves the dmx details
#' @return a data frame containing the dmx details
get.dmxdetails <- function() {
  return( read_excel(fname.cf, 
                            sheet = "DMX.Details" ))
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
  return(read_excel(fname.people, 
                    sheet = "People")
  )
}

get.peopleskill <- function() {
  return(read_excel(fname.people, 
                    sheet = "PeopleSkill")
  )
}

get.training <- function() {
  path <- file.path("~", "Documents", "UACTech" )
  
  fname <- file.path(path, "RightNowMediaTraining.xlsx" )
  return(read_excel(fname, sheet="training"))
}
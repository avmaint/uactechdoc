## A library of common functions used within this collection of Rmds.

# This function takes a list of asset tags and the inventory  returns a formatted kable table of the results. 
# It will force a stop if there is a mismatch.
# The inventory must have certain columns of data within it.
print_inv <- function(items, inventory) {
  
  selected <- items %>% 
    data.frame(AssetTag=.)
  
  merged <- merge( inventory, selected) 
  
  stopifnot(length(items) == nrow(merged) )
  
  merged %>% 
    select(AssetTag, Manufacturer, Model, Location, Desc ) %>%
    arrange( AssetTag ) %>%
    kable(align="l") %>%
    column_spec( 1,  bold = TRUE ) %>%
    kable_styling("striped", full_width = TRUE)
}

#Function to retrieve and format the git commit history for a file. 
#Meant to tack on to the end of the each document.
#takes a file name, returns html formatted table
#filename meant to be provided 
#intended usage: commit.log.html( knitr::current_input() )

commit.log.html <- function(file.name) {
  
  cmd <- "git"
  opt <- 'log --date=local --pretty=format:"%h,%an,%ad,%s" --'
  
  args <- paste( opt, file.name)
  
  o <- system2(cmd, args=args, stdout=TRUE)
  
  df <- read.csv(text=o, col.names=c("id", "user", "date", "message"), header=FALSE)
  
  return( df %>% 
            select(user, date, message) %>%
            kable(align="l", caption="git Commit Log") %>%
            column_spec( 1,  bold = TRUE ) %>%
            kable_styling("striped", full_width = TRUE)
  )
}

# Functions to get data used by most of the reports.

#globals
path <-"~/Documents/UACTech/SystemDocumentation"
inventoryfile <- "TechInventory.xlsx"
fname <- paste(path, inventoryfile, sep="/")

get.network <- function() {
  return(read_excel(fname, 
                    sheet = "Network")
  )
}

get.inventory <- function() {
  ct <- c(  "text"  , "text" ,  "numeric" , "text", "text" , "text"   , 
            "text", "text" , "text"   ,
            "text" , "text", "text", "text", "date", "text",    
            "text","numeric","text","numeric","numeric","numeric"     
  )
  
  return( read_excel(fname, 
                               sheet = "TechInventory", col_types=ct) 
  )
}

get.further <- function() {
  return( read_excel(fname, sheet = "Further")
          )
}

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

get.activities <- function() {
  f <- paste0(path, "/data/", "SystemOperationsGuide.xlsx")
  ct <- c("numeric" ,"numeric", "text", "numeric","text", "text","text", "text", "text", "text"  )
  
  activities <- read_excel(f, 
                   sheet = "linear",
                   col_types=ct)  %>% 
        rowwise() %>%
        mutate(Time = num2time(Time1) )
  
  return(activities)
}

get.events <- function() {
  events <- get.activities() %>%
    select(Time1, Time, Event ) %>%
    unique()
  return(events)
} 
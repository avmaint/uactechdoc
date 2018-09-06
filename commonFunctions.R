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
  
  df <- read.csv(text=o, col.names=c("id", "user", "date", "message"))
  
  return( df %>% 
            select(user, date, message) %>%
            kable(align="l", caption="git Commit Log") %>%
            column_spec( 1,  bold = TRUE ) %>%
            kable_styling("striped", full_width = TRUE)
  )
}
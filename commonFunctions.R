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
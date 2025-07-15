################################################################################
#                               Convert JSON to DOC                            #
#                                                                              #
# Author:  Christopher Schwarz                                                 #
# Date:    07/15/2025                                                          #
# Purpose: Take article .json summaries and save as DOCX format.               #
################################################################################

directory_path = "/Users/christopherschwarz/Dropbox/Side_Quests/Nagler_Articles_2025_07_15"

################################################################################
#                                Load Packages                                 #
################################################################################

library(officer)
library(jsonlite)
library(dplyr)
library(stringr)
library(crosstable)

################################################################################
#                               Conversion Function                            #
################################################################################

files <- list.files(directory_path, full.names = TRUE)
jsons <- files[grepl(".json",files)]

json_path <- jsons[1]

json_to_doc <- function(json_path){
  
  # Read in json
  json <- fromJSON(json_path)
  
  # Initialize empty doc
  doc <- read_docx()
  
  for (section in names(json)) {
    
    # Add Section Title
    section_title <- gsub("_", " ", section)
    section_title <- str_to_title(section_title)
    
    doc <- body_add_par(doc, section_title, style = "heading 1")
    
    section_content <- json[[section]]
    
    if (is.character(section_content) && length(section_content) > 1) {
      
      # If the section is a character vector of length > 1, treat as list
      #doc <- body_add_list(doc, section_content, ordered = FALSE)
      
      for(item in section_content){
        
        doc <- body_add_par(doc, item, style = "Normal") %>% 
          body_add_par("", style = "Normal")
        
      }

    } else {
      
      # Otherwise treat as regular paragraph
      doc <- body_add_par(doc, section_content, style = "Normal")
      
    }
  }
  
  # Output path and save
  output_path <- paste0(tools::file_path_sans_ext(json_path), ".docx")
  print(doc, target = output_path)
  return(output_path)
  
}

json_to_doc(json_path)





################################################################################
#                               Convert JSON to DOC                            #
#                                                                              #
# Author:  Christopher Schwarz                                                 #
# Date:    07/15/2025                                                          #
# Purpose: Take article .json summaries and save as DOCX format.               #
################################################################################

# Directory path to read from
directory_path = "/Users/christopherschwarz/Dropbox/Side_Quests/Nagler_Articles_2025_07_17"

# Extension to be rendered to a doc, likely either .json or _enriched.json
file_stub = "_enriched.json"


# More advanced usage; subsetting, combining, light formatting; no touchy
contents <- c("abstract",
              "research_questions",
              "hypotheses",
              "data",
              "methods",
              "findings")

################################################################################
#                                Load Packages                                 #
################################################################################

library(officer)
library(jsonlite)
library(dplyr)
library(stringr)

################################################################################
#                    Helper to Collapse Fields to single string                #
################################################################################

collapse_fields <- function(json, elements){
  
  for(element in elements){
    
    json[[element]] <- paste(json[[element]], collapse = ", ")
    
  }
  
  json
  
}

################################################################################
#                        Helper to make a Pseudo-citation                      #
################################################################################

make_citation <- function(json){
  
  authors <- collapse_fields(json, "authors")
  
  json$citation <- paste(authors$authors,
                        json$publication_date,
                        json$title,
                        json$journal,
                        json$doi,
                        sep = "; ")
  
  json
  
}

################################################################################
#                               Conversion Function                            #
################################################################################

json_to_doc <- function(json_path, subset = NULL, to_combine = NULL, make_citation = TRUE){
  
  # Read in json
  json <- fromJSON(json_path)
  
  # Combine declared fields
  if(!is.null(to_combine)){
    
    for(i in to_combine){
      
      json <- collapse_fields(json, i)
      
    }
    
  }
  
  # Make citation?
  if(make_citation){
    
    subset <- c("citation",subset)
    json <- make_citation(json)
    
  }

  # Subset
  if(!is.null(subset)){
    
    json <- json[subset]
    
  }
  
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


################################################################################
#                                        Run                                   #
################################################################################

articles <- list.files(directory_path, full.names = TRUE)
articles <- articles[grepl(file_stub,articles)]

for(article in articles){
  
  json_to_doc(article,
              subset = contents,
              to_combine = collapse_list)
  
}


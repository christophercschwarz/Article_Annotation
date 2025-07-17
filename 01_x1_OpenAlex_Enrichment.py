################################################################################
#                        Summary Enrichment with OpenAlex                      #
#                                                                              #
# Author:  Christopher Schwarz                                                 #
# Date:    07/16/2025                                                          #
# Purpose: Enrich article summaries using the OpenAlex API, specifically       #
#            by extracting the article abstract, authors, and DOI.             #
################################################################################

# Input: Directory of jsons to be enriched (i.e. article1.json, article2.json)
# Output: .jsons enriched with OpenAlex in the same directory (i.e. article1.json)

directory_path = "/Users/christopherschwarz/Dropbox/Side_Quests/Nagler_Articles_2025_07_16"

################################################################################
#                               Required Packages                              #
################################################################################

import requests
import pandas as pd
import os
import json

################################################################################
#                 Helper to safely navigate nested dictionaries                #
################################################################################

def safe_get(d, path):
    for key in path:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d

################################################################################
#                 Helper to List Files in Directory by Extention               #
################################################################################

def list_files_in_directory(directory_path, extension = ".pdf"):
    try:
        files = os.listdir(directory_path)
        return [directory_path+"/"+f for f in files 
                if os.path.isfile(os.path.join(directory_path, f)) and f.lower().endswith(extension)]
    except FileNotFoundError:
        return []

################################################################################
#                                 Query OpenAlex                               #
################################################################################

def fetch_openalex_paginated(n_max=1000, search_query=None, filter_query=None, sort_by="relevance_score:desc"):
    url = "https://api.openalex.org/works"
    per_page = 200
    cursor = "*"
    all_records = []

    while len(all_records) < n_max:
        params = {
            "per-page": per_page,
            "cursor": cursor,
            "sort": sort_by
        }

        if search_query:
            params["search"] = search_query
        if filter_query:
            params["filter"] = filter_query

        response = requests.get(url, params=params)
        data = response.json()

        results = data.get("results", [])
        cursor = data.get("meta", {}).get("next_cursor")

        for r in results:
            all_records.append({
                "title": r.get("display_name"),
                 "abstract": " ".join(
                    sorted(r.get("abstract_inverted_index", {}), key=lambda k: r["abstract_inverted_index"][k][0])
                ) if r.get("abstract_inverted_index") else None,
                "landing_page_url": safe_get(r, ["primary_location", "landing_page_url"]),
                "is_oa": safe_get(r, ["primary_location", "source","is_oa"]),
                "doi": r.get("doi"),
                "cited_by_count": r.get("cited_by_count"),
                "referenced_works_count": r.get("referenced_works_count"),
                "publication_date": r.get("publication_date"),
                "type": r.get("type"),
                "journal": safe_get(r, ["primary_location", "source", "display_name"]),
                "oa_url": safe_get(r, ["open_access", "oa_url"]),
                "pdf_url": safe_get(r, ["primary_location", "pdf_url"]),
                "concepts": [c["display_name"] for c in r.get("concepts", [])],
                "authors": [a["author"]["display_name"] for a in r.get("authorships", [])],
                "openalex_id": r.get("id")
            })

        if not cursor or not results:
            break

    return pd.DataFrame(all_records[:n_max])


# test = fetch_openalex_paginated(n_max = 1, search_query = "Polarization and public health: Partisan differences in social distancing during the coronavirus pandemic")
# View(test)

################################################################################
#                                       Run                                    #
################################################################################

jsons = list_files_in_directory(directory_path, ".json")

for json_path in jsons:
  try:
    
    # Read in json
    with open(json_path, "r", encoding = "utf-8") as f:
      data = json.load(f)
      
    # Search OpenAlex for the title
    openalex = fetch_openalex_paginated(n_max=1, search_query=data['title'])
    row_dict = openalex.iloc[0].to_dict()
    data.update(row_dict)
    
    json_path_out = os.path.splitext(json_path)[0] + "_enriched.json"
    
    # Save back to file
    if not openalex.empty:
      data.update(openalex.iloc[0].to_dict())
      with open(json_path_out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
  except Exception as e:
    print(f"Error processing {json_path}: {e}")

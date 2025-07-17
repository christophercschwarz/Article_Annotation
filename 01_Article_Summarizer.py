################################################################################
#                         Article Summarization Pipeline                       #
#                                                                              #
# Author:  Christopher Schwarz                                                 #
# Date:    07/15/2025                                                          #
# Purpose: For a given scientific PDF, do structured extraction of             #
#             1) Research Question                                             #
#             2) Hypotheses                                                    #
#             3) Data and Training Data                                        #
#             4) Methods/Model/Controls                                        #
#             5) Findings                                                      #
#          Note: this requires a recent install of Ollama as well as Qwen3     #
#          Note: updated to encourage list-style hypotheses                    #
# 07/16/2025: Updated to include title extraction, minor cleaning/corrections  #
################################################################################

# Input: Directory of pdfs to be summarized (i.e. article1.pdf, article2.pdf)
# Output: .json summaries of the pdfs in the same directory (i.e. article1.json)

directory_path = "/Users/christopherschwarz/Dropbox/Side_Quests/Nagler_Articles_2025_07_17"

################################################################################
#                               Required Packages                              #
################################################################################

import pdfplumber
import requests
import time
import contextlib
import io
import re
import os
import json
from collections import defaultdict

################################################################################
#                        Helper Function for Querying Ollama                   #
################################################################################

def query_ollama(prompt, model="openhermes", max_tokens=1024, retries=3):
    for attempt in range(retries):
        try:
            response = requests.post("http://localhost:11434/api/generate", json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": 12288,
                    "num_predict": max_tokens,
                    "temperature": 0.0
                }
            })
            response.raise_for_status()
            return response.json()["response"].strip()
        except Exception as e:
            if attempt == retries - 1:
                return f"[ERROR] {str(e)}"
            time.sleep(1)

################################################################################
#                   Function for Extracting Text from a Saved PDF              #
################################################################################

def extract_pdf_text_clean(pdf_path):
    import pdfplumber, io, contextlib
    with contextlib.redirect_stderr(io.StringIO()):
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(
                page.extract_text(x_tolerance=1, y_tolerance=1)
                for page in pdf.pages if page.extract_text()
            )

################################################################################
#                              Clean the PDF Text                              #
################################################################################

def clean_pdf_text(text):
    """
    Generic PDF text cleaner for academic articles.

    Handles:
    - Hyphenated line breaks
    - Mid-sentence line breaks
    - Header/footer removal (without relying on journal names)
    - Duplicate lines
    - Page numbers and URLs
    - Normalized whitespace
    """
    # 1. Dehyphenate wrapped words (e.g., 'Face-\nbook' → 'Facebook')
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # 2. Merge lines broken mid-sentence (leave double newlines untouched)
    text = re.sub(r'(?<!\n)\n(?![\nA-Z])', ' ', text)

    # 3. Remove bare page numbers and repeated headers/footers
    text = re.sub(r'^\s*\d{1,4}\s*$', '', text, flags=re.MULTILINE)  # standalone numbers
    text = re.sub(r'Page\s*\d+', '', text, flags=re.IGNORECASE)      # "Page 5"
    text = re.sub(r'\|\s*www\.\S+\s*\|?', '', text)                  # web domain footers
    text = re.sub(r'https?://\S+', '', text)                         # inline URLs

    # 4. Deduplicate short repeated lines (common in headers/footers)
    lines = text.split('\n')
    seen = set()
    deduped = []
    for line in lines:
        l = line.strip()
        if l and l.lower() not in seen:
            deduped.append(line)
            seen.add(l.lower())
    text = '\n'.join(deduped)

    # 5. Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)            # collapse horizontal space
    text = re.sub(r'\n[ \t]+', '\n', text)         # strip leading space
    text = re.sub(r'[ \t]+\n', '\n', text)         # strip trailing space
    text = re.sub(r'\n{3,}', '\n\n', text)         # max 2 line breaks
    text = re.sub(r'[ \t]{2,}', ' ', text)         # multiple spaces -> single

    return text.strip()

################################################################################
#                                 Remove References                            #
################################################################################

def strip_citations_and_references(text):
    """
    Cleans academic article text to reduce hallucination triggers from citations.
    - Removes inline parenthetical citations like (Smith 2020), (Smith & Doe, 2021)
    - Removes numeric citations like [12], [1, 3, 5]
    - Removes the References section entirely
    """
    # Remove parenthetical citations
    text = re.sub(r'\(([^)]*\d{4}[^)]*)\)', '', text)

    # Remove numeric citations like [12] or [4,5]
    text = re.sub(r'\[\d+(,\s*\d+)*\]', '', text)

    # Remove everything after a References heading
    text = re.split(r'\n\s*(References|Bibliography|Works Cited)\s*\n', text, flags=re.IGNORECASE)[0]

    return text.strip()

################################################################################
#                              Main Article Summarizer                         #
################################################################################

def summarize_structured(text, model="qwen3:0.6b", max_tokens=32768):
    """
    Processes a full academic article using a long-context model (e.g., Qwen3).
    Returns a structured JSON summary of key research elements.
    """
    json_prompt_template = (
        "You are a research assistant. From the following academic article, extract a structured summary covering these fields.\n"
        "- doi: The DOI of the article, if listed.\n"
        "- title: The title of the academic article.\n"
        "- authors: The authors of the article.\n"
        "- abstract: The article abstract, almost always the first paragraph of the paper.\n"
        "- research_questions: What research questions are the authors addressing?\n"
        "- hypotheses: What hypotheses do they formally propose?\n"
        "- data: Describe the data used in the analysis (years, geography, unit of analysis, dataset size, sources).\n"
        "- methods: Describe the statistical methods used and design decisions such as control variables.\n"
        "- findings: What did the authors find? What resuslts do they discuss?\n\n"
        "When writing each field, ensure:\n"
        "- doi is the exact doi of the article.\n"
        "- title is the exact title of the article.\n"
        "- abstract is the exact abstract of the artice.\n"
        "- authors include only names, concatenated into a single string.\n"
        "- research_questions contains exact or paraphrased questions from the introduction or abstract.\n"
        "- hypotheses only includes explicit predictions or testable claims declared as hypotheses to be tested. If none are stated, return an empty string.\n"
        "- data lists year(s), platform, dataset size, unit of analysis, and source, if stated.\n"
        "- methods describes actual models and metrics used (e.g., linear regression, GAMLSS, support vector machines, diffusion trees, structural virality, depth).\n"
        "- findings are only drawn from the Results or Discussion. Do not invent findings.\n\n"
        "Each field should be written as a detailed, multi-sentence paragraph (at least 3-4 sentences), using the exact terminology and evidence provided in the text.\n"
        "If there are multiple hypotheses, create a nested entry for each."
        "Be specific and include details such as time ranges, sample sizes, platforms, modeling techniques, and units of analysis.\n"
        "Use actual outcomes, patterns, or numerical/statistical results; mirror the exact language used in the article.\n"
        "If the article includes more than one hypothesis, data source, method, result, finding, or question, include each as a separate clearly delimited sentence or clause, rather than combining them into one vague statement.\n\n"
        "DO NOT infer or fabricate information — only include what the article states.\n"
        "DO NOT include commentary, preambles, reasoning, or planning steps.\n"
        "DO NOT return any text before or after the JSON. Return only the JSON.\n\n"
        "As a checklist, ensure:\n"
        "- Names entities are named explicitly (e.g., Facebook, not 'social media').\n"
        "- The dataset size, time range, and source are included.\n"
        "- The method includes named statistical metrics (e.g., linear regression, logistic regression, structural virality, depth).\n"
        "- Each answer is comprehensive and uses MULTIPLE SENTENCES in its answer.\n"
        "- No findings are invented — all numbers must come from the article and use its language. Do NOT use outside knowledge or general assumptions; only use what is specifically stated or measured in the article.\n\n"
        "=== ARTICLE TO PROCESS ===\n{text}\n=== END ARTICLE ===\n\n"
        "DO NOT include any content from the example below in your final answer. It is only provided to show formatting style.\n"
        "Return ONLY a valid JSON object like the example below. Do NOT include any prose, commentary, or explanation before or after it.\n\n"
        "=== Example (for structure only, not content!) ===\n\n"
        "{\"doi\": \"...\","
        "  \"title\": \"...\","
        "  \"authors\": \"...\","
        "  \"abstract\": \"...\","
        "  \"research_questions\": \"...\","
        "  \"hypotheses\": [\"hypothesis 1\", \"hypothesis 2\", \"...\"],"
        "  \"data\": \"...\","
        "  \"methods\": \"...\","
        "  \"findings\": \"...\"}\n\n"
        "=== End of Example ===\n\n"
    )

    prompt = json_prompt_template.replace("{text}", text)
    raw_response = query_ollama(prompt, model=model, max_tokens=max_tokens)

    return raw_response


################################################################################
#               Helper Function to Strip "thoughs" from LLM Output             #
################################################################################

def strip_thoughts(text):
    """
    Removes <think>...</think> style reasoning artifacts from LLM output.
    Supports multiple blocks.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
  

################################################################################
#               Helper Function to clean into JSON without thoughts            #
################################################################################
  
def clean_json(raw_text):
    """
    Cleans up a raw LLM stringified JSON object and returns a valid Python dict.
    """
    try:
        # Step 1: Strip thinking tags if present
        raw_text = strip_thoughts(str(raw_text))

        # Step 2: Normalize line breaks and whitespace
        raw_text = raw_text.replace('\\n', '\n').strip()

        # Step 3: Find JSON block inside text if wrapped in extra content
        json_start = raw_text.find("{")
        json_end = raw_text.rfind("}") + 1
        json_str = raw_text[json_start:json_end]

        # Step 4: Load as JSON
        parsed = json.loads(json_str)
        return parsed

    except Exception as e:
        print(f"[ERROR] Failed to parse JSON: {e}")
        return {}

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
#                                       Run                                    #
################################################################################

pdfs = list_files_in_directory(directory_path)

results = []

for pdf in pdfs:
  try:
    pdf_text = extract_pdf_text_clean(pdf)
    clean_text = strip_citations_and_references(pdf_text)
    raw_responses = summarize_structured(clean_text[0:30000], model = "qwen3:8b")
    
    # Save full results in memory
    results.append(raw_responses)
    
    # Save cleaned json
    cleaned = clean_json(raw_responses)
    json_path = os.path.splitext(pdf)[0] + ".json"
    with open(json_path, "w", encoding = "utf-8") as f:
      json.dump(cleaned, f, indent = 2, ensure_ascii=False)
    
  except Exception as e:
    print(f"Error processing {pdf}: {e}")


# # Single shot
# pdf_text = extract_pdf_text_clean("/Users/christopherschwarz/Dropbox/Side_Quests/Nagler_Articles_2025_07_16/Clinton_etal_2020.pdf")
# 
# # Remove references
# clean_text = strip_citations_and_references(pdf_text)
# 
# # Run model
# start_time = time.time()
# raw_responses = summarize_structured(clean_text[0:30000], model = "qwen3:8b")
# end_time = time.time()
# elapsed = end_time - start_time
# 
# # Assess
# print(f"Model response time: {elapsed:.2f} seconds")
# raw_responses
# print(json.dumps(clean_json(raw_responses),indent = 2))

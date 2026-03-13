import time
from typing import Optional, Any
from google import genai
from google.genai import types

from src.config import (
    GEMINI_API_KEY, MODEL_NAME, 
    MAX_RETRIES, RETRY_DELAY_SECONDS,
    PaperMetadata
)

# Initialize GenAI client
client = genai.Client(api_key=GEMINI_API_KEY)

def extract_metadata_from_paper(paper_text: str, document_id: str, volume: str, issue: str) -> Optional[PaperMetadata]:
    """
    Extracts structured JSON metadata directly matching PaperMetadata schema from paper text.
    """
    prompt = f"""
    You are an academic paper analyst. 
    Analyze the following paper text and extract the required fields exactly matching the JSON schema.
    If specific methodology details or sampling are not mentioned, put '미상/명시 없음'.
    Document ID: {document_id}
    Volume: {volume}
    Issue: {issue}
    
    Paper Text:
    {paper_text}
    """
    
    for attempt in range(MAX_RETRIES):
        try:
            print(f"Extracting JSON via Gemini... (Attempt {attempt+1}/{MAX_RETRIES}) for {document_id}")
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=PaperMetadata,
                    temperature=0.1
                )
            )
            
            # The prompt is set up to return JSON implicitly structured as PaperMetadata
            # Since we provide response_schema, the output text is guaranteed to be a valid JSON string 
            # adhering to PaperMetadata.
            return PaperMetadata.model_validate_json(response.text)
            
        except Exception as e:
            print(f"Extraction error on attempt {attempt+1}: {e}")
            time.sleep(RETRY_DELAY_SECONDS)
            
    print(f"Failed to extract metadata for {document_id} after {MAX_RETRIES} attempts.")
    return None

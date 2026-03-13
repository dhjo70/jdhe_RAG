import fitz  # PyMuPDF
import re

def clean_metadata_title(title: str) -> str:
    """Clean redundant tags or blank spaces from PDF metadata title."""
    if not title:
        return ""
    title = re.sub(r'<\?[^>]+\?>', '', title)
    title = re.sub(r'<[^>]+>', '', title)
    title = title.replace('\n', ' ').replace('\r', '')
    title = re.sub(r'\s+', ' ', title).strip()
    return title



def extract_text_from_pdf_file(pdf_path: str) -> str:
    """Extract all text from a local PDF file using PyMuPDF."""
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        print(f"Error extracting text from PDF file ({pdf_path}): {e}")
    return text

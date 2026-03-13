import os
import sys
import argparse
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pdf_utils import extract_text_from_pdf_file
from src.llm_client import extract_metadata_from_paper
from src.database import insert_paper_metadata, insert_paper_vectors

load_dotenv()

def ingest_volume(target_volume: str):
    base_dir = "papers"
    
    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} not found. Please run the download script first.")
        return
        
    vol_path = os.path.join(base_dir, target_volume)
    if not os.path.isdir(vol_path):
        print(f"Volume directory not found: {vol_path}")
        available_vols = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        print(f"Available volumes: {', '.join(sorted(available_vols))}")
        return
        
    print(f"🚀 Starting ingestion for volume: {target_volume}")
    
    success_count = 0
    fail_count = 0

    for issue_name in sorted(os.listdir(vol_path)):
        issue_path = os.path.join(vol_path, issue_name)
        if not os.path.isdir(issue_path): continue
        
        for pdf_name in sorted(os.listdir(issue_path)):
            if not pdf_name.endswith('.pdf'): continue
            
            document_id = pdf_name.replace(".pdf", "").strip()
            pdf_path = os.path.join(issue_path, pdf_name)
            
            print(f"\nProcessing {document_id} from {target_volume} / {issue_name} ...")
            
            try:
                paper_text = extract_text_from_pdf_file(pdf_path)
                if not paper_text.strip():
                    print("⚠️ PDF is empty or unreadable text. Skipping.")
                    fail_count += 1
                    continue
                    
                metadata = extract_metadata_from_paper(paper_text, document_id, target_volume, issue_name)
                
                if metadata:
                    insert_paper_metadata(metadata)
                    insert_paper_vectors(document_id, paper_text)
                    print(f"✅ Ingested {document_id} successfully.")
                    success_count += 1
                else:
                    print(f"❌ Failed to extract metadata for {document_id} (Returned None)")
                    fail_count += 1
                    
            except Exception as e:
                print(f"❌ Error processing {document_id}: {e}")
                fail_count += 1
                
    print(f"\n🎉 Ingestion completed for {target_volume}.")
    print(f"   Success: {success_count}")
    print(f"   Failed : {fail_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a specific volume of JDHE papers into SQLite and ChromaDB.")
    parser.add_argument("volume", type=str, help="The exact volume folder name to ingest (e.g., 'Vol13')")
    
    args = CLI_ARGS = parser.parse_args()
    
    ingest_volume(args.volume)

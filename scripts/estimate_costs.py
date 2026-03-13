import os
import sqlite3
import fitz
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Gemini 1.5 Pro or 2.5 Pro Pay-as-you-go pricing (per 1M tokens)
INPUT_PRICE_PER_M = 1.25
OUTPUT_PRICE_PER_M = 5.00

def get_existing_ids():
    try:
        conn = sqlite3.connect('data/metadata.db')
        cursor = conn.cursor()
        cursor.execute("SELECT document_id FROM paper_metadata")
        existing_ids = set(row[0] for row in cursor.fetchall())
        conn.close()
        return existing_ids
    except Exception:
        return set()

def count_tokens(text):
    # Rough estimation: 1 token ≈ 4 characters for English text
    return len(text) // 4

def main():
    existing_ids = get_existing_ids()
    print(f"이미 DB에 적재된 논문 수: {len(existing_ids)}편")
    
    papers_dir = "papers"
    total_new_papers = 0
    total_new_tokens = 0
    
    for root, dirs, files in os.walk(papers_dir):
        for file in files:
            if file.endswith('.pdf'):
                document_id = file.replace('.pdf', '')
                
                # 중복 다운로드(이미 DB에 있는 것) 스킵
                if document_id in existing_ids:
                    continue
                    
                pdf_path = os.path.join(root, file)
                total_new_papers += 1
                
                try:
                    text = ""
                    with fitz.open(pdf_path) as doc:
                        for page in doc:
                            text += page.get_text()
                    
                    tokens = count_tokens(text)
                    total_new_tokens += tokens
                except Exception as e:
                    print(f"Error reading {file}: {e}")
                    
    print(f"\n새로 적재해야 할 논문 수: {total_new_papers}편")
    print(f"예상되는 총 입력 토큰 수 (원문 텍스트): 약 {total_new_tokens:,} Tokens")
    
    # 1. 메타데이터 추출 (JSON) 비용
    # Prompt Tokens = 논문 원문 길이
    # Output Tokens = 평균 250 토큰 (JSON 길이)
    total_output_tokens = total_new_papers * 250
    
    input_cost_usd = (total_new_tokens / 1_000_000) * INPUT_PRICE_PER_M
    output_cost_usd = (total_output_tokens / 1_000_000) * OUTPUT_PRICE_PER_M
    
    total_cost_usd = input_cost_usd + output_cost_usd
    total_cost_krw = total_cost_usd * 1450 # 환율 대략 1450원 적용
    
    print("\n[Gemini 2.5 Pro (Pay-as-you-go) API 예상 비용]")
    print(f"- Input 토큰 비용: ${input_cost_usd:.4f}")
    print(f"- Output 토큰 비용: ${output_cost_usd:.4f}")
    print(f"- 총 예상 비용 (USD): ${total_cost_usd:.4f}")
    print(f"- 총 예상 비용 (KRW): 약 ₩{int(total_cost_krw):,}")
    print("\n*참고: 모델 버전에 따라 가격 정책이 다를 수 있으며, 위 계산은 입력 1.25$/1M, 출력 5.0$/1M 기준입니다.")

if __name__ == "__main__":
    main()

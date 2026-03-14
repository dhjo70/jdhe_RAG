from src.query_router import process_query_stream

query = "질적 연구를 사용한 2021년도 논문 중에 '학업 성취도'를 다룬 연구들을 찾아줘"
print("Testing Hybrid Pipeline...")
for chunk in process_query_stream(query, conversation_id=999):
    print(chunk, end="")
print("\nDone.")

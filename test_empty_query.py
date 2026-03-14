from src.query_router import process_query_stream

query = "전체 논문을 나열해줘"
print("Testing Generic Query Pipeline...")
for chunk in process_query_stream(query, conversation_id=999, search_mode="meta_analysis"):
    print(chunk, end="")
print("\nDone.")

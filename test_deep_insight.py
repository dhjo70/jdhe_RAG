from src.query_router import process_query_stream
import sys

query = "다양성 교육과 관련된 논문들의 핵심 결론을 요약해줘"
print(f"Testing Deep Insight Query: {query}")
try:
    for chunk in process_query_stream(query, conversation_id=999, search_mode="deep_insight"):
        sys.stdout.write(chunk)
        sys.stdout.flush()
    print("\nDONE.")
except Exception as e:
    print(f"\nFAILED: {e}")

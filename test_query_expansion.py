from src.query_router import analyze_query
import json

query = "소수인종이면서 성적소수자인 논문을 찾아줘"
print(f"Testing Query: {query}")
params = analyze_query(query)
print(json.dumps(params.model_dump(), indent=2, ensure_ascii=False))

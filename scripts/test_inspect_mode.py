import json

import requests

# Inspect 모드 테스트
payload = {
    "mode": "inspect",
    "query": "2023년 총 매출액은 얼마인가요?",
    "answer": "**총 매출액은 약 150억원입니다**",
    "query_type": "target_short",
    "use_lats": True,
    "inspector_comment": "LATS 및 Validator 테스트",
}

try:
    response = requests.post(
        "http://localhost:8000/api/workspace", json=payload, timeout=30
    )

    print("=" * 60)
    print("Inspect Mode 테스트 결과")
    print("=" * 60)
    print(f"Status Code: {response.status_code}")
    print("\nResponse:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

except requests.exceptions.ConnectionError:
    print("ERROR: 서버가 실행되지 않았습니다.")
    print("먼저 'uv run uvicorn src.web.api:app --reload' 실행하세요.")
except Exception as e:
    print(f"ERROR: {e}")

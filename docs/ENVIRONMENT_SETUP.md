# QA 시스템 환경 설정 가이드

QA 그래프 시스템 실행을 위해 다음 환경 변수를 `.env` 파일에 설정해야 합니다.

## 필수 환경 변수

### 1. Neo4j 데이터베이스 (QA 지식 그래프)

```bash
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

**Neo4j Aura 무료 인스턴스 생성:**

1. <https://neo4j.com/cloud/aura-free/> 접속
2. "Start Free" 클릭
3. 인스턴스 생성 후 연결 정보 복사
4. **중요**: 비밀번호는 재확인 불가하므로 안전하게 저장

### 2. Notion API (규칙 추출용)

```bash
NOTION_API_KEY=secret_xxxxx
NOTION_PAGE_IDS=page_id_1,page_id_2
```

**Notion Integration 생성:**

1. <https://www.notion.so/my-integrations> 접속
2. "New integration" 클릭
3. API 키 복사
4. 대상 페이지에서 "Connections" → Integration 연결

## 선택적 환경 변수

### Gemini (임베딩/워크플로우용)

```bash
GEMINI_API_KEY=AIzaxxxxx
```

## 빠른 시작

```bash
# 1. .env.example을 .env로 복사
cp .env.example .env

# 2. .env 파일 편집하여 실제 값 입력
# (VS Code, notepad 등 사용)

# 3. 환경 변수 확인
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('NEO4J_URI:', os.getenv('NEO4J_URI'))"

# 4. 그래프 스키마 구축
python graph_schema_builder.py

# 5. QA 시스템 테스트
python qa_rag_system.py
```

## 문제 해결

### "환경 변수 NEO4J_URI가 설정되지 않았습니다"

→ `.env` 파일에 `NEO4J_URI` 추가 필요

### "Neo4j 연결 실패"

→ URI/User/Password 확인, 네트워크 연결 확인

### "GEMINI_API_KEY 미설정: 벡터 검색을 건너뜁니다"

→ 정상 동작 (벡터 검색은 선택 사항)

## 로컬 개발 속도 향상 (개인용)

- 테스트 워치: `uv run pytest-watcher .` (파일 변경 시 자동 재실행), 빠른 재시작 `uv run pytest --lf` / `--ff`
- 병렬 테스트: `uv run pytest -n auto tests/` (실패 우선 실행은 `--ff` 추가)
- 프로파일링: `python scripts/auto_profile.py --module src.main -- --help` (임의 모듈에 `--` 뒤 인자 전달)
- 결과 비교: `python scripts/compare_runs.py --sort-by cost` (최신 `data/outputs/result_*.md` 요약)
- 빠른 백업: `pwsh scripts/backup.ps1` (민감 정보 포함 시 `-SkipEnv` 옵션 사용)

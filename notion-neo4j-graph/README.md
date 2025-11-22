# Notion-Neo4j Graph Pipeline

Notion 페이지의 데이터를 추출하여 Neo4j Aura(Graph Database)에 지식 그래프로 구축하는 프로젝트입니다.

## 🚀 시작하기

### 1. 환경 설정

```bash
# 의존성 설치
uv sync
```

### 2. 환경 변수 설정 (.env)

`.env` 파일을 생성하고 다음 정보를 입력하세요:

```ini
# Notion 설정
NOTION_TOKEN=your_integration_token
NOTION_PAGE_IDS=page_id_1,page_id_2

# Neo4j Aura 설정
NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

### 3. 실행

**데이터 파이프라인 실행 (Notion -> Neo4j):**
```bash
uv run import_pipeline.py
```

**검증:**
```bash
uv run verify_import.py
```

## 📂 프로젝트 구조

- `import_pipeline.py`: 메인 파이프라인 스크립트 (추출 및 임포트)
- `test_*.py`: 연결 테스트 스크립트
- `verify_import.py`: 데이터 검증 스크립트

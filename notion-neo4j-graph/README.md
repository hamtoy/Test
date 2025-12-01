# Notion-Neo4j Graph Pipeline

Notion 페이지의 데이터를 추출하여 Neo4j Aura(Graph Database)에 지식 그래프로 구축하는 프로젝트입니다.

## 🚀 시작하기

### 1. 환경 설정

```bash
# 의존성 설치 (루트에서)
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

```bash
# 데이터 파이프라인 실행
uv run python notion-neo4j-graph/import_pipeline.py

# 검증
uv run python notion-neo4j-graph/verify_import.py
```

## 📂 프로젝트 구조

```
notion-neo4j-graph/
├── import_pipeline.py   # 메인 파이프라인 (Notion → Neo4j)
├── verify_import.py     # 데이터 검증
├── test_notion.py       # Notion 연결 테스트
├── test_neo4j.py        # Neo4j 연결 테스트
└── pyproject.toml       # 의존성 정의
```

## 🔗 메인 프로젝트와의 관계

이 모듈은 `src/graph/builder.py`와 연동되어 QA 시스템의 지식 그래프를 구축합니다.

```bash
# 메인 프로젝트에서 그래프 빌더 실행
python -m src.graph.builder
```

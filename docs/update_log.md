# Update Log

본 문서는 주요 변경 사항 및 업데이트 이력을 추적합니다.

## 2025-11-24 (Performance Optimization & Documentation)

**성능 최적화:**

- **Lazy Import 구현**: `google.generativeai` 및 관련 모듈을 지연 로딩하여 초기화 시간 ~20% 단축 (2.84s → 2.28s)
- **Property-based 지연 임포트**: `_genai`, `_caching`, `_google_exceptions`, `_protos`, `_harm_types` 프로퍼티 추가
- **테스트 커버리지 목표**: 68% → 75% 상향 조정 (`pyproject.toml` 업데이트)

**코드 품질 개선:**

- **주석 정리**: 중복 주석 4개 제거 (`src/agent.py`, `src/main.py`)
- **Python 3.10 호환성**: `datetime.UTC` → `datetime.timezone.utc` 교체
- **린트 수정**: 미사용 임포트 및 변수 정리

**문서화:**

- **원칙 준수 리뷰**: `docs/PRINCIPLES_REVIEW.md` 생성 (YAGNI, KISS, SOLID 등 18개 원칙 분석)
- **주석 리뷰**: `docs/COMMENT_REVIEW.md` 생성 (200+ 주석 품질 분석)
- **환경 설정 가이드**: `docs/ENVIRONMENT_SETUP.md` 업데이트 (Gemini 워크플로우 중심으로 재작성)

**의존성:**

- `pyproject.toml`에 `[dependency-groups]` 추가 (`pre-commit>=4.4.0`)

## 2024-11-23 (QA RAG System & Refactoring)

**주요 변경사항:**

- **구조 개선**: QA RAG 관련 핵심 모듈들을 `src/` 디렉토리로 이동하여 프로젝트 구조 일원화
  - `qa_rag_system.py`, `integrated_quality_system.py`, `gemini_model_client.py` 등
- **안정성 강화**:
  - `gemini_model_client.py`: 답변 개수 부족(0~2개) 시 길이 기반 Fallback 로직 추가로 `IndexError` 방지
  - `qa_rag_system.py`: Neo4j 자격 증명 주입 방식 개선 (생성자 인자 우선, 환경변수 Fallback) 및 타입 안전성 확보
  - `advanced_context_augmentation.py`: `GEMINI_API_KEY` 부재 시 벡터 검색을 건너뛰고 그래프 기반 대체 검색 수행
  - `adaptive_difficulty.py`: 그래프 쿼리 결과(`None`)에 대한 방어 로직 추가
- **의존성 업데이트**: `langchain`, `langchain-neo4j` 등 최신 패키지 적용 및 `types-aiofiles` 추가로 타입 체크 강화
- **문서화**: `README.md`의 프로젝트 구조 및 실행 명령어 경로(`src/`) 최신화

## 2024-11-23 (Validator & Docs)

**추가/변경:**

- `checks/validate_session.py` 추가: 턴 수, 설명/요약 슬롯, 추론 필수 여부, 금지 패턴 검사
- `checks/detect_forbidden_patterns.py` 정제: 영어 table/graph 패턴 제거, 한국어 패턴 집중
- `README.md` 템플릿 렌더/세션 빌드/검증 사용법 추가
- `examples/session_input.json` 보강: text_density 문자열화, calc 카운트/포커스 필드 포함
- `scripts/run_pipeline.py` 추가: 세션 생성→금지 패턴 재렌더→검증 파이프라인 러너
- `scripts/build_session.py` 개선: calc 사용 플래그 전달, focus_history 활용

## 2024-11-22 (Initial Implementation)

**구현 완료:**

1. **템플릿 패밀리**: `templates/{system,user,eval,rewrite,fact}` 9개 템플릿 생성
2. **세션 빌더**: `scripts/build_session.py` - 3~4턴, 설명/요약 선택, 추론 포함
3. **금지 패턴 검출**: `checks/detect_forbidden_patterns.py` - 표/그래프 참조, 용어 정의 등
4. **문서화**: `docs/guide_mapping.md` - 규범-구현 매핑
5. **샘플 데이터**: `examples/sample_image_meta.json`, `examples/session_input.json`

## 2024-11 (29_MultiTurn_Nov)

**Notion 가이드 변경사항:**

- **세션 턴 수 제한**: 3~4턴으로 엄격히 제한
- **부분 설명/요약 금지**: 전체(Full) 설명/요약만 허용
- **4턴 세션 특례**: 길이 차이가 과도하지 않은 경우에 한해 설명+요약 동시 사용 허용

**템플릿 반영:**

- `scripts/build_session.py`: `session_turns` 파라미터 3~4 검증 로직 추가
- `templates/system/text_image_qa_explanation_system.j2`: "전체 본문" 강조
- `templates/system/text_image_qa_summary_system.j2`: "전체 본문" 강조, 부분 요약 금지 명시
- `checks/detect_forbidden_patterns.py`: "전체 이미지" 패턴 검출 추가

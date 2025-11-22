# Update Log

본 문서는 Notion 가이드 업데이트 및 템플릿/검증기 변경 이력을 추적합니다.

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

## 2024-11-22 (Initial Implementation)

**구현 완료:**
1. **템플릿 패밀리**: `templates/{system,user,eval,rewrite,fact}` 9개 템플릿 생성
2. **세션 빌더**: `scripts/build_session.py` - 3~4턴, 설명/요약 선택, 추론 포함
3. **금지 패턴 검출**: `checks/detect_forbidden_patterns.py` - 표/그래프 참조, 용어 정의 등
4. **문서화**: `docs/guide_mapping.md` - 규범-구현 매핑
5. **샘플 데이터**: `examples/sample_image_meta.json`, `examples/session_input.json`

**향후 계획:**
- [x] 세션 빌더와 검증기 통합 (validate_session)
- [x] 엣지케이스 테스트 추가 (session input 샘플 보강 예정)
- [ ] 평가/리라이팅 파이프라인 연결

## 2024-11-23 (Validator & Docs)

**추가/변경:**
- `checks/validate_session.py` 추가: 턴 수, 설명/요약 슬롯, 추론 필수 여부, 금지 패턴 검사
- `checks/detect_forbidden_patterns.py` 정제: 영어 table/graph 패턴 제거, 한국어 패턴 집중
- `README.md` 템플릿 렌더/세션 빌드/검증 사용법 추가
- `examples/session_input.json` 보강: text_density 문자열화, calc 카운트/포커스 필드 포함
- `scripts/run_pipeline.py` 추가: 세션 생성→금지 패턴 재렌더→검증 파이프라인 러너
- `scripts/build_session.py` 개선: calc 사용 플래그 전달, focus_history 활용

**향후 작업:**
- 평가/리라이팅 파이프라인과 validator 연결
- 다양한 메타데이터 케이스 스냅샷 테스트 작성

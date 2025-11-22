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
- [ ] 세션 빌더와 검증기 통합
- [ ] 엣지케이스 테스트 추가
- [ ] 평가/리라이팅 파이프라인 연결

# Repo Housekeeping Plan

목표: 루트 디렉터리의 산출물/도구/데이터를 구분해 가독성과 유지보수성을 높입니다. 코드 경로나 스크립트 참조를 깨지 않도록 순차 적용합니다. (artifacts/, data/neo4j 정리는 완료됨)

## 1) 실행 산출물/로그 분리
- 완료: `artifacts/` 생성 및 `verification_result.txt` 이동
- 남은 이동 대상: `coverage.xml`, `.coverage`, `semantic_analysis.log`
- 후속 작업: CI/스크립트에서 커버리지 경로를 `artifacts/coverage.xml`로 읽도록 확인 후 반영.

## 2) 대용량 CSV/임포트 스크립트 정리
- 완료: `data/neo4j/` 생성 및 CSV/임포트 스크립트/README 이동
- 후속 작업: 임포트 스크립트/문서의 경로를 `data/neo4j/` 기준으로 업데이트 검증.

## 3) 외부 도구/백업 분리
- 새 폴더 제안: `tools/` → `Redis-x64-5.0.14.1` 이동
- 백업: `backup_v3_20251127_225953` → `archive/` 등으로 이동/압축

## 4) 중복/혼동 폴더 점검
- `config/` vs `configs/` 용도 확인 후 하나로 통합.

## 5) .gitignore 보강
- 루트 산출물 경로 변경 후 `artifacts/`, 임시/로그 파일, 로컬 도구 디렉터리(`tools/`) 등을 무시 목록에 추가.

## 적용 순서 제안
1. `artifacts/` 생성 후 커버리지/로그 이동 및 경로 업데이트.
2. `data/neo4j/` 생성 후 CSV/임포트 스크립트 이동 및 문서/스크립트 경로 수정.
3. 도구/백업 폴더 이동 (`tools/`, `archive/`), 필요한 경우 스크립트 경로 업데이트.
4. `config/` vs `configs/` 통합 결정 및 반영.
5. `.gitignore` 갱신 후 CI/스크립트 검증.

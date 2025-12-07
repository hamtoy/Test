# Web API 로깅 가이드

## 개요

웹 API 서버는 이제 파일 기반 로깅을 자동으로 설정합니다. 서버가 시작되면 두 개의 로그 파일이 생성됩니다:

- **`app.log`**: 모든 로그 레벨 (INFO, WARNING, ERROR 등)
- **`error.log`**: ERROR 레벨 이상의 로그만

## 로그 파일 위치

로그 파일은 프로젝트 루트 디렉토리에 생성됩니다:

```
/home/runner/work/Test/Test/
├── app.log
├── error.log
└── ...
```

## 로그 레벨 설정

환경 변수를 통해 로그 레벨을 조정할 수 있습니다:

```bash
# 기본값: INFO
LOG_LEVEL=DEBUG python run_web.py

# 또는 .env 파일에서
LOG_LEVEL=WARNING
```

사용 가능한 로그 레벨:
- `DEBUG`: 디버깅 정보 포함
- `INFO`: 일반 정보 (기본값)
- `WARNING`: 경고 메시지
- `ERROR`: 오류 메시지
- `CRITICAL`: 심각한 오류

## 로그 파일 순환

로그 파일은 자동으로 순환됩니다:
- 최대 파일 크기: 10MB
- 백업 파일 수: 5개
- 파일 형식: `app.log`, `app.log.1`, `app.log.2`, ...

## 구조화된 로깅 (선택사항)

JSON 형식의 구조화된 로깅을 사용하려면:

```bash
ENABLE_STRUCT_LOGGING=true python run_web.py
```

이 경우 파일 기반 로깅 대신 stdout으로 JSON 형식의 로그가 출력됩니다.

## 로그 비활성화

파일 기반 로깅은 기본적으로 활성화되어 있습니다. 비활성화하려면:

```bash
ENABLE_STRUCT_LOGGING=true  # 파일 대신 stdout 사용
```

## 예제 로그 출력

### app.log
```
[2025-12-07 12:38:03] INFO | File-based logging initialized (app.log, error.log)
[2025-12-07 12:38:05] INFO | GeminiAgent 초기화 완료
[2025-12-07 12:38:06] WARNING | Neo4j 연결 실패 (RAG 비활성화)
[2025-12-07 12:38:10] ERROR | Failed to process request
```

### error.log
```
[2025-12-07 12:38:10] ERROR | Failed to process request
```

## 민감 정보 보호

로깅 시스템은 자동으로 민감한 정보(API 키 등)를 마스킹합니다:
- `AIza...` → `[FILTERED_API_KEY]`

## 주의사항

- 로그 파일은 `.gitignore`에 포함되어 있어 Git에 커밋되지 않습니다
- 프로덕션 환경에서는 로그 파일을 정기적으로 백업하고 정리하세요
- 디스크 공간을 모니터링하세요 (로그 파일이 커질 수 있음)

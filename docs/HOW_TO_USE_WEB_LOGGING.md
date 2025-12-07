# 웹 API 로깅 (app.log) 사용 가이드

## 개요

웹 API 서버가 이제 자동으로 파일 기반 로깅을 생성합니다. 서버 실행 시 자동으로 로그 파일이 생성되며, 별도 설정 없이 즉시 사용할 수 있습니다.

## 빠른 시작

### 1. 웹 서버 실행

```bash
python run_web.py
```

### 2. 로그 파일 확인

서버가 시작되면 프로젝트 루트에 두 개의 로그 파일이 자동 생성됩니다:

```
/home/runner/work/Test/Test/
├── app.log      # 모든 로그 (INFO, WARNING, ERROR 등)
└── error.log    # ERROR 레벨 이상만
```

### 3. 로그 내용 확인

```bash
# 모든 로그 확인
cat app.log

# 에러 로그만 확인
cat error.log

# 실시간 로그 모니터링
tail -f app.log
```

## 로그 파일 예제

### app.log (모든 레벨)
```
[2025-12-07 12:44:32] INFO | File-based logging initialized (app.log, error.log)
[2025-12-07 12:44:33] INFO | GeminiAgent 초기화 완료
[2025-12-07 12:44:34] WARNING | Neo4j 연결 실패 (RAG 비활성화)
[2025-12-07 12:44:35] ERROR | Failed to process request
```

### error.log (에러만)
```
[2025-12-07 12:44:35] ERROR | Failed to process request
```

## 환경 변수 설정

### 로그 레벨 변경

```bash
# DEBUG 레벨로 상세 로그 출력
LOG_LEVEL=DEBUG python run_web.py

# WARNING 레벨 이상만 출력 (프로덕션 환경)
LOG_LEVEL=WARNING python run_web.py
```

사용 가능한 로그 레벨:
- `DEBUG` - 상세한 디버깅 정보
- `INFO` - 일반 정보 메시지 (기본값)
- `WARNING` - 경고 메시지
- `ERROR` - 오류 메시지
- `CRITICAL` - 심각한 오류

### 구조화된 로깅 (JSON)

파일 대신 stdout으로 JSON 형식 로그를 출력하려면:

```bash
ENABLE_STRUCT_LOGGING=true python run_web.py
```

이 경우 `app.log`와 `error.log`는 생성되지 않습니다.

## 로그 파일 관리

### 자동 순환 (Rotation)

로그 파일은 자동으로 순환됩니다:
- **최대 파일 크기**: 10MB
- **백업 파일 수**: 5개
- **명명 규칙**: `app.log`, `app.log.1`, `app.log.2`, ..., `app.log.5`

### 로그 파일 정리

```bash
# 로그 파일 삭제 (서버 중지 후)
rm -f app.log* error.log*
```

로그 파일은 `.gitignore`에 포함되어 있어 Git에 커밋되지 않습니다.

## 보안

### 민감 정보 자동 마스킹

API 키 등 민감한 정보는 자동으로 마스킹됩니다:

```
[2025-12-07 12:00:00] INFO | Using API key: [FILTERED_API_KEY]
```

### 로그 파일 권한

프로덕션 환경에서는 로그 파일 권한을 적절히 설정하세요:

```bash
chmod 600 app.log error.log
```

## 데모 스크립트

로깅 기능을 시연하는 데모 스크립트가 제공됩니다:

```bash
python examples/demo_web_logging.py
```

이 스크립트는 다음을 수행합니다:
1. 로깅 시스템 초기화
2. 다양한 레벨의 로그 메시지 작성
3. 생성된 로그 파일 확인 및 내용 표시
4. 정리

## 문제 해결

### 로그 파일이 생성되지 않음

1. **구조화된 로깅 확인**: `ENABLE_STRUCT_LOGGING=true`가 설정되어 있으면 파일 로깅이 비활성화됩니다.
   ```bash
   unset ENABLE_STRUCT_LOGGING
   ```

2. **권한 확인**: 프로젝트 루트에 쓰기 권한이 있는지 확인하세요.
   ```bash
   ls -la app.log error.log
   ```

3. **디스크 공간 확인**: 충분한 디스크 공간이 있는지 확인하세요.
   ```bash
   df -h .
   ```

### 로그가 즉시 표시되지 않음

로그는 버퍼링되므로 약간의 지연이 있을 수 있습니다. 서버를 정상 종료하거나 잠시 기다리면 모든 로그가 파일에 기록됩니다.

## 관련 문서

- **상세 가이드**: [docs/web_api_logging.md](../docs/web_api_logging.md)
- **데모 스크립트**: [examples/demo_web_logging.py](../examples/demo_web_logging.py)
- **로깅 인프라**: [src/infra/logging.py](../src/infra/logging.py)

## 지원

문제가 발생하면 다음을 확인하세요:
1. 로그 파일 권한
2. 디스크 공간
3. 환경 변수 설정 (`LOG_LEVEL`, `ENABLE_STRUCT_LOGGING`)

추가 질문이 있으면 이슈를 생성해 주세요.

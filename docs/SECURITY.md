# 보안 가이드 (Security)

API 키 관리, 파일 권한, 보안 모범 사례에 대한 가이드입니다.

---

## 🔑 API 키 관리

### API 키 형식

Gemini API 키는 다음 형식을 따릅니다:

- **접두사**: `AIza`
- **길이**: 정확히 39자
- **문자**: 영숫자 및 `_`, `-`

### 안전한 키 저장

1. **`.env` 파일 사용**
   ```bash
   GEMINI_API_KEY=AIza...
   ```

2. **파일 권한 설정**
   ```bash
   chmod 600 .env
   ```

3. **Git에서 제외**
   `.gitignore`에 이미 포함:
   ```
   .env
   .env.*
   ```

### 키 로테이션

정기적으로 API 키를 교체하는 것이 좋습니다:

1. [Google AI Studio](https://makersuite.google.com/app/apikey)에서 새 키 생성
2. `.env` 파일 업데이트
3. 이전 키 삭제

---

## 📁 파일 권한

### .env 파일 권한 확인

시스템 시작 시 `.env` 파일 권한을 확인합니다:

```python
# 권장: 600 (소유자만 읽기/쓰기)
# 경고: 그룹/기타 접근 가능 시 경고 표시
```

권한 설정:
```bash
chmod 600 .env
```

### 민감한 파일 보호

다음 파일들은 Git에서 제외되어야 합니다:

```gitignore
# 환경 변수
.env
.env.*

# 로그 (민감 정보 포함 가능)
*.log
app.log
error.log

# 캐시 데이터
.cache/
cache_stats.jsonl

# 체크포인트
checkpoint.jsonl
```

---

## 🐳 Docker 보안

### Non-root 사용자

Dockerfile에서 non-root 사용자를 사용합니다:

```dockerfile
# 보안: non-root 사용자 생성
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

USER appuser
```

### .dockerignore

Docker 빌드에서 민감한 파일 제외:

```dockerignore
# 환경 파일
.env
.env.*
!.env.example

# Git
.git
.github

# 테스트
tests/

# 로그
*.log
```

### 시크릿 관리

프로덕션 환경에서는 환경 변수 대신 시크릿 매니저 사용:

- Kubernetes Secrets
- Docker Secrets
- HashiCorp Vault
- AWS Secrets Manager

---

## 🔒 로깅 보안

### API 키 마스킹

로그에서 API 키가 자동으로 마스킹됩니다:

```python
SENSITIVE_PATTERN = r"AIza[0-9A-Za-z_-]{35}"
```

마스킹 결과:
```
# 원본
API Key: AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz12345

# 마스킹됨
API Key: AIza***[REDACTED]***
```

### 로그 분리

민감도에 따라 로그 파일 분리:

```bash
LOG_FILE=app.log       # INFO+ 로그
ERROR_LOG_FILE=error.log  # ERROR+ 로그
```

---

## 🌐 네트워크 보안

### HTTPS 사용

프로덕션 환경에서는 HTTPS 강제:

```bash
# 프록시 뒤에서 실행 시
uvicorn src.web.api:app --host 0.0.0.0 --port 8000 --proxy-headers
```

### 방화벽 설정

필요한 포트만 노출:

| 포트 | 서비스 | 노출 |
|------|--------|------|
| 8000 | FastAPI | 외부 |
| 7687 | Neo4j | 내부 |
| 6379 | Redis | 내부 |

---

## ✅ 보안 체크리스트

### 배포 전

- [ ] `.env` 파일 권한 600
- [ ] API 키 유효성 확인
- [ ] Git에서 민감 파일 제외 확인
- [ ] Docker non-root 사용자 사용
- [ ] HTTPS 설정

### 운영 중

- [ ] 정기적 API 키 로테이션
- [ ] 로그 모니터링 (민감 정보 유출)
- [ ] 액세스 로그 검토
- [ ] 의존성 보안 업데이트

### 사고 대응

- [ ] API 키 유출 시 즉시 교체
- [ ] 영향 범위 파악
- [ ] 로그 보존
- [ ] 재발 방지 대책

---

## 🛡️ 의존성 보안

### 취약점 스캔

```bash
# pip-audit 사용
pip install pip-audit
pip-audit

# Safety 사용
pip install safety
safety check
```

### 정기 업데이트

```bash
# 의존성 업데이트
pip install --upgrade -e ".[all]"

# 락 파일 갱신
uv lock
```

---

## 📞 보안 이슈 보고

보안 취약점 발견 시:

1. **비공개 보고**: 공개 Issue에 게시하지 않음
2. **이메일 연락**: 저장소 관리자에게 직접 연락
3. **상세 정보 제공**: 재현 단계, 영향 범위, 가능한 해결책

---

## ⏭️ 관련 문서

- [설정 가이드](CONFIGURATION.md)
- [문제 해결](TROUBLESHOOTING.md)
- [모니터링](MONITORING.md)

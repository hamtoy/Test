# 문제 해결 가이드 (Troubleshooting)

자주 묻는 질문과 일반적인 문제 해결 방법입니다.

---

## 🔑 API 키 관련 문제

### GEMINI_API_KEY is not set

**증상:**
```
GEMINI_API_KEY is not set. Please check your .env file.
```

**해결 방법:**
1. `.env` 파일 생성
   ```bash
   cp .env.example .env
   ```
2. API 키 발급: [Google AI Studio](https://makersuite.google.com/app/apikey)
3. `.env` 파일에 추가
   ```bash
   GEMINI_API_KEY=AIza...
   ```

---

### Must start with 'AIza'

**증상:**
```
GEMINI_API_KEY validation failed:
  - Must start with 'AIza'
```

**해결 방법:**
1. API 키가 `AIza`로 시작하는지 확인
2. 키 앞뒤 공백 제거
3. 따옴표 없이 입력

```bash
# 올바른 형식
GEMINI_API_KEY=AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz12345

# 잘못된 형식
GEMINI_API_KEY="AIza..."  # 따옴표 불필요
GEMINI_API_KEY= AIza...   # 공백 불필요
```

---

### 39 characters 오류

**증상:**
```
GEMINI_API_KEY validation failed:
  - Got 38 characters
  - Must be exactly 39 characters
```

**해결 방법:**
1. 키 복사 시 잘리지 않았는지 확인
2. 새로운 API 키 발급 시도

---

## 📁 파일/디렉토리 오류

### Templates directory missing

**증상:**
```
Templates directory missing: /path/to/templates
```

**해결 방법:**
1. `templates/` 디렉토리 존재 확인
2. `PROJECT_ROOT` 환경 변수 설정
   ```bash
   export PROJECT_ROOT=/path/to/project
   ```
3. 프로젝트 루트에서 실행

---

### Input file not found

**증상:**
```
Input file not found: data/inputs/input_ocr.txt
```

**해결 방법:**
1. 파일 존재 확인
2. `data/inputs/` 디렉토리에 파일 배치
3. 파일명 정확히 입력

---

## 🔗 Neo4j 연결 오류

### Neo4j 연결 실패

**증상:**
```
Failed to connect to Neo4j: Connection refused
```

**해결 방법:**
1. Neo4j 서버 실행 확인
   ```bash
   docker-compose up -d neo4j
   ```
2. `.env` 설정 확인
   ```bash
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```
3. 포트 7687이 열려있는지 확인
   ```bash
   nc -zv localhost 7687
   ```

### RAG 없이 실행

Neo4j 없이 기본 워크플로우만 사용하려면:

```bash
# .env에서 Neo4j 설정 주석 처리
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=your_password
```

---

## 🚀 Redis 연결 오류

### Redis 연결 실패

**증상:**
```
Cannot connect to Redis: Connection refused
```

**해결 방법:**
1. Redis 서버 실행
   ```bash
   docker-compose up -d redis
   ```
2. LATS 워커 없이 실행
   ```bash
   # .env
   ENABLE_LATS=false
   ```

---

## 💰 예산/비용 오류

### Budget exceeded

**증상:**
```
Budget limit exceeded: Current cost $10.50 exceeds limit $10.00
```

**해결 방법:**
1. 예산 한도 증가
   ```bash
   BUDGET_LIMIT_USD=20.0
   ```
2. 예산 한도 제거
   ```bash
   # BUDGET_LIMIT_USD=  (주석 처리)
   ```
3. 세션 종료 후 재시작

---

## ⏱️ 타임아웃 오류

### API Timeout

**증상:**
```
Timeout waiting for API response
```

**해결 방법:**
1. 타임아웃 값 증가
   ```bash
   GEMINI_TIMEOUT=300
   ```
2. 네트워크 상태 확인
3. API 상태 페이지 확인

---

## 🔄 Rate Limiting

### Too Many Requests

**증상:**
```
429 Too Many Requests
```

**해결 방법:**
1. 동시 요청 수 감소
   ```bash
   GEMINI_MAX_CONCURRENCY=3
   ```
2. 잠시 대기 후 재시도
3. API 할당량 확인

---

## 🧪 테스트 관련

### Coverage below threshold

**증상:**
```
FAIL Required coverage of 80% not reached. Got 75%
```

**해결 방법:**
1. 누락된 테스트 추가
2. 임계값 확인
   ```bash
   pytest tests/ --cov=src --cov-fail-under=75
   ```

---

### Import errors

**증상:**
```
ModuleNotFoundError: No module named 'src.xxx'
```

**해결 방법:**
1. 패키지 재설치
   ```bash
   pip install -e .
   ```
2. PYTHONPATH 확인
   ```bash
   export PYTHONPATH=$PWD
   ```

---

## 🔍 디버깅 팁

### 상세 로그 활성화

```bash
LOG_LEVEL=DEBUG python -m src.main
```

### 로그 파일 확인

```bash
# INFO 이상 로그
tail -f app.log

# ERROR 이상 로그
tail -f error.log
```

### API 호출 확인

```bash
# 모델 목록 확인
python -m src.list_models

# 캐시 통계 확인
python -m src.main --analyze-cache
```

---

## 📞 추가 지원

문제가 해결되지 않으면:

1. [GitHub Issues](https://github.com/hamtoy/Test/issues)에 문의
2. 로그 파일 첨부
3. `.env` 파일 내용 (API 키 제외)
4. 실행 환경 정보 (OS, Python 버전)

---

## ⏭️ 관련 문서

- [시작 가이드](GETTING_STARTED.md)
- [설정 가이드](CONFIGURATION.md)
- [보안 가이드](SECURITY.md)

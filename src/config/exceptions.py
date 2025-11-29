class APIRateLimitError(Exception):
    """API 요청 한도가 초과되었습니다.

    🔧 해결 방법:
    1. 동시 요청 수 감소
       $ GEMINI_MAX_CONCURRENCY=3

    2. 잠시 대기 후 재시도
       - 일반적으로 1-2분 후 재시도

    3. API 할당량 확인
       https://makersuite.google.com/app/apikey

    4. 예산 모니터링
       $ python -m src.main --analyze-cache
    """


class ValidationFailedError(Exception):
    """데이터 검증이 실패했습니다.

    🔧 해결 방법:
    1. 입력 데이터 형식 확인
       - OCR 파일: UTF-8 텍스트
       - 후보 파일: 유효한 JSON

    2. 파일 경로 확인
       $ ls data/inputs/

    3. 필수 필드 확인
       - candidates: A, B, C 키 필요

    4. 로그 확인
       $ tail -f error.log
    """


class CacheCreationError(Exception):
    """컨텍스트 캐시 생성이 실패했습니다.

    🔧 해결 방법:
    1. 토큰 수 확인
       - 최소 2048 토큰 필요
       - 프롬프트가 너무 짧으면 캐싱 불가

    2. API 연결 상태 확인
       $ python -m src.list_models

    3. 캐시 설정 확인
       GEMINI_CACHE_SIZE=50
       GEMINI_CACHE_TTL_MINUTES=360

    4. 재시도
       - 일시적 오류일 수 있음
    """


class SafetyFilterError(Exception):
    """안전 필터에 의해 생성이 차단되었습니다.

    🔧 해결 방법:
    1. 입력 내용 검토
       - 민감한 내용이 포함되어 있는지 확인

    2. 프롬프트 수정
       - 문제가 되는 부분 제거 또는 수정

    3. 다른 접근 방식 시도
       - 질문 방식 변경

    ⚠️ 참고:
    - STOP 외의 finish_reason이 발생한 경우입니다
    - 안전 필터는 비활성화할 수 없습니다
    """


class BudgetExceededError(Exception):
    """설정된 예산 한도를 초과했습니다.

    🔧 해결 방법:
    1. 예산 한도 증가
       $ BUDGET_LIMIT_USD=20.0

    2. 예산 한도 제거
       .env에서 BUDGET_LIMIT_USD 주석 처리

    3. 현재 비용 확인
       $ python -m src.main --analyze-cache

    4. 캐싱 최적화
       - 캐시 히트율 향상으로 비용 절감
       - docs/CACHING.md 참조

    💡 팁:
    - 예산 경고 단계: 80%, 90%, 95%
    - 세션 종료 후 재시작하면 새 세션으로 시작
    """


class APIKeyError(Exception):
    """GEMINI_API_KEY가 설정되지 않았거나 형식이 올바르지 않습니다.

    🔧 해결 방법:
    1. .env 파일 생성
       $ cp .env.example .env

    2. API 키 발급
       https://makersuite.google.com/app/apikey

    3. .env 파일에 추가
       GEMINI_API_KEY=AIza...

    4. 형식 확인
       - AIza로 시작
       - 총 39자
       - 공백/따옴표 없음
    """


class Neo4jConnectionError(Exception):
    """Neo4j 연결이 실패했습니다.

    🔧 해결 방법:
    1. Neo4j 서버 실행 확인
       $ docker-compose up -d neo4j

    2. .env 설정 확인
       NEO4J_URI=bolt://localhost:7687
       NEO4J_USER=neo4j
       NEO4J_PASSWORD=your_password

    3. 포트 확인
       $ nc -zv localhost 7687

    4. 연결 테스트
       $ python scripts/neo4j_benchmark_stub.py

    🔍 RAG 없이 실행하려면:
    .env에서 NEO4J_* 변수 주석 처리
    """


class RedisConnectionError(Exception):
    """Redis 연결이 실패했습니다.

    🔧 해결 방법:
    1. Redis 서버 실행
       $ docker-compose up -d redis

    2. .env 설정 확인
       REDIS_URL=redis://localhost:6379

    3. 연결 테스트
       $ redis-cli ping

    🔍 LATS 없이 실행하려면:
    .env에서 ENABLE_LATS=false 설정
    """

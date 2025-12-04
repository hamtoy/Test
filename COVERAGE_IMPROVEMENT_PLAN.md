# 코드 커버리지 개선 계획 (Coverage Improvement Plan)

이 문서는 커버리지가 80% 미만인 18개 모듈에 대한 구체적인 테스트 개선 계획을 제공합니다.

---

## 🔴 HIGH Priority (즉시 조치 필요)

### 1. `src/infra/structured_logging.py` (28.00%)

**현재 상태:**
- 총 25 lines, 7 covered, 18 missing
- 커버리지: 28.00%

**누락된 기능:**
- JsonFormatter의 exc_info 처리 (lines 19-22)
- JsonFormatter의 stack_info 처리 (lines 21-22)
- 커스텀 필드 필터링 로직 (lines 24-50)
- setup_structured_logging 함수 (lines 55-60)

**제안 테스트:**

```python
# tests/unit/infra/test_structured_logging.py

import json
import logging
from src.infra.structured_logging import JsonFormatter, setup_structured_logging


class TestJsonFormatter:
    """JsonFormatter 단위 테스트"""
    
    def test_basic_log_formatting(self):
        """기본 로그 메시지 JSON 포맷팅 테스트"""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "Test message"
    
    def test_log_with_exception(self):
        """예외 정보가 포함된 로그 테스트"""
        formatter = JsonFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info()
            )
            result = formatter.format(record)
            data = json.loads(result)
            
            assert data["level"] == "ERROR"
            assert "exc_info" in data
            assert "ValueError: Test error" in data["exc_info"]
    
    def test_log_with_stack_info(self):
        """스택 정보가 포함된 로그 테스트"""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Warning message",
            args=(),
            exc_info=None
        )
        record.stack_info = "Stack trace here"
        result = formatter.format(record)
        data = json.loads(result)
        
        assert "stack" in data
        assert data["stack"] == "Stack trace here"
    
    def test_custom_fields_included(self):
        """커스텀 필드가 포함되는지 테스트"""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Custom fields test",
            args=(),
            exc_info=None
        )
        record.user_id = "12345"
        record.request_id = "abc-def"
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["user_id"] == "12345"
        assert data["request_id"] == "abc-def"
    
    def test_internal_fields_excluded(self):
        """내부 필드가 제외되는지 테스트"""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        data = json.loads(result)
        
        # 내부 필드들이 포함되지 않아야 함
        assert "pathname" not in data
        assert "filename" not in data
        assert "lineno" not in data
        assert "funcName" not in data


class TestSetupStructuredLogging:
    """setup_structured_logging 함수 테스트"""
    
    def test_setup_default_level(self):
        """기본 로그 레벨(INFO) 설정 테스트"""
        setup_structured_logging()
        root = logging.getLogger()
        
        assert root.level == logging.INFO
        assert len(root.handlers) > 0
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
    
    def test_setup_custom_level(self):
        """커스텀 로그 레벨 설정 테스트"""
        setup_structured_logging("DEBUG")
        root = logging.getLogger()
        
        assert root.level == logging.DEBUG
    
    def test_setup_invalid_level_defaults_to_info(self):
        """잘못된 로그 레벨은 INFO로 기본 설정"""
        setup_structured_logging("INVALID_LEVEL")
        root = logging.getLogger()
        
        assert root.level == logging.INFO
    
    def test_setup_clears_existing_handlers(self):
        """기존 핸들러가 제거되는지 테스트"""
        root = logging.getLogger()
        initial_handler_count = len(root.handlers)
        
        setup_structured_logging()
        
        # 핸들러가 클리어되고 새로 추가됨
        assert len(root.handlers) == 1
```

**예상 개선 효과:** 28% → 85%+

---

### 2. `src/qa/template_rules.py` (28.17%)

**현재 상태:**
- 총 71 lines, 20 covered, 51 missing
- 커버리지: 28.17%

**누락된 기능:**
- Neo4j 연결 실패 처리
- 빈 결과 처리
- 캐시 동작 검증
- 다양한 query_type 테스트

**제안 테스트:**

```python
# tests/unit/qa/test_template_rules.py

from unittest.mock import Mock, patch, MagicMock
import pytest
from src.qa.template_rules import (
    get_rules_for_query_type,
    get_rules_from_neo4j,
    get_common_mistakes,
    get_best_practices,
    get_constraint_details,
    get_all_template_context,
    get_neo4j_config
)


class TestGetRulesForQueryType:
    """get_rules_for_query_type 함수 테스트"""
    
    @patch('src.qa.template_rules.GraphDatabase')
    def test_get_rules_success(self, mock_graph_db):
        """규칙 조회 성공 테스트"""
        # Mock setup
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [
            {
                "title": "Rule 1",
                "content": "Content 1",
                "category": "Category A",
                "subcategory": "Subcategory 1"
            }
        ]
        
        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        # Clear cache first
        get_rules_for_query_type.cache_clear()
        
        # Execute
        result = get_rules_for_query_type(
            "explanation", 
            "neo4j://localhost", 
            "user", 
            "password"
        )
        
        # Verify
        assert len(result) == 1
        assert result[0]["title"] == "Rule 1"
        mock_driver.close.assert_called_once()
    
    @patch('src.qa.template_rules.GraphDatabase')
    def test_get_rules_empty_result(self, mock_graph_db):
        """빈 결과 처리 테스트"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value.run.return_value = []
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        get_rules_for_query_type.cache_clear()
        
        result = get_rules_for_query_type(
            "unknown_type",
            "neo4j://localhost",
            "user",
            "password"
        )
        
        assert result == []
    
    @patch('src.qa.template_rules.GraphDatabase')
    def test_caching_works(self, mock_graph_db):
        """LRU 캐시 동작 검증"""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        
        get_rules_for_query_type.cache_clear()
        
        # 첫 호출
        get_rules_for_query_type("test", "uri", "user", "pass")
        first_call_count = mock_graph_db.driver.call_count
        
        # 동일한 인자로 두 번째 호출 (캐시에서 반환되어야 함)
        get_rules_for_query_type("test", "uri", "user", "pass")
        second_call_count = mock_graph_db.driver.call_count
        
        # 캐시로 인해 driver 호출 횟수가 증가하지 않아야 함
        assert first_call_count == second_call_count


class TestGetCommonMistakes:
    """get_common_mistakes 함수 테스트"""
    
    @patch('src.qa.template_rules.GraphDatabase')
    def test_with_category_filter(self, mock_graph_db):
        """카테고리 필터링 테스트"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [
            {
                "title": "Mistake 1",
                "preview": "Preview text",
                "subcategory": "질의"
            }
        ]
        
        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        get_common_mistakes.cache_clear()
        
        result = get_common_mistakes(
            "질의",
            "neo4j://localhost",
            "user",
            "password"
        )
        
        assert len(result) == 1
        assert result[0]["subcategory"] == "질의"
    
    @patch('src.qa.template_rules.GraphDatabase')
    def test_without_category_filter(self, mock_graph_db):
        """카테고리 필터 없이 전체 조회 테스트"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [
            {"title": "M1", "preview": "P1", "subcategory": "질의"},
            {"title": "M2", "preview": "P2", "subcategory": "답변"}
        ]
        
        mock_session.__enter__.return_value.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        
        get_common_mistakes.cache_clear()
        
        result = get_common_mistakes(
            None,
            "neo4j://localhost",
            "user",
            "password"
        )
        
        assert len(result) == 2


class TestGetAllTemplateContext:
    """get_all_template_context 함수 테스트"""
    
    @patch('src.qa.template_rules.get_rules_for_query_type')
    @patch('src.qa.template_rules.get_common_mistakes')
    @patch('src.qa.template_rules.get_best_practices')
    @patch('src.qa.template_rules.get_constraint_details')
    @patch('src.qa.template_rules.get_rules_from_neo4j')
    def test_full_context_answer_stage(
        self, mock_rules_neo4j, mock_constraints, 
        mock_best, mock_mistakes, mock_rules
    ):
        """전체 컨텍스트 생성 테스트 (답변 단계)"""
        mock_rules.return_value = [{"rule": "test"}]
        mock_mistakes.return_value = [{"mistake": "test"}]
        mock_best.return_value = ["best practice"]
        mock_constraints.return_value = ["constraint"]
        mock_rules_neo4j.return_value = [{"neo4j_rule": "test"}]
        
        context = get_all_template_context(
            query_type="explanation",
            neo4j_uri="uri",
            neo4j_user="user",
            neo4j_password="pass",
            include_mistakes=True,
            include_best_practices=True,
            include_constraints=True,
            context_stage="answer"
        )
        
        assert "guide_rules" in context
        assert "common_mistakes" in context
        assert "best_practices" in context
        assert "constraint_details" in context
        assert "rules" in context
    
    @patch('src.qa.template_rules.get_rules_for_query_type')
    @patch('src.qa.template_rules.get_rules_from_neo4j')
    def test_minimal_context(self, mock_rules_neo4j, mock_rules):
        """최소 컨텍스트 생성 테스트"""
        mock_rules.return_value = []
        mock_rules_neo4j.return_value = []
        
        context = get_all_template_context(
            query_type="test",
            neo4j_uri="uri",
            neo4j_user="user",
            neo4j_password="pass",
            include_mistakes=False,
            include_best_practices=False,
            include_constraints=False
        )
        
        assert "guide_rules" in context
        assert "common_mistakes" not in context
        assert "best_practices" not in context
        assert "constraint_details" not in context
    
    @patch('src.qa.template_rules.get_rules_for_query_type')
    @patch('src.qa.template_rules.get_rules_from_neo4j')
    def test_rules_error_handling(self, mock_rules_neo4j, mock_rules):
        """Rule 조회 실패 시 에러 처리 테스트"""
        mock_rules.return_value = []
        mock_rules_neo4j.side_effect = Exception("Connection failed")
        
        # 예외가 발생해도 빈 리스트로 처리되어야 함
        context = get_all_template_context(
            query_type="test",
            neo4j_uri="uri",
            neo4j_user="user",
            neo4j_password="pass"
        )
        
        assert context["rules"] == []


class TestGetNeo4jConfig:
    """get_neo4j_config 함수 테스트"""
    
    @patch.dict('os.environ', {
        'NEO4J_URI': 'neo4j://custom',
        'NEO4J_USERNAME': 'admin',
        'NEO4J_PASSWORD': 'secret'
    })
    def test_from_env_with_username(self):
        """환경변수에서 설정 로드 (NEO4J_USERNAME 우선)"""
        config = get_neo4j_config()
        
        assert config["neo4j_uri"] == "neo4j://custom"
        assert config["neo4j_user"] == "admin"
        assert config["neo4j_password"] == "secret"
    
    @patch.dict('os.environ', {
        'NEO4J_USER': 'user_legacy',
        'NEO4J_PASSWORD': 'pass123'
    }, clear=True)
    def test_fallback_to_neo4j_user(self):
        """NEO4J_USER로 폴백 테스트"""
        config = get_neo4j_config()
        
        assert config["neo4j_user"] == "user_legacy"
    
    @patch.dict('os.environ', {}, clear=True)
    def test_default_values(self):
        """기본값 테스트"""
        config = get_neo4j_config()
        
        assert "neo4j_uri" in config
        assert config["neo4j_user"] == "neo4j"  # 기본값
        assert config["neo4j_password"] == ""  # 기본값
```

**예상 개선 효과:** 28% → 85%+

---

### 3. `src/infra/telemetry.py` (40.94%)

**현재 상태:**
- 총 127 lines, 52 covered, 75 missing
- 커버리지: 40.94%

**누락된 기능:**
- OpenTelemetry 초기화 (init_telemetry)
- Noop tracer/meter 구현
- traced/traced_async 데코레이터
- 에러 처리 경로

**제안 테스트:**

```python
# tests/unit/infra/test_telemetry.py

import os
from unittest.mock import Mock, patch, MagicMock
import pytest
from src.infra.telemetry import (
    init_telemetry,
    get_tracer,
    get_meter,
    traced,
    traced_async
)


class TestInitTelemetry:
    """init_telemetry 함수 테스트"""
    
    @patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317'})
    @patch('src.infra.telemetry.trace')
    @patch('src.infra.telemetry.metrics')
    def test_init_with_endpoint(self, mock_metrics, mock_trace):
        """OTLP 엔드포인트가 있을 때 초기화 성공"""
        # Mocking이 복잡하므로 초기화 함수 호출만 확인
        init_telemetry("test-service", "http://localhost:4317")
        
        # trace provider 설정 호출 확인
        mock_trace.set_tracer_provider.assert_called_once()
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('src.infra.telemetry.trace')
    def test_init_without_endpoint(self, mock_trace):
        """엔드포인트 없을 때 텔레메트리 비활성화"""
        init_telemetry("test-service")
        
        # trace provider가 설정되지 않아야 함
        mock_trace.set_tracer_provider.assert_not_called()
    
    @patch('src.infra.telemetry.trace', None)
    def test_init_without_opentelemetry(self):
        """OpenTelemetry 미설치 시 graceful 처리"""
        # 예외가 발생하지 않아야 함
        init_telemetry("test-service", "http://localhost:4317")


class TestGetTracer:
    """get_tracer 함수 테스트"""
    
    def test_get_tracer_returns_callable(self):
        """tracer가 호출 가능한 객체를 반환하는지 확인"""
        tracer = get_tracer()
        
        assert tracer is not None
        assert hasattr(tracer, 'start_as_current_span')
    
    @patch('src.infra.telemetry.trace', None)
    def test_noop_tracer_when_no_trace(self):
        """trace가 None일 때 noop tracer 반환"""
        tracer = get_tracer()
        
        # Noop tracer의 메서드들이 정상 동작해야 함
        span = tracer.start_as_current_span("test")
        with span:
            span.set_attribute("key", "value")
            span.record_exception(Exception("test"))
            span.set_status("OK")


class TestGetMeter:
    """get_meter 함수 테스트"""
    
    def test_get_meter_returns_callable(self):
        """meter가 호출 가능한 객체를 반환하는지 확인"""
        meter = get_meter()
        
        assert meter is not None
        assert hasattr(meter, 'create_counter')
    
    @patch('src.infra.telemetry.metrics', None)
    def test_noop_meter_when_no_metrics(self):
        """metrics가 None일 때 noop meter 반환"""
        meter = get_meter()
        
        # Noop meter의 메서드들이 정상 동작해야 함
        counter = meter.create_counter("test_counter")
        counter.add(1)  # 예외가 발생하지 않아야 함


class TestTracedDecorator:
    """traced 데코레이터 테스트"""
    
    def test_traced_decorator_basic(self):
        """기본 traced 데코레이터 동작 테스트"""
        @traced("test_operation")
        def sample_function():
            return "result"
        
        result = sample_function()
        assert result == "result"
    
    def test_traced_with_attributes(self):
        """속성이 포함된 traced 데코레이터 테스트"""
        @traced("test_op", attributes={"key": "value"})
        def sample_function():
            return 42
        
        result = sample_function()
        assert result == 42
    
    def test_traced_exception_handling(self):
        """예외 처리가 포함된 traced 데코레이터 테스트"""
        @traced("failing_operation")
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
    
    def test_traced_preserves_function_metadata(self):
        """함수 메타데이터 보존 확인"""
        @traced("test_op")
        def documented_function():
            """This is a docstring"""
            pass
        
        assert documented_function.__doc__ == "This is a docstring"
        assert documented_function.__name__ == "documented_function"


class TestTracedAsyncDecorator:
    """traced_async 데코레이터 테스트"""
    
    @pytest.mark.asyncio
    async def test_traced_async_decorator_basic(self):
        """기본 traced_async 데코레이터 동작 테스트"""
        @traced_async("async_operation")
        async def async_sample_function():
            return "async_result"
        
        result = await async_sample_function()
        assert result == "async_result"
    
    @pytest.mark.asyncio
    async def test_traced_async_with_attributes(self):
        """속성이 포함된 traced_async 데코레이터 테스트"""
        @traced_async("async_op", attributes={"user_id": "123"})
        async def async_function():
            return 100
        
        result = await async_function()
        assert result == 100
    
    @pytest.mark.asyncio
    async def test_traced_async_exception_handling(self):
        """예외 처리가 포함된 traced_async 데코레이터 테스트"""
        @traced_async("failing_async_op")
        async def failing_async_function():
            raise RuntimeError("Async error")
        
        with pytest.raises(RuntimeError, match="Async error"):
            await failing_async_function()
```

**예상 개선 효과:** 40% → 80%+

---

## 🟡 MEDIUM Priority (개선 권장)

### 4. `src/web/routers/workspace.py` (52.30%)

**주요 누락:**
- 다양한 API 엔드포인트의 에러 케이스
- 파일 업로드/다운로드 시나리오
- 권한 검증
- 세션 관리

**권장사항:**
- 각 엔드포인트별로 성공/실패 시나리오 테스트 추가
- Mock을 활용한 의존성 분리
- 엣지 케이스 (빈 입력, 잘못된 형식 등) 테스트

### 5. `src/agent/batch_processor.py` (54.95%)

**주요 누락:**
- 배치 재시도 로직
- 부분 실패 처리
- 타임아웃 시나리오

**권장사항:**
- 배치 처리의 다양한 실패 시나리오 테스트
- 재시도 메커니즘 검증
- 대용량 배치 테스트

### 6. `src/qa/graph/rule_upsert.py` (64.16%)

**주요 누락:**
- Neo4j 트랜잭션 실패 처리
- 중복 규칙 처리
- 업데이트 충돌 해결

**권장사항:**
- Mock Neo4j 드라이버를 사용한 단위 테스트
- 트랜잭션 롤백 시나리오 테스트
- 동시성 테스트

---

## 🟢 LOW Priority (점진적 개선)

LOW Priority 모듈들 (70-80% 커버리지)은 기존 테스트를 확장하여 점진적으로 개선할 수 있습니다.

### 일반 권장사항:
1. 각 모듈의 missing lines를 확인하여 우선순위 결정
2. 에러 핸들링 경로 우선 테스트 추가
3. 엣지 케이스 및 경계값 테스트 추가
4. 통합 테스트로 복잡한 플로우 검증

---

## 📊 진행 상황 추적

### Week 1-2 목표 (HIGH Priority)
- [ ] `src/infra/structured_logging.py` 테스트 추가 → 85%
- [ ] `src/qa/template_rules.py` 테스트 추가 → 85%
- [ ] `src/infra/telemetry.py` 테스트 추가 → 80%

### Week 3-4 목표 (MEDIUM Priority)
- [ ] `src/web/routers/workspace.py` 테스트 확장 → 80%
- [ ] `src/agent/batch_processor.py` 테스트 확장 → 80%
- [ ] `src/qa/graph/rule_upsert.py` 테스트 확장 → 80%

### Monthly Review
- [ ] 전체 커버리지 90% 달성
- [ ] 모든 모듈 80% 이상 달성
- [ ] CI/CD 파이프라인에 커버리지 체크 강화

---

## 🛠️ 테스트 작성 베스트 프랙티스

### 1. 단위 테스트 작성 가이드
```python
# 좋은 예
def test_specific_behavior():
    """테스트가 검증하는 내용을 명확히 설명"""
    # Given: 테스트 준비
    input_data = {...}
    
    # When: 테스트 실행
    result = function_under_test(input_data)
    
    # Then: 결과 검증
    assert result == expected_output
```

### 2. Mock 사용 가이드
```python
from unittest.mock import Mock, patch

# 외부 의존성은 Mock으로 대체
@patch('module.external_dependency')
def test_with_mock(mock_dependency):
    mock_dependency.return_value = "expected"
    result = function_using_dependency()
    assert result == "expected"
```

### 3. 비동기 테스트
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

---

## 📈 예상 효과

### 현재 상태
- 전체 커버리지: 84.97%
- 80% 미만 모듈: 18개

### 1단계 완료 후 (HIGH Priority 개선)
- 예상 전체 커버리지: 88%+
- 80% 미만 모듈: 15개

### 2단계 완료 후 (MEDIUM Priority 개선)
- 예상 전체 커버리지: 92%+
- 80% 미만 모듈: 9개

### 최종 목표 달성 후
- 목표 전체 커버리지: 95%+
- 80% 미만 모듈: 0개

---

**작성일**: 2025-12-04  
**다음 업데이트**: 2주 후 진행 상황 리뷰

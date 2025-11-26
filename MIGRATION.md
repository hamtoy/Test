# Migration Guide

## From v1.x to v2.x - Import Path Changes

### Overview

프로젝트가 모듈화된 패키지 구조로 전환되었습니다. 이전 import 경로는 여전히 작동하지만 deprecation 경고가 표시됩니다. v3.0에서 이전 경로는 제거될 예정입니다.

### Import Path 매핑표

| 구분 | 기존 Import Path | 새 Import Path |
|------|-----------------|---------------|
| **설정 및 상수** | | |
| AppConfig | `from src.config import AppConfig` | `from src.config import AppConfig` *(변경 없음)* |
| 상수 | `from src.constants import ...` | `from src.config.constants import ...` |
| 예외 | `from src.exceptions import ...` | `from src.config.exceptions import ...` |
| **핵심 모델** | | |
| 모델 | `from src.models import ...` | `from src.core.models import ...` |
| **인프라** | | |
| 유틸리티 | `from src.utils import ...` | `from src.infra.utils import ...` |
| 로깅 | `from src.logging_setup import ...` | `from src.infra.logging import ...` |
| Neo4j | `from src.neo4j_utils import ...` | `from src.infra.neo4j import ...` |
| 워커 | `from src.worker import ...` | `from src.infra.worker import ...` |
| **Q&A 시스템** | | |
| RAG 시스템 | `from src.qa_rag_system import ...` | `from src.qa.rag_system import ...` |
| **데이터 처리** | | |
| 데이터 로더 | `from src.data_loader import ...` | `from src.processing.loader import ...` |
| **캐싱** | | |
| 캐싱 레이어 | `from src.caching_layer import ...` | `from src.caching.layer import ...` |
| **라우팅** | | |
| 그래프 라우터 | `from src.graph_enhanced_router import ...` | `from src.routing.graph_router import ...` |

### 마이그레이션 예시

#### Before (deprecated)
```python
from src.constants import ERROR_MESSAGES, LOG_MESSAGES
from src.exceptions import BudgetExceededError, ValidationFailedError
from src.models import WorkflowResult, EvaluationResultSchema
from src.utils import clean_markdown_code_block, safe_json_parse
from src.logging_setup import setup_logging, log_metrics
from src.neo4j_utils import SafeDriver, create_sync_driver
from src.qa_rag_system import QAKnowledgeGraph
from src.data_loader import load_input_data, validate_candidates
```

#### After (recommended)
```python
from src.config.constants import ERROR_MESSAGES, LOG_MESSAGES
from src.config.exceptions import BudgetExceededError, ValidationFailedError
from src.core.models import WorkflowResult, EvaluationResultSchema
from src.infra.utils import clean_markdown_code_block, safe_json_parse
from src.infra.logging import setup_logging, log_metrics
from src.infra.neo4j import SafeDriver, create_sync_driver
from src.qa.rag_system import QAKnowledgeGraph
from src.processing.loader import load_input_data, validate_candidates
```

### 자동 마이그레이션 스크립트

프로젝트의 모든 import를 자동으로 업데이트하려면 다음 스크립트를 사용하세요:

```python
#!/usr/bin/env python3
"""Automatically migrate imports to new paths."""
import re
import sys
from pathlib import Path

IMPORT_MAPPINGS = {
    r'from src\.constants import': 'from src.config.constants import',
    r'from src\.exceptions import': 'from src.config.exceptions import',
    r'from src\.models import': 'from src.core.models import',
    r'from src\.utils import': 'from src.infra.utils import',
    r'from src\.logging_setup import': 'from src.infra.logging import',
    r'from src\.neo4j_utils import': 'from src.infra.neo4j import',
    r'from src\.worker import': 'from src.infra.worker import',
    r'from src\.data_loader import': 'from src.processing.loader import',
    r'from src\.qa_rag_system import': 'from src.qa.rag_system import',
    r'from src\.caching_layer import': 'from src.caching.layer import',
    r'from src\.graph_enhanced_router import': 'from src.routing.graph_router import',
}

def migrate_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    for old_pattern, new_import in IMPORT_MAPPINGS.items():
        content = re.sub(old_pattern, new_import, content)
    
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"✓ Migrated {filepath}")

# Usage: python migrate_imports.py <file.py>
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_imports.py <file.py>")
        sys.exit(1)
    migrate_file(sys.argv[1])
```

### 타임라인

- **v2.0 (현재)**: 새 import 경로 도입, 이전 경로는 deprecation 경고와 함께 유지
- **v2.5**: 이전 import 경로 사용 시 경고 레벨 증가
- **v3.0**: 이전 import 경로 제거 (shim 파일 삭제)

### 자주 묻는 질문

#### Q: 이전 import를 계속 사용할 수 있나요?
A: 네, v2.x 버전에서는 작동합니다. 하지만 deprecation 경고가 표시되며, v3.0에서는 제거될 예정입니다.

#### Q: AppConfig import는 왜 변경되지 않았나요?
A: `from src.config import AppConfig`는 이미 패키지 레벨 import이므로 변경할 필요가 없습니다. `src.config` 패키지의 `__init__.py`에서 직접 export합니다.

#### Q: 마이그레이션을 꼭 해야 하나요?
A: v2.x를 사용하는 동안에는 필수는 아니지만, v3.0으로 업그레이드할 계획이라면 미리 마이그레이션하는 것이 좋습니다.

#### Q: 테스트 파일도 마이그레이션해야 하나요?
A: 네, 테스트 파일도 동일한 규칙을 따라 마이그레이션하는 것이 좋습니다.

### 추가 도움

마이그레이션 중 문제가 발생하면 이슈를 생성하거나 프로젝트 메인테이너에게 문의하세요.

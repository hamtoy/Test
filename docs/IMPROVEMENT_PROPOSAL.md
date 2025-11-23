# 개인 프로젝트 맞춤 개선 영역 분석 (2025년 기준)

혼자 사용하는 프로젝트이고 배포 계획이 없다는 점을 고려하여, **실제 작업 효율성과 개발 경험(DX) 향상**에 초점을 맞춘 개선 영역을 제안합니다. 웹 검색을 통해 최신 도구 트렌드(2025년 기준)와 호환성을 검증하여 내용을 보완했습니다.

---

## 🎯 1. 개발 경험(DX) 개선

**현재 상태:**

- UV 패키지 매니저 사용 중
- Pre-commit 훅 설정됨
- Pytest 테스트 프레임워크 구축됨

**개인 프로젝트에 유용한 개선:**

### 1.1 더 빠른 피드백 루프

```bash
# 현재: 전체 테스트 실행 시간이 길 수 있음
pytest tests/ -v

# 개선: 변경된 파일만 테스트 (pytest-watcher 권장)
uv run pytest-watcher .  # 파일 변경 감지 시 자동 테스트
pytest --lf  # 마지막 실패 테스트만 재실행
pytest --ff  # 실패 테스트 우선 실행
```

**추천 도구:**

- **`pytest-watcher`**: `pytest-watch`는 유지보수가 중단되었으므로, `uv`와 호환성이 좋은 `pytest-watcher`를 사용하는 것이 2025년 표준입니다.
- `pytest-xdist`: 병렬 테스트 실행으로 속도 향상 (`-n auto` 옵션)
- `pytest-sugar`: 테스트 결과 가독성 개선 (진행바, 즉각적인 실패 피드백)

### 1.2 코드 품질 자동 개선

```toml
# pyproject.toml에 추가
[tool.ruff]
fix = true  # 자동 수정 활성화
unsafe-fixes = false  # 안전한 수정만

[tool.ruff.lint]
extend-select = [
    "PERF",  # 성능 최적화 제안
    "FURB",  # 현대적인 Python 패턴 제안
    "SIM",   # 코드 단순화
]
```

**LLM 기반 코드 품질 도구:**

- **GitHub Copilot CLI**: 터미널에서 바로 코드 리팩토링 제안
- **aider**: LLM이 직접 코드 수정 (GPT-4o/Claude 지원) - 혼자 개발할 때 페어 프로그래밍 파트너로 매우 유용합니다.

---

## ⚡ 2. 성능 최적화 (실용적 접근)

**현재 상태:**

- `cache_analytics.py`로 캐시 통계 추적
- `latency_baseline.py`로 API 지연 분석
- 병렬 쿼리 처리 구현됨

**혼자 쓸 때 체감되는 성능 개선:**

### 2.1 프로파일링 자동화

```python
# scripts/auto_profile.py
import cProfile
import pstats
from pathlib import Path

def profile_main():
    """main.py를 프로파일링하고 top 20 병목 출력"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    from src import main
    main.run()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumtime')
    stats.print_stats(20)  # 상위 20개만

# 실행: python scripts/auto_profile.py
```

### 2.2 메모리 사용량 모니터링

```python
# requirements에 추가
memory-profiler>=0.61

# 사용법
@profile
def heavy_function():
    # 메모리 사용량 라인별 추적
    large_list = [x for x in range(10**7)]
    return sum(large_list)
```

### 2.3 Dead Code 제거 자동화

```bash
# vulture: 전통적인 사용하지 않는 코드 탐지
uv add --dev vulture
vulture src/ --min-confidence 80

# deadcode: 더 현대적인 대안 (선택 사항)
# uv add --dev deadcode
# deadcode src/

# autoflake: 사용하지 않는 import 자동 제거
autoflake --remove-all-unused-imports --in-place src/**/*.py
```

---

## 🔧 3. 워크플로우 효율성

**현재 상태:**

- 체크포인트 기반 복구 (`--resume`)
- 캐시 통계 분석 (`--analyze-cache`)
- AUTO/CHAT 모드 지원

**개인 사용에 최적화된 개선:**

### 3.1 빠른 실험을 위한 별칭 (Alias)

```bash
# ~/.bashrc 또는 ~/.zshrc (Windows의 경우 PowerShell Profile)에 추가
function qa-quick { uv run python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json }
function qa-resume { uv run python -m src.main --resume }
function qa-cache { uv run python -m src.main --analyze-cache }

# 사용: 터미널에서 'qa-quick' 입력만으로 실행
```

### 3.2 개발 모드 추가

```python
# src/config.py에 추가
class Config:
    # ...
    DEBUG_MODE: bool = Field(default=False)
    SAMPLE_SIZE: int = Field(default=None)  # 테스트용 샘플링
    
# .env에 추가
DEBUG_MODE=true
SAMPLE_SIZE=3  # 전체 데이터 대신 3개만 처리
```

### 3.3 로그 필터링 단순화

```bash
# 특정 모듈만 로깅
$env:PYTHONPATH="src"; python -m main --log-level INFO src.agent:DEBUG

# 에러만 빠르게 확인
Select-String "ERROR" app.log | Select-Object -Last 20
```

---

## 📊 4. 데이터 관리 개선

**현재 상태:**

- `data/inputs/`, `data/outputs/` 구조
- `checkpoint.jsonl` 저장

**개인 프로젝트에 유용한 개선:**

### 4.1 실험 결과 비교 스크립트

```python
# scripts/compare_runs.py
import json
from pathlib import Path
from rich.table import Table

def compare_experiments():
    """여러 실험 결과를 테이블로 비교"""
    results = []
    for file in Path("data/outputs").glob("result_*.md"):
        # 토큰 사용량, 비용, 시간 추출
        results.append(parse_result(file))
    
    table = Table(title="Experiment Comparison")
    table.add_column("File")
    table.add_column("Tokens")
    table.add_column("Cost")
    table.add_column("Time")
    # ...
```

### 4.2 자동 백업 스크립트

```bash
# scripts/backup.ps1 (PowerShell)
$date = Get-Date -Format "yyyyMMdd"
Compress-Archive -Path "data/", ".env", "cache_stats.jsonl", "checkpoint.jsonl" -DestinationPath "backups/shining-quasar-$date.zip"

# 작업 스케줄러에 등록하여 주 1회 백업
```

---

## 🧪 5. 테스트 효율성

**현재 상태:**

- 77% 커버리지 달성 (최근 향상됨)
- 주요 모듈 커버리지 높음

**혼자 쓸 때 현실적인 테스트 전략:**

### 5.1 핵심 경로만 집중 테스트

```python
# tests/test_critical_paths.py
"""자주 실행하는 워크플로우만 테스트"""

def test_end_to_end_auto_mode():
    """가장 자주 사용하는 AUTO 모드 통합 테스트"""
    # 실제 사용 시나리오 재현
    pass
```

### 5.2 Snapshot 테스트로 회귀 방지

```python
# requirements에 추가
syrupy>=4.0  # 강력한 스냅샷 테스팅 (외부 파일 저장)
# 또는
# inline-snapshot>=0.8.0  # 코드 내에 스냅샷 저장 (빠른 수정 용이)

# tests/test_snapshots.py
def test_query_generation_output(snapshot):
    """질의 생성 결과가 변경되지 않았는지 확인"""
    result = generate_query(sample_ocr)
    assert result == snapshot
```

---

## 🎨 6. 사용성 개선

**현재 상태:**

- Rich 기반 콘솔 UI
- 비용/토큰 사용량 표시

**혼자 쓸 때 편한 개선:**

### 6.1 대화형 모드 강화

```python
# src/interactive.py
from rich.prompt import Prompt, Confirm
from rich.console import Console

def interactive_setup():
    """설정을 대화형으로 입력"""
    console = Console()
    
    model = Prompt.ask(
        "모델 선택",
        choices=["gemini-3-pro", "gemini-2-flash"],
        default="gemini-3-pro"
    )
    
    if Confirm.ask("캐싱 활성화?"):
        # ...
```

### 6.2 실행 결과 알림

```python
# requirements에 추가
plyer>=2.1  # 데스크톱 알림

# src/utils.py
from plyer import notification

def notify_completion(title, message):
    """긴 작업 완료 시 알림"""
    notification.notify(
        title=title,
        message=message,
        app_name="Shining Quasar",
        timeout=10
    )
```

---

## 🛠️ 7. 디버깅 도구

### 7.1 빠른 디버깅을 위한 설정

```json
// .vscode/launch.json
{
    "configurations": [
        {
            "name": "Debug Main",
            "type": "debugpy",
            "request": "launch",
            "module": "src.main",
            "args": [
                "--mode", "AUTO",
                "--ocr-file", "example_ocr.txt",
                "--cand-file", "example_candidates.json",
                "--log-level", "DEBUG"
            ],
            "console": "integratedTerminal"
        }
    ]
}
```

### 7.2 LLM 응답 저장 및 재현

```python
# src/agent.py 수정
class GeminiAgent:
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        
    async def generate_content(self, prompt):
        response = await self.model.generate(prompt)
        
        if self.debug_mode:
            # LLM 응답을 파일로 저장하여 비용 절감 및 디버깅 용이
            Path("debug/responses").mkdir(exist_ok=True)
            with open(f"debug/responses/{timestamp}.json", "w") as f:
                json.dump({
                    "prompt": prompt,
                    "response": response
                }, f)
```

---

## 📝 우선순위 추천

**혼자 쓰는 프로젝트에서 즉시 효과를 볼 수 있는 순서:**

1. **빠른 실험** → PowerShell Profile에 별칭 설정 (3.1)
2. **디버깅** → VS Code `launch.json` 설정 (7.1)
3. **테스트 속도** → `pytest-watcher` 설치 및 사용 (1.1)
4. **코드 품질** → `ruff` 설정 강화 (1.2)
5. **편의성** → 긴 작업 완료 시 `plyer` 알림 (6.2)

이 개선사항들은 모두 **배포 없이 개인 사용에만 초점**을 맞추고 있으며, 실제 개발 속도와 편의성을 높이는 데 집중합니다.

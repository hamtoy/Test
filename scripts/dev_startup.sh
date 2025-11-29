#!/bin/bash
# 로컬 개발 환경 시작 스크립트
#
# 사용법:
#   ./scripts/dev_startup.sh
#
# 환경 변수:
#   SKIP_CACHE_WARMING=true  캐시 워밍 건너뛰기

set -e

echo "🚀 Development Environment Startup"
echo "=================================="

# 1. Python 환경 체크
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.10+."
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "📌 Python version: $PYTHON_VERSION"

# 2. 의존성 체크 (선택)
if [ -f "pyproject.toml" ]; then
    echo "📦 Dependencies configured via pyproject.toml"
fi

# 3. Redis 체크 (선택)
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "✅ Redis is running"
    else
        echo "⚠️  Redis is installed but not running"
    fi
else
    echo "ℹ️  Redis not found (optional dependency)"
fi

# 4. 캐시 워밍 (선택)
if [ "$SKIP_CACHE_WARMING" = "true" ]; then
    echo "⏭️  Skipping cache warming (SKIP_CACHE_WARMING=true)"
else
    echo ""
    read -p "🔥 Run cache warming? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Running cache warming..."
        python scripts/cache_warming.py high || echo "⚠️  Cache warming had some failures"
    fi
fi

# 5. 환경 변수 체크
echo ""
echo "🔐 Environment Variables Check:"

if [ -z "$GEMINI_API_KEY" ]; then
    if [ -f ".env" ]; then
        echo "   GEMINI_API_KEY: Found in .env file"
    else
        echo "   ⚠️  GEMINI_API_KEY: Not set (check .env or export)"
    fi
else
    echo "   GEMINI_API_KEY: ✓ Set"
fi

# 6. 애플리케이션 시작
echo ""
echo "=================================="
echo "✅ Environment ready!"
echo ""
echo "Start commands:"
echo "  • CLI:     python -m src.main"
echo "  • Web API: python -m uvicorn src.web.api:app --reload"
echo "  • Tests:   pytest tests/ -v"
echo ""

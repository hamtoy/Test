#!/bin/bash
# 매일 오전 10시 실행
# Daily self-improvement check script
# cron: 0 10 * * * /path/to/project/scripts/daily_improvement_check.sh

set -e

# Change to project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🔍 Running daily improvement check..."

python -c "
import asyncio
from src.features.self_improvement import SelfImprovingSystem

async def main():
    system = SelfImprovingSystem()
    result = await system.analyze_and_suggest()
    
    if result.get('status') == 'insufficient_data':
        print('⚠️ Insufficient data for analysis (need at least 7 days)')
    else:
        issues_count = result.get('issues_found', 0)
        if issues_count > 0:
            print(f'💡 Found {issues_count} improvement suggestions')
            for issue in result.get('issues', []):
                severity = issue.get('severity', 'unknown')
                desc = issue.get('description', 'No description')
                print(f'   [{severity.upper()}] {desc}')
        else:
            print('✅ No issues detected - system performing well!')

asyncio.run(main())
"

echo "✅ Daily improvement check complete!"

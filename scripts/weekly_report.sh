#!/bin/bash
# 매주 월요일 오전 9시 실행
# Weekly report generation script
# cron: 0 9 * * 1 /path/to/project/scripts/weekly_report.sh

set -e

# Change to project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🚀 Generating weekly dashboard report..."

python -c "
from src.analytics.dashboard import UsageDashboard

dashboard = UsageDashboard()
result = dashboard.generate_weekly_report()

if 'error' in result:
    print(f'⚠️ Warning: {result[\"error\"]}')
else:
    print(f'📊 Report Summary:')
    print(f'   - Total sessions: {result.get(\"total_sessions\", 0)}')
    print(f'   - Total cost: \${result.get(\"total_cost_usd\", 0):.2f}')
    print(f'   - Cache hit rate: {result.get(\"cache_hit_rate\", 0):.1f}%')
"

echo "✅ Weekly report generation complete!"

# Optional: Send report via email
# mail -s 'Weekly Dashboard' your@email.com < reports/weekly_dashboard.html

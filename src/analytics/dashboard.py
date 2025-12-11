"""사용 현황 대시보드 - Usage pattern analytics and reporting."""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class UsageDashboard:
    """사용 패턴 분석 및 리포트 생성.

    Usage pattern analysis and weekly report generation.
    """

    def __init__(self, stats_file: Path | None = None) -> None:
        """Initialize the dashboard.

        Args:
            stats_file: Path to the JSONL stats file. Defaults to cache_stats.jsonl
        """
        self.stats_file = stats_file or Path("cache_stats.jsonl")

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """Parse ISO timestamp string safely."""
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _sum_field(
        self,
        entries: list[dict[str, Any]],
        field: str,
        default: float = 0,
    ) -> float:
        """Sum a numeric field across entries."""
        return float(sum(float(e.get(field, default) or 0.0) for e in entries))

    def _load_last_n_days(self, days: int) -> list[dict[str, Any]]:
        """Load entries from the last n days.

        Args:
            days: Number of days to look back

        Returns:
            List of entry dictionaries
        """
        if not self.stats_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        entries: list[dict[str, Any]] = []

        try:
            with open(self.stats_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        # Parse timestamp if present
                        ts = self._parse_timestamp(entry.get("timestamp", ""))
                        if ts is None or ts.replace(tzinfo=None) >= cutoff:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to load stats file: {e}")

        return entries

    def generate_weekly_report(self) -> dict[str, Any]:
        """지난 7일 사용 현황 분석.

        Analyze usage patterns for the last 7 days and generate an HTML report.

        Returns:
            Dictionary containing calculated statistics
        """
        # 1. 데이터 로드
        entries = self._load_last_n_days(7)

        if not entries:
            return {"error": "데이터 없음"}

        # 2. 주요 지표 계산
        stats: dict[str, Any] = {
            # 사용량
            "total_sessions": len(entries),
            "total_queries": self._sum_field(entries, "query_count"),
            "total_cost_usd": self._sum_field(entries, "cost"),
            # 성능
            "cache_hit_rate": self._calc_cache_hit_rate(entries),
            "avg_tokens_per_query": self._calc_avg_tokens(entries),
            # 트렌드 (이번주 vs 지난주)
            "cost_change_percent": self._calc_week_over_week(entries, "cost"),
            "quality_change_percent": self._calc_week_over_week(entries, "quality"),
            # 최다 사용 기능
            "top_features": self._top_features(entries),
            # 시간대별 분포
            "hourly_distribution": self._hourly_distribution(entries),
        }

        # 3. HTML 리포트 생성
        html = self._render_html(stats)
        output_path = Path("reports/weekly_dashboard.html")
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        logger.info(f"✅ 리포트 생성 완료: {output_path}")

        return stats

    def _calc_cache_hit_rate(self, entries: list[dict[str, Any]]) -> float:
        """캐시 hit rate 계산.

        Args:
            entries: List of entry dictionaries

        Returns:
            Cache hit rate as a percentage (0-100)
        """
        total_hits = self._sum_field(entries, "cache_hits")
        total_misses = self._sum_field(entries, "cache_misses")

        if total_hits + total_misses == 0:
            return 0.0

        return float((total_hits / (total_hits + total_misses)) * 100)

    def _calc_avg_tokens(self, entries: list[dict[str, Any]]) -> float:
        """Calculate average tokens per query.

        Args:
            entries: List of entry dictionaries

        Returns:
            Average tokens per query
        """
        total_tokens = self._sum_field(entries, "tokens")
        total_queries = self._sum_field(entries, "query_count", default=1) or 0

        if total_queries == 0:
            return 0.0

        return float(total_tokens / total_queries)

    def _calc_week_over_week(self, entries: list[dict[str, Any]], field: str) -> float:
        """Calculate week-over-week change percentage.

        Args:
            entries: List of entry dictionaries (assumed to be last 7 days)
            field: Field name to calculate change for

        Returns:
            Percentage change from previous week
        """
        # Load previous week data
        prev_entries = self._load_last_n_days(14)
        # Filter to only previous week (days 7-14)
        cutoff_recent = datetime.now() - timedelta(days=7)

        prev_week_entries = [
            e
            for e in prev_entries
            if (ts := self._parse_timestamp(e.get("timestamp", "")))
            and ts.replace(tzinfo=None) < cutoff_recent
        ]

        current_total = self._sum_field(entries, field)
        prev_total = self._sum_field(prev_week_entries, field)

        if prev_total == 0:
            return 0.0 if current_total == 0 else 100.0

        return float(((current_total - prev_total) / prev_total) * 100)

    def _top_features(self, entries: list[dict[str, Any]]) -> list[tuple[str, int]]:
        """Get top used features.

        Args:
            entries: List of entry dictionaries

        Returns:
            List of (feature_name, count) tuples, sorted by count descending
        """
        counter: Counter[str] = Counter()
        for e in entries:
            feature = e.get("feature", "unknown")
            if feature:
                counter[feature] += 1

        return counter.most_common(10)

    def _hourly_distribution(self, entries: list[dict[str, Any]]) -> dict[int, int]:
        """Get hourly usage distribution.

        Args:
            entries: List of entry dictionaries

        Returns:
            Dictionary mapping hour (0-23) to usage count
        """
        distribution: dict[int, int] = dict.fromkeys(range(24), 0)

        for e in entries:
            ts = self._parse_timestamp(e.get("timestamp", ""))
            if ts:
                hour = ts.hour
                distribution[hour] = distribution.get(hour, 0) + 1

        return distribution

    def get_today_stats(self) -> dict[str, Any]:
        """Get today's statistics.

        Returns:
            Dictionary containing today's stats
        """
        today = datetime.now().date()
        entries = self._load_last_n_days(1)

        # Filter to today only
        today_entries = [
            e
            for e in entries
            if (ts := self._parse_timestamp(e.get("timestamp", "")))
            and ts.date() == today
        ]

        return {
            "sessions": len(today_entries),
            "cost": sum(e.get("cost", 0) for e in today_entries),
            "cache_hit_rate": self._calc_cache_hit_rate(today_entries),
        }

    def get_week_total_cost(self) -> float:
        """Get total cost for the current week.

        Returns:
            Total cost in USD
        """
        entries = self._load_last_n_days(7)
        return float(sum(e.get("cost", 0) for e in entries))

    def get_week_avg_quality(self) -> float:
        """Get average quality score for the current week.

        Returns:
            Average quality score
        """
        entries = self._load_last_n_days(7)
        qualities = [e.get("quality", 0) for e in entries if "quality" in e]

        if not qualities:
            return 0.0

        return float(sum(qualities) / len(qualities))

    def _render_html(self, stats: dict[str, Any]) -> str:
        """HTML 리포트 렌더링.

        Args:
            stats: Dictionary containing calculated statistics

        Returns:
            HTML string for the dashboard
        """
        now = datetime.now()
        week_ago = now - timedelta(days=7)

        # Build feature list HTML
        features_html = ""
        top_features = stats.get("top_features", [])
        if top_features:
            features_html = "".join(
                f"<li>{feat}: {count}회</li>" for feat, count in top_features[:5]
            )
        else:
            features_html = "<li>데이터 없음</li>"

        # Build hourly distribution HTML
        hourly_html = ""
        hourly_dist = stats.get("hourly_distribution", {})
        if hourly_dist:
            hourly_html = "".join(
                f"<li>{hour}시: {count}회</li>"
                for hour, count in sorted(hourly_dist.items())
                if count > 0
            )
        if not hourly_html:
            hourly_html = "<li>데이터 없음</li>"

        # Determine trend direction
        cost_change = stats.get("cost_change_percent", 0)
        cost_trend_class = "trend-up" if cost_change > 0 else "trend-down"

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>사용 현황 대시보드</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 20px;
            background: #1e1e1e;
            color: #cccccc;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #252526;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #3e3e42;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #0078d4;
        }}
        .metric-label {{
            font-size: 0.9em;
            color: #999;
            margin-top: 5px;
        }}
        .trend-up {{ color: #4ec9b0; }}
        .trend-down {{ color: #f48771; }}
        h1 {{ color: #0078d4; }}
        h2 {{ color: #cccccc; border-bottom: 1px solid #3e3e42; padding-bottom: 10px; }}
        ul {{ list-style: none; padding-left: 0; }}
        li {{ padding: 5px 0; }}
    </style>
</head>
<body>
    <h1>📊 사용 현황 대시보드</h1>
    <p>기간: {week_ago.strftime("%Y-%m-%d")} ~ {now.strftime("%Y-%m-%d")}</p>

    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-value">{stats.get("total_sessions", 0)}</div>
            <div class="metric-label">총 세션 수</div>
        </div>

        <div class="metric-card">
            <div class="metric-value">${stats.get("total_cost_usd", 0):.2f}</div>
            <div class="metric-label">총 비용</div>
            <div class="{cost_trend_class}">
                {cost_change:+.1f}% (전주 대비)
            </div>
        </div>

        <div class="metric-card">
            <div class="metric-value">{stats.get("cache_hit_rate", 0):.1f}%</div>
            <div class="metric-label">캐시 Hit Rate</div>
        </div>

        <div class="metric-card">
            <div class="metric-value">{stats.get("avg_tokens_per_query", 0):.0f}</div>
            <div class="metric-label">평균 토큰/쿼리</div>
        </div>
    </div>

    <h2>🔥 최다 사용 기능</h2>
    <ul>
        {features_html}
    </ul>

    <h2>🕐 시간대별 사용량</h2>
    <ul>
        {hourly_html}
    </ul>
</body>
</html>
"""

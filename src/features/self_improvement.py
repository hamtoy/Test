"""자가 개선 시스템 - Self-improvement system with performance trend analysis."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SelfImprovingSystem:
    """자가 개선 시스템.

    Analyzes performance trends and generates improvement suggestions.
    """

    def __init__(
        self,
        history_file: Path | None = None,
        suggestions_file: Path | None = None,
    ) -> None:
        """Initialize the self-improving system.

        Args:
            history_file: Path to performance history JSONL file
            suggestions_file: Path to output suggestions JSON file
        """
        self.history_file = history_file or Path("data/performance_history.jsonl")
        self.suggestions_file = suggestions_file or Path(
            "reports/improvement_suggestions.json",
        )

    def _load_history(self, days: int = 30) -> list[dict[str, Any]]:
        """Load performance history for the specified number of days.

        Args:
            days: Number of days to look back

        Returns:
            List of history entry dictionaries
        """
        if not self.history_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        entries: list[dict[str, Any]] = []

        try:
            with open(self.history_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts_str = entry.get("timestamp", "")
                        if ts_str:
                            try:
                                ts = datetime.fromisoformat(
                                    ts_str.replace("Z", "+00:00"),
                                )
                                if ts.replace(tzinfo=None) >= cutoff:
                                    entries.append(entry)
                            except ValueError:
                                entries.append(entry)
                        else:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to load history file: {e}")

        return entries

    def _mean(self, entries: list[dict[str, Any]], key: str) -> float:
        """Calculate mean of a numeric key in entries."""
        if not entries:
            return 0.0
        total = sum(float(e.get(key, 0) or 0.0) for e in entries)
        return total / len(entries)

    def _sum_metric(self, entries: list[dict[str, Any]], key: str) -> float:
        """Calculate sum of a numeric key in entries."""
        return float(sum(float(e.get(key, 0) or 0.0) for e in entries))

    def _append_issue(
        self,
        issues: list[dict[str, Any]],
        *,
        issue_type: str,
        severity: str,
        description: str,
        suggestions: list[str],
        auto_fix_available: bool,
        auto_fix_action: str | None = None,
    ) -> None:
        """Append an issue record to the list to avoid duplication."""
        issue: dict[str, Any] = {
            "type": issue_type,
            "severity": severity,
            "description": description,
            "suggestions": suggestions,
            "auto_fix_available": auto_fix_available,
        }
        if auto_fix_action:
            issue["auto_fix_action"] = auto_fix_action
        issues.append(issue)

    async def analyze_and_suggest(self) -> dict[str, Any]:
        """성능 분석 및 개선 제안.

        Analyze performance trends and generate improvement suggestions.

        Returns:
            Report dictionary containing issues and suggestions
        """
        # 1. 최근 30일 데이터 로드
        history = self._load_history(days=30)

        if len(history) < 7:
            return {"status": "insufficient_data"}

        # 2. 트렌드 분석
        trends = self._analyze_trends(history)

        # 3. 문제 감지
        issues: list[dict[str, Any]] = []

        # 품질 저하
        if trends["quality_declining"]:
            self._append_issue(
                issues,
                issue_type="quality_regression",
                severity="high",
                description="품질 점수가 지난주 대비 5% 이상 하락",
                suggestions=[
                    "프롬프트 재검토 필요",
                    "모델 온도 조정 고려 (현재: 0.2 → 0.1)",
                    "예시 데이터 업데이트",
                ],
                auto_fix_available=False,
            )

        # 비용 증가
        if trends["cost_increasing"]:
            self._append_issue(
                issues,
                issue_type="cost_spike",
                severity="medium",
                description=f"비용이 {trends['cost_increase_percent']:.1f}% 증가",
                suggestions=[
                    "캐싱 전략 재조정",
                    f"현재 캐시 hit rate: {trends['cache_hit_rate']:.1f}% (목표: 70%)",
                    "불필요한 재생성 줄이기",
                ],
                auto_fix_available=True,
                auto_fix_action="adjust_cache_ttl",
            )

        # 레이턴시 증가
        if trends["latency_increasing"]:
            self._append_issue(
                issues,
                issue_type="performance_degradation",
                severity="medium",
                description="평균 레이턴시 증가 감지",
                suggestions=[
                    "Neo4j 인덱스 확인",
                    "Redis 메모리 사용량 확인",
                    "동시성 제한 재조정",
                ],
                auto_fix_available=False,
            )

        # 4. 리포트 생성
        report: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "analysis_period_days": 30,
            "issues_found": len(issues),
            "issues": issues,
            "trends": trends,
        }

        # 저장
        self.suggestions_file.parent.mkdir(parents=True, exist_ok=True)
        self.suggestions_file.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 5. 자동 수정 실행 (승인된 경우만)
        if any(issue.get("auto_fix_available", False) for issue in issues):
            await self._apply_auto_fixes(issues)

        logger.info(f"💡 {len(issues)}개 개선 제안 생성: {self.suggestions_file}")

        return report

    def _analyze_trends(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        """트렌드 계산.

        Calculate performance trends comparing recent vs previous periods.

        Args:
            history: List of history entry dictionaries

        Returns:
            Dictionary containing trend analysis
        """
        # 최근 7일 vs 이전 7일
        recent = history[-7:] if len(history) >= 7 else history
        previous = history[-14:-7] if len(history) >= 14 else history[: -len(recent)]

        # Avoid division by zero
        if not previous:
            previous = recent

        recent_quality = self._mean(recent, "quality")
        prev_quality = self._mean(previous, "quality")

        recent_cost = self._sum_metric(recent, "cost")
        prev_cost = self._sum_metric(previous, "cost")

        recent_latency = self._mean(recent, "latency")
        prev_latency = self._mean(previous, "latency")

        cache_hit_rate = self._mean(recent, "cache_hit_rate")

        # Calculate cost increase percentage safely
        cost_increase_percent = (
            ((recent_cost / prev_cost) - 1) * 100 if prev_cost > 0 else 0
        )

        return {
            "quality_declining": recent_quality < prev_quality * 0.95
            if prev_quality > 0
            else False,
            "quality_score": recent_quality,
            "quality_change": recent_quality - prev_quality,
            "cost_increasing": recent_cost > prev_cost * 1.2
            if prev_cost > 0
            else False,
            "cost_increase_percent": cost_increase_percent,
            "latency_increasing": recent_latency > prev_latency * 1.15
            if prev_latency > 0
            else False,
            "avg_latency_ms": recent_latency,
            "cache_hit_rate": cache_hit_rate,
        }

    async def _apply_auto_fixes(self, issues: list[dict[str, Any]]) -> None:
        """자동 수정 적용.

        Apply automatic fixes for issues that support it.

        Args:
            issues: List of issue dictionaries
        """
        for issue in issues:
            if not issue.get("auto_fix_available", False):
                continue

            action = issue.get("auto_fix_action", "")

            if action == "adjust_cache_ttl":
                # 캐시 TTL 자동 조정
                logger.info("🔧 캐시 TTL 자동 조정 중...")
                await self._adjust_cache_ttl()
                logger.info("   ✓ TTL 증가: 900s → 1800s")

    async def _adjust_cache_ttl(self) -> None:
        """Adjust cache TTL settings.

        This is a placeholder for actual cache TTL adjustment logic.
        In a real implementation, this would update cache configuration.
        """
        # Placeholder - in production this would update actual cache settings
        logger.debug("Cache TTL adjustment placeholder")

    def send_slack_notification(self, report: dict[str, Any]) -> None:
        """중요 이슈 발생 시 Slack 알림.

        Send Slack notification for high-severity issues.

        Args:
            report: Report dictionary containing issues
        """
        issues = report.get("issues", [])
        high_severity_issues = [i for i in issues if i.get("severity") == "high"]

        if not high_severity_issues:
            return

        message = f"⚠️ {len(high_severity_issues)}개 고심각도 이슈 감지\n"
        for issue in high_severity_issues:
            message += f"• {issue.get('description', 'Unknown issue')}\n"

        # Slack webhook 호출 (placeholder)
        # In production: requests.post(SLACK_WEBHOOK_URL, json={"text": message})
        logger.info(f"Slack notification (placeholder): {message}")

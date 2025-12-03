# src/qa/ab_test.py
"""A/B Testing Framework for Prompt Optimization in hamtoy/Test.

Comparing different prompt strategies for OCR and RAG tasks.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.agent.core import GeminiAgent

logger = logging.getLogger(__name__)

# Cost estimation constants (Gemini API pricing approximation)
CHARS_PER_TOKEN = 4  # Approximate characters per token
INPUT_TOKEN_COST = 0.000125  # Cost per input token (in millionths of USD)
OUTPUT_TOKEN_COST = 0.000375  # Cost per output token (in millionths of USD)
COST_DIVISOR = 1000  # Divisor to convert to actual USD


@dataclass
class ExperimentResult:
    """Result of a single experiment run."""

    variant_name: str
    input_id: str
    response: str
    latency: float
    token_count: int
    cost: float
    success: bool
    error_msg: Optional[str] = None


@dataclass
class ExperimentConfig:
    """Configuration for an A/B test experiment."""

    name: str
    control_prompt_template: str
    treatment_prompt_template: str
    sample_size: int = 10
    output_dir: str = "experiments/results"


class PromptExperimentManager:
    """Manager for running A/B test experiments comparing prompt variants."""

    def __init__(self, agent: "GeminiAgent"):
        """Initialize the experiment manager.

        Args:
            agent: GeminiAgent instance for generating responses
        """
        self.agent = agent
        self.results: List[ExperimentResult] = []

    async def run_experiment(
        self,
        config: ExperimentConfig,
        test_dataset: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run A/B test comparing Control vs Treatment prompts.

        Args:
            config: Experiment configuration
            test_dataset: List of inputs (e.g., OCR text, user queries)

        Returns:
            Experiment report with metrics and comparison
        """
        logger.info("Starting experiment: %s", config.name)
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)

        samples = test_dataset[: config.sample_size]

        # Run Control (Variant A)
        logger.info("Running Control Group (Variant A)...")
        control_results = await self._run_batch(
            "control",
            config.control_prompt_template,
            samples,
        )

        # Run Treatment (Variant B)
        logger.info("Running Treatment Group (Variant B)...")
        treatment_results = await self._run_batch(
            "treatment",
            config.treatment_prompt_template,
            samples,
        )

        # Save and Analyze
        self.results.extend(control_results + treatment_results)
        report = self._generate_report(config.name, control_results, treatment_results)

        self._save_results(config, report)
        return report

    async def _run_batch(
        self,
        variant: str,
        template_name: str,
        samples: List[Dict[str, Any]],
    ) -> List[ExperimentResult]:
        """Run a batch of experiments for a variant.

        Args:
            variant: Variant name (control or treatment)
            template_name: Template name to use for generation
            samples: List of input samples

        Returns:
            List of experiment results
        """
        results = []

        for item in samples:
            start_time = time.time()
            try:
                # Call agent.generate_query with optional template_name
                response = await self.agent.generate_query(
                    ocr_text=item["input_text"],
                    user_intent=item.get("user_intent"),
                    template_name=template_name,
                )

                latency = time.time() - start_time

                # Calculate cost using defined constants
                input_tokens = len(item["input_text"]) / CHARS_PER_TOKEN
                output_tokens = len(str(response)) / CHARS_PER_TOKEN
                cost = (
                    input_tokens * INPUT_TOKEN_COST + output_tokens * OUTPUT_TOKEN_COST
                ) / COST_DIVISOR

                results.append(
                    ExperimentResult(
                        variant_name=variant,
                        input_id=item.get("id", "unknown"),
                        response=str(response),
                        latency=latency,
                        token_count=int(input_tokens + output_tokens),
                        cost=cost,
                        success=True,
                    )
                )

            except Exception as e:
                logger.error("Error in %s: %s", variant, str(e))
                results.append(
                    ExperimentResult(
                        variant_name=variant,
                        input_id=item.get("id", "unknown"),
                        response="",
                        latency=time.time() - start_time,
                        token_count=0,
                        cost=0.0,
                        success=False,
                        error_msg=str(e),
                    )
                )

        return results

    def _generate_report(
        self,
        exp_name: str,
        control: List[ExperimentResult],
        treatment: List[ExperimentResult],
    ) -> Dict[str, Any]:
        """Generate experiment report comparing control and treatment groups.

        Args:
            exp_name: Experiment name
            control: Control group results
            treatment: Treatment group results

        Returns:
            Report dictionary with metrics and comparison
        """

        def avg(items: List[ExperimentResult], key: str) -> float:
            """Calculate average value for a given attribute."""
            valid = [float(getattr(i, key)) for i in items if i.success]
            return (sum(valid) / len(valid)) if len(valid) > 0 else 0.0

        control_success = [i for i in control if i.success]
        treatment_success = [i for i in treatment if i.success]

        report: Dict[str, Any] = {
            "experiment": exp_name,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "control": {
                "avg_latency": avg(control, "latency"),
                "avg_cost": avg(control, "cost"),
                "success_rate": len(control_success) / len(control) if control else 0,
            },
            "treatment": {
                "avg_latency": avg(treatment, "latency"),
                "avg_cost": avg(treatment, "cost"),
                "success_rate": (
                    len(treatment_success) / len(treatment) if treatment else 0
                ),
            },
            "winner": "TBD",
        }

        # Winner determination logic with more nuanced comparison
        control_latency = report["control"]["avg_latency"]
        treatment_latency = report["treatment"]["avg_latency"]
        control_cost = report["control"]["avg_cost"]
        treatment_cost = report["treatment"]["avg_cost"]

        latency_better = treatment_latency < control_latency
        cost_better = treatment_cost < control_cost

        if latency_better and cost_better:
            report["winner"] = "Treatment (Faster & Cheaper)"
        elif latency_better and not cost_better:
            report["winner"] = (
                "Treatment (Faster, Higher Cost) - Manual Review Required"
            )
        elif not latency_better and cost_better:
            report["winner"] = "Treatment (Slower, Lower Cost) - Manual Review Required"
        else:
            report["winner"] = "Control (No Improvement)"

        return report

    def _save_results(
        self,
        config: ExperimentConfig,
        report: Dict[str, Any],
    ) -> None:
        """Save experiment results to a JSON file.

        Args:
            config: Experiment configuration
            report: Experiment report dictionary
        """
        path = Path(config.output_dir) / f"{config.name}_{int(time.time())}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("Experiment report saved to %s", path)

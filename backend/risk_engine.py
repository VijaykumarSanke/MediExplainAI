"""
risk_engine.py – Benchmark Comparison & Risk Scoring Engine
============================================================
Architecture Role: Layer 3 – Benchmark Comparison Engine
                   Layer 4 – Risk Scoring Engine
Responsibility:
    - Load benchmark.json
    - Compare extracted lab values against normal ranges
    - Label each test: Low | Normal | High
    - Compute a weighted risk score
    - Map score to a risk category
    - Detect lightweight correlation patterns (anemia, cardiovascular)
"""

import json
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
import pandas as pd

logger = logging.getLogger(__name__)

# Path to benchmark database (relative to this file)
_BENCHMARK_PATH = Path(__file__).parent / "benchmark.json"

# ---------------------------------------------------------------------------
# Risk category thresholds (from specification)
# ---------------------------------------------------------------------------
RISK_THRESHOLDS = [
    (0,   "Stable"),
    (2,   "Monitor"),        # score 1–2
    (4,   "Moderate Concern"),  # score 3–4
    (9999, "Elevated Risk"),    # score 5+
]


def _load_benchmarks() -> dict:
    """Load and return the benchmark.json database."""
    try:
        with open(_BENCHMARK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(
            f"benchmark.json not found at {_BENCHMARK_PATH}. "
            "Ensure the file exists in the backend directory."
        )


@dataclass
class TestResult:
    """Holds the analysis result for a single lab test."""
    test_name: str
    measured_value: float
    unit: str
    reference_range: str
    status: str           # "Low" | "Normal" | "High" | "Unknown"
    normal_min: float = 0.0
    normal_max: float = 0.0
    risk_weight: int = 0
    description: str = ""
    status_description: str = ""
    in_benchmark: bool = True
    is_critical: bool = False


@dataclass
class AnalysisReport:
    """Full analysis result for one lab report."""
    results: list[TestResult] = field(default_factory=list)
    risk_score: float = 0.0
    risk_category: str = "Stable"
    abnormal_count: int = 0
    patterns: list[dict] = field(default_factory=list)
    trends: list[dict] = field(default_factory=list)

class RiskEngine:
    """
    Compares extracted lab values against benchmarks,
    scores risk, and detects correlation patterns.
    """

    def __init__(self):
        data = _load_benchmarks()
        self.benchmarks: dict = data.get("tests", {})
        self.correlations: list = data.get("correlations", [])
        logger.info("RiskEngine loaded %d benchmark tests.", len(self.benchmarks))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(self, df: pd.DataFrame, historical_df: pd.DataFrame = None) -> AnalysisReport:
        """
        Run the full analysis pipeline on extracted lab values.

        Parameters
        ----------
        df : pd.DataFrame
            Output of parser.parse_pdf() with columns:
            [test_name, measured_value, unit, reference_range]
        historical_df : pd.DataFrame, optional
            Output of a previous parser.parse_pdf() to compare against.

        Returns
        -------
        AnalysisReport
        """
        report = AnalysisReport()

        for _, row in df.iterrows():
            result = self._evaluate_test(row)
            report.results.append(result)

        # Compute weighted risk score (only from abnormal tests)
        report.risk_score = sum(
            r.risk_weight for r in report.results if r.status in ("Low", "High")
        )

        # Map score to category
        report.risk_category = self._score_to_category(report.risk_score)

        # Count abnormal tests
        report.abnormal_count = sum(
            1 for r in report.results if r.status in ("Low", "High")
        )

        # Detect correlation patterns
        report.patterns = self._detect_patterns(report.results)

        # Detect trends if we have historical data
        if historical_df is not None and not historical_df.empty:
            report.trends = self._analyze_trends(report.results, historical_df)

        logger.info(
            "Analysis complete: %d tests, score=%.1f, category=%s, patterns=%d, trends=%d",
            len(report.results),
            report.risk_score,
            report.risk_category,
            len(report.patterns),
            len(report.trends),
        )
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_benchmark(self, test_name: str):
        """
        Find the best matching benchmark for a test name.
        Tries exact match first, then case-insensitive, then substring.
        Returns (benchmark_key, benchmark_data) or (None, None).
        """
        # 1. Exact match
        if test_name in self.benchmarks:
            return test_name, self.benchmarks[test_name]

        # 2. Case-insensitive match
        lower_name = test_name.lower().strip()
        for key, bm in self.benchmarks.items():
            if key.lower() == lower_name:
                return key, bm

        # 3. Substring match — benchmark key is IN the test name or vice versa
        #    Only match if the key is at least 3 chars to avoid false positives
        for key, bm in self.benchmarks.items():
            key_lower = key.lower()
            if len(key_lower) >= 3 and (key_lower in lower_name or lower_name in key_lower):
                return key, bm

        return None, None

    def _evaluate_test(self, row) -> TestResult:
        """Evaluate a single test row against the benchmark."""
        test_name = row["test_name"]
        value = float(row["measured_value"])
        unit = str(row.get("unit", ""))
        ref_range = str(row.get("reference_range", ""))

        bm_key, bm = self._find_benchmark(test_name)

        if bm is None:
            # Test not in benchmark — try to use PDF reference range
            status = "Unknown"
            status_desc = "This test was not found in our reference database."

            # Attempt to parse reference range from PDF (e.g. "70-99")
            ref_match = re.match(r"(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)", ref_range)
            if ref_match:
                ref_min = float(ref_match.group(1))
                ref_max = float(ref_match.group(2))
                if value < ref_min:
                    status = "Low"
                    status_desc = f"Below the reference range ({ref_range})."
                elif value > ref_max:
                    status = "High"
                    status_desc = f"Above the reference range ({ref_range})."
                else:
                    status = "Normal"
                    status_desc = "Within the reference range."

            logger.debug("Test '%s' not found in benchmark DB. Status from PDF range: %s", test_name, status)
            return TestResult(
                test_name=test_name,
                measured_value=value,
                unit=unit,
                reference_range=ref_range,
                status=status,
                in_benchmark=False,
                description="This test was not found in our reference database.",
                status_description=status_desc,
            )

        min_val = float(bm["normal_min"])
        max_val = float(bm["normal_max"])
        risk_weight = int(bm.get("risk_weight", 1))

        is_critical = False
        
        # Determine status
        if value < min_val:
            status = "Low"
            status_desc = bm.get("low_description", "")
            if "critical_min" in bm and value <= float(bm["critical_min"]):
                is_critical = True
        elif value > max_val:
            status = "High"
            status_desc = bm.get("high_description", "")
            if "critical_max" in bm and value >= float(bm["critical_max"]):
                is_critical = True
        else:
            status = "Normal"
            status_desc = "This value is within the typical reference range."

        return TestResult(
            test_name=test_name,
            measured_value=value,
            unit=unit,
            reference_range=ref_range,
            status=status,
            normal_min=min_val,
            normal_max=max_val,
            risk_weight=risk_weight if status != "Normal" else 0,
            description=bm.get("description", ""),
            status_description=status_desc,
            in_benchmark=True,
            is_critical=is_critical,
        )

    def _score_to_category(self, score: float) -> str:
        """Map numeric risk score to a qualitative risk category."""
        if score == 0:
            return "Stable"
        for threshold, category in RISK_THRESHOLDS:
            if score <= threshold:
                return category
        return "Elevated Risk"

    def _detect_patterns(self, results: list[TestResult]) -> list[dict]:
        """
        Lightweight correlation pattern detection.
        Checks predefined patterns from benchmark.json correlations list.
        Does NOT diagnose — only surfaces educational observations.
        """
        status_map = {r.test_name: r.status for r in results}
        matched_patterns = []

        for corr in self.correlations:
            tests = corr["tests"]
            conditions = corr["conditions"]

            # Check all tests in the pattern are present and match conditions
            if all(
                status_map.get(t) == c for t, c in zip(tests, conditions)
            ):
                matched_patterns.append(
                    {
                        "id": corr["id"],
                        "tests": tests,
                        "message": corr["message"],
                    }
                )

        return matched_patterns

    def _analyze_trends(self, current_results: list[TestResult], historical_df: pd.DataFrame) -> list[dict]:
        """
        Compare current results to a historical DataFrame and detect trends.
        """
        trends = []
        historical_dict = {}
        for _, row in historical_df.iterrows():
            historical_dict[row["test_name"].lower().strip()] = row

        for r in current_results:
            key = r.test_name.lower().strip()
            if key in historical_dict:
                hist_row = historical_dict[key]
                try:
                    hist_val = float(hist_row["measured_value"])
                    curr_val = r.measured_value
                    if hist_val == 0:
                        continue
                        
                    pct_change = ((curr_val - hist_val) / hist_val) * 100
                    
                    if abs(pct_change) < 5:
                        trend_type = "Stable"
                    elif pct_change >= 20:
                        trend_type = "Rapid change" if curr_val > hist_val else "Rapid change (decrease)"
                    elif pct_change > 5:
                        trend_type = "Gradually increasing"
                    else:
                        trend_type = "Gradually decreasing"
                        
                    trends.append({
                        "test_name": r.test_name,
                        "current_value": curr_val,
                        "historical_value": hist_val,
                        "unit": r.unit,
                        "trend_type": trend_type,
                        "percent_change": round(pct_change, 1)
                    })
                except ValueError:
                    pass
                    
        return trends


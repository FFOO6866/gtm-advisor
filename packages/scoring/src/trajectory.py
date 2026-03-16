"""Growth Trajectory Engine — deterministic, no LLM.

Operates on CompanyFinancialSnapshot time-series to compute:
  - Revenue CAGR (3-year and 5-year)
  - Acceleration classification
  - Margin trends (gross, operating, net)
  - GTM efficiency trends (SG&A, R&D intensity)
  - FCF conversion trend
  - Overall trajectory classification

All methods are synchronous, pure, and thread-safe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class TrajectoryReport:
    """Output of TrajectoryEngine.compute()."""

    ticker: str
    name: str
    periods_analyzed: int
    # Growth
    revenue_cagr_3y: float | None
    revenue_cagr_5y: float | None
    acceleration: str  # "accelerating" | "stable" | "decelerating"
    # Margins
    gross_margin_trend: str  # "expanding" | "stable" | "compressing"
    operating_margin_trend: str
    net_margin_trend: str
    # GTM efficiency
    sga_efficiency_trend: str  # "improving" | "stable" | "declining"
    rnd_intensity_trend: str   # "expanding" | "stable" | "compressing" (raw trend — not inverted)
    # Cash
    fcf_conversion_trend: str  # "improving" | "stable" | "declining"
    # Overall
    trajectory_class: str  # "ACCELERATING" | "STABLE" | "DECELERATING" | "TURNAROUND" | "INSUFFICIENT_DATA"
    narrative: str  # 2-3 sentence deterministic summary

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "periods_analyzed": self.periods_analyzed,
            "revenue_cagr_3y": self.revenue_cagr_3y,
            "revenue_cagr_5y": self.revenue_cagr_5y,
            "acceleration": self.acceleration,
            "gross_margin_trend": self.gross_margin_trend,
            "operating_margin_trend": self.operating_margin_trend,
            "net_margin_trend": self.net_margin_trend,
            "sga_efficiency_trend": self.sga_efficiency_trend,
            "rnd_intensity_trend": self.rnd_intensity_trend,
            "fcf_conversion_trend": self.fcf_conversion_trend,
            "trajectory_class": self.trajectory_class,
            "narrative": self.narrative,
        }


# Minimum periods required for meaningful analysis
_MIN_PERIODS = 3


class TrajectoryEngine:
    """Deterministic growth trajectory analysis — no LLM, stdlib only."""

    def compute(self, snapshots: list[dict]) -> TrajectoryReport:
        """Compute trajectory report from a time-ordered list of snapshot dicts.

        Each dict should have keys matching CompanyFinancialSnapshot columns:
        revenue, gross_margin, operating_margin, net_margin,
        sga_to_revenue, rnd_to_revenue, free_cash_flow, revenue_growth_yoy,
        period_end_date, and optionally ticker/name.

        Snapshots must be ordered oldest-first (ascending by period_end_date).
        """
        ticker = snapshots[0].get("ticker", "UNKNOWN") if snapshots else "UNKNOWN"
        name = snapshots[0].get("name", ticker) if snapshots else ticker
        n = len(snapshots)

        if n < _MIN_PERIODS:
            return TrajectoryReport(
                ticker=ticker,
                name=name,
                periods_analyzed=n,
                revenue_cagr_3y=None,
                revenue_cagr_5y=None,
                acceleration="stable",
                gross_margin_trend="stable",
                operating_margin_trend="stable",
                net_margin_trend="stable",
                sga_efficiency_trend="stable",
                rnd_intensity_trend="stable",
                fcf_conversion_trend="stable",
                trajectory_class="INSUFFICIENT_DATA",
                narrative=f"Only {n} period(s) available — insufficient for trajectory analysis.",
            )

        # Extract revenue series for CAGR — pair each revenue with its
        # snapshot index so we can compute actual year span from period_end_date
        # (not just position distance, which breaks when years are missing).
        valid_rev_entries = [
            (i, s.get("revenue"))
            for i, s in enumerate(snapshots)
            if s.get("revenue") is not None and s.get("revenue") > 0
        ]

        revenue_cagr_3y = None
        revenue_cagr_5y = None
        if len(valid_rev_entries) >= 2:
            end_idx, end_rev = valid_rev_entries[-1]
            # 3-year: find the valid revenue closest to 3 periods back
            if len(valid_rev_entries) >= 4:
                start_idx, start_rev = valid_rev_entries[-4]
                years = _year_span(snapshots, start_idx, end_idx)
                if years > 0:
                    revenue_cagr_3y = self._cagr(start_rev, end_rev, years)
            # 5-year: find the valid revenue closest to 5 periods back
            if len(valid_rev_entries) >= 6:
                start_idx, start_rev = valid_rev_entries[-6]
                years = _year_span(snapshots, start_idx, end_idx)
                if years > 0:
                    revenue_cagr_5y = self._cagr(start_rev, end_rev, years)

        # Growth rates for acceleration detection
        growth_rates = [s.get("revenue_growth_yoy") for s in snapshots]
        valid_growth = [g for g in growth_rates if g is not None]
        acceleration = self._acceleration(valid_growth)

        # Margin trends
        gross_margins = [s.get("gross_margin") for s in snapshots]
        operating_margins = [s.get("operating_margin") for s in snapshots]
        net_margins = [s.get("net_margin") for s in snapshots]
        gross_margin_trend = self._trend(gross_margins)
        operating_margin_trend = self._trend(operating_margins)
        net_margin_trend = self._trend(net_margins)

        # GTM efficiency: SG&A/revenue declining = improving efficiency
        sga_ratios = [s.get("sga_to_revenue") for s in snapshots]
        sga_trend_raw = self._trend(sga_ratios)
        # Invert: compressing SG&A ratio means improving efficiency
        sga_efficiency_trend = _invert_trend(sga_trend_raw)

        rnd_ratios = [s.get("rnd_to_revenue") for s in snapshots]
        rnd_intensity_trend = self._trend(rnd_ratios)

        # FCF conversion: free_cash_flow / revenue
        fcf_conversions = []
        for s in snapshots:
            fcf = s.get("free_cash_flow")
            rev = s.get("revenue")
            if fcf is not None and rev is not None and rev > 0:
                fcf_conversions.append(fcf / rev)
            else:
                fcf_conversions.append(None)
        fcf_conversion_trend = self._trend(fcf_conversions)

        # Overall trajectory classification
        trajectory_class = self._classify(
            acceleration=acceleration,
            gross_margin_trend=gross_margin_trend,
            operating_margin_trend=operating_margin_trend,
            revenue_cagr_3y=revenue_cagr_3y,
        )

        # Generate narrative
        narrative = self._narrative(
            ticker=ticker,
            name=name,
            trajectory_class=trajectory_class,
            revenue_cagr_3y=revenue_cagr_3y,
            acceleration=acceleration,
            gross_margin_trend=gross_margin_trend,
            operating_margin_trend=operating_margin_trend,
            sga_efficiency_trend=sga_efficiency_trend,
        )

        return TrajectoryReport(
            ticker=ticker,
            name=name,
            periods_analyzed=n,
            revenue_cagr_3y=revenue_cagr_3y,
            revenue_cagr_5y=revenue_cagr_5y,
            acceleration=acceleration,
            gross_margin_trend=gross_margin_trend,
            operating_margin_trend=operating_margin_trend,
            net_margin_trend=net_margin_trend,
            sga_efficiency_trend=sga_efficiency_trend,
            rnd_intensity_trend=rnd_intensity_trend,
            fcf_conversion_trend=fcf_conversion_trend,
            trajectory_class=trajectory_class,
            narrative=narrative,
        )

    def _cagr(self, start: float, end: float, years: int) -> float | None:
        """Compound Annual Growth Rate. Returns None if inputs invalid."""
        if start <= 0 or end <= 0 or years <= 0:
            return None
        try:
            return (end / start) ** (1.0 / years) - 1.0
        except (ZeroDivisionError, OverflowError, ValueError):
            return None

    def _trend(self, values: list[float | None]) -> str:
        """Determine trend direction using linear regression slope.

        Returns "expanding" | "stable" | "compressing" based on the slope
        relative to the mean absolute value of the series.
        """
        clean = [(i, v) for i, v in enumerate(values) if v is not None and math.isfinite(v)]
        if len(clean) < _MIN_PERIODS:
            return "stable"

        n = len(clean)
        sum_x = sum(x for x, _ in clean)
        sum_y = sum(y for _, y in clean)
        sum_xy = sum(x * y for x, y in clean)
        sum_x2 = sum(x * x for x, _ in clean)

        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            return "stable"

        slope = (n * sum_xy - sum_x * sum_y) / denom
        mean_abs = sum(abs(y) for _, y in clean) / n if n > 0 else 0

        # Normalize slope: how much does the metric change per period relative to its scale
        if mean_abs < 1e-9:
            return "stable"

        normalized = slope / mean_abs

        if normalized > 0.03:  # >3% of mean per period
            return "expanding"
        elif normalized < -0.03:
            return "compressing"
        return "stable"

    def _acceleration(self, growth_rates: list[float]) -> str:
        """Determine if growth is accelerating, stable, or decelerating.

        Compares the slope of the growth rate series itself.
        """
        if len(growth_rates) < _MIN_PERIODS:
            return "stable"

        # Use second half vs first half comparison
        mid = len(growth_rates) // 2
        first_half_avg = sum(growth_rates[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(growth_rates[mid:]) / (len(growth_rates) - mid) if (len(growth_rates) - mid) > 0 else 0

        diff = second_half_avg - first_half_avg

        if diff > 0.03:  # 3pp acceleration
            return "accelerating"
        elif diff < -0.03:  # 3pp deceleration
            return "decelerating"
        return "stable"

    def _classify(
        self,
        acceleration: str,
        gross_margin_trend: str,
        operating_margin_trend: str,
        revenue_cagr_3y: float | None,
    ) -> str:
        """Classify overall trajectory."""
        is_growing = revenue_cagr_3y is not None and revenue_cagr_3y > 0.05
        is_shrinking = revenue_cagr_3y is not None and revenue_cagr_3y < -0.05
        margins_expanding = gross_margin_trend == "expanding" or operating_margin_trend == "expanding"
        margins_compressing = gross_margin_trend == "compressing" and operating_margin_trend == "compressing"

        if acceleration == "accelerating" and is_growing:
            return "ACCELERATING"
        if is_shrinking and margins_expanding:
            return "TURNAROUND"
        if acceleration == "decelerating" or (is_shrinking and margins_compressing):
            return "DECELERATING"
        return "STABLE"

    def _narrative(
        self,
        ticker: str,
        name: str,
        trajectory_class: str,
        revenue_cagr_3y: float | None,
        acceleration: str,  # noqa: ARG002
        gross_margin_trend: str,
        operating_margin_trend: str,
        sga_efficiency_trend: str,
    ) -> str:
        """Generate a 2-3 sentence deterministic narrative."""
        parts: list[str] = []

        # Sentence 1: growth trajectory
        cagr_str = f"{revenue_cagr_3y:.0%}" if revenue_cagr_3y is not None else "N/A"
        if trajectory_class == "ACCELERATING":
            parts.append(
                f"{name} ({ticker}) shows accelerating growth with a 3-year revenue CAGR of {cagr_str}."
            )
        elif trajectory_class == "DECELERATING":
            parts.append(
                f"{name} ({ticker}) shows decelerating growth; 3-year revenue CAGR is {cagr_str}."
            )
        elif trajectory_class == "TURNAROUND":
            parts.append(
                f"{name} ({ticker}) appears to be in a turnaround phase with improving margins despite a {cagr_str} revenue CAGR."
            )
        else:
            parts.append(
                f"{name} ({ticker}) exhibits stable growth with a 3-year revenue CAGR of {cagr_str}."
            )

        # Sentence 2: margin dynamics
        if gross_margin_trend == "expanding" and operating_margin_trend == "expanding":
            parts.append("Both gross and operating margins are expanding, indicating improving unit economics.")
        elif gross_margin_trend == "compressing":
            parts.append("Gross margins are compressing, suggesting pricing pressure or rising input costs.")
        elif operating_margin_trend == "compressing":
            parts.append("Operating margins are under pressure despite stable gross margins.")

        # Sentence 3: GTM efficiency
        if sga_efficiency_trend == "improving":
            parts.append("SG&A efficiency is improving — the company is generating more revenue per marketing dollar.")
        elif sga_efficiency_trend == "declining":
            parts.append("SG&A efficiency is declining — sales and marketing costs are growing faster than revenue.")

        return " ".join(parts) if parts else f"{name} ({ticker}) has a {trajectory_class.lower()} trajectory."


def _year_span(snapshots: list[dict], start_idx: int, end_idx: int) -> int:
    """Compute actual year span between two snapshot positions.

    Uses period_end_date (e.g. "2021-12-31") to compute real calendar year
    difference. Falls back to index distance if dates are unavailable/unparseable.
    """
    try:
        start_date = snapshots[start_idx].get("period_end_date", "")
        end_date = snapshots[end_idx].get("period_end_date", "")
        if start_date and end_date:
            start_year = int(str(start_date)[:4])
            end_year = int(str(end_date)[:4])
            span = end_year - start_year
            if span > 0:
                return span
    except (ValueError, TypeError, IndexError):
        pass
    # Fallback: index distance (correct when every year has data)
    return end_idx - start_idx


def _invert_trend(trend: str) -> str:
    """Invert a trend label (for metrics where declining is good)."""
    if trend == "expanding":
        return "declining"
    if trend == "compressing":
        return "improving"
    return "stable"

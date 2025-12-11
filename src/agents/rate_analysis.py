"""
Rate Analysis Agent - Market rate analysis and pricing optimization.

This agent:
- Analyzes historical rate data for specific lanes
- Identifies market trends and seasonal patterns
- Calculates optimal pricing for competitive advantage
- Provides negotiation guidance for brokers
"""

import json
from datetime import datetime
from decimal import Decimal
from time import time
from typing import Any, Optional

from pydantic import BaseModel

from src.agents.base import AgentDecision, BaseAgent


class LaneRate(BaseModel):
    """Rate information for a specific lane."""

    origin_city: str
    origin_state: str
    destination_city: str
    destination_state: str
    distance_miles: int
    rate_per_mile: Decimal
    total_rate: Decimal
    timestamp: datetime


class RateAnalysisResult(BaseModel):
    """Result of rate analysis for a lane."""

    lane_description: str
    distance_miles: int

    # Rate statistics
    current_market_rate: Optional[Decimal] = None
    recommended_rate: Decimal
    minimum_acceptable_rate: Decimal
    target_rate: Decimal

    # Market insights
    market_trend: str  # "rising", "falling", "stable"
    confidence_level: float  # 0.0 to 1.0
    reasoning: str

    # Historical context
    historical_average: Optional[Decimal] = None
    rate_range_low: Optional[Decimal] = None
    rate_range_high: Optional[Decimal] = None

    # Recommendations
    negotiation_tips: list[str]
    risk_factors: list[str]

    timestamp: datetime
    execution_time_seconds: float


class RateAnalysisAgent(BaseAgent):
    """
    Rate Analysis Agent for market rate analysis and pricing.

    Uses LLM to:
    - Analyze market conditions
    - Identify rate trends
    - Provide pricing recommendations
    - Guide negotiation strategy
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the rate analysis agent."""
        super().__init__(agent_name="rate_analysis", **kwargs)

        # Load business configuration
        self.rate_thresholds = self.config_manager.get_rate_thresholds()
        self.operating_costs = self.config_manager.get_operating_costs()

    def analyze_lane(
        self,
        origin_city: str,
        origin_state: str,
        destination_city: str,
        destination_state: str,
        distance_miles: int,
        historical_rates: Optional[list[LaneRate]] = None,
    ) -> RateAnalysisResult:
        """
        Analyze rates for a specific lane.

        Args:
            origin_city: Origin city
            origin_state: Origin state
            destination_city: Destination city
            destination_state: Destination state
            distance_miles: Distance in miles
            historical_rates: Optional list of historical rates for this lane

        Returns:
            RateAnalysisResult with recommendations
        """
        start_time = time()

        lane_desc = f"{origin_city}, {origin_state} → {destination_city}, {destination_state}"
        self.logger.info("analyzing_lane", lane=lane_desc, distance=distance_miles)

        # Calculate baseline rates from business rules
        min_rpm = Decimal(str(self.rate_thresholds.get("minimum_rate_per_mile", 2.0)))
        target_rpm = Decimal(str(self.rate_thresholds.get("target_rate_per_mile", 2.5)))

        min_acceptable = min_rpm * distance_miles
        target_rate = target_rpm * distance_miles

        # Analyze historical data if available
        historical_avg = None
        rate_low = None
        rate_high = None
        current_market = None

        if historical_rates and len(historical_rates) > 0:
            rates = [float(r.rate_per_mile) for r in historical_rates]
            historical_avg = Decimal(str(sum(rates) / len(rates)))
            rate_low = Decimal(str(min(rates)))
            rate_high = Decimal(str(max(rates)))

            # Most recent rate as current market
            recent_rates = sorted(historical_rates, key=lambda x: x.timestamp, reverse=True)
            current_market = recent_rates[0].rate_per_mile * distance_miles

        # Build context for LLM analysis
        context = {
            "lane": lane_desc,
            "distance_miles": distance_miles,
            "business_rules": {
                "minimum_rpm": float(min_rpm),
                "target_rpm": float(target_rpm),
                "cost_per_mile": self.operating_costs.get("cost_per_mile", 0.39),
            },
            "historical_data": {
                "average_rpm": float(historical_avg) if historical_avg else None,
                "low_rpm": float(rate_low) if rate_low else None,
                "high_rpm": float(rate_high) if rate_high else None,
                "sample_size": len(historical_rates) if historical_rates else 0,
            } if historical_rates else None,
        }

        # Get LLM analysis
        prompt = f"""Analyze this freight lane and provide rate recommendations.

Lane Analysis:
{json.dumps(context, indent=2)}

Provide a comprehensive analysis including:
1. Recommended rate per mile for this lane
2. Market trend assessment (rising/falling/stable)
3. Confidence level in your analysis (0.0-1.0)
4. Reasoning for your recommendations
5. Negotiation tips for dealing with brokers
6. Risk factors to consider

Format your response as JSON:
{{
    "recommended_rpm": <decimal>,
    "market_trend": "<rising|falling|stable>",
    "confidence": <0.0-1.0>,
    "reasoning": "<detailed analysis>",
    "negotiation_tips": ["<tip1>", "<tip2>"],
    "risk_factors": ["<risk1>", "<risk2>"]
}}
"""

        try:
            response = self.call_llm(prompt, temperature=0.1, max_tokens=1500)
            response_data = self._parse_llm_json(response)

            recommended_rpm = Decimal(str(response_data.get("recommended_rpm", float(target_rpm))))
            market_trend = response_data.get("market_trend", "stable")
            confidence = float(response_data.get("confidence", 0.7))
            reasoning = response_data.get("reasoning", "")
            negotiation_tips = response_data.get("negotiation_tips", [])
            risk_factors = response_data.get("risk_factors", [])

        except Exception as e:
            self.logger.error("rate_analysis_failed", error=str(e), lane=lane_desc)
            # Fallback to business rules
            recommended_rpm = target_rpm
            market_trend = "stable"
            confidence = 0.5
            reasoning = "Analysis based on business rules (LLM unavailable)"
            negotiation_tips = ["Stick to target rate", "Be prepared to walk away"]
            risk_factors = ["Limited market data"]

        recommended_rate = recommended_rpm * distance_miles

        result = RateAnalysisResult(
            lane_description=lane_desc,
            distance_miles=distance_miles,
            current_market_rate=current_market,
            recommended_rate=recommended_rate,
            minimum_acceptable_rate=min_acceptable,
            target_rate=target_rate,
            market_trend=market_trend,
            confidence_level=confidence,
            reasoning=reasoning,
            historical_average=historical_avg * distance_miles if historical_avg else None,
            rate_range_low=rate_low * distance_miles if rate_low else None,
            rate_range_high=rate_high * distance_miles if rate_high else None,
            negotiation_tips=negotiation_tips,
            risk_factors=risk_factors,
            timestamp=datetime.now(),
            execution_time_seconds=time() - start_time,
        )

        # Log decision
        decision = AgentDecision(
            timestamp=datetime.now(),
            agent_name=self.agent_name,
            decision_type="lane_rate_analysis",
            input_data={"lane": lane_desc, "distance": distance_miles},
            reasoning=reasoning,
            confidence=confidence,
            output_data={
                "recommended_rate": float(recommended_rate),
                "market_trend": market_trend,
            },
            tools_used=["llm_analysis", "historical_data", "business_rules"],
            execution_time_seconds=time() - start_time,
        )
        self.log_decision(decision)

        return result

    def compare_rates(
        self, lanes: list[tuple[str, str, str, str, int]]
    ) -> list[RateAnalysisResult]:
        """
        Compare rates across multiple lanes.

        Args:
            lanes: List of (origin_city, origin_state, dest_city, dest_state, distance) tuples

        Returns:
            List of RateAnalysisResult for each lane
        """
        results = []
        for origin_city, origin_state, dest_city, dest_state, distance in lanes:
            try:
                result = self.analyze_lane(
                    origin_city, origin_state, dest_city, dest_state, distance
                )
                results.append(result)
            except Exception as e:
                self.logger.error(
                    "lane_comparison_error",
                    origin=f"{origin_city}, {origin_state}",
                    destination=f"{dest_city}, {dest_state}",
                    error=str(e),
                )

        return results

    def execute(self, *args: Any, **kwargs: Any) -> RateAnalysisResult:
        """
        Execute rate analysis (delegates to analyze_lane).

        Args:
            *args: Positional arguments for analyze_lane
            **kwargs: Keyword arguments for analyze_lane

        Returns:
            RateAnalysisResult
        """
        return self.analyze_lane(*args, **kwargs)

    def _parse_llm_json(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response."""
        # Try to extract JSON from markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()

        return json.loads(response)


def main() -> None:
    """Example usage of the rate analysis agent."""
    import structlog

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )

    # Create agent
    agent = RateAnalysisAgent()

    # Example: Analyze a lane
    result = agent.analyze_lane(
        origin_city="Tulsa",
        origin_state="OK",
        destination_city="Dallas",
        destination_state="TX",
        distance_miles=250,
    )

    # Print results
    print("\n" + "=" * 80)
    print("RATE ANALYSIS RESULTS")
    print("=" * 80)
    print(f"Lane: {result.lane_description}")
    print(f"Distance: {result.distance_miles} miles")
    print()
    print(f"Recommended Rate: ${result.recommended_rate:.2f}")
    print(f"  (${result.recommended_rate / result.distance_miles:.2f}/mile)")
    print(f"Minimum Acceptable: ${result.minimum_acceptable_rate:.2f}")
    print(f"Target Rate: ${result.target_rate:.2f}")
    print()
    print(f"Market Trend: {result.market_trend}")
    print(f"Confidence: {result.confidence_level:.1%}")
    print()
    print(f"Reasoning: {result.reasoning}")
    print()
    if result.negotiation_tips:
        print("Negotiation Tips:")
        for tip in result.negotiation_tips:
            print(f"  - {tip}")
    print()
    if result.risk_factors:
        print("Risk Factors:")
        for risk in result.risk_factors:
            print(f"  - {risk}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

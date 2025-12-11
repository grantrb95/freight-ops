"""
Dispatch Agent - Automated load matching and booking.

This agent:
- Searches load boards for available freight
- Analyzes profitability (rate per mile, deadhead, total revenue)
- Recommends optimal loads based on business rules
- Considers strategic positioning for future loads
"""

import json
from datetime import datetime
from decimal import Decimal
from time import time
from typing import Any, Optional

from pydantic import BaseModel

from src.agents.base import AgentDecision, BaseAgent
from src.data.models.load import Load


class LoadRecommendation(BaseModel):
    """Recommendation for a specific load."""

    load: Load
    score: float  # 0-100, higher is better
    reasoning: str
    profitability_metrics: dict[str, Any]
    warnings: list[str] = []


class DispatchResult(BaseModel):
    """Result of dispatch agent execution."""

    timestamp: datetime
    loads_analyzed: int
    recommendations: list[LoadRecommendation]
    top_recommendation: Optional[LoadRecommendation] = None
    execution_time_seconds: float


class DispatchAgent(BaseAgent):
    """
    Dispatch Agent for automated load matching and booking.

    Uses LLM to analyze loads considering:
    - Rate per mile (loaded and all-in)
    - Deadhead percentage
    - Total trip profitability
    - Strategic positioning
    - Market conditions
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the dispatch agent."""
        super().__init__(agent_name="dispatch", **kwargs)

        # Load business rules from config
        self.rate_thresholds = self.config_manager.get_rate_thresholds()
        self.operating_costs = self.config_manager.get_operating_costs()
        self.equipment_config = self.config_manager.get_equipment_config()

    def analyze_load(self, load: Load) -> LoadRecommendation:
        """
        Analyze a single load and provide a recommendation.

        Args:
            load: Load to analyze

        Returns:
            LoadRecommendation with score and reasoning
        """
        start_time = time()

        # Calculate basic profitability metrics
        metrics = self._calculate_metrics(load)

        # Build context for LLM
        context = self._build_load_context(load, metrics)

        # Get LLM analysis and reasoning
        prompt = f"""Analyze this freight load and provide a recommendation.

Load Details:
{json.dumps(context, indent=2, default=str)}

Business Rules:
- Minimum Rate Per Mile: ${self.rate_thresholds.get('minimum_rate_per_mile', 2.0)}
- Target Rate Per Mile: ${self.rate_thresholds.get('target_rate_per_mile', 2.5)}
- Max Deadhead %: {self.rate_thresholds.get('max_deadhead_percentage', 20)}%
- Cost Per Mile: ${self.operating_costs.get('cost_per_mile', 0.39)}

Provide:
1. Overall score (0-100)
2. Detailed reasoning
3. Key pros and cons
4. Any warnings or concerns

Format your response as JSON:
{{
    "score": <number 0-100>,
    "reasoning": "<detailed analysis>",
    "pros": ["<pro1>", "<pro2>"],
    "cons": ["<con1>", "<con2>"],
    "warnings": ["<warning1>"]
}}
"""

        try:
            response = self.call_llm(prompt, temperature=0.2, max_tokens=1024)

            # Parse LLM response
            # Try to extract JSON from response
            response_data = self._parse_llm_json(response)

            score = float(response_data.get("score", 0))
            reasoning = response_data.get("reasoning", "")
            warnings = response_data.get("warnings", [])

            # Add automatic warnings based on thresholds
            warnings.extend(self._check_warnings(load, metrics))

        except Exception as e:
            self.logger.error("load_analysis_failed", error=str(e), load_id=load.load_id)
            # Fallback to rule-based scoring
            score = self._calculate_rule_based_score(load, metrics)
            reasoning = "Analysis based on business rules (LLM unavailable)"
            warnings = self._check_warnings(load, metrics)

        recommendation = LoadRecommendation(
            load=load,
            score=score,
            reasoning=reasoning,
            profitability_metrics=metrics,
            warnings=warnings,
        )

        # Log decision
        decision = AgentDecision(
            timestamp=datetime.now(),
            agent_name=self.agent_name,
            decision_type="load_analysis",
            input_data={"load_id": load.load_id},
            reasoning=reasoning,
            confidence=score / 100.0,
            output_data={"score": score, "warnings": warnings},
            tools_used=["llm_analysis", "profitability_calculator"],
            execution_time_seconds=time() - start_time,
        )
        self.log_decision(decision)

        return recommendation

    def execute(
        self, loads: list[Load], max_recommendations: int = 5
    ) -> DispatchResult:
        """
        Analyze multiple loads and provide ranked recommendations.

        Args:
            loads: List of available loads to analyze
            max_recommendations: Maximum number of recommendations to return

        Returns:
            DispatchResult with ranked recommendations
        """
        start_time = time()

        self.logger.info("dispatch_execution_started", load_count=len(loads))

        # Analyze each load
        recommendations = []
        for load in loads:
            try:
                rec = self.analyze_load(load)
                recommendations.append(rec)
            except Exception as e:
                self.logger.error("load_analysis_error", load_id=load.load_id, error=str(e))
                continue

        # Sort by score (highest first)
        recommendations.sort(key=lambda x: x.score, reverse=True)

        # Limit to top N
        top_recommendations = recommendations[:max_recommendations]

        result = DispatchResult(
            timestamp=datetime.now(),
            loads_analyzed=len(loads),
            recommendations=top_recommendations,
            top_recommendation=top_recommendations[0] if top_recommendations else None,
            execution_time_seconds=time() - start_time,
        )

        self.logger.info(
            "dispatch_execution_completed",
            loads_analyzed=len(loads),
            recommendations_count=len(top_recommendations),
            top_score=result.top_recommendation.score if result.top_recommendation else 0,
        )

        return result

    def _calculate_metrics(self, load: Load) -> dict[str, Any]:
        """Calculate profitability metrics for a load."""
        # Fuel cost calculation
        truck_mpg = self.equipment_config.get("truck", {}).get("mpg", 9)
        fuel_cost_per_gallon = self.operating_costs.get("fuel_cost_per_gallon", 3.50)
        fuel_gallons = load.total_miles / truck_mpg
        fuel_cost = fuel_gallons * fuel_cost_per_gallon

        # Operating cost
        cost_per_mile = self.operating_costs.get("cost_per_mile", 0.39)
        total_operating_cost = load.total_miles * cost_per_mile

        # Net profit
        gross_revenue = float(load.gross_revenue)
        net_profit = gross_revenue - total_operating_cost - fuel_cost

        return {
            "rate_per_loaded_mile": float(load.rate_per_mile),
            "rate_per_all_miles": float(load.all_miles_rate),
            "deadhead_percentage": load.deadhead_percentage,
            "gross_revenue": gross_revenue,
            "fuel_cost": fuel_cost,
            "fuel_gallons": fuel_gallons,
            "operating_cost": total_operating_cost,
            "net_profit": net_profit,
            "profit_margin_pct": (net_profit / gross_revenue * 100) if gross_revenue > 0 else 0,
            "total_miles": load.total_miles,
            "loaded_miles": load.loaded_miles,
            "deadhead_miles": load.deadhead_miles,
        }

    def _build_load_context(self, load: Load, metrics: dict[str, Any]) -> dict[str, Any]:
        """Build context dictionary for LLM analysis."""
        return {
            "load_id": load.load_id,
            "origin": str(load.origin),
            "destination": str(load.destination),
            "pickup_date": load.pickup_date.isoformat(),
            "delivery_date": load.delivery_date.isoformat(),
            "commodity": load.commodity,
            "weight": load.weight,
            "equipment_type": load.equipment_type,
            "metrics": metrics,
            "special_requirements": {
                "hazmat": load.is_hazmat,
                "team_required": load.is_team_required,
                "expedited": load.is_expedited,
                "requires_tarp": load.requires_tarp,
            },
        }

    def _parse_llm_json(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling various formats."""
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

    def _calculate_rule_based_score(self, load: Load, metrics: dict[str, Any]) -> float:
        """Calculate score using business rules (fallback when LLM fails)."""
        score = 50.0  # Start at middle

        # Rate per mile scoring
        rpm = metrics["rate_per_loaded_mile"]
        min_rpm = self.rate_thresholds.get("minimum_rate_per_mile", 2.0)
        target_rpm = self.rate_thresholds.get("target_rate_per_mile", 2.5)
        premium_rpm = self.rate_thresholds.get("premium_rate_per_mile", 3.0)

        if rpm < min_rpm:
            score -= 30
        elif rpm >= premium_rpm:
            score += 30
        elif rpm >= target_rpm:
            score += 20
        else:
            score += 10

        # Deadhead scoring
        deadhead_pct = metrics["deadhead_percentage"]
        max_deadhead = self.rate_thresholds.get("max_deadhead_percentage", 20)

        if deadhead_pct <= 10:
            score += 20
        elif deadhead_pct <= max_deadhead:
            score += 10
        else:
            score -= 20

        # Profit margin scoring
        profit_margin = metrics["profit_margin_pct"]
        if profit_margin >= 50:
            score += 20
        elif profit_margin >= 30:
            score += 10
        elif profit_margin < 10:
            score -= 20

        # Special requirements penalties
        if load.is_hazmat:
            score -= 5
        if load.is_team_required:
            score -= 10
        if load.requires_tarp:
            score -= 5

        # Expedited premium
        if load.is_expedited:
            score += 10

        # Clamp to 0-100
        return max(0, min(100, score))

    def _check_warnings(self, load: Load, metrics: dict[str, Any]) -> list[str]:
        """Check for warning conditions."""
        warnings = []

        # Rate warnings
        min_rpm = self.rate_thresholds.get("minimum_rate_per_mile", 2.0)
        if metrics["rate_per_loaded_mile"] < min_rpm:
            warnings.append(f"Rate per mile (${metrics['rate_per_loaded_mile']:.2f}) below minimum (${min_rpm})")

        # Deadhead warnings
        max_deadhead = self.rate_thresholds.get("max_deadhead_percentage", 20)
        if metrics["deadhead_percentage"] > max_deadhead:
            warnings.append(f"Deadhead ({metrics['deadhead_percentage']:.1f}%) exceeds maximum ({max_deadhead}%)")

        # Profit warnings
        if metrics["net_profit"] < 0:
            warnings.append(f"Load is unprofitable: ${metrics['net_profit']:.2f} loss")

        # Weight warnings
        max_weight = self.equipment_config.get("trailer", {}).get("max_weight_lbs", 16500)
        if load.weight > max_weight:
            warnings.append(f"Load weight ({load.weight} lbs) exceeds trailer capacity ({max_weight} lbs)")

        # Special requirements
        if load.is_hazmat:
            warnings.append("Requires HAZMAT certification")
        if load.is_team_required:
            warnings.append("Requires team drivers")

        return warnings


def main() -> None:
    """Example usage of the dispatch agent."""
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
    agent = DispatchAgent()

    # Example: Create mock loads (in production, these would come from load boards)
    from src.data.models.load import Location, LoadType

    mock_loads = [
        Load(
            load_id="LOAD-001",
            broker_name="Test Broker",
            origin=Location(city="Tulsa", state="OK"),
            destination=Location(city="Dallas", state="TX"),
            pickup_date=datetime.now(),
            delivery_date=datetime.now(),
            commodity="Auto Parts",
            weight=5000,
            rate=Decimal("600"),
            loaded_miles=250,
            deadhead_miles=20,
            equipment_type="Hotshot",
        ),
        Load(
            load_id="LOAD-002",
            broker_name="Test Broker 2",
            origin=Location(city="Oklahoma City", state="OK"),
            destination=Location(city="Houston", state="TX"),
            pickup_date=datetime.now(),
            delivery_date=datetime.now(),
            commodity="Machinery",
            weight=8000,
            rate=Decimal("900"),
            loaded_miles=450,
            deadhead_miles=100,
            equipment_type="Hotshot",
        ),
    ]

    # Execute dispatch
    result = agent.execute(mock_loads)

    # Print results
    print("\n" + "=" * 80)
    print("DISPATCH AGENT RESULTS")
    print("=" * 80)
    print(f"Loads Analyzed: {result.loads_analyzed}")
    print(f"Execution Time: {result.execution_time_seconds:.2f}s")
    print()

    if result.top_recommendation:
        print("TOP RECOMMENDATION:")
        print(f"  Load ID: {result.top_recommendation.load.load_id}")
        print(f"  Score: {result.top_recommendation.score:.1f}/100")
        print(f"  Route: {result.top_recommendation.load.origin} → {result.top_recommendation.load.destination}")
        print(f"  Rate/Mile: ${result.top_recommendation.profitability_metrics['rate_per_loaded_mile']:.2f}")
        print(f"  Net Profit: ${result.top_recommendation.profitability_metrics['net_profit']:.2f}")
        print(f"\n  Reasoning: {result.top_recommendation.reasoning}")
        if result.top_recommendation.warnings:
            print(f"\n  Warnings:")
            for warning in result.top_recommendation.warnings:
                print(f"    - {warning}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

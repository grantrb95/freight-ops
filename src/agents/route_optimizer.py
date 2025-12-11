"""
Route Optimizer Agent - Efficient routing and deadhead reduction.

This agent:
- Finds optimal routes between pickup and delivery
- Minimizes deadhead miles through backhaul opportunities
- Considers fuel costs, tolls, and traffic
- Identifies strategic positioning for future loads
- Optimizes multi-stop routes
"""

import json
from datetime import datetime
from decimal import Decimal
from time import time
from typing import Any, Optional

from pydantic import BaseModel

from src.agents.base import AgentDecision, BaseAgent
from src.data.models.load import Load, Location


class RouteSegment(BaseModel):
    """A segment of a route."""

    start_location: Location
    end_location: Location
    distance_miles: int
    estimated_time_hours: float
    fuel_cost: Decimal
    toll_cost: Decimal
    description: str


class RouteOption(BaseModel):
    """A complete route option."""

    route_name: str
    segments: list[RouteSegment]
    total_distance_miles: int
    total_time_hours: float
    total_fuel_cost: Decimal
    total_toll_cost: Decimal
    total_cost: Decimal
    advantages: list[str]
    disadvantages: list[str]
    score: float  # 0-100, higher is better


class BackhaulOpportunity(BaseModel):
    """Potential backhaul load to reduce deadhead."""

    load: Load
    deadhead_to_pickup: int
    compatibility_score: float
    reasoning: str


class RouteOptimizationResult(BaseModel):
    """Result of route optimization."""

    origin: Location
    destination: Location
    recommended_route: RouteOption
    alternative_routes: list[RouteOption]
    backhaul_opportunities: list[BackhaulOpportunity]
    execution_time_seconds: float
    timestamp: datetime


class RouteOptimizerAgent(BaseAgent):
    """
    Route Optimizer Agent for efficient routing and deadhead reduction.

    Uses LLM to:
    - Analyze route options
    - Consider real-world factors (weather, traffic, road conditions)
    - Identify strategic positioning
    - Find backhaul opportunities
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the route optimizer agent."""
        super().__init__(agent_name="route_optimizer", **kwargs)

        # Load configuration
        self.operating_costs = self.config_manager.get_operating_costs()
        self.equipment_config = self.config_manager.get_equipment_config()
        self.home_base = self.config_manager.business_config.get("home_base", {})

    def optimize_route(
        self,
        origin: Location,
        destination: Location,
        current_location: Optional[Location] = None,
        available_backhauls: Optional[list[Load]] = None,
    ) -> RouteOptimizationResult:
        """
        Optimize route from origin to destination.

        Args:
            origin: Starting location
            destination: Ending location
            current_location: Optional current truck location (for deadhead calculation)
            available_backhauls: Optional list of available backhaul loads

        Returns:
            RouteOptimizationResult with recommended route and alternatives
        """
        start_time = time()

        self.logger.info(
            "optimizing_route",
            origin=str(origin),
            destination=str(destination),
        )

        # Calculate route options
        # In a real implementation, this would use Google Maps API or similar
        route_options = self._calculate_route_options(origin, destination)

        # Analyze backhaul opportunities if available
        backhaul_opportunities = []
        if available_backhauls:
            backhaul_opportunities = self._analyze_backhauls(
                destination, current_location or origin, available_backhauls
            )

        # Use LLM to select best route
        recommended_route = self._select_best_route(route_options, origin, destination)

        result = RouteOptimizationResult(
            origin=origin,
            destination=destination,
            recommended_route=recommended_route,
            alternative_routes=[r for r in route_options if r != recommended_route],
            backhaul_opportunities=backhaul_opportunities,
            execution_time_seconds=time() - start_time,
            timestamp=datetime.now(),
        )

        # Log decision
        decision = AgentDecision(
            timestamp=datetime.now(),
            agent_name=self.agent_name,
            decision_type="route_optimization",
            input_data={
                "origin": str(origin),
                "destination": str(destination),
            },
            reasoning=f"Selected {recommended_route.route_name}",
            confidence=recommended_route.score / 100.0,
            output_data={
                "total_miles": recommended_route.total_distance_miles,
                "total_cost": float(recommended_route.total_cost),
                "backhauls_found": len(backhaul_opportunities),
            },
            tools_used=["route_calculator", "llm_analysis", "backhaul_matcher"],
            execution_time_seconds=time() - start_time,
        )
        self.log_decision(decision)

        return result

    def calculate_deadhead_reduction(
        self,
        completed_load: Load,
        potential_backhauls: list[Load],
    ) -> list[BackhaulOpportunity]:
        """
        Find backhaul opportunities to reduce deadhead from completed load.

        Args:
            completed_load: Just-completed load
            potential_backhauls: Available loads to consider

        Returns:
            List of BackhaulOpportunity sorted by score
        """
        return self._analyze_backhauls(
            completed_load.destination,
            self._location_from_dict(self.home_base),
            potential_backhauls,
        )

    def execute(self, *args: Any, **kwargs: Any) -> RouteOptimizationResult:
        """
        Execute route optimization (delegates to optimize_route).

        Args:
            *args: Positional arguments for optimize_route
            **kwargs: Keyword arguments for optimize_route

        Returns:
            RouteOptimizationResult
        """
        return self.optimize_route(*args, **kwargs)

    def _calculate_route_options(
        self, origin: Location, destination: Location
    ) -> list[RouteOption]:
        """
        Calculate multiple route options.

        In production, this would use Google Maps API or similar.
        This is a simplified version.
        """
        # Simplified distance calculation (would use actual routing API)
        # Using approximate straight-line distance * 1.2 for road distance
        estimated_distance = self._estimate_distance(origin, destination)

        # Calculate costs
        mpg = self.equipment_config.get("truck", {}).get("mpg", 9)
        fuel_cost_per_gallon = self.operating_costs.get("fuel_cost_per_gallon", 3.50)
        fuel_cost = Decimal(str((estimated_distance / mpg) * fuel_cost_per_gallon))

        # Create route options (simplified - would have multiple real routes)
        primary_route = RouteOption(
            route_name="Primary Highway Route",
            segments=[
                RouteSegment(
                    start_location=origin,
                    end_location=destination,
                    distance_miles=estimated_distance,
                    estimated_time_hours=estimated_distance / 55.0,  # Assume 55 mph average
                    fuel_cost=fuel_cost,
                    toll_cost=Decimal("15.00"),  # Estimated tolls
                    description="Interstate highway route",
                )
            ],
            total_distance_miles=estimated_distance,
            total_time_hours=estimated_distance / 55.0,
            total_fuel_cost=fuel_cost,
            total_toll_cost=Decimal("15.00"),
            total_cost=fuel_cost + Decimal("15.00"),
            advantages=["Fastest route", "Well-maintained roads", "Easy navigation"],
            disadvantages=["Toll roads", "Higher fuel cost"],
            score=85.0,
        )

        alternate_route = RouteOption(
            route_name="Toll-Free Route",
            segments=[
                RouteSegment(
                    start_location=origin,
                    end_location=destination,
                    distance_miles=int(estimated_distance * 1.1),  # 10% longer
                    estimated_time_hours=(estimated_distance * 1.1) / 50.0,  # Slower
                    fuel_cost=fuel_cost * Decimal("1.1"),
                    toll_cost=Decimal("0.00"),
                    description="Highway route avoiding tolls",
                )
            ],
            total_distance_miles=int(estimated_distance * 1.1),
            total_time_hours=(estimated_distance * 1.1) / 50.0,
            total_fuel_cost=fuel_cost * Decimal("1.1"),
            total_toll_cost=Decimal("0.00"),
            total_cost=fuel_cost * Decimal("1.1"),
            advantages=["No tolls", "Lower overall cost"],
            disadvantages=["Longer distance", "More time"],
            score=75.0,
        )

        return [primary_route, alternate_route]

    def _select_best_route(
        self, route_options: list[RouteOption], origin: Location, destination: Location
    ) -> RouteOption:
        """Use LLM to select the best route considering multiple factors."""
        context = {
            "origin": str(origin),
            "destination": str(destination),
            "routes": [
                {
                    "name": r.route_name,
                    "distance": r.total_distance_miles,
                    "time_hours": r.total_time_hours,
                    "fuel_cost": float(r.total_fuel_cost),
                    "toll_cost": float(r.total_toll_cost),
                    "total_cost": float(r.total_cost),
                    "advantages": r.advantages,
                    "disadvantages": r.disadvantages,
                }
                for r in route_options
            ],
        }

        prompt = f"""Analyze these route options and select the best one.

Routes:
{json.dumps(context, indent=2)}

Consider:
- Total cost (fuel + tolls)
- Time efficiency
- Road conditions and safety
- Driver comfort

Respond with JSON:
{{
    "selected_route_name": "<route name>",
    "reasoning": "<explanation>"
}}
"""

        try:
            response = self.call_llm(prompt, temperature=0.3, max_tokens=512)
            response_data = self._parse_llm_json(response)
            selected_name = response_data.get("selected_route_name", route_options[0].route_name)

            # Find the selected route
            for route in route_options:
                if route.route_name == selected_name:
                    return route

        except Exception as e:
            self.logger.error("route_selection_failed", error=str(e))

        # Fallback: return highest scored route
        return max(route_options, key=lambda r: r.score)

    def _analyze_backhauls(
        self,
        current_destination: Location,
        return_location: Location,
        available_loads: list[Load],
    ) -> list[BackhaulOpportunity]:
        """Analyze available loads for backhaul opportunities."""
        opportunities = []

        for load in available_loads:
            # Calculate deadhead to pickup
            deadhead = self._estimate_distance(current_destination, load.origin)

            # Simple compatibility score
            # Would be more sophisticated in production
            compatibility = 100.0

            # Penalize high deadhead
            if deadhead > 100:
                compatibility -= min(50, (deadhead - 100) * 0.5)

            # Bonus if delivery is near return location
            delivery_to_home = self._estimate_distance(load.destination, return_location)
            if delivery_to_home < 50:
                compatibility += 20

            if compatibility > 50:  # Only include reasonable opportunities
                opportunities.append(
                    BackhaulOpportunity(
                        load=load,
                        deadhead_to_pickup=deadhead,
                        compatibility_score=compatibility,
                        reasoning=f"Backhaul reduces empty miles; {deadhead}mi deadhead to pickup",
                    )
                )

        # Sort by compatibility
        opportunities.sort(key=lambda x: x.compatibility_score, reverse=True)
        return opportunities[:5]  # Top 5

    def _estimate_distance(self, loc1: Location, loc2: Location) -> int:
        """
        Estimate distance between two locations.

        This is a very simplified version. Production would use actual routing API.
        """
        # If we have lat/lon, use haversine
        if all([loc1.latitude, loc1.longitude, loc2.latitude, loc2.longitude]):
            from math import radians, sin, cos, sqrt, atan2

            R = 3959  # Earth radius in miles

            lat1, lon1 = radians(loc1.latitude), radians(loc1.longitude)
            lat2, lon2 = radians(loc2.latitude), radians(loc2.longitude)

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))

            distance = R * c
            return int(distance * 1.2)  # Add 20% for road distance vs straight line

        # Fallback: rough estimate based on state proximity
        # This is very crude - production must use real routing
        return 250  # Default estimate

    def _location_from_dict(self, loc_dict: dict[str, Any]) -> Location:
        """Create Location from dictionary."""
        coords = loc_dict.get("coordinates", {})
        return Location(
            city=loc_dict.get("city", ""),
            state=loc_dict.get("state", ""),
            latitude=coords.get("latitude"),
            longitude=coords.get("longitude"),
        )

    def _parse_llm_json(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response."""
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
    """Example usage of the route optimizer agent."""
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
    agent = RouteOptimizerAgent()

    # Example: Optimize a route
    origin = Location(city="Tulsa", state="OK", latitude=36.1540, longitude=-95.9928)
    destination = Location(city="Dallas", state="TX", latitude=32.7767, longitude=-96.7970)

    result = agent.optimize_route(origin, destination)

    # Print results
    print("\n" + "=" * 80)
    print("ROUTE OPTIMIZATION RESULTS")
    print("=" * 80)
    print(f"Origin: {result.origin}")
    print(f"Destination: {result.destination}")
    print()
    print("RECOMMENDED ROUTE:")
    print(f"  {result.recommended_route.route_name}")
    print(f"  Distance: {result.recommended_route.total_distance_miles} miles")
    print(f"  Time: {result.recommended_route.total_time_hours:.1f} hours")
    print(f"  Fuel Cost: ${result.recommended_route.total_fuel_cost:.2f}")
    print(f"  Toll Cost: ${result.recommended_route.total_toll_cost:.2f}")
    print(f"  Total Cost: ${result.recommended_route.total_cost:.2f}")
    print()
    print("  Advantages:")
    for adv in result.recommended_route.advantages:
        print(f"    ✓ {adv}")
    print()

    if result.alternative_routes:
        print("ALTERNATIVE ROUTES:")
        for alt in result.alternative_routes:
            print(f"  {alt.route_name}: {alt.total_distance_miles}mi, ${alt.total_cost:.2f}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

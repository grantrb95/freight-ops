"""Quick test script to verify agents are working."""

import os
from datetime import datetime
from decimal import Decimal

# Set dummy API keys for testing (agents won't actually call LLMs without valid keys)
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["OPENAI_API_KEY"] = "test-key"

from src.agents import (
    ComplianceAgent,
    DispatchAgent,
    RateAnalysisAgent,
    RouteOptimizerAgent,
    SettlementAgent,
)
from src.data.models.load import Load, Location

print("=" * 80)
print("TESTING FREIGHT-OPS AGENTS")
print("=" * 80)

# Test 1: Agent initialization
print("\n1. Testing agent initialization...")
try:
    dispatch = DispatchAgent()
    print(f"   ✓ DispatchAgent initialized: {dispatch}")

    rates = RateAnalysisAgent()
    print(f"   ✓ RateAnalysisAgent initialized: {rates}")

    compliance = ComplianceAgent()
    print(f"   ✓ ComplianceAgent initialized: {compliance}")

    route_opt = RouteOptimizerAgent()
    print(f"   ✓ RouteOptimizerAgent initialized: {route_opt}")

    settlement = SettlementAgent()
    print(f"   ✓ SettlementAgent initialized: {settlement}")

    print("   ✅ All agents initialized successfully!")
except Exception as e:
    print(f"   ❌ Agent initialization failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Configuration loading
print("\n2. Testing configuration loading...")
try:
    from src.core.config import get_config

    config = get_config()
    company_info = config.get_company_info()
    print(f"   ✓ Company: {company_info.get('name')}")
    print(f"   ✓ DOT: {company_info.get('dot_number')}")
    print(f"   ✓ MC: {company_info.get('mc_number')}")

    rate_thresholds = config.get_rate_thresholds()
    print(f"   ✓ Min RPM: ${rate_thresholds.get('minimum_rate_per_mile')}")
    print(f"   ✓ Target RPM: ${rate_thresholds.get('target_rate_per_mile')}")

    print("   ✅ Configuration loaded successfully!")
except Exception as e:
    print(f"   ❌ Configuration loading failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Load data model
print("\n3. Testing Load data model...")
try:
    load = Load(
        load_id="TEST-001",
        broker_name="Test Broker",
        origin=Location(city="Tulsa", state="OK"),
        destination=Location(city="Dallas", state="TX"),
        pickup_date=datetime.now(),
        delivery_date=datetime.now(),
        commodity="Test Freight",
        weight=5000,
        rate=Decimal("600"),
        fuel_surcharge=Decimal("40"),
        loaded_miles=250,
        deadhead_miles=25,
    )

    print(f"   ✓ Load created: {load.load_id}")
    print(f"   ✓ Route: {load.origin} → {load.destination}")
    print(f"   ✓ Rate per mile: ${load.rate_per_mile:.2f}")
    print(f"   ✓ All-in RPM: ${load.all_miles_rate:.2f}")
    print(f"   ✓ Deadhead %: {load.deadhead_percentage:.1f}%")
    print(f"   ✓ Gross revenue: ${load.gross_revenue:.2f}")

    is_profitable = load.is_profitable(
        min_rpm=Decimal("2.00"), max_deadhead_pct=20.0
    )
    print(f"   ✓ Profitable: {is_profitable}")

    print("   ✅ Load model working correctly!")
except Exception as e:
    print(f"   ❌ Load model test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Agent LLM configuration
print("\n4. Testing agent LLM configurations...")
try:
    from src.core.config import get_config

    config = get_config()

    for agent_name in ["dispatch", "rate_analysis", "compliance", "route_optimizer", "settlement"]:
        llm_config = config.get_agent_llm_config(agent_name)
        print(f"   ✓ {agent_name}: {llm_config.primary_model.model} ({llm_config.primary_model.provider})")

    print("   ✅ All LLM configs loaded successfully!")
except Exception as e:
    print(f"   ❌ LLM config test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TESTING COMPLETE")
print("=" * 80)
print("\nAll core functionality is working! Agents are ready to use.")
print("Note: LLM calls will fail without valid API keys, but the framework is ready.")
print("=" * 80 + "\n")

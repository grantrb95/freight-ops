# Freight Operations Platform - Claude Code Instructions

## Project Overview

This is an AI-powered freight operations platform designed specifically for hotshot trucking businesses. The platform leverages AI agents to automate and optimize critical freight operations including dispatch, rate analysis, compliance tracking, and route optimization.

## Architecture

### Core Components

1. **AI Agents** (`src/agents/`)
   - Dispatch Agent: Automated load matching and booking
   - Rate Analysis Agent: Real-time rate per mile calculations and market analysis
   - Compliance Agent: IFTA tracking, HOS monitoring, and DOT compliance
   - Route Optimizer Agent: Deadhead reduction and fuel-efficient routing
   - Settlement Agent: Automated driver pay calculations

2. **MCP Tool Integrations** (`src/tools/`)
   - Load Board Tools: DAT, Truckstop.com API integrations
   - Mapping Tools: Route planning and distance calculations
   - Financial Tools: Fuel cost tracking, profit margin analysis
   - Tracking Tools: Real-time GPS and shipment tracking

3. **Custom MCP Servers** (`mcp_servers/`)
   - Truckstop.com server: Custom MCP for load board access
   - DAT server: DAT Load Board and RateView integration
   - Fuel server: Fuel price tracking and optimization

4. **Core Infrastructure** (`src/core/`)
   - Sandbox: Secure execution environment for agent operations
   - MCP Registry: Tool discovery and management
   - Config: Centralized configuration management

## Development Guidelines

### When Working on This Project

1. **Freight Domain Knowledge**
   - Understand hotshot trucking operates with lighter loads (typically Class 3-5 trucks)
   - Focus on speed and flexibility over maximum payload
   - Deadhead miles are critical - aim to minimize empty return trips
   - Rate per mile varies significantly by lane, season, and urgency

2. **Agent Development**
   - Agents should use the MCP protocol for tool access
   - All agents inherit from base agent class in `src/agents/base.py`
   - Use structured outputs with Pydantic models from `src/data/models/`
   - Implement proper error handling for API failures (load boards go down)

3. **API Integrations**
   - Load board APIs (DAT, Truckstop) require authentication
   - Rate limiting is critical - implement exponential backoff
   - Cache frequently accessed data (fuel prices, common routes)
   - Handle partial data gracefully (not all loads have complete info)

4. **Testing**
   - Use mock data for load board responses to avoid API costs
   - Test edge cases: no available loads, extreme rates, multi-stop routes
   - Validate compliance calculations against known correct values
   - Test agent decision-making with historical load data

### Key Freight Concepts

**Rate Per Mile (RPM)**
- Gross rate divided by loaded miles
- Target varies by equipment type and market conditions
- Factor in fuel costs, deadhead, and time commitment

**Deadhead**
- Empty miles driven to pickup or after delivery
- Minimize by finding backhauls
- Calculate deadhead percentage: (deadhead miles / total miles) * 100

**IFTA (International Fuel Tax Agreement)**
- Track fuel purchases and miles by jurisdiction
- Required for quarterly reporting
- Penalties for non-compliance are severe

**Driver Settlement**
- Calculate based on percentage or per-mile rate
- Deduct advances, fuel card purchases, insurance
- Must comply with owner-operator agreements

### Environment Variables Required

See `.env.example` for full list. Critical ones:
- `DAT_API_KEY`: DAT Load Board access
- `TRUCKSTOP_API_KEY`: Truckstop.com access
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`: LLM providers
- `GOOGLE_MAPS_API_KEY`: Route optimization

### Configuration

- Main config: `config/config.yaml` - business rules, thresholds, defaults
- LLM config: `config/llms.json` - model selection per agent
- Agent configs: Individual YAML files in `config/agents/`

### Common Commands

```bash
# Install dependencies
uv sync

# Run specific agent
python -m src.agents.dispatch

# Run tests
pytest tests/

# Start Jupyter for analysis
jupyter notebook notebooks/

# Lint and format
ruff check src/
ruff format src/
```

### Integration with open-ptc-agent

This project is designed to work alongside open-ptc-agent for advanced agent capabilities:
- Use MCP protocol for tool standardization
- Share context through structured data models
- Coordinate multi-agent workflows for complex operations

### Best Practices

1. **Always validate load data** - Brokers sometimes post incorrect info
2. **Consider total trip profitability** - Not just loaded miles
3. **Factor in realistic transit times** - Speed limits, HOS rules, loading times
4. **Implement circuit breakers** - Don't hammer APIs when they're down
5. **Log all agent decisions** - Critical for debugging and improvement
6. **Use type hints everywhere** - This is a complex domain, types help
7. **Document business logic** - Rate calculations, compliance rules, etc.

### Data Models Priority

When creating or modifying data models:
1. Load (freight shipment details)
2. Route (pickup/delivery locations, distance, time)
3. Rate (price per mile, fuel surcharge, accessorials)
4. Driver (contact, equipment, settlements)
5. Expense (fuel, tolls, maintenance)
6. Settlement (driver pay calculations)

### Agent Decision-Making

Agents should log their reasoning in structured format:
- What data was considered
- What thresholds/rules were applied
- Why a particular load/route was chosen
- Confidence level in the decision

This enables human oversight and continuous improvement.

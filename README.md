# Freight Operations Platform

An AI-powered operations platform for hotshot trucking businesses, featuring intelligent agents for dispatch, rate analysis, compliance tracking, and route optimization.

## Features

### AI Agents

- **Dispatch Agent**: Automated load matching from multiple load boards (DAT, Truckstop.com)
- **Rate Analysis Agent**: Real-time rate per mile calculations and market intelligence
- **Compliance Agent**: IFTA tracking, HOS monitoring, and DOT compliance automation
- **Route Optimizer**: Deadhead reduction and fuel-efficient route planning
- **Settlement Agent**: Automated driver pay calculations and expense tracking

### Tool Integrations (MCP)

- **Load Boards**: DAT, Truckstop.com API access
- **Mapping**: Route planning, distance calculations, traffic analysis
- **Financial**: Fuel cost tracking, profit margin analysis, expense categorization
- **Tracking**: Real-time GPS integration and shipment status updates

### Custom MCP Servers

- **Truckstop Server**: Custom MCP for Truckstop.com load board
- **DAT Server**: DAT Load Board and RateView market data
- **Fuel Server**: Real-time fuel price tracking and optimization

## Project Structure

```
freight-ops/
├── src/
│   ├── agents/           # AI agents for freight operations
│   │   ├── dispatch.py
│   │   ├── rate_analysis.py
│   │   ├── compliance.py
│   │   ├── route_optimizer.py
│   │   └── settlement.py
│   ├── tools/            # MCP tool integrations
│   │   ├── load_boards/
│   │   ├── mapping/
│   │   ├── financials/
│   │   └── tracking/
│   ├── core/             # Shared infrastructure
│   │   ├── sandbox.py
│   │   ├── mcp_registry.py
│   │   └── config.py
│   └── data/
│       └── models/       # Pydantic data models
├── mcp_servers/          # Custom MCP server implementations
│   ├── truckstop/
│   ├── dat/
│   └── fuel/
├── config/               # Configuration files
│   ├── config.yaml
│   └── llms.json
├── notebooks/            # Jupyter notebooks for analysis
├── scripts/              # Utility scripts
└── tests/                # Test suite
```

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- API keys for load boards and LLM providers

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd freight-ops
```

2. Install dependencies with uv:
```bash
uv sync
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. Update configuration:
```bash
# Edit config/config.yaml with your business rules
# Edit config/llms.json with your preferred LLM providers
```

## Configuration

### Environment Variables

See `.env.example` for all required variables:

- **Load Board APIs**: `DAT_API_KEY`, `TRUCKSTOP_API_KEY`
- **LLM Providers**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- **Mapping**: `GOOGLE_MAPS_API_KEY`
- **Database**: `DATABASE_URL`

### Business Rules (config/config.yaml)

Configure your business-specific thresholds:
- Minimum acceptable rate per mile
- Maximum deadhead percentage
- Fuel surcharge calculations
- Driver settlement percentages
- Insurance and operating costs

### LLM Configuration (config/llms.json)

Assign specific models to each agent:
- Dispatch agent: GPT-4 for complex decision-making
- Rate analysis: Claude for numerical analysis
- Compliance: Smaller models for structured tasks

## Usage

### Running Agents

```bash
# Dispatch agent - find and book loads
python -m src.agents.dispatch

# Rate analysis - analyze market rates
python -m src.agents.rate_analysis --lane "TX-CA"

# Compliance check - generate IFTA report
python -m src.agents.compliance --report ifta --quarter Q1
```

### Interactive Analysis

```bash
# Start Jupyter for data analysis
jupyter notebook notebooks/

# Common notebooks:
# - rate_trends.ipynb: Analyze historical rate data
# - route_analysis.ipynb: Optimize common lanes
# - profit_analysis.ipynb: Margin analysis by load type
```

### Running Tests

```bash
# All tests
pytest tests/

# Specific test suite
pytest tests/agents/test_dispatch.py

# With coverage
pytest --cov=src tests/
```

## Key Concepts

### Rate Per Mile (RPM)

The fundamental metric for load profitability:

```
RPM = Total Revenue / Loaded Miles
```

Consider:
- Base rate from shipper/broker
- Fuel surcharge
- Accessorial charges (detention, layover, etc.)
- Deadhead miles impact on overall profitability

### Deadhead Optimization

Minimize empty miles:

```
Deadhead % = (Deadhead Miles / Total Miles) * 100
```

Target: Keep below 10-15% for optimal profitability

### IFTA Compliance

Track fuel purchases and miles by jurisdiction:
- Record every fuel purchase (gallons, price, location)
- Track miles driven in each state/province
- Generate quarterly reports
- Calculate tax owed or refund due

### Driver Settlement

Calculate driver pay accurately:

```
Gross Pay = Revenue * Driver Percentage
Net Pay = Gross Pay - Advances - Fuel - Deductions + Reimbursements
```

## Development

### Adding a New Agent

1. Create agent file in `src/agents/`
2. Inherit from `BaseAgent`
3. Define required tools via MCP
4. Implement decision logic with clear reasoning
5. Add tests in `tests/agents/`
6. Update `config/llms.json` with model assignment

### Creating a Custom MCP Server

1. Create directory in `mcp_servers/`
2. Implement MCP protocol handlers
3. Define tool schemas
4. Add authentication handling
5. Document API endpoints used
6. Add integration tests

### Data Models

Use Pydantic for all data structures:

```python
from pydantic import BaseModel, Field

class Load(BaseModel):
    load_id: str
    origin: Location
    destination: Location
    pickup_date: datetime
    delivery_date: datetime
    rate: Decimal = Field(gt=0)
    miles: int = Field(gt=0)
    weight: int
    commodity: str
```

## Integration with open-ptc-agent

This platform is designed to integrate with open-ptc-agent:

1. All tools exposed via MCP protocol
2. Agents can be orchestrated by open-ptc-agent
3. Shared context through structured data models
4. Compatible with Claude Desktop and other MCP clients

## Roadmap

- [ ] Real-time load monitoring and alerts
- [ ] Predictive rate modeling with historical data
- [ ] Multi-agent collaboration for complex scenarios
- [ ] Mobile app for driver communication
- [ ] Integration with TMS (Transportation Management Systems)
- [ ] Blockchain for transparent load tracking
- [ ] Insurance claim automation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

[Your chosen license]

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Documentation: [docs-url]

## Acknowledgments

- Built with the MCP (Model Context Protocol)
- Integrates with open-ptc-agent
- Powered by Claude and GPT models

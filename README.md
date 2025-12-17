# CrewAI Trading Strategy Generator

An AI-powered cryptocurrency trading strategy generator that uses multiple AI agents to research, design, and implement profitable trading strategies. Built with [CrewAI](https://crewai.com), this project leverages a multi-agent system to automatically create, backtest, and iterate on trading strategies for Bitcoin.

## 🎯 Purpose

This project demonstrates a sophisticated AI workflow that:

- **Researches** historical cryptocurrency price data to identify profitable trading patterns
- **Designs** detailed technical specifications for trading strategy implementations
- **Implements** self-contained Python trading strategies following strict API guidelines
- **Backtests** strategies against historical data to validate performance
- **Iterates** automatically to improve strategy profitability across multiple attempts

The system uses three specialized AI agents working in sequence: a Strategy Researcher, an Engineering Lead, and a Senior Developer, each with specific expertise to ensure high-quality trading strategy development.

## 🏗️ Architecture Overview

### Multi-Agent Workflow

The project employs a **CrewAI Flow** architecture with three specialized agents:

1. **Strategy Researcher Agent** (`strategy_researcher`)

   - Role: Senior crypto trading strategy researcher
   - Goal: Analyze daily cryptocurrency data and define profitable trading strategies
   - Tools: Historical price data analysis, custom code execution on datasets
   - Output: Trading strategy outline document
2. **Engineering Lead Agent** (`engineering_lead`)

   - Role: Senior engineering lead
   - Goal: Create detailed technical designs for strategy implementation
   - Input: Strategy outline from researcher
   - Output: Comprehensive design document with pseudocode and API specifications
3. **Developer Agent** (`developer`)

   - Role: Senior Python developer
   - Goal: Implement trading strategies based on engineering designs
   - Input: Design document from engineering lead
   - Output: Production-ready Python code following strict API guidelines

### Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  TradingStrategyCreationFlow                │
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  Start   │──▶│ Research │──▶│  Design  │──▶│Implement │  │
│  └──────────┘   │ Strategy │   │ Strategy │   │ Strategy │  │
│                 └──────────┘   └──────────┘   └──────────┘  │
│                                                    │        │
│                                                    ▼        │
│                 ┌─────────────────────────────────────┐     │
│                 │        Backtest Strategy            │     │
│                 └─────────────────────────────────────┘     │
│                       │                                     │
│                       ▼                                     │
│                 ┌──────────────┐                            │
│     ┌───────────│ MAX_ATTEMPTS │──────────┐                 │
│     │           │   Reached?   │          │                 │
│     │           └──────────────┘          │                 │
│    NO                                    YES                │
│     │                                     │                 │
│     │                                     ▼                 │
│     │                               ┌──────────┐            │
│     └─────────────────────────────▶ │  Finish  │            │
│           (Continue loop)           └──────────┘            │
└─────────────────────────────────────────────────────────────┘
```

The flow automatically runs up to `MAX_ATTEMPTS` (default: 3) iterations, learning from previous attempts to improve strategy performance.

## 📁 Project Structure

```
crewai_trading_strategy/
├── data/                          # Historical price data
│   ├── BTC-USD_2014_2024.csv     # Bitcoin historical OHLCV data
│   └── ETH-USD_2017_2024.csv     # Ethereum historical data
├── output/                        # Generated outputs
│   ├── trading_strategy_outline.md
│   ├── trading_strategy_design.md
│   ├── trading_strategy_implementation.py
│   └── trading_strategy_creation_attempts_log.json
├── src/
│   ├── crewai_trading_strategy/
│   │   ├── crews/
│   │   │   ├── trading_strategy_crew/  # Main trading strategy crew
│   │   │   │   ├── config/
│   │   │   │   │   ├── agents.yaml    # Agent definitions
│   │   │   │   │   └── tasks.yaml     # Task definitions
│   │   │   │   └── trading_strategy_crew.py
│   │   │   └── dummy_developer_crew/  # Example/test crew
│   │   ├── tools/                     # Custom CrewAI tools
│   │   │   ├── execute_analysis_code_tool.py  # Run custom analysis
│   │   │   ├── get_for_date_range_tool.py     # Fetch price data
│   │   │   └── run_strategy_backtest_tool.py  # Backtest strategies
│   │   ├── guardrails/                # Input/output validation
│   │   ├── main.py                    # Main flow orchestration
│   │   ├── strategy_code_guidelines.py  # API specifications
│   │   ├── constants.py               # Project constants
│   │   └── types.py                   # Type definitions
│   └── utils/                         # Utility modules
│       ├── historical_daily_prices_helper.py
│       ├── strategy_backtester.py
│       ├── safe_python_code_executor.py
│       ├── code_utils.py
│       ├── date_utils.py
│       └── json_utils.py
├── tests/                         # Test suite
├── pyproject.toml                 # Project dependencies
├── .env                           # Environment variables (API keys)
└── README.md                      # This file
```

## 🚀 Installation and Setup

### Prerequisites

- **Python**: Version >=3.10 and <3.14
- **OpenAI API Key**: Required for the AI agents (or Anthropic API key if using Claude)

### Installation Steps

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd crewai_trading_strategy
   ```
2. **Install UV** (if not already installed)

   ```bash
   pip install uv
   ```
3. **Install project dependencies**

   ```bash
   crewai install
   ```

   Alternatively, using uv directly:

   ```bash
   uv pip install -e .
   ```
4. **Configure API Keys**

   Create a `.env` file in the project root with your API key:

   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## 📊 Usage

### Running the Trading Strategy Generator

To start the multi-agent workflow and generate trading strategies:

```bash
crewai flow kickoff
```

### What Happens During Execution

1. **Iteration Loop**: The flow runs up to 3 attempts (configurable via `MAX_ATTEMPTS`)
2. **Each Iteration**:
   - Strategy Researcher analyzes BTC historical data
   - Engineering Lead creates detailed design
   - Developer implements the strategy
   - Strategy is backtested automatically
   - Results are logged and fed into the next iteration
3. **Output**: All attempts are saved, and the best-performing strategy is selected
4. **Results**: Check the `output/` directory for:
   - Strategy outlines and designs
   - Implementation code
   - Backtest results
   - Full attempts log (JSON)

### Configuration

#### Modify Agent Behavior

Edit agent configurations in:

```
src/crewai_trading_strategy/crews/trading_strategy_crew/config/agents.yaml
```

You can change:

- Agent roles and goals
- LLM models (default: `gpt-4.1`)
- Agent backstories

#### Modify Tasks

Edit task definitions in:

```
src/crewai_trading_strategy/crews/trading_strategy_crew/config/tasks.yaml
```

You can adjust:

- Task descriptions and expected outputs
- Agent assignments
- Context dependencies
- Output file paths

#### Adjust Flow Parameters

Edit `src/crewai_trading_strategy/main.py`:

- Change `MAX_ATTEMPTS` for more/fewer iterations
- Modify the coin symbol (currently `BTC`)
- Adjust dataset date ranges
- Customize backtesting parameters

## 🔧 Tools and Features

### Custom CrewAI Tools

1. **Execute Analysis Code Tool** (`execute_analysis_code_tool.py`)

   - Allows agents to run custom Python analysis on the full dataset
   - Useful for complex statistical analysis and pattern recognition
2. **Get Price Data For Date Range Tool** (`get_for_date_range_tool.py`)

   - Fetches OHLCV data for specific date ranges (max 30 days)
   - Enables focused analysis on specific time periods
3. **Run Strategy Backtest Tool** (`run_strategy_backtest_tool.py`)

   - Executes strategy code against historical data
   - Returns performance metrics

### Backtesting Engine

The `StrategyBacktester` (`src/utils/strategy_backtester.py`) provides:

- Realistic trade execution simulation
- Portfolio management with USD and BTC holdings
- Stop-loss and take-profit order handling
- Comprehensive performance metrics:
  - Total revenue (USD and percentage)
  - Number of trades executed
  - Win/loss ratio
  - Maximum drawdown
  - Sharpe ratio

### Strategy API Guidelines

All generated strategies must follow a strict API contract defined in `strategy_code_guidelines.py`:

```python
def run(df, holdings):
    """
    df: pandas DataFrame with OHLCV data (Date, Open, High, Low, Close, Volume)
    holdings: list of current portfolio positions
  
    Returns: list of order dictionaries (BUY/SELL)
    """
    # Strategy logic here
    return orders
```

## 📈 Understanding the Output

### Strategy Outline (`output/trading_strategy_outline.md`)

High-level description of the trading strategy approach, including:

- Market analysis insights
- Trading signals and conditions
- Risk management approach

### Strategy Design (`output/trading_strategy_design.md`)

Detailed technical specification with:

- Function signatures
- Data structures
- Pseudocode
- Implementation details

### Strategy Implementation (`output/trading_strategy_implementation.py`)

Production-ready Python code that:

- Follows the strict API contract
- Includes technical indicators
- Manages positions and risk
- Returns executable orders

### Attempts Log (`output/trading_strategy_creation_attempts_log.json`)

Complete record of all iterations with:

- Full strategy code for each attempt
- Backtest results
- Performance metrics
- Timestamps

## 🧪 Testing

Run the test suite:

```bash
pytest
```

The project includes tests for:

- Utility functions
- Backtesting engine
- Code execution safety
- Data processing

## 🛠️ Development

### Adding New Cryptocurrencies

1. Add historical CSV data to the `data/` directory
2. Update constants in `src/crewai_trading_strategy/constants.py`
3. Modify `BASE_INPUTS` in `main.py` to include the new coin symbol and date range

### Creating Custom Agents

1. Define agent configuration in the appropriate YAML file
2. Create corresponding task definitions
3. Update the crew class to include the new agent

### Extending the Flow

The `TradingStrategyCreationFlow` class can be extended with additional steps:

- Pre-processing or data enrichment
- Additional validation steps
- Alternative backtesting strategies
- Post-processing and reporting

## 📝 Dependencies

Key dependencies (see `pyproject.toml` for full list):

- `crewai[anthropic,tools]==1.5.0` - Multi-agent framework
- `pandas>=2.3.3` - Data manipulation
- `pydantic>=2.12.5` - Data validation
- `pytest>=9.0.2` - Testing framework

## ⚠️ Disclaimer

This project is for educational and research purposes only. The generated trading strategies are not financial advice. Always perform thorough testing and validation before using any trading strategy with real funds. Cryptocurrency trading carries significant risk.


---

**Built with [CrewAI](https://crewai.com) - Empowering AI agents to collaborate on complex tasks**

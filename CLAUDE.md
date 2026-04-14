# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment and commands

- Python project managed with `pyproject.toml` and `uv.lock`.
- Prefer `uv` for local development commands.
- Always run Python through `uv` in this repo (`uv run python ...`); do not rely on bare `python`/`python3` from the system PATH.
- API keys are loaded from the repo-root `.env` file, which is gitignored.

### Install dependencies

```bash
uv sync
```

### Run the main trading-strategy flow

Use the CrewAI flow entrypoint from the package module:

```bash
uv run python -m crewai_trading_strategy.main
```

The project also defines console scripts in `pyproject.toml`:

```bash
uv run kickoff
uv run run_crew
uv run plot
```

### Run tests

Run all tests:

```bash
uv run pytest
```

Run a single test file:

```bash
uv run pytest tests/test_strategy_backtester.py
uv run pytest tests/test_safe_executor.py
uv run pytest tests/test_historical_prices.py
```

Run a single test:

```bash
uv run pytest tests/test_strategy_backtester.py -k warmup
```

## High-level architecture

This repository is a CrewAI-based pipeline that tries to generate a BTC trading strategy end-to-end, backtests it, and repeats that loop a few times to keep the best result.

### Runtime flow

Primary entrypoint: `src/crewai_trading_strategy/main.py`

- `TradingStrategyCreationFlow` is the orchestration layer.
- It runs up to `MAX_ATTEMPTS = 3` attempts.
- Each attempt invokes `TradingStrategyCrew`, captures the crew outputs, strips markdown formatting from the generated code, backtests the implementation, and appends the attempt to `state.attempts_log`.
- At the end, it picks the attempt with the best `revenue_percent` and writes the winning outline/design/code plus the full attempts log into `output/`.

Conceptually:

1. Research a strategy outline
2. Turn the outline into a technical design
3. Generate Python implementation code
4. Validate/backtest that code
5. Feed previous attempts back into the next iteration

### Crew structure

Main crew: `src/crewai_trading_strategy/crews/trading_strategy_crew/trading_strategy_crew.py`

The crew is sequential and has three agents configured via YAML:

- `strategy_researcher` researches BTC price behavior and can inspect data through custom tools
- `engineering_lead` converts the outline into an implementation design
- `developer` writes the final strategy code

Prompt/config sources:

- agents: `src/crewai_trading_strategy/crews/trading_strategy_crew/config/agents.yaml`
- tasks: `src/crewai_trading_strategy/crews/trading_strategy_crew/config/tasks.yaml`

The task outputs are written to `output/` and also consumed by the orchestration flow.

There is also a smaller `dummy_developer_crew` used for isolated developer-task experiments, but the main application path is the trading-strategy crew.

### Data and execution model

Dataset constants live in `src/crewai_trading_strategy/constants.py`.

- The main dataset path is `data/BTC-USD_2014_2024.csv`.
- Dataset bounds used by the system are `2017-11-10` through `2024-01-19`.

`src/utils/historical_daily_prices_helper.py` is the core data access layer:

- loads the CSV into a pandas DataFrame indexed by `Date`
- validates OHLCV columns
- exposes bounded date-range queries
- exposes `get_df_until_date(...)` for no-lookahead strategy inputs
- exposes `executeCode(...)` to run user/agent analysis code against a copy of the dataset with a materialized `Date` column

### Strategy contract and backtesting

The generated strategy code must follow the contract defined in `src/crewai_trading_strategy/strategy_code_guidelines.py`:

- return a single self-contained Python snippet
- define a top-level `run(df, holdings)` function
- consume only historical rows already available before the execution day
- return a list of BUY/SELL order dicts matching the documented schema

`src/utils/strategy_backtester.py` is the most important domain module.

It is responsible for:

- maintaining portfolio state (`USD` cash plus BTC holdings)
- compiling and executing strategy code through the safe executor
- enforcing that `run(df, holdings)` exists and has the correct signature
- validating BUY/SELL orders through Pydantic discriminated unions
- simulating order execution across trading dates
- enforcing stop-loss / take-profit rules intraday
- returning either a structured `BacktestResult` or an error string

Important behavioral detail: the strategy only sees history up to the previous day, and sizing/execution is currently based on the last known close, not the current day's open. The code comments note this simplification explicitly.

### Sandbox / safe code execution

`src/utils/safe_python_code_executor.py` provides AST-level validation plus restricted execution.

Allowed analysis/strategy code can use only a small safe subset:

- standard modules: `math`, `statistics`, `datetime`, `re`
- scientific libs: `numpy`, `pandas`

It blocks imports outside that allowlist and rejects dangerous builtins/attributes such as `open`, `eval`, `exec`, and object-introspection escape hatches.

This executor is used both for:

- research-time custom analysis over the full dataset
- runtime compilation of generated strategy code before backtesting

### Crew tools and guardrails

Custom tools live under `src/crewai_trading_strategy/tools/`.

They provide the researcher/backtester interfaces:

- `get_for_date_range_tool.py`: small bounded OHLCV queries, capped at 30 days
- `execute_analysis_code_tool.py`: run safe Python analysis against the full dataset
- `run_strategy_backtest_tool.py`: wrap `StrategyBacktester` for a fixed backtest window

Guardrail:

- `src/crewai_trading_strategy/guardrails/backtester_guardrail.py`
- validates the developer task output by extracting the generated implementation and immediately backtesting it
- the implement task retries up to 5 times if validation fails

### Output artifacts

Generated artifacts are written under `output/`:

- `trading_strategy_outline.md`
- `trading_strategy_design.md`
- `trading_strategy_implementation.py`
- `trading_strategy_creation_attempts_log.json`

These files are part of the runtime workflow, not just documentation. Be careful not to break paths expected by `main.py`.

## Testing structure

Tests are focused on the three core non-LLM subsystems:

- `tests/test_historical_prices.py`: dataset loading, range slicing, and code-execution inputs
- `tests/test_safe_executor.py`: sandbox restrictions and safe execution behavior
- `tests/test_strategy_backtester.py`: backtest rules, warm-up requirements, order validation, and stop-loss/take-profit behavior

For code changes, run only the relevant test module(s).

## Important repository-specific notes

- The repo uses `src/` layout, but some local imports use top-level package names like `from utils...`; keep that in mind when changing execution paths.
- `pyproject.toml` declares a `run_with_trigger` script, but there is no corresponding `run_with_trigger` function in `src/crewai_trading_strategy/main.py`.
- The README contains some architecture/performance descriptions that are broader than the current implementation. When in doubt, trust the source files over the README.
- The main flow currently hardcodes BTC inputs through `BASE_INPUTS` in `src/crewai_trading_strategy/main.py`; this is not yet a generic multi-asset pipeline.

from __future__ import annotations

from datetime import timedelta
from typing import Type, Any, Tuple

from crewai import TaskOutput
from crewai_trading_strategy.constants import BTC_DATASET_END_DATE, BTC_DATASET_START_DATE
from crewai_trading_strategy.types import ImplementationTaskOutput
from utils.code_utils import strip_llm_formatting
from utils.date_utils import parse_yyyy_mm_dd
from utils.strategy_backtester import StrategyBacktester

# Backtest window constants
START_DATE = parse_yyyy_mm_dd(BTC_DATASET_START_DATE) + timedelta(days=1)
END_DATE = parse_yyyy_mm_dd(BTC_DATASET_END_DATE)

class ValidateBacktesterGuardrail:
    _backtester: StrategyBacktester

    def __init__(self, backtester: StrategyBacktester):
        self._backtester = backtester

    def get_guardrail_function(self):
        return lambda task_output: self._validate_backtest_on_strategy(task_output)

    def _validate_backtest_on_strategy(self, task_output: TaskOutput) -> Tuple[bool, Any]:

        model = task_output.pydantic
        if model is None:
            return False, "Task output could not be parsed into the expected Pydantic model."

        if not isinstance(model, ImplementationTaskOutput):
            return False, f"Unexpected output type: {type(model)}"

        code = strip_llm_formatting(model.implementation)
        result = self._backtester.test_strategy(
            start_date=START_DATE,
            end_date=END_DATE,
            trading_strategy_code=code,
        )

        # Error string
        if isinstance(result, str):
            return False, result

        # BacktestResult is valid
        return True, code
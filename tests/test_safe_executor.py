# tests/test_safe_executor.py
import pytest

from utils.safe_python_code_executor import SafePythonCodeExecutor


def test_check_and_compile_rejects_empty():
    ex = SafePythonCodeExecutor()
    with pytest.raises(ValueError, match="non-empty"):
        ex.check_and_compile("   \n")


def test_check_and_compile_rejects_syntax_error():
    ex = SafePythonCodeExecutor()
    with pytest.raises(ValueError, match="syntax"):
        ex.check_and_compile("def bad(:\n  pass\n")


def test_check_and_compile_blocks_unsafe_import():
    ex = SafePythonCodeExecutor()
    code = """
import os
def runOnData(df):
    return 1
"""
    with pytest.raises(ValueError, match="Unsafe import"):
        ex.check_and_compile(code)


def test_check_and_compile_blocks_banned_name_open():
    ex = SafePythonCodeExecutor()
    code = """
def runOnData(df):
    f = open("x.txt", "w")
    return 1
"""
    with pytest.raises(ValueError, match="banned name"):
        ex.check_and_compile(code)


def test_execute_compiled_runs_and_returns_namespace():
    ex = SafePythonCodeExecutor()
    code = """
def runOnData(df):
    return 123
"""
    compiled = ex.check_and_compile(code)
    ns = ex.execute_compiled(compiled)
    assert "runOnData" in ns
    assert callable(ns["runOnData"])
    assert ns["runOnData"](None) == 123


def test_execute_compiled_can_use_injected_np_without_import():
    ex = SafePythonCodeExecutor()
    code = """
def runOnData(df):
    return int(np.sum([1, 2, 3]))
"""
    compiled = ex.check_and_compile(code)
    ns = ex.execute_compiled(compiled)
    assert ns["runOnData"](None) == 6

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
def run_on_data(df):
    return 1
"""
    with pytest.raises(ValueError, match="Unsafe import"):
        ex.check_and_compile(code)


def test_check_and_compile_blocks_banned_name_open():
    ex = SafePythonCodeExecutor()
    code = """
def run_on_data(df):
    f = open("x.txt", "w")
    return 1
"""
    with pytest.raises(ValueError, match="banned name"):
        ex.check_and_compile(code)


def test_execute_compiled_runs_and_returns_namespace():
    ex = SafePythonCodeExecutor()
    code = """
def run_on_data(df):
    return 123
"""
    compiled = ex.check_and_compile(code)
    ns = ex.execute_compiled(compiled)
    assert "run_on_data" in ns
    assert callable(ns["run_on_data"])
    assert ns["run_on_data"](None) == 123


def test_execute_with_helper_function():
    ex = SafePythonCodeExecutor()
    code = """
def helper_function():
    return 42

def run_on_data(df):
    return helper_function()
"""
    compiled = ex.check_and_compile(code)
    ns = ex.execute_compiled(compiled)
    assert "helper_function" in ns
    assert "run_on_data" in ns
    assert ns["run_on_data"](None) == 42


def test_execute_with_class_definition():
    ex = SafePythonCodeExecutor()
    code = """
class Adder:
    def __init__(self, x):
        self.x = x
    def add(self, y):
        return self.x + y

def run_on_data(df):
    return Adder(10).add(5)
"""
    compiled = ex.check_and_compile(code)
    ns = ex.execute_compiled(compiled)
    assert "Adder" in ns
    assert ns["run_on_data"](None) == 15


def test_execute_class_method_can_call_helper():
    ex = SafePythonCodeExecutor()
    code = """
def helper(x):
    return x * 2

class Model:
    def score(self, x):
        return helper(x) + 1

def run_on_data(df):
    return Model().score(20)
"""
    compiled = ex.check_and_compile(code)
    ns = ex.execute_compiled(compiled)
    assert ns["run_on_data"](None) == 41


def test_execute_compiled_can_use_injected_np_without_import():
    ex = SafePythonCodeExecutor()
    code = """
def run_on_data(df):
    return int(np.sum([1, 2, 3]))
"""
    compiled = ex.check_and_compile(code)
    ns = ex.execute_compiled(compiled)
    assert ns["run_on_data"](None) == 6

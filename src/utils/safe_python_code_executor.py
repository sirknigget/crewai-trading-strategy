from __future__ import annotations

import ast
import datetime as dt
from typing import Any, Optional, Union

import pandas as pd
import numpy as np



class SafePythonCodeExecutor:
    """
    Best-effort restricted executor for user-provided Python source.

    Responsibilities:
      - Parse + validate code (imports + banned names)
      - Compile code
      - Execute compiled code with restricted builtins + safe import hook
    """
    def __init__(
        self,
        allowed_modules: Optional[set[str]] = None,
        banned_names: Optional[set[str]] = None,
    ):
        self.allowed_modules = allowed_modules or {
            "math", "statistics", "datetime", "re",
            "numpy", "pandas",
        }
        self.banned_names = banned_names or {
            "__import__", "open", "exec", "eval", "compile", "input",
            "globals", "locals", "vars", "dir", "help",
            "getattr", "setattr", "delattr",
        }

    def check_and_compile(self, code: str) -> Any:
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code must be a non-empty string.")

        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as e:
            raise ValueError(f"Provided code has a syntax error: {e}") from e

        # Import allowlist + banned-name check using AST. [web:21]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".", 1)[0]
                    if top not in self.allowed_modules:
                        raise ValueError(f"Unsafe import not allowed: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    raise ValueError("Unsafe relative import is not allowed.")
                top = node.module.split(".", 1)[0]
                if top not in self.allowed_modules:
                    raise ValueError(f"Unsafe import not allowed: from {node.module} import ...")
            elif isinstance(node, ast.Name) and node.id in self.banned_names:
                raise ValueError(f"Use of banned name is not allowed: {node.id}")

        return compile(tree, filename="<user_code>", mode="exec")

    def execute_compiled(
        self,
        compiled: Any,
        injected_globals: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        # Safe import hook: blocks non-allowlisted imports at runtime too. [web:26][web:34]
        def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            top = name.split(".", 1)[0]
            if top not in self.allowed_modules:
                raise ImportError(f"Import blocked: {name}")
            return __import__(name, globals, locals, fromlist, level)

        safe_builtins = {
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "print": print,
            "len": len,
            "range": range,
            "min": min,
            "max": max,
            "sum": sum,
            "abs": abs,
            "sorted": sorted,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "all": all,
            "any": any,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "float": float,
            "int": int,
            "str": str,
            "bool": bool,
            "__import__": _safe_import,
        }

        exec_globals = {
            "__builtins__": safe_builtins,
            "pd": pd,
            "np": np,
        }
        if injected_globals:
            exec_globals.update(injected_globals)

        exec_locals: dict[str, Any] = {}
        exec(compiled, exec_globals, exec_locals)
        return {**exec_globals, **exec_locals}

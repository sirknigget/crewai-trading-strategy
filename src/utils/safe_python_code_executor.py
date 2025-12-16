from __future__ import annotations

import ast
import builtins as py_builtins
from types import MappingProxyType
from typing import Any, Optional

import pandas as pd
import numpy as np


class SafePythonCodeExecutor:
    def __init__(
        self,
        allowed_modules: Optional[set[str]] = None,
        banned_names: Optional[set[str]] = None,
        banned_builtins: Optional[set[str]] = None,
        banned_attributes: Optional[set[str]] = None,
    ):
        self.allowed_modules = allowed_modules or {
            "math", "statistics", "datetime", "re",
            "numpy", "pandas",
        }

        self.banned_names = banned_names or {
            "__import__", "open", "exec", "eval", "compile", "input",
            "globals", "locals", "vars", "dir", "help",
            "getattr", "setattr", "delattr",
            # block grabbing the provided builtins dict directly
            "__builtins__",
        }

        # Allow classes: DO NOT ban __build_class__/object/type/super.
        self.banned_builtins = banned_builtins or {
            "eval", "exec", "compile",  # arbitrary code execution
            "open", "input", "breakpoint",  # IO / debugger
            "globals", "locals", "vars", "dir", "help",  # introspection helpers
            "getattr", "setattr", "delattr",  # attribute escape helpers
        }

        # Target common sandbox-escape introspection attributes (don’t ban all dunders).
        self.banned_attributes = banned_attributes or {
            "__class__", "__subclasses__", "__bases__", "__mro__",
            "__getattribute__", "__getattr__", "__setattr__", "__delattr__",
            "__dict__", "__globals__", "__code__", "__closure__",
            # frame/coroutine/generator introspection (often used to reach globals)
            "f_globals", "f_locals",
            "gi_frame", "cr_frame",
        }

    def check_and_compile(self, code: str) -> Any:
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code must be a non-empty string.")

        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as e:
            raise ValueError(f"Provided code has a syntax error: {e}") from e

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

            elif isinstance(node, ast.Attribute) and node.attr in self.banned_attributes:
                raise ValueError(f"Access to banned attribute is not allowed: .{node.attr}")

        return compile(tree, filename="<user_code>", mode="exec")

    def _build_safe_builtins(self, safe_import) -> MappingProxyType:
        safe: dict[str, Any] = {}

        for name, obj in py_builtins.__dict__.items():
            # Keep most builtins, but drop private ones EXCEPT __build_class__ (needed for 'class').
            if name.startswith("_") and name != "__build_class__":
                continue
            if name in self.banned_builtins:
                continue
            safe[name] = obj

        # Force the sandbox import hook.
        safe["__import__"] = safe_import

        return MappingProxyType(safe)

    def execute_compiled(
        self,
        compiled: Any,
        injected_globals: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            top = name.split(".", 1)[0]
            if top not in self.allowed_modules:
                raise ImportError(f"Import blocked: {name}")
            return py_builtins.__import__(name, globals, locals, fromlist, level)

        safe_builtins = self._build_safe_builtins(_safe_import)

        exec_globals = {
            "__builtins__": safe_builtins,
            "__name__": "__sandbox__",  # helps some class/module behaviors
            "pd": pd,
            "np": np,
        }
        if injected_globals:
            exec_globals.update(injected_globals)

        exec_locals: dict[str, Any] = {}
        exec(compiled, exec_globals, exec_locals)
        return {**exec_globals, **exec_locals}

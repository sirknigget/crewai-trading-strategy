def strip_llm_formatting(code: str) -> str:
    """Strips away LLM formatting if present around the Python code."""
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    return code
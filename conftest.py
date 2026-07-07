"""Pytest bootstrap: put the repo root on sys.path so `import src...` works.

Its presence at the repo root is what makes the top-level tests/ able to import
the src package under pytest's default (prepend) import mode.
"""

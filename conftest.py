"""Root conftest: puts the repo root on sys.path so `evals.*` imports resolve.

The evals subsystem deliberately keeps the spec's flat layout
(`evals/{permitbench,metrics.py,runner.py}`, ARCHITECTURE §10) instead of a
packaged src/ tree; pytest and tooling reach it through this file's presence.
"""

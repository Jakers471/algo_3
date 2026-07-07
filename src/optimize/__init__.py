"""Optimize area: search a parameter grid over one window, rank by objective.

The machinery walk-forward stands on: grid.py expands the search space,
objective.py scores a result, sweep.py runs the grid and ranks it. It only
optimizes on the window it is handed - keeping in-sample and out-of-sample
strictly separate is the caller's (walkforward's) job.
"""

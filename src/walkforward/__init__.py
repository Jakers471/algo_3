"""Walk-forward area: optimize on in-sample windows, test out-of-sample, stitch.

folds.py generates the IS/OOS window pairs; wfaspec.py is the JSON run config;
engine.py orchestrates - for each fold it sweeps params on IS, picks the best,
runs them on OOS, and stitches the OOS trades into one honest equity curve.
The judgement is on the stitched OOS, never the in-sample optimization.
"""

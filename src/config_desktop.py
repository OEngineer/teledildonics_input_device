# Desktop shim: re-exports STROKE_* constants from config.py without MicroPython deps.
# Used by tools/plot_strokes.py to annotate plots with current parameter values.
STROKE_EMA_ALPHA         = 0.25
STROKE_MIN_AMPLITUDE     = 8
STROKE_STOPPED_WINDOW    = 5
STROKE_STOPPED_THRESHOLD = 2
STROKE_POLL_MS           = 100
STROKE_MIN_MOVE_MS       = 300
STROKE_INITIAL_MOVE_MS   = 2000
STROKE_MOTION_MARGIN_MS  = 50

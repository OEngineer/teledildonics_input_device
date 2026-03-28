#!/usr/bin/env python3
"""
Plot raw insertion, EMA, and BLE emit decision points from device serial output.

Usage:
  # Capture live from device and plot when done (Ctrl-C to stop):
  mpremote repl | python tools/plot_strokes.py

  # Or save first, then plot:
  mpremote repl | tee capture.txt
  python tools/plot_strokes.py capture.txt

Enable logging on the device by setting STROKE_LOG = True in src/config.py,
then deploying: mpremote cp src/config.py :/config.py

CSV lines emitted by the device have the form:
  S,<t_ms>,<raw>,<ema>,<emit>
All other lines are ignored.
"""

import sys
import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

LINE_RE = re.compile(r"^S,(\d+),(\d+),([\d.]+),([01])$")


def parse(source):
    t, raw, ema, emits = [], [], [], []
    for line in source:
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        line = line.strip()
        m = LINE_RE.match(line)
        if not m:
            continue
        t.append(int(m.group(1)))
        raw.append(int(m.group(2)))
        ema.append(float(m.group(3)))
        emits.append(int(m.group(4)))
    return t, raw, ema, emits


def plot(t, raw, ema, emits, title="Stroke detector"):
    if not t:
        print("No S,... lines found in input.", file=sys.stderr)
        sys.exit(1)

    t_s = [x / 1000.0 for x in t]
    emit_t = [t_s[i] for i, e in enumerate(emits) if e]
    emit_y = [ema[i]  for i, e in enumerate(emits) if e]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(t_s, raw, color="steelblue", alpha=0.45, linewidth=1, label="raw insertion")
    ax.plot(t_s, ema, color="darkorange", linewidth=1.5, label="EMA")
    ax.scatter(emit_t, emit_y, color="red", s=60, zorder=5, label="BLE emit")

    ax.set_xlabel("time (s)")
    ax.set_ylabel("position (0–100)")
    ax.set_ylim(-5, 105)
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(which="major", alpha=0.3)
    ax.grid(which="minor", alpha=0.1)
    ax.legend(loc="upper right")
    ax.set_title(title)

    # Annotate config values from src/config.py if importable
    try:
        import importlib.util, os
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "src", "config_desktop.py")
        spec = importlib.util.spec_from_file_location("config_desktop", cfg_path)
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        params = (
            f"alpha={cfg.STROKE_EMA_ALPHA}  min_amp={cfg.STROKE_MIN_AMPLITUDE}  "
            f"stop_win={cfg.STROKE_STOPPED_WINDOW}  stop_thr={cfg.STROKE_STOPPED_THRESHOLD}  "
            f"poll={cfg.STROKE_POLL_MS}ms  min_move={cfg.STROKE_MIN_MOVE_MS}ms"
        )
        ax.set_title(f"{title}\n{params}", fontsize=9)
    except Exception:
        pass

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            t, raw, ema, emits = parse(f)
    else:
        t, raw, ema, emits = parse(sys.stdin)
    plot(t, raw, ema, emits)

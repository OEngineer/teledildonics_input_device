"""touch_analysis.py - Calibration and analysis of multi-touch sensor values.

Provides normalization using persistent calibration data, and derives:
  - insertion: fraction of sensors actively engaged
  - focus: concentration of activity (higher when fewer sensors active)
  - center: weighted-average position of activity along the shaft (0=base, 1=tip)
"""

import asyncio
from time import ticks_ms, ticks_diff

try:
    import ujson as json
except ImportError:
    import json

CALIBRATION_FILE = '/calibration.json'
ACTIVE_THRESHOLD = 0.1   # normalized value to consider a sensor "active"


class TouchAnalyzer:
    """Wraps a MultiTouchSensor to add calibration, normalization, and metrics."""

    def __init__(self, sensor, active_threshold=ACTIVE_THRESHOLD):
        self._sensor = sensor
        self._n = sensor.num_pins
        self._active_threshold = active_threshold
        self._offsets = [0] * self._n   # idle baseline per sensor
        self._scales  = [1] * self._n   # touch range per sensor
        self._load_calibration()

    # ------------------------------------------------------------------ #
    # Calibration                                                          #
    # ------------------------------------------------------------------ #

    def _load_calibration(self):
        try:
            with open(CALIBRATION_FILE, 'r') as f:
                data = json.load(f)
            self._offsets = data['offsets']
            self._scales  = data['scales']
            print("Calibration loaded.")
        except (OSError, KeyError, ValueError):
            print("No valid calibration found; using defaults.")

    def _save_calibration(self):
        data = {'offsets': self._offsets, 'scales': self._scales}
        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(data, f)
        print("Calibration saved.")

    async def calibrate(self, rest_ms=3000, handle_ms=10000, sample_interval_ms=50):
        """Two-phase calibration.

        Phase 1 (rest_ms):   set the device down and do not touch it.
                             Captures the idle baseline (offset) per sensor.
        Phase 2 (handle_ms): pick up and handle the device naturally.
                             Captures the peak touch value per sensor.

        On ESP32-S3 the raw value increases when touched, so:
          offset = minimum seen at rest  (idle baseline)
          scale  = peak during handling - offset  (full dynamic range)

        Results are persisted to CALIBRATION_FILE.
        """
        n = self._n

        # --- Phase 1: rest ---
        rest_mins = [0x7FFFFFFF] * n
        print("Phase 1 ({} s): set the device down - do not touch it.".format(
            rest_ms // 1000))
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) < rest_ms:
            raw = await self._sensor.read_async()
            for i, v in enumerate(raw):
                if v < rest_mins[i]:
                    rest_mins[i] = v
            await asyncio.sleep_ms(sample_interval_ms)

        # --- Phase 2: handle ---
        handle_maxs = [0] * n
        print("Phase 2 ({} s): handle the device now.".format(handle_ms // 1000))
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) < handle_ms:
            raw = await self._sensor.read_async()
            for i, v in enumerate(raw):
                if v > handle_maxs[i]:
                    handle_maxs[i] = v
            await asyncio.sleep_ms(sample_interval_ms)

        self._offsets = list(rest_mins)
        # Guard against a sensor that was never touched: floor scale at 1
        self._scales  = [max(1, handle_maxs[i] - rest_mins[i]) for i in range(n)]

        print("Calibration done.")
        print("  offsets:", self._offsets)
        print("  scales: ", self._scales)
        self._save_calibration()

    # ------------------------------------------------------------------ #
    # Normalization                                                        #
    # ------------------------------------------------------------------ #

    def normalize(self, raw_values):
        """Normalize raw sensor readings to [0.0, 1.0].

        0.0 = untouched, 1.0 = maximum touch observed during calibration.
        """
        result = []
        for i, raw in enumerate(raw_values):
            scale = self._scales[i]
            if scale == 0:
                result.append(0.0)
            else:
                v = (raw - self._offsets[i]) / scale
                result.append(max(0.0, min(1.0, v)))
        return result

    async def read_normalized(self):
        """Read sensors and return a list of normalized [0.0, 1.0] values."""
        return self.normalize(await self._sensor.read_async())

    # ------------------------------------------------------------------ #
    # Derived metrics                                                      #
    # ------------------------------------------------------------------ #

    def insertion(self, normalized):
        """Insertion / engagement level [0.0, 1.0].

        Rises as more sensors (and more intensely) show activity.  Computed
        as the mean of all normalized values so it reflects both the count
        of active sensors and their individual magnitudes.
        """
        n = len(normalized)
        return sum(normalized) / n if n else 0.0

    def focus(self, normalized):
        """Focus level [0.0, 1.0].

        Higher when activity is concentrated on fewer sensors.  Combines:
          - spread: contrast between the most and least active sensor
          - concentration: fraction of sensors that are *not* active

        Both factors must be non-zero to produce a non-zero focus value,
        so uniform all-sensor or zero activity both yield 0.0.
        """
        n = len(normalized)
        if n == 0:
            return 0.0

        max_val = max(normalized)
        if max_val < self._active_threshold:
            return 0.0          # nothing is happening

        min_val = min(normalized)
        spread = max_val - min_val  # contrast between most and least active

        num_active = sum(1 for v in normalized if v >= self._active_threshold)

        # concentration: 1.0 when only 1 sensor active, 0.0 when all active
        concentration = (1.0 - (num_active - 1) / (n - 1)) if n > 1 else 1.0

        return spread * concentration

    def center_of_activity(self, normalized):
        """Weighted-average position of activity along the shaft.

        Returns a value in [0.0, 1.0] where 0.0 is the base (sensor 0) and
        1.0 is the tip (sensor n-1).  Returns None when there is no activity.
        """
        n = len(normalized)
        if n == 0:
            return None

        total = sum(normalized)
        if total == 0.0:
            return None

        if n == 1:
            return 0.0

        weighted = sum((i / (n - 1)) * normalized[i] for i in range(n))
        return weighted / total

    # ------------------------------------------------------------------ #
    # Convenience                                                          #
    # ------------------------------------------------------------------ #

    async def analyze(self):
        """Read sensors and return a dict with all metrics.

        Keys:
          'normalized' - list of per-sensor normalized values
          'insertion'  - float [0, 1]
          'focus'      - float [0, 1]
          'center'     - float [0, 1] or None
        """
        normalized = await self.read_normalized()
        return {
            'normalized': normalized,
            'insertion':  self.insertion(normalized),
            'focus':      self.focus(normalized),
            'center':     self.center_of_activity(normalized),
        }

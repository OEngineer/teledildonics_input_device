class StrokeDetector:
    """
    Detects stroke extrema (peaks and troughs) in a 0-100 insertion signal.

    Uses EMA smoothing only for direction detection.  Tracks the raw
    peak/trough seen during each direction run and emits that value (not the
    lagging EMA) when a reversal with sufficient amplitude is confirmed.
    Also emits on sustained stillness.  Call update() at a fixed rate;
    returns (emit, pos_int) on every sample.
    """

    def __init__(self, ema_alpha, min_amplitude, stopped_window, stopped_threshold,
                 history_len=10):
        """
        ema_alpha         - EMA weight for new samples (0 < alpha < 1; lower = smoother)
        min_amplitude     - minimum change (0-100 units) from last extremum to emit
        stopped_window    - consecutive STROKE_POLL_MS samples within threshold -> stopped
        stopped_threshold - position units defining "not moving"
        history_len       - unused; kept for API compatibility
        """
        self.ema_alpha = ema_alpha
        self.min_amplitude = min_amplitude
        self.stopped_window = stopped_window
        self.stopped_threshold = stopped_threshold
        self._smoothed = None
        self._prev = None
        self._direction = 0   # 0=unknown, 1=rising, -1=falling
        self._raw_extreme = None  # best raw value seen in current direction run
        self._last_extreme = None # raw value of the last emitted extremum
        self._stable_count = 0
        self._last_emit = None
        self._stopped_armed = True

    def reset(self):
        """Clear all state (call when reconnecting)."""
        self._smoothed = None
        self._prev = None
        self._direction = 0
        self._raw_extreme = None
        self._last_extreme = None
        self._stable_count = 0
        self._last_emit = None
        self._stopped_armed = True

    def update(self, raw):
        """
        Feed the next insertion sample (0-100, int or float).
        Returns (emit: bool, pos: int).
        On the first call, always emits so the caller can send an initial position.
        """
        raw = float(raw)

        if self._smoothed is None:
            self._smoothed = raw
            self._prev = raw
            self._last_extreme = raw
            self._last_emit = raw
            self._raw_extreme = raw
            return True, round(raw)

        # EMA smoothing (used only for direction detection)
        self._smoothed = self.ema_alpha * raw + (1 - self.ema_alpha) * self._smoothed

        delta = self._smoothed - self._prev
        self._prev = self._smoothed

        # Classify direction with deadband to avoid triggering on tiny noise
        if delta > 0.5:
            new_dir = 1
        elif delta < -0.5:
            new_dir = -1
        else:
            new_dir = self._direction  # hold current direction through flat region

        emit = False
        emit_pos = self._smoothed

        # Track raw extremum in the current direction run
        if self._direction == 1:
            if raw > self._raw_extreme:
                self._raw_extreme = raw
        elif self._direction == -1:
            if raw < self._raw_extreme:
                self._raw_extreme = raw

        # Extremum: direction reversal with sufficient amplitude from last emitted extreme.
        # Emit the raw peak/trough, not the lagging EMA value.
        if new_dir != 0 and new_dir != self._direction and self._direction != 0:
            if abs(self._raw_extreme - self._last_extreme) >= self.min_amplitude:
                emit = True
                emit_pos = self._raw_extreme
                self._last_extreme = self._raw_extreme
            # Reset raw extremum tracker for the new direction run
            self._raw_extreme = raw

        if new_dir != 0:
            self._direction = new_dir

        # Stopped: position hasn't moved beyond threshold sample-to-sample for stopped_window samples.
        # Re-arms only after a stopped emit, once position moves meaningfully.
        if abs(delta) > self.stopped_threshold:
            self._stable_count = 0
        elif self._stopped_armed:
            self._stable_count += 1
            if self._stable_count >= self.stopped_window:
                emit = True
                emit_pos = self._smoothed
                self._stable_count = 0
                self._stopped_armed = False

        # Re-arm stopped detection once position moves far enough from where we last stopped.
        if not self._stopped_armed and abs(self._smoothed - self._last_emit) > self.min_amplitude:
            self._stopped_armed = True

        if emit:
            self._last_emit = emit_pos

        return emit, round(emit_pos)

    @property
    def smoothed(self):
        return self._smoothed if self._smoothed is not None else 0.0

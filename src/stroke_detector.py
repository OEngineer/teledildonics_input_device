class StrokeDetector:
    """
    Detects stroke extrema (peaks and troughs) in a 0-100 insertion signal.

    Applies EMA smoothing, then emits on direction reversal (with minimum amplitude
    guard) and on sustained stillness.  Call update() at a fixed rate; it returns
    (emit, smoothed_pos_int) on every sample.
    """

    def __init__(self, ema_alpha, min_amplitude, stopped_window, stopped_threshold):
        """
        ema_alpha         - EMA weight for new samples (0 < alpha < 1; lower = smoother)
        min_amplitude     - minimum change (0-100 units) from last extremum to emit
        stopped_window    - consecutive samples within stopped_threshold before emitting
        stopped_threshold - position units defining "not moving"
        """
        self.ema_alpha = ema_alpha
        self.min_amplitude = min_amplitude
        self.stopped_window = stopped_window
        self.stopped_threshold = stopped_threshold
        self._smoothed = None
        self._prev = None
        self._direction = 0   # 0=unknown, 1=rising, -1=falling
        self._last_extreme = None
        self._stable_count = 0
        self._last_emit = None
        self._stopped_armed = True

    def reset(self):
        """Clear all state (call when reconnecting)."""
        self._smoothed = None
        self._prev = None
        self._direction = 0
        self._last_extreme = None
        self._stable_count = 0
        self._last_emit = None
        self._stopped_armed = True

    def update(self, raw):
        """
        Feed the next insertion sample (0-100, int or float).
        Returns (emit: bool, smoothed_pos: int).
        On the first call, always emits so the caller can send an initial position.
        """
        if self._smoothed is None:
            self._smoothed = float(raw)
            self._prev = float(raw)
            self._last_extreme = float(raw)
            self._last_emit = float(raw)
            return True, round(raw)

        # EMA smoothing
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

        # Extremum: direction reversal with sufficient amplitude from last extreme
        if new_dir != 0 and new_dir != self._direction and self._direction != 0:
            if abs(self._smoothed - self._last_extreme) >= self.min_amplitude:
                emit = True
                self._last_extreme = self._smoothed

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
                self._stable_count = 0
                self._stopped_armed = False

        # Re-arm stopped detection once position moves far enough from where we last stopped.
        if not self._stopped_armed and abs(self._smoothed - self._last_emit) > self.min_amplitude:
            self._stopped_armed = True

        if emit:
            self._last_emit = self._smoothed

        return emit, round(self._smoothed)

    @property
    def smoothed(self):
        return self._smoothed if self._smoothed is not None else 0.0

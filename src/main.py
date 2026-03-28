import asyncio, machine, esp32
from machine import Pin
from time import ticks_ms, ticks_diff
import touch_sensor, touch_analysis
from config import (
    WAKEUP_PIN, SLEEP_TIMEOUT_MS, BLE_SPEED, BLE_DEPTH, BLE_STROKE,
    STROKE_EMA_ALPHA, STROKE_MIN_AMPLITUDE,
    STROKE_STOPPED_WINDOW, STROKE_STOPPED_THRESHOLD,
    STROKE_PEAK_HISTORY, STROKE_POLL_MS, STROKE_MIN_MOVE_MS, STROKE_INITIAL_MOVE_MS,
    STROKE_LOG,
)
from touch_analysis import ACTIVE_THRESHOLD
from ble_remote import OSSMRemote, RECONNECT_DELAY_MS
from stroke_detector import StrokeDetector
from queue import Queue, QueueFull

# IO21: RTC pin, internal pull-up; button shorts to GND to wake from deep sleep.
# hold=True ensures that pull-up is maintained in deep-sleep.
_wakeup_pin = Pin(WAKEUP_PIN, Pin.IN, Pin.PULL_UP, hold=True)

# Log wakeup reason once on boot.
_reset_cause = machine.reset_cause()
if _reset_cause == machine.DEEPSLEEP_RESET:
    print("Woke from deep sleep (button press).")
else:
    print(f"Cold boot (reset cause {_reset_cause}).")

s = touch_sensor.MultiTouchSensor()
a = touch_analysis.TouchAnalyzer(s)

# Shared state: run_output writes here; ble_task reads from it.
_last_analyzed = {}

if not a._calibrated:
    yn = input("Do you want to calibrate now (y/n)?")
    if yn.lower() in ("y", "yes"):
        asyncio.run(a.calibrate())

# Shared idle-tracking state.
_last_active_ms = ticks_ms()

def recalibrate():
    asyncio.run(a.calibrate())

def _record_activity():
    global _last_active_ms
    _last_active_ms = ticks_ms()


def _enter_deepsleep():
    print(f"Entering deep sleep. Press IO{WAKEUP_PIN} button to wake.")
    # EXT0 wakeup: wake when the pin is driven low (button press pulls to GND).
    esp32.wake_on_ext0(_wakeup_pin, 0)
    machine.deepsleep()


async def idle_monitor():
    """Sleep the device after SLEEP_TIMEOUT_MS of no touch activity."""
    while True:
        await asyncio.sleep_ms(1000)
        if ticks_diff(ticks_ms(), _last_active_ms) >= SLEEP_TIMEOUT_MS:
            _enter_deepsleep()


async def run_output():
    global _last_analyzed
    while True:
        analyzed = await a.analyze()
        _last_analyzed = analyzed
        if analyzed["insertion"] >= ACTIVE_THRESHOLD:
            _record_activity()
        print(
            f"focus: {analyzed['focus'] * 100:.0f} insertion: {analyzed['insertion'] * 100:.0f} center: {analyzed['center'] * 100:.0f}"
        )
        await asyncio.sleep_ms(100)


_stroke_queue = Queue(maxsize=4)


async def stroke_task():
    """Detect stroke extrema and enqueue (position, interval_ms) tuples."""
    detector = StrokeDetector(
        STROKE_EMA_ALPHA, STROKE_MIN_AMPLITUDE,
        STROKE_STOPPED_WINDOW, STROKE_STOPPED_THRESHOLD,
        STROKE_PEAK_HISTORY,
    )
    last_emit_ms = ticks_ms()
    prev_elapsed = None

    t0 = ticks_ms()
    while True:
        raw = int(_last_analyzed.get("insertion", 0) * 100)
        emit, pos = detector.update(raw)
        if STROKE_LOG:
            print(f"S,{ticks_diff(ticks_ms(), t0)},{raw},{detector.smoothed:.2f},{pos if emit else -1}")
        if emit:
            now = ticks_ms()
            elapsed = ticks_diff(now, last_emit_ms)
            if prev_elapsed is None:
                interval_ms = STROKE_INITIAL_MOVE_MS
            else:
                interval_ms = max(STROKE_MIN_MOVE_MS, min(prev_elapsed, 2000))
            prev_elapsed = elapsed
            last_emit_ms = now
            try:
                _stroke_queue.put_nowait((pos, interval_ms))
            except QueueFull:
                pass  # BLE not consuming; drop this event
        await asyncio.sleep_ms(STROKE_POLL_MS)


async def ble_task():
    remote = OSSMRemote({"speed": BLE_SPEED, "depth": BLE_DEPTH, "stroke": BLE_STROKE})
    while True:
        await remote.connect()
        if remote.connected:
            # Drain stale events queued while disconnected.
            while not _stroke_queue.empty():
                _stroke_queue.get_nowait()
            await remote.run(_stroke_queue)
        await asyncio.sleep_ms(RECONNECT_DELAY_MS)


async def main():
    asyncio.create_task(idle_monitor())
    asyncio.create_task(stroke_task())
    asyncio.create_task(ble_task())
    await run_output()


asyncio.run(main())

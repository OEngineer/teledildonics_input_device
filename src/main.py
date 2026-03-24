import asyncio, machine, esp32
from machine import Pin
from time import ticks_ms, ticks_diff
import touch_sensor, touch_analysis
from config import WAKEUP_PIN, SLEEP_TIMEOUT_MS
from touch_analysis import ACTIVE_THRESHOLD
from ble_remote import OSSMRemote, RECONNECT_DELAY_MS

# IO21: RTC pin, internal pull-up; button shorts to GND to wake from deep sleep.
_wakeup_pin = Pin(WAKEUP_PIN, Pin.IN, Pin.PULL_UP)

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


async def ble_task():
    remote = OSSMRemote()
    while True:
        await remote.connect()
        if remote.connected:
            await remote.run(lambda: int(_last_analyzed.get("insertion", 0) * 100))
        await asyncio.sleep_ms(RECONNECT_DELAY_MS)


async def main():
    asyncio.create_task(idle_monitor())
    asyncio.create_task(ble_task())
    await run_output()


asyncio.run(main())

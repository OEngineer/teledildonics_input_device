import asyncio
from machine import Pin

STA_CHANNEL=9 # avoid channels < 9 on ESP32-S3
TXPOWER=17

# client only:
LED_PIN = 5
MAX_VAL = 30000

# server only:
CLIENT_MAC=b'\xec\xda;\x8c\xe7\x00' # from sta.config('mac') on client device
REFRESH_INTERVAL_MS = 100 # add about 110ms delay because of network
THRESHOLD = 35000

# BLE initial settings sent to OSSM before streaming (0-100, None to skip)
BLE_SPEED = 50
BLE_DEPTH = 100
BLE_STROKE = 80

# Power management
WAKEUP_PIN = 21          # RTC-capable GPIO for EXT0 deep-sleep wakeup (active-low button)
SLEEP_TIMEOUT_MS = 30_000  # idle time before deep sleep (ms)

# Stroke detection (see stroke_detector.py)
STROKE_EMA_ALPHA         = 0.25  # smoothing factor (lower = smoother, more lag)
STROKE_MIN_AMPLITUDE     = 8     # min 0-100 change from last extremum to count as a stroke
STROKE_STOPPED_WINDOW    = 5     # consecutive STROKE_POLL_MS samples within threshold → stopped
STROKE_STOPPED_THRESHOLD = 2     # position units (0-100) defining "not moving"
STROKE_POLL_MS           = 100   # detector poll interval; matches sensor update rate
STROKE_MIN_MOVE_MS       = 300   # floor for stream interval_ms sent to OSSM
STROKE_INITIAL_MOVE_MS   = 2000  # interval_ms for the first emit after connect (gentle start)

def set_global_exception():
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

boot_pin = Pin(0, Pin.IN, Pin.PULL_UP)
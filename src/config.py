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

def set_global_exception():
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

boot_pin = Pin(0, Pin.IN, Pin.PULL_UP)
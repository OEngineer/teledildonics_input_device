import asyncio
import struct
import array
from time import ticks_ms
from micropython import const
from display import led_display

import wifi_reset
from lazyaioespnow import LazyAIOESPNow
from config import STA_CHANNEL, TXPOWER, set_global_exception

AVERAGED_SAMPLES=const(10)
NUM_VALUES=const(9)

# return baseline numbers after averaging 10 samples
async def calibrate(e):
    sums = [0] * NUM_VALUES
    n = 0
    async for mac, msg in e:
        values = struct.unpack("<9L", msg)
        for i in range(NUM_VALUES):
            sums[i] += values[i]
        n += 1
        if n == AVERAGED_SAMPLES:
            return array.array('l', [int(sum/AVERAGED_SAMPLES) for sum in sums])
    

async def main(e):
    e.active(True)
    refs = await calibrate(e)
    rel = array.array('l', [0]*NUM_VALUES)
    print("refs=", refs)
    n = 0
    last_time = ticks_ms()
    while True:
        async for _, msg in e:
            now = ticks_ms()
            values = struct.unpack("<9L", msg)
            for i in range(NUM_VALUES):
                rel[i] = values[i] - refs[i]
            print(now, now - last_time, list(rel))
            led_display.display_values(rel)
            last_time = now
            n += 1


# reset wifi to AP_IF off, STA_IF on and disconnected
sta, ap = wifi_reset.wifi_reset()
sta.config(channel=STA_CHANNEL)
sta.config(txpower=TXPOWER)

espnow = LazyAIOESPNow()
espnow.debug = True

try:
    set_global_exception()
    asyncio.run(main(espnow))
finally:
    asyncio.new_event_loop()

import asyncio
import struct
from lazyaioespnow import LazyAIOESPNow
import touch_sensor
import wifi_reset
from config import STA_CHANNEL, CLIENT_MAC, TXPOWER, REFRESH_INTERVAL_MS, set_global_exception, boot_pin


# TODO: sense no-activity and go to sleep
async def main(e, sensor, peer):
    e.active(True)
    e.add_peer(peer, encrypt=False)
    try:
        while True:
            if boot_pin.value() == 0:
                print("boot_pin pressed, stopping...")
                break
            values = await sensor.read_async()
            data = struct.pack("<9L", *values)
            await e.asend(peer, data)
            await asyncio.sleep_ms(REFRESH_INTERVAL_MS)
    except OSError:
        print("OSError, restarting...")
        await asyncio.sleep(2)


# reset wifi to AP_IF off, STA_IF on and disconnected
sta, ap = wifi_reset.wifi_reset()
sta.config(channel=STA_CHANNEL)
sta.config(txpower=TXPOWER)

sensor = touch_sensor.MultiTouchSensor()
espnow = LazyAIOESPNow()
peer = CLIENT_MAC  # client STA mac address

# TODO: doesn't work yet
# sensor.sleep_until_touch()
# print("awake!")

try:
    set_global_exception()
    asyncio.run(main(espnow, sensor, peer))
finally:
    asyncio.new_event_loop()  # Clear retained state
    

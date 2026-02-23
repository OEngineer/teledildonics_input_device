# client:
# import client

# server:
# import server

import asyncio, touch_sensor, touch_analysis
s = touch_sensor.MultiTouchSensor()
a = touch_analysis.TouchAnalyzer(s)

async def run_test():
    while True:
        analyzed = await a.analyze()
        print("focus: {} insertion: {} center: {}".format(
            analyzed['focus'], analyzed['insertion'], analyzed['center']))
        await asyncio.sleep_ms(100)

asyncio.run(run_test())
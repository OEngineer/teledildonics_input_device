# client:
# import client

# server:
# import server

import asyncio, touch_sensor, touch_analysis
s = touch_sensor.MultiTouchSensor()
a = touch_analysis.TouchAnalyzer(s)

if not a._calibrated:
    yn = input("Do you want to calibrate now (y/n)?")
    if yn.lower() in ('y', 'yes'):
        asyncio.run(a.calibrate())

async def run_test():
    while True:
        analyzed = await a.analyze()
        print("focus: {:.0f} insertion: {:.0f} center: {:.0f}".format(
            analyzed['focus'] * 100, analyzed['insertion'] * 100, analyzed['center'] * 100))
        await asyncio.sleep_ms(100)

asyncio.run(run_test())
import asyncio
import machine
from machine import TouchPad, Pin
import esp32
from config import THRESHOLD
from micropython import const

_NUM_PINS = const(9)

async def _read_pin_async(pin):
    await asyncio.sleep_ms(30)
    return pin.read() 

class MultiTouchSensor:
    def __init__(self):
        self._touch_pins = [None] * _NUM_PINS
        # Configure all the touch pins (1-9) on the ESP32 TinyS3 board
        for pin_num in range(_NUM_PINS):
            # self._touch_pins[pin_num] = TouchPad(Pin(pin_num + 1, mode=Pin.IN, pull=Pin.PULL_DOWN))
            self._touch_pins[pin_num] = TouchPad(Pin(pin_num + 1))
        self.threshold = THRESHOLD

    def read(self):
        # Read all the touch pins
        return [pin.read() for pin in self._touch_pins]

    async def read_async(self):
        # Read all the touch pins
        retval = [] * _NUM_PINS
        for pin in self._touch_pins:
            retval.append(await _read_pin_async(pin))
        return retval

    @property
    def num_pins(self):
        return _NUM_PINS

    @property
    def threshold(self):
        return self._threshold

    @threshold.setter
    def threshold(self, threshold):
        self._threshold = threshold
        for pin in self._touch_pins:
            pin.config(threshold)

    @staticmethod
    def sleep_until_touch():
        esp32.wake_on_touch(True)
        machine.lightsleep()

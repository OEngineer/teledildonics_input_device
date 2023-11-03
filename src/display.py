# display on LED board
import neopixel
from machine import Pin
from config import LED_PIN, MAX_VAL

NUM_LEDS = 32
FIRST_LED = 4
NUM_VALUES = 9
LEDS_PER_ARCH = NUM_LEDS // 2


# 16 LEDS on top arch, 16 LEDs on bottom arch
# use magnitude of values to set brightness
# and average of values to set color
class Display:
    def __init__(self, pin_num, max_val):
        self.pin = Pin(pin_num, Pin.OUT)
        self.leds = neopixel.NeoPixel(self.pin, NUM_LEDS)
        self.leds.fill((0, 0, 0))
        self.max_val = max_val

    def display_values(self, values):
        scaled = [min(max(v, 0) / self.max_val, 1.0) for v in values]
        average = sum(scaled) / NUM_VALUES
        for led in range(NUM_VALUES):
            h = max(0.0, min(1.0, (scaled[led] - average) + 0.5))
            v = scaled[led]
            rgb = tuple(
                map(
                    lambda v: int(v * 256),
                    self.hsv_to_rgb(h, 1.0, v),
                )
            )
            self.leds[led + FIRST_LED] = rgb
            self.leds[led + FIRST_LED + LEDS_PER_ARCH] = rgb

        self.leds.write()

    # convert HSV color to RGB tuple
    @staticmethod
    def hsv_to_rgb(h, s, v):
        if s == 0.0:
            return (v, v, v)
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6
        if i == 0:
            return (v, t, p)
        if i == 1:
            return (q, v, p)
        if i == 2:
            return (p, v, t)
        if i == 3:
            return (p, q, v)
        if i == 4:
            return (t, p, v)
        if i == 5:
            return (v, p, q)


led_display = Display(LED_PIN, MAX_VAL)  # GPIO5 on prototype v2

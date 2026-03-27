import asyncio
import bluetooth
import aioble
import ujson
from time import ticks_ms, ticks_diff, ticks_add
from config import STROKE_MOTION_MARGIN_MS

# Standard OSSM BLE service
_SERVICE_UUID = bluetooth.UUID("522b443a-4f53-534d-0001-420badbabe69")
_COMMAND_UUID = bluetooth.UUID("522b443a-4f53-534d-1000-420badbabe69")
_STATE_UUID   = bluetooth.UUID("522b443a-4f53-534d-2000-420badbabe69")

SCAN_DURATION_MS = 5000
RECONNECT_DELAY_MS = 3000
HOMING_TIMEOUT_MS = 30000

class OSSMRemote:
    def __init__(self, settings=None):
        """
        settings: dict of initial OSSM parameters, e.g.
            {"speed": 50, "depth": 100, "stroke": 80}
        Each key maps to a "set:<key>:<value>" command sent before "go:streaming".
        """
        self.connected = False
        self._connection = None
        self._command_char = None
        self._state_char = None
        self._settings = settings or {}

    async def find(self):
        """Scan for an OSSM device advertising the standard service UUID."""
        print("BLE: scanning for OSSM...")
        async with aioble.scan(
            SCAN_DURATION_MS, interval_us=30000, window_us=30000, active=True
        ) as scanner:
            async for result in scanner:
                if _SERVICE_UUID in result.services():
                    print(f"BLE: found OSSM at {result.device}")
                    return result.device
        return None

    async def connect(self):
        """Scan, connect, discover characteristic, and activate streaming mode."""
        self.connected = False
        self._connection = None
        self._command_char = None
        self._state_char = None

        device = await self.find()
        if device is None:
            print("BLE: no OSSM found")
            return

        try:
            self._connection = await device.connect()
        except Exception as e:
            print(f"BLE: connect failed: {e}")
            return

        try:
            mtu = await self._connection.exchange_mtu(512)
            print(f"BLE: MTU={mtu}")
        except Exception as e:
            print(f"BLE: MTU exchange failed: {e}")

        try:
            service = await self._connection.service(_SERVICE_UUID)
            self._command_char = await service.characteristic(_COMMAND_UUID)
            self._state_char = await service.characteristic(_STATE_UUID)
        except Exception as e:
            print(f"BLE: service discovery failed: {e}")
            await self._connection.disconnect()
            self._connection = None
            return

        for key, value in self._settings.items():
            try:
                await self._send_command(f"set:{key}:{value}", response=True)
                print(f"BLE: set {key}={value}")
            except Exception as e:
                print(f"BLE: failed to set {key}: {e}")
                await self._connection.disconnect()
                self._connection = None
                return

        try:
            await self._send_command("go:streaming", response=True)
        except Exception as e:
            print(f"BLE: failed to activate streaming: {e}")
            await self._connection.disconnect()
            self._connection = None
            return

        if not await self._wait_for_streaming():
            await self._connection.disconnect()
            self._connection = None
            return

        self.connected = True
        print("BLE: connected, streaming mode active")

    async def _wait_for_streaming(self):
        """Subscribe to state notifications; block until OSSM reaches streaming state."""
        try:
            await self._state_char.subscribe(notify=True)
        except Exception as e:
            print(f"BLE: state subscribe failed: {e}")
            return False

        deadline = ticks_add(ticks_ms(), HOMING_TIMEOUT_MS)
        while True:
            remaining = ticks_diff(deadline, ticks_ms())
            if remaining <= 0:
                break
            try:
                data = await self._state_char.notified(timeout_ms=remaining)
            except asyncio.TimeoutError:
                break
            except Exception as e:
                print(f"BLE: state notify error: {e}")
                return False
            print(f"BLE: state notify ({len(data)}b): {data}")
            try:
                state = ujson.loads(data).get("state", "")
                print(f"BLE: OSSM state: {state}")
                if "streaming" in state or "idle" in state:
                    return True
            except Exception as e:
                print(f"BLE: JSON parse error: {e}")

        print("BLE: timed out waiting for streaming state")
        return False

    async def _send_command(self, cmd, response=False):
        """Write a command to the OSSM command characteristic."""
        await self._command_char.write(cmd.encode(), response=response)

    async def _send(self, position, interval_ms):
        """Write a single stream command."""
        cmd = f"stream:{position}:{interval_ms}"
        await self._send_command(cmd)

    async def run(self, queue):
        """
        Main send loop.  Dequeues (position, interval_ms) tuples produced by
        stroke_task and writes them to the OSSM.  Waits interval_ms +
        STROKE_MOTION_MARGIN_MS after each send so the previous move completes
        before the next command is consumed.  Returns when the connection is lost.
        """
        while self.connected:
            pos, interval_ms = await queue.get()
            try:
                await self._send(pos, interval_ms)
                print(f"BLE: stream {pos} interval={interval_ms}")
            except Exception as e:
                print(f"BLE: send failed: {e}")
                self.connected = False
                break
            await asyncio.sleep_ms(interval_ms + STROKE_MOTION_MARGIN_MS)
        print("BLE: disconnected")

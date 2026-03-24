import asyncio
import bluetooth
import aioble

# Standard OSSM BLE service (ossm/ Rust firmware v3.0+)
_SERVICE_UUID = bluetooth.UUID("522b443a-4f53-534d-0001-420badbabe69")
_COMMAND_UUID = bluetooth.UUID("522b443a-4f53-534d-1000-420badbabe69")

SCAN_DURATION_MS = 5000
RECONNECT_DELAY_MS = 3000
STREAM_INTERVAL_MS = 200  # send interval and position time budget for OSSM trajectory planner
MIN_CHANGE = 2  # minimum position change (0-100) before sending a new command


class OSSMRemote:
    def __init__(self):
        self.connected = False
        self._connection = None
        self._command_char = None

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
            service = await self._connection.service(_SERVICE_UUID)
            self._command_char = await service.characteristic(_COMMAND_UUID)
        except Exception as e:
            print(f"BLE: service discovery failed: {e}")
            await self._connection.disconnect()
            self._connection = None
            return

        try:
            await self._command_char.write(b"go:streaming", response=False)
        except Exception as e:
            print(f"BLE: failed to activate streaming: {e}")
            await self._connection.disconnect()
            self._connection = None
            return

        self.connected = True
        print("BLE: connected, streaming mode active")

    async def _send(self, position):
        """Write a single stream command. Caller must hold connection."""
        cmd = f"stream:{position}:{STREAM_INTERVAL_MS}".encode()
        await self._command_char.write(cmd, response=False)

    async def run(self, get_insertion):
        """
        Main send loop. Calls get_insertion() each iteration (returns int 0-100),
        sends a stream command only when the value changes by >= MIN_CHANGE.
        Returns when the connection is lost.
        """
        last_sent = -MIN_CHANGE  # force a send on the first iteration
        while self.connected:
            position = get_insertion()
            if abs(position - last_sent) >= MIN_CHANGE:
                try:
                    await self._send(position)
                    last_sent = position
                except Exception as e:
                    print(f"BLE: send failed: {e}")
                    self.connected = False
                    break
            await asyncio.sleep_ms(STREAM_INTERVAL_MS)
        print("BLE: disconnected")

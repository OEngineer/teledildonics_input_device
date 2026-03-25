import asyncio
import bluetooth
import aioble

# Standard OSSM BLE service (ossm/ Rust firmware v3.0+)
_SERVICE_UUID = bluetooth.UUID("522b443a-4f53-534d-0001-420badbabe69")
_COMMAND_UUID = bluetooth.UUID("522b443a-4f53-534d-1000-420badbabe69")

SCAN_DURATION_MS = 5000
RECONNECT_DELAY_MS = 3000
STREAM_INTERVAL_MS = 200  # send interval and position time budget for OSSM trajectory planner
COMMAND_TIMEOUT_MS = 1000


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
            await self._command_char.subscribe(notify=True)
        except Exception as e:
            print(f"BLE: service discovery failed: {e}")
            await self._connection.disconnect()
            self._connection = None
            return

        try:
            await self._send_command("go:streaming")
        except Exception as e:
            print(f"BLE: failed to activate streaming: {e}")
            await self._connection.disconnect()
            self._connection = None
            return

        self.connected = True
        print("BLE: connected, streaming mode active")

    async def _send_command(self, cmd):
        """Write a command and wait for the ok:/fail: response."""
        await self._command_char.write(cmd.encode(), response=False)
        response = await asyncio.wait_for_ms(self._command_char.notified(), COMMAND_TIMEOUT_MS)
        response_str = bytes(response).decode()
        if not response_str.startswith("ok:"):
            raise Exception(f"command rejected: {response_str}")
        return response_str

    async def _send(self, position):
        """Write a single stream command and wait for acknowledgement."""
        cmd = f"stream:{position}:{STREAM_INTERVAL_MS}"
        await self._send_command(cmd)

    async def run(self, get_insertion):
        """
        Main send loop. Calls get_insertion() each iteration (returns int 0-100),
        sends a stream command every interval.
        Returns when the connection is lost.
        """
        while self.connected:
            position = get_insertion()
            try:
                await self._send(position)
            except Exception as e:
                print(f"BLE: send failed: {e}")
                self.connected = False
                break
            await asyncio.sleep_ms(STREAM_INTERVAL_MS)
        print("BLE: disconnected")

import asyncio
from bleak import BleakClient

LED_CHAR_UUID    = "794F1fE3-9BE8-4875-83BA-731E1037A882"
IR_CHAR_UUID = "794F1fE3-9BE8-4875-83BA-731E1037A883"

class Gate:
    def __init__(self, address: str, role: str, color: str):
        self.address = address
        self.role    = role    # "start" | "end"
        self.color   = color   # led color for visual recognition
        self._client  = BleakClient(address)
        self._crossed = asyncio.Event()

    async def connect(self)-> None:
        """Connect to the gate and observe IR values
        """
        await self._client.connect()
        await self._client.start_notify(IR_CHAR_UUID, lambda sender, data: self._on_ir(data))

    async def disconnect(self) -> None:
        """Disconnet from the gate
        """
        await self._client.stop_notify(IR_CHAR_UUID)
        await self._client.disconnect()

    def _on_ir(self, data: bytearray) -> None:
        """IR notify callback — set _crossed if an object is detected

        Args:
            data (bytearray): 1 = object detected, 0 = clear
        """
        if data[0] == 1:
            self._crossed.set()

    async def wait_crossed(self) -> None:
        """Block to wait until the next IR crossing is detected
        """
        self._crossed.clear()
        await self._crossed.wait()

    def crossed(self) -> bool:
        """Return whether the gate has been crossed

        Returns:
            bool: True if an IR crossing was detected
        """
        return self._crossed.is_set()

    def reset(self) -> None:
        """Reset the state of _crossed
        """
        self._crossed.clear()

    async def set_led(self, r: int, g: int, b: int) -> None:
        """Set led color

        Args:
            r (int): red value [0-255]
            g (int): green value [0-255]
            b (int): blue value [0-255]
        """
        await self._client.write_gatt_char(LED_CHAR_UUID, bytes([r, g, b]), response=False)


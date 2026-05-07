import asyncio
import logging
from bleak import BleakClient, BLEDevice

BUTTON_CHAR_UUID = "794F1fE3-9BE8-4875-83BA-731E1037A881"
LED_CHAR_UUID    = "794F1fE3-9BE8-4875-83BA-731E1037A882"
IR_CHAR_UUID     = "794F1fE3-9BE8-4875-83BA-731E1037A883"

logger = logging.getLogger(__name__)

class Gate:
    def __init__(self, devices: BLEDevice | str, role: str):
        self.address = devices.address
        self._device = devices
        self.role    = role
        self._client  = BleakClient(self._device, timeout=20.0)
        self._crossed = asyncio.Event()
        self._pressed = asyncio.Event()

    async def connect(self) -> None:
        if self._client.is_connected:
            return
        await self._client.connect()
        await self._client.start_notify(IR_CHAR_UUID,     lambda _, data: self._on_ir(data))
        await self._client.start_notify(BUTTON_CHAR_UUID, lambda _, data: self._on_button(data))

    async def disconnect(self) -> None:
        """Disconnect from the gate
        """
        await self._client.stop_notify(IR_CHAR_UUID)
        await self._client.stop_notify(BUTTON_CHAR_UUID)
        await self._client.disconnect()

    def _on_ir(self, data: bytearray) -> None:
        """IR notify callback — set _crossed if an object is detected

        Args:
            data (bytearray): 1 = object detected, 0 = clear
        """
        if data[0] == 1:
            self._crossed.set()

    def _on_button(self, data: bytearray) -> None:
        """Button notify callback — set _pressed if a pressure is detected

        Args:
            data (bytearray): 1 = button pressed, 0 = not pressed
        """
        if data[0] == 1:
            self._pressed.set()

    async def wait_crossed(self) -> None:
        """Block to wait until the next IR crossing is detected
        """
        self._crossed.clear()
        await self._crossed.wait()

    async def wait_pressed(self) -> None:
        """Block to wait until the next button pressure is detected
        """
        self._pressed.clear()
        await self._pressed.wait()

    def is_crossed(self) -> bool:
        """Whether the gate has been crossed

        Returns:
            bool: True if an IR crossing was detected
        """
        return self._crossed.is_set()

    def is_pressed(self) -> bool:
        """Whether the button has been pressed

        Returns:
            bool: True if an button pressure has been detected
        """
        return self._pressed.is_set()

    def reset_crossed(self) -> None:
        """Reset the state of _crossed
        """
        self._crossed.clear()

    def reset_pressed(self) -> None:
        """Reset the state of _pressed
        """
        self._pressed.clear()

    async def set_led(self, r: int, g: int, b: int) -> None:
        """Set led color

        Args:
            r (int): red value [0-255]
            g (int): green value [0-255]
            b (int): blue value [0-255]
        """
        await self._client.write_gatt_char(LED_CHAR_UUID, bytes([r, g, b]), response=False)

    async def running_blink(self) -> None:
        """Green led blink while the race is running"""
        while True:
            await self.set_led(0, 255, 0)
            await asyncio.sleep(0.3)
            await self.set_led(0, 0, 0)
            await asyncio.sleep(0.3)

    async def pairing_blink(self) -> None:
        """White led pairing_blink mode to signal gate in pairing and waiting manual confirmation
        """
        while True:
            await self.set_led(255, 255, 255)
            await asyncio.sleep(0.2)
            await self.set_led(0, 0, 0)
            await asyncio.sleep(0.2)

    async def finish_blink(self) -> None:
        """Blink to signal race finish"""
        for r, g, b in  [(255, 0, 0),
                         (0, 255, 0),
                         (0, 0, 255),
                         (255, 255, 0),
                         (255, 0, 255),
                         (0, 255, 255),
                         (255, 255, 255),]:

            await self.set_led(r, g, b)
            await asyncio.sleep(0.2)
            await self.set_led(0, 0, 0)
            await asyncio.sleep(0.2)
            await self.set_led(0, 255, 0)

    async def starting_blink(self) -> None:
        """Start LED sequence
        """
        for r, g, b in [(255, 0, 0),
                        (255, 200, 0),
                        (0, 255, 0),]:
            for _ in range(2):
                await self.set_led(r, g, b)
                await asyncio.sleep(0.25)
                await self.set_led(0, 0, 0)
                await asyncio.sleep(0.25)
        await self.set_led(255, 255, 255)

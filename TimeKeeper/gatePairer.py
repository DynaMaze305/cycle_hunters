import asyncio
import logging
from bleak import BleakScanner, BLEDevice
from .gate import Gate

logger = logging.getLogger("gatePairer")

BUTTON_CHAR_UUID = "794F1fE3-9BE8-4875-83BA-731E1037A881"
LED_CHAR_UUID    = "794F1fE3-9BE8-4875-83BA-731E1037A882"
PORTIC_NAME      = "Timing Node"

COLORS = ["orange", "purple"]
LEDS = {
    "orange":   b"\xFF\xA5\x00",
    "purple":   b"\xFF\x00\xFF",
}
ROLES = ["start", "end"]


async def find_two_gates(timeout=3.0) -> list[BLEDevice]:
    while True:
        logger.debug("[gatePairer] -- Searching out 2 gates to connect to...")
        connections = await BleakScanner.discover(timeout=timeout)
        portics = [gate for gate in connections if gate.name == PORTIC_NAME]
        # Use top two on the list
        if len(portics) >= 2:
            logger.debug(f"[gatePairer] -- Using: {portics[0].address} & {portics[1].address}")
            return portics[:2]
        # search again
        logger.debug("[gatePairer] -- Not enough gates found, re-trying...")

async def configure_pair_of_gates(pair: list[BLEDevice]) -> list[Gate]:
    """Pair of gates configuration process

    Args:
        pair (list[BLEDevice]): the two gates to configure

    Returns:
        list[Gate]: [start_gate, end_gate]; connected and with the attributed LED color
    """
    gatesPair: list[Gate] = []

    for i, device in enumerate(pair):
        # get the role and color of the gate (1rst one is start, 2nd is end)
        role  = ROLES[i]
        color = COLORS[i]

        gate = Gate(address=device.address, role="", color="")
        await gate.connect()
        logger.info(f"[gatePairer] -- Connected to {device.address}")

        flash_task = asyncio.create_task(gate.pairing_blink())
        logger.info(f"[gatePairer] -- Press the button on the pairing_blink gate to assign it as {role}_gate")
        await gate.wait_pressed()
        # stop "gracefully" the white blinking 
        flash_task.cancel()
        try:
            await flash_task
        except asyncio.CancelledError:
            pass
        # attribute role, color and set led color
        gate.role  = role
        gate.color = color
        r, g, b = LEDS[color]
        await gate.set_led(r, g, b)

        gatesPair.append(gate)
        logger.info(f"[gatePairer] -- {role}_gate assigned: {device.address} -> {color}")

    return gatesPair


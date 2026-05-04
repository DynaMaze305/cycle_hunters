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


async def find_two_gates(timeout: float = 5.0) -> list[BLEDevice]:
    """Scan for BLE Thingy:52 and return the first two found

    Args:
        timeout (float, optional): Maximum scan time (s)

    Raises:
        TimeoutError: If fewer than two gates are found in the timeout

    Returns:
        list[BLEDevice]: The paire of gates to use in a raceSession
    """
    portics: dict[str, BLEDevice] = {}
    two_found = asyncio.Event()

    def on_detection(device: BLEDevice, _) -> None:
        # if it's a Thingy:52 and not already found
        if device.name == PORTIC_NAME and device.address not in portics:
            portics[device.address] = device
            logger.debug(f"[gatePairer] -- Found: {device.address} ({len(portics)}/2)")

            if len(portics) >= 2:
                two_found.set()

    async with BleakScanner(detection_callback=on_detection):
        try:
            await asyncio.wait_for(two_found.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Only {len(portics)}/2 gates found after {timeout}s")

    pair_to_configure = list(portics.values())[:2]
    logger.debug(f"[gatePairer] -- Using: {pair_to_configure[0].address} & {pair_to_configure[1].address}")

    return pair_to_configure

async def configure_pair_of_gates(pair: list[BLEDevice]) -> list[Gate]:
    """Pair of gates configuration process - working both in parallel

    Args:
        pair (list[BLEDevice]): the two gates to configure

    Returns:
        list[Gate]: [start_gate, end_gate]; connected and with the attributed LED color
    """
    # to connect both gates in parallel
    gates = [Gate(address=device, role="", color="") 
                for device in pair]
    
    await asyncio.gather(*[gate.connect() 
                            for gate in gates])
    
    logger.info(f"[gatePairer] -- Connected to {gates[0].address} & {gates[1].address}")

    # Pairing blink
    flash_tasks = [asyncio.create_task(gate.pairing_blink()) 
                        for gate in gates]
    logger.info("[gatePairer] -- Press the button on the start_gate, then end_gate")

    # Assign roles in order of button press
    # https://stackoverflow.com/questions/71958008/asyncio-wait-process-results-as-they-come
    gatesPair: list[Gate] = []
    pending: dict[asyncio.Task, Gate] = {asyncio.create_task(gate.wait_pressed()): gate 
                                            for gate in gates}

    for role, color in zip(ROLES, COLORS):
        done, _ = await asyncio.wait(pending.keys(), return_when=asyncio.FIRST_COMPLETED)
        press_task = next(iter(done))
        gate = pending.pop(press_task)

        # stop "gracefully" the white blinking
        flash_task = flash_tasks[gates.index(gate)]
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
        logger.info(f"[gatePairer] -- {role}_gate assigned: {gate.address} -> {color}")

    return gatesPair


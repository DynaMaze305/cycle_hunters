import asyncio
from bleak import BleakScanner, BLEDevice
from .gate import Gate

BUTTON_CHAR_UUID = "794F1fE3-9BE8-4875-83BA-731E1037A881"
LED_CHAR_UUID    = "794F1fE3-9BE8-4875-83BA-731E1037A882"
PORTIC_NAME      = "Timing Node"

COLORS = ["orange", "darkblue", "yellow", "purple"]
LEDS = {
    "orange":   b"\xFF\xA5\x00",
    "darkblue": b"\x00\x00\x8B",
    "yellow":   b"\xFF\xFF\x00",
    "purple":   b"\xFF\x00\xFF",
}
ROLES = ["start", "end"]


async def find_two_gates(timeout=5.0) -> list[BLEDevice]:
    print("[gatePairer] -- Looking out for 2 gates...")
    connections = await BleakScanner.discover(timeout=timeout)
    portics = [gate
             for gate in connections
                if gate.name == PORTIC_NAME]
    print(f"[gatePairer] -- {len(portics)} gates found : {portics[0].address} & {portics[1].address}")
    return portics[:2]

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

        # Flash white to signal gate in configuration
        flash_task = asyncio.create_task(gate.flashing())

        print(f"[gatePairer] -- Press the button on the flashing gate to assign it as {role}_gate")
        await gate.wait_pressed()

        # stop "gracefully" the flashing 
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
        print(f"[gatePairer] -- {role}_gate : {device.address} -> {color}")

    return gatesPair


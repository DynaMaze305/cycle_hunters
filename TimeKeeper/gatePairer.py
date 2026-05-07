import asyncio
import logging

from bleak import BleakScanner
from .gate import Gate

logger = logging.getLogger(__name__)

SCAN_TIMEOUT = 5.0

async def gates_finder() -> list[Gate]:
    """Find and connect to two Thingy:52 "Timing Node" BLE devices

    Raises:
        RuntimeError: if not enough Thingy:52 "Timing Node" found in the timeout

    Returns:
        list[Gate]: the two connected gates
    """
    devices = await BleakScanner.discover(timeout=SCAN_TIMEOUT)

    thingy = [device for device in devices 
             if device.name and "Timing" in device.name] # to avoid not named device and only recover timing node gate
    
    if len(thingy) < 2:
        raise RuntimeError(f"Only {len(thingy)} gate thingy:52 found, 2 required...")

    TimingNodes = []

    for i, device in enumerate(thingy[:2]):
        gate = Gate(device, role="unknown", color="unknown")
        await gate.connect()
        logger.info(f"[gatePairer] Connected to gate {i+1} ({device.address})")
        TimingNodes.append(gate)

    return TimingNodes


async def gates_configurator(gates: list[Gate]) -> list[Gate]:
    """Process to configure the gates (color and role)

    Args:
        gates (list[Gate]): list of connected gates

    Returns:
        list[Gate]: list of the configured gates (start|end)
    """
    gate_a, gate_b = gates

    blink_a   = asyncio.create_task(gate_a.pairing_blink())
    blink_b   = asyncio.create_task(gate_b.pairing_blink())
    pressed_a = asyncio.create_task(gate_a.wait_pressed())
    pressed_b = asyncio.create_task(gate_b.wait_pressed())

    logger.info("[gatePairer] Press the button on the [start_gate] (thus the other will be [end_gate])")
    # done = 1rst completed pressed task, pending = the second one
    done, pending = await asyncio.wait([pressed_a, pressed_b], return_when=asyncio.FIRST_COMPLETED)
    
    # "gracefully" stop the tasks
    for task in [blink_a, blink_b, *pending]:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Assign roles and colors
    start_gate, end_gate = (gate_a, gate_b) if pressed_a in done else (gate_b, gate_a)

    start_gate.role, start_gate.color = "start", "turquoise"
    end_gate.role, end_gate.color = "end", "olive"

    await start_gate.set_led(0, 125, 125)
    await end_gate.set_led(125, 125, 0)

    logger.info(f"[gatePairer] Configuration done -- Start gate: {start_gate.address} | End gate: {end_gate.address}")
    return [start_gate, end_gate]
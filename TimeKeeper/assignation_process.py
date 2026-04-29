import asyncio
from queue import Empty
from bleak import BleakScanner, BleakClient, BLEDevice

BUTTON_CHAR_UUID = "794F1fE3-9BE8-4875-83BA-731E1037A881"
LED_CHAR_UUID    = "794F1fE3-9BE8-4875-83BA-731E1037A882"
PORTIC_NAME      = "Timing Node"

COLORS = ["red", "green", "yellow", "purple"]
LEDS = {
    "red":    b"\xFF\x00\x00",
    "green":  b"\x00\xFF\x00",
    "yellow": b"\xFF\xFF\x00",
    "purple": b"\xFF\x00\xFF",
}


async def find_portics(timeout=5.0) -> list:
    """Scan around for TimeKeeper devices to obtain their adresses

    Args:
        timeout (float, optional): Time of scanning

    Returns:
        list: list of the portics adresses
    """
    print("Scanning BLE...")
    connections = await BleakScanner.discover(timeout=timeout)
    portics = [gate 
             for gate in connections 
                if gate.name == PORTIC_NAME]
    print(f"[✔] {len(portics)} portiques trouvées :")

    for p in portics:
        print(f" - {p.address}")
    return portics


async def register_portics(portics: list[BLEDevice]) -> dict:
    """Use button press, to assign a color to detected portics

    Args:
        list[BLEDevice]: portics -> list of the detected 

    Returns:
        dict: color_name -> device_address 
    """
    # Allow iterative update of colors without creating explicit loop in the function
    color_iter = iter(COLORS)
    registered: dict = {}

    # event to stop the process when all portics are set
    all_registered = asyncio.Event()
    lock = asyncio.Lock()

    async def handle_gate(device: BLEDevice):
        """Inner function to iteratively map portics with colors

        Args:
            device (BLEDevice): the portics
        """
        async with BleakClient(device) as client:
            registered_portics = asyncio.Event()

            async def on_button(_, data):
                # If not pressed, wait
                if data[0] != 1:
                    return
                
                async with lock:
                    # Ensure that portic can't be multiple registered
                    if registered_portics.is_set():
                        return
                    
                    color = next(color_iter, None)
                    registered[color] = device.address
                    registered_portics.set()

                    print(f"  {device.address}  ->  '{color}'")

                # Updte the LED color
                await client.write_gatt_char(LED_CHAR_UUID, LEDS[color], response=False)

                async with lock:
                    # Check and raise is all portics are registred
                    if len(registered) == len(portics):
                        all_registered.set()

            # Launch on_button if a button notification GATT is detected
            await client.start_notify(BUTTON_CHAR_UUID, on_button)
            # wait that all portics are registred
            await all_registered.wait()

    await asyncio.gather(*[handle_gate(p) 
                           for p in portics])
    return registered

async def main() -> dict:
    portics = await find_portics()
    if not portics:
        print("Aucuns portiques trouvé...")
        return {}
    print("Presser les boutons pour assigner les portiques...")
    gate_map = await register_portics(portics)
    print("\n Assignation :")
    for color, addr in gate_map.items():
        print(f"  {color}: {addr}")

    return gate_map


if __name__ == "__main__":
    map = asyncio.run(main())

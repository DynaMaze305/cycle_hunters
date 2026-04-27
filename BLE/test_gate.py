import asyncio
from bleak import BleakScanner
from gate import Gate

PORTIC_NAME = "Timing Node"


async def find_gate() -> str:
    devices = await BleakScanner.discover(timeout=5.0)
    found = [d 
             for d in devices 
             if d.name == PORTIC_NAME]
    if not found:
        raise RuntimeError("Aucun Timing Node trouvé.")
    return found[0].address

async def main():
    address = await find_gate()
    gate = Gate(address, role="start", color="red")

    print("\nTest de la connexion...")
    await gate.connect()
    print("    [✔]")

    print("\nTest clignotement LED...")
    for _ in range(3):
        await gate.set_led(255, 255, 255)
        await asyncio.sleep(0.2)
        await gate.set_led(0, 0, 0)
        await asyncio.sleep(0.2)
    print("    [✔]")

    print("\nTest IR...")
    await gate.wait_crossed()
    print("    [✔] crossed() =", gate.crossed())

    print("\nTest Reset state :")
    gate.reset()
    print("    Après reset : crossed() =", gate.crossed())
    print("    Passe à nouveau...")
    await gate.wait_crossed()
    print("    [✔]")

    print("\nTest déconnexion")
    await gate.disconnect()
    print("    [✔]\n")


asyncio.run(main())

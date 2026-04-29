import asyncio
from bleak import BleakScanner
from ..gate import Gate
from ..race_session import RaceSession

PORTIC_NAME = "Timing Node"

async def find_gates() -> tuple[str, str]:
    print("Scanning BLE en cours...")

    devices = await BleakScanner.discover(timeout=5.0)
    found = [d 
             for d in devices 
             if d.name == PORTIC_NAME]

    for d in found:
        print(f"  - {d.address}")

    return found[0].address, found[1].address

def on_event(event: str, session: RaceSession) -> None:
    if event == "race_start":
        print(f"\n[Session {session.session_id}] : course start ")
    elif event == "race_finish":
        print(f"[Session {session.session_id}] : course end —> {session.time:.3f}s")
    elif event == "session_ended":
        print(f"[Session {session.session_id}] >> course terminée")


async def main():
    # Trouver les deux gates leur attribuer un rôle et une couleur
    addr_start, addr_end = await find_gates()

    start_gate = Gate(addr_start, role="start", color="red")
    end_gate   = Gate(addr_end,   role="end",   color="green")

    # Crée une session et la subscribe à on_event
    session = RaceSession(session_id=1, start_gate=start_gate, end_gate=end_gate)
    session.subscribe(on_event)

    await session.start()
    await start_gate.set_led(255, 0, 0)
    await end_gate.set_led(0, 255, 0)

    print("Veuillez déclencher le portique rouge pour démarrer le test...")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass

    await session.stop()

asyncio.run(main())

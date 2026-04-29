import asyncio
from ..gatePairer import find_two_gates, configure_pair_of_gates

async def main():
    pair = await find_two_gates(timeout=5.0)
    print("[Test] -- gate registration")
    gates = await configure_pair_of_gates(pair)
    print("[Test] -- pairing succesfull  [✔]")

    print("\n[Test] -- Assignment result :")
    for gate in gates:
        print(f"[Test] --  role : {gate.role} | {gate.address} | {gate.color}")

    await asyncio.sleep(3)

    for gate in gates:
        await gate.disconnect()

asyncio.run(main())

import asyncio
from bleak import BleakClient, BleakScanner

THINGY_ADDRESS = "F9:CB:B8:48:B5:92"
BUTTON_CHAR_UUID = "794F1fE3-9BE8-4875-83BA-731E1037A881"
LED_CHAR_UUID = "794F1fE3-9BE8-4875-83BA-731E1037A882"

async def main():
    devices = await BleakScanner.discover(timeout=5.0)
    device = next((d for d in devices if d.address.upper() == THINGY_ADDRESS.upper()), None)
    if device is None:
        print(f"[⚠] Appareil {THINGY_ADDRESS} pas trouvé...")
        return

    async with BleakClient(device) as client:
        print("[✔] Connection effectuée...")
        async def button_handler(_, data):
            if data[0] == 1:
                print("button pressé")
                await client.write_gatt_char(LED_CHAR_UUID, b"\xFF\x00\x00", response=False)
            else:
                print("button relâché")
                await client.write_gatt_char(LED_CHAR_UUID, b"\x00\x00\x00", response=False)

        await client.start_notify(BUTTON_CHAR_UUID, button_handler)
        
        # Maintient la connexion active
        await asyncio.sleep(1E9)

if __name__ == "__main__":
    asyncio.run(main())

# Code largement inspiré des [slides fournies](https://isc.hevs.ch/learn/pluginfile.php/7945/mod_resource/content/0/05%20Introduction%20to%20Bluetooth%20LE.pdf)
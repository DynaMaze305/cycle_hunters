## Données des portiques (TimeKeeper)
*Tiré des [slides fournies](https://isc.hevs.ch/learn/pluginfile.php/7945/mod_resource/content/0/05%20Introduction%20to%20Bluetooth%20LE.pdf)*

### Spécifications Techniques : Thingy:52 (Custom Firmware)

*   **Plateforme :** Basé sur le Nordic Thingy:52 IoT.
*   **Firmware :** Custom, basé sur **Zephyr RTOS**.
*   **Service Propriétaire :** Gère le capteur IR, le bouton et la LED RGB.
    *   **Service UUID :** `794f1fe3-9be8-4875-83ba-731e1037a880`

#### Caractéristiques GATT

*   **Capteur IR**
    *   **UUID :** `794f1fe3-9be8-4875-83ba-731e1037a883`
    *   **Opération :** Notification
    *   **Données :** `UInt8` (1 octet) — `1` si un objet est détecté, `0` sinon.

*   **Bouton**
    *   **UUID :** `794F1fE3-9BE8-4875-83BA-731E1037A881`
    *   **Opération :** Notification
    *   **Données :** `UInt8` (1 octet) — `1` si pressé, `0` sinon.

*   **RGB LED**
    *   **UUID :** `794F1fE3-9BE8-4875-83BA-731E1037A882`
    *   **Opération :** Write without response
    *   **Données :** `UInt8[3]` (3 octets) — Intensité R-G-B (0-255).

## Règles concernant la BLE

Après discussions avec Mr.Calvaresi, les modalités suivantes ont été conclues :

- les portiques seront positionnées dans des culs-de-sac
- Si un robot trigger le mauvais prtique de fin -> disqualification
- Un seul agent timer pour les deux équipes (sur le Raspberry Pi)
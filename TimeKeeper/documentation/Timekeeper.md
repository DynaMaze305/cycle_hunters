# Timekeeper

Agent externe, commun pour les deux équipes, pour la gestion des chronos et des portiques BLE

### Etapes de fonctionnement
0. Avoir allumer au moins 2 portiques Thingy:52
1. Logger envoie `Hello TimeKeeper ! Please initialise a race.`
2. TimeKeeper scanne les portiques BLE et les mets en mode appariements
    - Lorsque les portiques clignotent en blanc, pressez le bouton du portique qui doit être le `start_gate` (l'autre devient automatiquement le `end_gate`)
    - La `start_gate` s'allume en **turquoise**, la `end_gate` en **olive** pour confirmer leur rôle
3. TimeKeeper confirme le processus et envoie `Pairing succesful : start_gate = turquoise & end_gate = olive`
4. Quand on souhaite démarrer la course : Logger envoie `I'm ready to race !`
5. Dès que toutes les équipes sont prêtes, le TimeKeeper déclenche le compte à rebours
6. Le chrono de temps de course total se déclenche lorsque le `Go!!!` est envoyé
7. Les chronos individuels se déclenchent au moment où le laser du départ est coupé
    - La `start_gate` clignote en **vert** pendant toute la durée de la course
    - La `end_gate` s'allume en **blanc** pour signaler qu'elle est active
8. Les chronos individuels se terminent au moment où le laser d'arrivée est coupé
9. Le chrono de temps de course total s'arrête au moment où le dernier concurrent franchit la ligne
10. Le TimeKeeper envoie les chronos individuels et le chrono total à chaque concurrent
11. Les portes sont déconnectées

## Infrastructure XMPP

- **Serveur :** Prosody sur `isc-coordinator2.lan`

### Protocole XMPP

#### messages exacts acceptés TimeKeeper

| Message envoyé au TimeKeeper | Effet |
|------------------------------|-------|
| `Hello TimeKeeper ! Please initialise a race.` | Démarre une session, lance le scan BLE et la phase d'appariement |
| `I'm ready to race !` | Marque le concurrent (session) comme prête ; lance la course dès que toutes les concurrents sont prêts |

#### messages exacts envoyés par TimeKeeper

| Message envoyé par TimeKeeper | Raison |
|-------------------------------|--------|
| `A pairing is already in progress. Please wait...` | Un appariement des portes BLE est déjà en cours par un autre Logger|
| `The pairing for your gates is now starting...` | La file d'attente de la phase d'appariement est libre |
| `Pairing succesful : start_gate = {color} & end_gate = {color}` | Phase d'appariement réussie + donne la couleur et le rôle des portiques |
| `Pairing failed: {error}` | Erreur survenue lors de la phase d'appariement (envoyé au Logger concerné) |
| `A concurrent's pairing failed...` | Un appariement adverse a échoué — la course ne peut pas démarrer (envoyé aux autres Loggers) |
| `Waiting for the other team to announce themselve as ready to race...` | Le Logger s'est annoncé 'ready', mais un autre compétiteur ne l'est pas encore |
| `Your competitor is: {jid}` (ou `solo run`) | Annonce l'adversaire (JID) à chaque compétiteur avant le départ |
| `3` / `2` / `1` / `Go !!!` | Séquence de compte à rebours envoyée séquentiellement à tous les concurrents |
| `Total race time: {time:.3f}s` | Temps total de course envoyé à tous les compétiteurs à la fin de la course (lorsque le dernier concurrent à franchi la ligne d'arrivée) |
| `The race is finished! Your race time is: {time:.3f}s` | Temps personnel envoyé à chaque concurrent à la fin de sa course |

## Données des portiques
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
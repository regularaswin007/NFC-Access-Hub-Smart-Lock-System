# NFC Access Hub & IoT Smart Lock System

An end-to-end, IoT-based access control and smart lock system powered by an **ESP32**, **PN532 NFC RFID module**, **Firebase Realtime Database**, and a **Streamlit Dashboard** for real-time monitoring, management, and anomaly detection.

---

## Features

- **Real-time Access Control:** Scan NFC tags/cards to instantly validate authorization via secure MD5-hashed UIDs.
- **Time-Based Access Validation:** Support for `ValidFrom` and `ValidUntil` restriction windows per user.
- **Firebase Integration:** Real-time cloud logging of access attempts, remote command handling (`lock`, `unlock`, `restart`, `register_mode`), and synchronization of live system statuses.
- **Registration Mode:** Remotely or locally trigger a registration window to easily onboard new NFC tags into the database.
- **Interactive Streamlit Dashboard:** 
  - **Real-time Status:** Monitor current lock status, connection state, and last access metadata.
  - **Live Access Logs:** Filterable records by date and status with direct CSV export.
  - **Remote Control Panel:** Actuate door locks, trigger system restarts, activate registration mode, and tweak auto-lock timeouts.
  - **User Management:** Onboard, edit time windows, toggle authorization, or delete users.
  - **Anomaly Detection:** Visual heatmaps and automatic alerts for unauthorized or off-hours access attempts.

---

## System Architecture

```text
┌──────────────┐      NFC Scan       ┌──────────────┐      WiFi/HTTPS      ┌──────────────────────┐
│  NFC Tag /   │ ──────────────────> │ ESP32 WROOM  │ ───────────────────> │ Firebase Realtime DB │
│     Card     │                     │   (PN532)    │ <─────────────────── │                      │
└──────────────┘                     └──────┬───────┘      JSON Sync       └──────────┬───────────┘
                                            │                                         │
                                            │ Local LED Status                        │ Cloud Sync
                                            ▼                                         ▼
                                     [ Door Lock / LED ]                       ┌──────────────────────┐
                                                                               │ Streamlit Dashboard  │
                                                                               │    (Access Hub)      │
                                                                               └──────────────────────┘

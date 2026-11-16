# S1072 — Industroyer2

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **Platforms:** Field Controller/RTU/PLC/IED, Engineering Workstation
- **ATT&CK URL:** https://attack.mitre.org/software/S1072
- **Last modified:** 2025-04-16

## Description

Industroyer2 is a compiled and static piece of malware that has the ability to communicate over the IEC-104 protocol. It is similar to the IEC-104 module found in Industroyer. Security researchers assess that Industroyer2 was designed to cause impact to high-voltage electrical substations. The initial Industroyer2 sample was compiled on 03/23/2022 and scheduled to execute on 04/08/2022, however it was discovered before deploying, resulting in no impact.

## Techniques used

- **T0801 Monitor Process State** — Industroyer2 uses a General Interrogation command to monitor the device’s Information Object Addresses (IOAs) and their IO state values.
- **T0802 Automated Collection** — Industroyer2 leverages a hardcoded list of remote-station IP addresses to iteratively initiate communications and collect information across multiple priority IEC-104 priority levels.
- **T0806 Brute Force I/O** — Industroyer2 can iterate across a device’s IOAs to modify the ON/OFF value of a given IO state.
- **T0836 Modify Parameter** — Industroyer2 modifies specified Information Object Addresses (IOAs) for specified Application Service Data Unit (ASDU) addresses to either the ON or OFF state.
- **T0881 Service Stop** — Industroyer2 has the capability to terminate specified processes (i.e., PServiceControl.exe and PService_PDD.exe) and rename each process to prevent restart. These are defined through a hardcoded configuration.
- **T0888 Remote System Information Discovery** — Industroyer2 has the capability to poll a target device about its connection status, data transfer status, Common Address (CA), Information Object Addresses (IOAs), and IO state values across multiple priority levels.
- **T1057 Process Discovery** — Industroyer2 has the ability to cyclically enumerate running processes such as PServiceControl.exe, PService_PDD.exe, and other targets supplied through a hardcoded configuration.
- **T1692.001 Unauthorized Message: Command Message** — Industroyer2 is capable of sending command messages from the compromised device to target remote stations to open data channels, retrieve the location and values of Information Object Addresses (IOAs), and modify the IO state values through Select Before Operate I/O, Select/Execute, and Invert Default State operations.

## Used by

- **G0034 Sandworm Team** (group)

# S1165 — FrostyGoop

- **Type:** software (malware)
- **Domain:** ICS ATT&CK
- **Also known as:** BUSTLEBERM
- **Platforms:** Control Server, Field Controller/RTU/PLC/IED
- **ATT&CK URL:** https://attack.mitre.org/software/S1165
- **Last modified:** 2024-11-20

## Description

FrostyGoop is a Windows-based binary written in Golang that allows for interaction with industrial control system (ICS) equipment via Modbus TCP over port 502. FrostyGoop allows for reading and writing data to holding registers on targeted devices, manipulating the operation of systems for malicious purposes. FrostyGoop is associated with the FrostyGoop Incident in Ukraine.

## Techniques used

- **T0801 Monitor Process State** — FrostyGoop can read data from holding registers via Modbus communication.
- **T0836 Modify Parameter** — FrostyGoop allows for the modification of system settings by reading and writing to registers via Modbus commands.
- **T0869 Standard Application Layer Protocol** — FrostyGoop utilizes the Modbus protocol for transmitting commands to victim devices.
- **T0885 Commonly Used Port** — FrostyGoop communicates using the Modbus protocol over the standard port of TCP 502.
- **T1701 Command and Scripting Interpreter** — FrostyGoop is compiled for Windows systems and leverages a Windows-based command line interface. Modbus interaction functionality is based off a publicly available Github repository for command line input.

## Used by

- **C0041 FrostyGoop Incident** (campaign) — FrostyGoop Incident used FrostyGoop to manipulate OT devices to induce a district heating disruption in Ukraine.

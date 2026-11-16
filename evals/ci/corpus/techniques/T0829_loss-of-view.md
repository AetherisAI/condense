# T0829 — Loss of View

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Impact
- **Platforms:** None
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0829
- **Last modified:** 2026-05-12

## Description

Adversaries may cause a sustained or permanent loss of view where the ICS equipment will require local, hands-on operator intervention; for instance, a restart or manual operation. By causing a sustained reporting or visibility loss, the adversary can effectively hide the present state of operations. This loss of view can occur without affecting the physical processes themselves.

## Mitigations

- **M0810 Out-of-Band Communications Channel** — Provide operators with redundant, out-of-band communication to support monitoring and control of the operational processes, especially when recovering from a network outage. Out-of-band communication should utilize diverse systems and technologies to minimize common failure modes and vulnerabilities within the communications infrastructure. For example, wireless networks (e.g., 3G, 4G) can be used to provide diverse and redundant delivery of data.
- **M0811 Redundancy of Service** — Hot-standbys in diverse locations can ensure continued operations if the primarily system are compromised or unavailable. At the network layer, protocols such as the Parallel Redundancy Protocol can be used to simultaneously use redundant and diverse communication over a local network.
- **M0953 Data Backup** — Take and store data backups from end user systems and critical servers. Ensure backup and storage systems are hardened and kept separate from the corporate network to prevent compromise. Maintain and exercise incident response plans, including the management of gold-copy back-up images and configurations for key systems to enable quick recovery and response from adversarial activities that impact control, view, or availability.

## Detection strategies

- **DET0763 Detection of Loss of View**
  - AN1895 (None): No standard detection method currently exists for this technique.

## Procedure examples

- **C0031 Unitronics Defacement Campaign** (campaign) — During the Unitronics Defacement Campaign, the CyberAv3ngers replaced the existing graphic on the Programmable Logic Controller (PLC) Human-Machine Interface (HMI) with their own, thereby preventing PLC owners and operators from viewing PLC information on the HMI.
- **C0041 FrostyGoop Incident** (campaign) — During FrostyGoop Incident, the adversary initiated a firmware downgrade on victim devices to a version lacking monitoring.
- **C0063 2025 Poland Wiper Attacks** (campaign) — During the 2025 Poland Wiper Attacks, the adversaries wiped devices and also damaged Mikronika RTUs, Hitachi Relion Protection and Control Relays (IEDs), and HMI workstations resulting in a loss of communications and view between the facility and the distribution system operators (DSO).
- **C0066 2026 U.S. Water Utilities Attacks** (campaign) — During the 2026 U.S. Water Utilities Attacks, the adversary changed passwords on internet-facing MicroLogix controllers, causing the affected utilities to lose monitoring of their equipment (e.g., water tower, lift station, etc.).
- **G1027 CyberAv3ngers** (group) — During the 2026 Iranian Water Campaign, CyberAv3ngers manipulated process logic, HMI, and SCADA displays, which may disrupt operators view of the system.
- **S0372 LockerGoga** (software) — Some of Norsk Hydro's production systems were impacted by a LockerGoga infection. This resulted in a loss of view which forced the company to switch to manual operations.
- **S0604 Industroyer** (software) — Industroyer's data wiper component removes the registry image path throughout the system and overwrites all files, rendering the system unusable.
- **S0607 KillDisk** (software) — KillDisk erases the master boot record (MBR) and system logs, leaving the system unusable.
- **S1157 Fuxnet** (software) — Fuxnet impaired sensor communication to impacted devices resulting in a loss of view condition for overall system monitoring.

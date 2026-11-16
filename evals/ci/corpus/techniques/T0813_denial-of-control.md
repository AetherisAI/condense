# T0813 — Denial of Control

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Impact
- **Platforms:** None
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0813
- **Last modified:** 2025-04-15

## Description

Adversaries may cause a denial of control to temporarily prevent operators and engineers from interacting with process controls. An adversary may attempt to deny process control access to cause a temporary loss of communication with the control device or to prevent operator adjustment of process controls. An affected process may still be operating during the period of control loss, but not necessarily in a desired state.

In the 2017 Dallas Siren incident operators were unable to disable the false alarms from the Office of Emergency Management headquarters.

## Mitigations

- **M0810 Out-of-Band Communications Channel** — Provide operators with redundant, out-of-band communication to support monitoring and control of the operational processes, especially when recovering from a network outage. Out-of-band communication should utilize diverse systems and technologies to minimize common failure modes and vulnerabilities within the communications infrastructure. For example, wireless networks (e.g., 3G, 4G) can be used to provide diverse and redundant delivery of data.
- **M0811 Redundancy of Service** — Hot-standbys in diverse locations can ensure continued operations if the primarily system are compromised or unavailable. At the network layer, protocols such as the Parallel Redundancy Protocol can be used to simultaneously use redundant and diverse communication over a local network.
- **M0953 Data Backup** — Take and store data backups from end user systems and critical servers. Ensure backup and storage systems are hardened and kept separate from the corporate network to prevent compromise. Maintain and exercise incident response plans, including the management of gold-copy back-up images and configurations for key systems to enable quick recovery and response from adversarial activities that impact control, view, or availability.

## Detection strategies

- **DET0786 Detection of Denial of Control**
  - AN1918 (None): No standard detection method currently exists for this technique.

## Procedure examples

- **C0020 Maroochy Water Breach** (campaign) — In the Maroochy Water Breach, the adversary temporarily shut an investigator out of the network preventing them from issuing any controls.
- **C0028 2015 Ukraine Electric Power Attack** (campaign) — During the 2015 Ukraine Electric Power Attack, KillDisk rendered devices that were necessary for remote recovery unusable, including at least one RTU. Additionally, Sandworm Team overwrote the firmware for serial-to-ethernet converters, denying operators control of the downstream devices.
- **C0066 2026 U.S. Water Utilities Attacks** (campaign) — During the 2026 U.S. Water Utilities Attacks, the adversary denied operators the ability to control their systems by shutting down and disabling computerized water plant controls via malware over a wireless connection.
- **S0604 Industroyer** (software) — Industroyer is able to block serial COM channels temporarily causing a denial of control.

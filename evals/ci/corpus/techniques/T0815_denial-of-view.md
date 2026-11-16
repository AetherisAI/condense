# T0815 — Denial of View

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Impact
- **Platforms:** None
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0815
- **Last modified:** 2025-04-15

## Description

Adversaries may cause a denial of view in attempt to disrupt and prevent operator oversight on the status of an ICS environment. This may manifest itself as a temporary communication failure between a device and its control source, where the interface recovers and becomes available once the interference ceases. 

An adversary may attempt to deny operator visibility by preventing them from receiving status and reporting messages. Denying this view may temporarily block and prevent operators from noticing a change in state or anomalous behavior. The environment's data and processes may still be operational, but functioning in an unintended or adversarial manner.

## Mitigations

- **M0810 Out-of-Band Communications Channel** — Provide operators with redundant, out-of-band communication to support monitoring and control of the operational processes, especially when recovering from a network outage. Out-of-band communication should utilize diverse systems and technologies to minimize common failure modes and vulnerabilities within the communications infrastructure. For example, wireless networks (e.g., 3G, 4G) can be used to provide diverse and redundant delivery of data.
- **M0811 Redundancy of Service** — Hot-standbys in diverse locations can ensure continued operations if the primarily system are compromised or unavailable. At the network layer, protocols such as the Parallel Redundancy Protocol can be used to simultaneously use redundant and diverse communication over a local network.
- **M0953 Data Backup** — Take and store data backups from end user systems and critical servers. Ensure backup and storage systems are hardened and kept separate from the corporate network to prevent compromise. Maintain and exercise incident response plans, including the management of gold-copy back-up images and configurations for key systems to enable quick recovery and response from adversarial activities that impact control, view, or availability.

## Detection strategies

- **DET0769 Detection of Denial of View**
  - AN1901 (None): No standard detection method currently exists for this technique.

## Procedure examples

- **C0020 Maroochy Water Breach** (campaign) — In the Maroochy Water Breach, the adversary temporarily shut an investigator out of the network, preventing them from viewing the state of the system.
- **S0604 Industroyer** (software) — Industroyer is able to block serial COM channels temporarily causing a denial of view.

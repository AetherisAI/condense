# T0826 — Loss of Availability

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Impact
- **Platforms:** None
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0826
- **Last modified:** 2025-04-15

## Description

Adversaries may attempt to disrupt essential components or systems to prevent owner and operator from delivering products or services. 

Adversaries may leverage malware to delete or encrypt critical data on HMIs, workstations, or databases.

In the 2021 Colonial Pipeline ransomware incident, pipeline operations were temporally halted on May 7th and were not fully restarted until May 12th.

## Mitigations

- **M0810 Out-of-Band Communications Channel** — Provide operators with redundant, out-of-band communication to support monitoring and control of the operational processes, especially when recovering from a network outage. Out-of-band communication should utilize diverse systems and technologies to minimize common failure modes and vulnerabilities within the communications infrastructure. For example, wireless networks (e.g., 3G, 4G) can be used to provide diverse and redundant delivery of data.
- **M0811 Redundancy of Service** — Hot-standbys in diverse locations can ensure continued operations if the primarily system is compromised or unavailable. At the network layer, protocols such as the Parallel Redundancy Protocol can be used to simultaneously use redundant and diverse communication over a local network.
- **M0953 Data Backup** — Take and store data backups from end user systems and critical servers. Ensure backup and storage systems are hardened and kept separate from the corporate network to prevent compromise. Maintain and exercise incident response plans, including the management of gold-copy back-up images and configurations for key systems to enable quick recovery and response from adversarial activities that impact control, view, or availability.

## Detection strategies

- **DET0729 Detection of Loss of Availability**
  - AN1862 (None): No standard detection method currently exists for this technique.

## Procedure examples

- **C0028 2015 Ukraine Electric Power Attack** (campaign) — During the 2015 Ukraine Electric Power Attack, Sandworm Team opened the breakers at the infected sites, shutting the power off for thousands of businesses and households for around 6 hours.
- **C0031 Unitronics Defacement Campaign** (campaign) — During the Unitronics Defacement Campaign, the CyberAv3ngers caused multiple businesses to halt operations due to the unavailability of the Programmable Logic Controller (PLC) and Human-Machine Interface (HMI). These victims covered multiple sectors.
- **C0041 FrostyGoop Incident** (campaign) — During FrostyGoop Incident, the adversary modified victim control system parameters resulting in the loss of heating services to impacted district heating customers.
- **C0066 2026 U.S. Water Utilities Attacks** (campaign) — During the 2026 U.S. Water Utilities Attacks, the adversary temporarily shut down the well and water treatment plant, causing loss of cellular connectivity across multiple sites interrupting the service the plant provides leading operators to revert to manual operations. During the 2026 U.S. Water Utilities Attacks, the adversary caused loss of water pressure and flooding at affected water and wastewater utilities.
- **G1027 CyberAv3ngers** (group) — During the 2026 Iranian Water Campaign, CyberAv3ngers degraded operations across at least seven states that resulted in reported incidents, pressure loss and flooding.
- **S0608 Conficker** (software) — A Conficker infection at a nuclear power plant forced the facility to temporarily shutdown.

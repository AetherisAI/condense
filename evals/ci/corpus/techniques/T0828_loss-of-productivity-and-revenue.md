# T0828 — Loss of Productivity and Revenue

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Impact
- **Platforms:** None
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0828
- **Last modified:** 2025-04-16

## Description

Adversaries may cause loss of productivity and revenue through disruption and even damage to the availability and integrity of control system operations, devices, and related processes. This technique may manifest as a direct effect of an ICS-targeting attack or tangentially, due to an IT-targeting attack against non-segregated environments. 

In cases where these operations or services are brought to a halt, the loss of productivity may eventually present an impact for the end-users or consumers of products and services. The disrupted supply-chain may result in supply shortages and increased prices, among other consequences. 

A ransomware attack on an Australian beverage company resulted in the shutdown of some manufacturing sites, including precautionary halts to protect key systems. The company announced the potential for temporary shortages of their products following the attack. 

In the 2021 Colonial Pipeline ransomware incident, the pipeline was unable to transport approximately 2.5 million barrels of fuel per day to the East Coast.

## Mitigations

- **M0953 Data Backup** — Take and store data backups from end user systems and critical servers. Ensure backup and storage systems are hardened and kept separate from the corporate network to prevent compromise. Maintain and exercise incident response plans, including the management of gold-copy back-up images and configurations for key systems to enable quick recovery and response from adversarial activities that impact control, view, or availability.

## Detection strategies

- **DET0757 Detection of Loss of Productivity and Revenue**
  - AN1889 (None): No standard detection method currently exists for this technique.

## Procedure examples

- **C0028 2015 Ukraine Electric Power Attack** (campaign) — During the 2015 Ukraine Electric Power Attack, power breakers were opened which caused the operating companies to be unable to deliver power, and left thousands of businesses and households without power for around 6 hours.
- **C0030 Triton Safety Instrumented System Attack** (campaign) — In the Triton Safety Instrumented System Attack, TEMP.Veles tripped a controller into a failed safe state, which caused an automatic shutdown of the plant, this resulted in a pause of plant operations for more than a week. Thereby impacting industrial processes and halting productivity.
- **C0031 Unitronics Defacement Campaign** (campaign) — During the Unitronics Defacement Campaign, the CyberAv3ngers caused multiple businesses to halt operations in their industrial environments, impacting their typical business operations. These victims covered multiple sectors.
- **S0368 NotPetya** (software) — NotPetya disrupted manufacturing facilities supplying vaccines, resulting in a halt of production and the inability to meet demand for specific vaccines.
- **S0372 LockerGoga** (software) — While Norsk Hydro attempted to recover from a LockerGoga infection, most of its 160 manufacturing locations switched to manual (non-IT driven) operations. Manual operations can result in a loss of productivity.
- **S0446 Ryuk** (software) — An enterprise resource planning (ERP) manufacturing server was lost to the Ryuk attack. The manufacturing process had to rely on paper and existing orders to keep the shop floor open.
- **S0496 REvil** (software) — The REvil malware gained access to an organizations network and encrypted sensitive files used by OT equipment.
- **S0605 EKANS** (software) — EKANS infection resulted in a temporary production loss within a Honda manufacturing plant.
- **S0606 Bad Rabbit** (software) — Several transportation organizations in Ukraine have suffered from being infected by Bad Rabbit, resulting in some computers becoming encrypted, according to media reports.
- **S0608 Conficker** (software) — A Conficker infection at a nuclear power plant forced the facility to shutdown and go through security procedures involved with such events, with its staff scanning computer systems and going through all the regular checks and motions before putting the plant back into production.

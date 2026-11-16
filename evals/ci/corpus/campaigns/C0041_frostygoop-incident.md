# C0041 — FrostyGoop Incident

- **Type:** campaign
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **First seen:** 2024-01-01
- **Last seen:** 2024-01-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0041
- **Last modified:** 2026-07-31

## Description

FrostyGoop Incident took place in January 2024 against a municipal district heating company in Ukraine. Following initial access via likely exploitation of external facing services, FrostyGoop was used to manipulate ENCO control systems via legitimate Modbus commands to impact the delivery of heating services to Ukrainian civilians.

## Techniques used

- **T0826 Loss of Availability** — During FrostyGoop Incident, the adversary modified victim control system parameters resulting in the loss of heating services to impacted district heating customers.
- **T0829 Loss of View** — During FrostyGoop Incident, the adversary initiated a firmware downgrade on victim devices to a version lacking monitoring.
- **T0836 Modify Parameter** — In FrostyGoop Incident, the adversary caused the victim controllers to report incorrect measurements by modifying parameters.
- **T1003.002 OS Credential Dumping: Security Account Manager** — During FrostyGoop Incident, the adversary retrieved the contents of the Security Account Manager (SAM) hive in the victim environment for credential capture.
- **T1071 Application Layer Protocol** — During FrostyGoop Incident, the adversary initiated Layer Two Tunnelling Protocol (L2TP) connections to Moscow-based IP addresses.
- **T1190 Exploit Public-Facing Application** — FrostyGoop Incident was likely enabled by the adversary exploiting an unknown vulnerability in an external-facing router.
- **T1505.003 Server Software Component: Web Shell** — FrostyGoop Incident deployed a ReGeorg variant web shell to impacted systems following initial access for persistence.
- **T1689 Downgrade Attack** — During FrostyGoop Incident, the adversary downgraded firmware on victim devices in order to impair visibility into the process environment.
- **T1693.001 Modify Firmware: System Firmware** — During FrostyGoop Incident, the adversary initiated a firmware downgrade on impacted devices.

## Software used

- **S1165 FrostyGoop** — FrostyGoop Incident used FrostyGoop to manipulate OT devices to induce a district heating disruption in Ukraine.

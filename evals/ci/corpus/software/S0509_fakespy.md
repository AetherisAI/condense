# S0509 — FakeSpy

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0509
- **Last modified:** 2026-09-02

## Description

FakeSpy is Android spyware that has been operated by the Chinese threat actor behind the Roaming Mantis campaigns.

## Techniques used

- **T1406 Obfuscated Files or Information** — FakeSpy stores its malicious code in encrypted asset files that are decrypted at runtime. Newer versions of FakeSpy encrypt the C2 address.
- **T1409 Stored Application Data** — FakeSpy can collect account information stored on the device, as well as data in external storage.
- **T1418 Software Discovery** — FakeSpy can collect a list of installed applications.
- **T1421 System Network Connections Discovery** — FakeSpy can collect the device’s network information.
- **T1422 System Network Configuration Discovery** — FakeSpy can collect device networking information, including phone number, IMEI, and IMSI.
- **T1422.001 System Network Configuration Discovery: Internet Connection Discovery** — FakeSpy can collect device networking information, including phone number, IMEI, and IMSI.
- **T1426 System Information Discovery** — FakeSpy can collect device information, including OS version and device model.
- **T1437.001 Application Layer Protocol: Web Protocols** — FakeSpy exfiltrates data using HTTP requests.
- **T1476 Deliver Malicious Application via Other Means** — FakeSpy has been distributed via direct download links in SMS phishing messages.
- **T1582 SMS Control** — FakeSpy can send SMS messages.
- **T1624.001 Event Triggered Execution: Broadcast Receivers** — FakeSpy can register for the `BOOT_COMPLETED` broadcast Intent.
- **T1628.001 Hide Artifacts: Suppress Application Icon** — FakeSpy can hide its icon if it detects that it is being run on an emulator.
- **T1633.001 Virtualization/Sandbox Evasion: System Checks** — FakeSpy can detect if it is running in an emulator and adjust its behavior accordingly.
- **T1636.003 Protected User Data: Contact List** — FakeSpy can collect the device’s contact list.
- **T1636.004 Protected User Data: SMS Messages** — FakeSpy can collect SMS messages.
- **T1655.001 Masquerading: Match Legitimate Name or Location** — FakeSpy masquerades as local postal service applications.

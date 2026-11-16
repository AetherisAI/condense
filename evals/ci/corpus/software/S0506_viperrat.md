# S0506 — ViperRAT

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0506
- **Last modified:** 2026-09-02

## Description

ViperRAT is sophisticated surveillanceware that has been in operation since at least 2015 and was used to target the Israeli Defense Force.

## Techniques used

- **T1407 Download New Code at Runtime** — ViperRAT has been installed in two stages and can secretly install new applications.
- **T1421 System Network Connections Discovery** — ViperRAT can collect the device’s cell tower information.
- **T1422 System Network Configuration Discovery** — ViperRAT can collect network configuration data from the device, including phone number, SIM operator, and network operator.
- **T1422.001 System Network Configuration Discovery: Internet Connection Discovery** — ViperRAT can collect network configuration data from the device, including phone number, SIM operator, and network operator.
- **T1426 System Information Discovery** — ViperRAT can collect system information, including brand, manufacturer, and serial number.
- **T1429 Audio Capture** — ViperRAT can collect and record audio content.
- **T1430 Location Tracking** — ViperRAT can track the device’s location.
- **T1476 Deliver Malicious Application via Other Means** — ViperRAT has been distributed through third party websites.
- **T1512 Video Capture** — ViperRAT can take photos with the device camera.
- **T1533 Data from Local System** — ViperRAT can collect device photos, PDF documents, Office documents, browser history, and browser bookmarks.
- **T1636.002 Protected User Data: Call Log** — ViperRAT can collect the device’s call log.
- **T1636.003 Protected User Data: Contact List** — ViperRAT can collect the device’s contact list.
- **T1636.004 Protected User Data: SMS Messages** — ViperRAT can collect SMS messages.
- **T1655.001 Masquerading: Match Legitimate Name or Location** — ViperRAT’s second stage has masqueraded as “System Updates”, “Viber Update”, and “WhatsApp Update”.

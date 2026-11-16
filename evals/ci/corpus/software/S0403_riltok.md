# S0403 — Riltok

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0403
- **Last modified:** 2026-09-02

## Description

Riltok is banking malware that uses phishing popups to collect user credentials.

## Techniques used

- **T1417.002 Input Capture: GUI Input Capture** — Riltok can open a fake Google Play screen requesting bank card credentials and mimic the screen of relevant mobile banking apps to request user/bank card details.
- **T1418 Software Discovery** — Riltok can retrieve a list of installed applications. Installed application names are then checked against an adversary-defined list of targeted applications.
- **T1422 System Network Configuration Discovery** — Riltok can query the device's IMEI.
- **T1426 System Information Discovery** — Riltok can query various details about the device, including phone number, country, mobile operator, model, root availability, and operating system version.
- **T1437.001 Application Layer Protocol: Web Protocols** — Riltok communicates with the command and control server using HTTP requests.
- **T1476 Deliver Malicious Application via Other Means** — Riltok has been distributed via phishing SMS messages from infected devices.
- **T1516 Input Injection** — Riltok injects input to set itself as the default SMS handler by clicking the appropriate places on the screen. It can also close or minimize targeted antivirus applications and the device security settings screen.
- **T1636.003 Protected User Data: Contact List** — Riltok can access and upload the device's contact list to the command and control server.
- **T1636.004 Protected User Data: SMS Messages** — Riltok can intercept incoming SMS messages.

# S0489 — WolfRAT

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0489
- **Last modified:** 2025-04-25

## Description

WolfRAT is malware based on a leaked version of Dendroid that has primarily targeted Thai users. WolfRAT has most likely been operated by the now defunct organization Wolf Research.

## Techniques used

- **T1406 Obfuscated Files or Information** — WolfRAT’s code is obfuscated.
- **T1407 Download New Code at Runtime** — WolfRAT can update the running malware.
- **T1418 Software Discovery** — WolfRAT can obtain a list of installed applications.
- **T1422 System Network Configuration Discovery** — WolfRAT sends the device’s IMEI with each exfiltration request.
- **T1424 Process Discovery** — WolfRAT uses `dumpsys` to determine if certain applications are running.
- **T1429 Audio Capture** — WolfRAT can record call audio.
- **T1512 Video Capture** — WolfRAT can take photos and videos.
- **T1513 Screen Capture** — WolfRAT can record the screen and take screenshots to capture messages from Line, Facebook Messenger, and WhatsApp.
- **T1517 Access Notifications** — WolfRAT can receive system notifications.
- **T1533 Data from Local System** — WolfRAT can collect user account, photos, browser history, and arbitrary files.
- **T1582 SMS Control** — WolfRAT can delete and send SMS messages.
- **T1630.002 Indicator Removal on Host: File Deletion** — WolfRAT can delete files from the device.
- **T1633.001 Virtualization/Sandbox Evasion: System Checks** — WolfRAT can perform primitive emulation checks.
- **T1636.002 Protected User Data: Call Log** — WolfRAT can collect the device’s call log.
- **T1636.003 Protected User Data: Contact List** — WolfRAT can collect the device’s contact list.
- **T1636.004 Protected User Data: SMS Messages** — WolfRAT can collect SMS messages.
- **T1655.001 Masquerading: Match Legitimate Name or Location** — WolfRAT has masqueraded as “Google service”, “GooglePlay”, and “Flash update”.

# S0327 — Skygofree

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0327
- **Last modified:** 2025-04-25

## Description

Skygofree is Android spyware that is believed to have been developed in 2014 and used through at least 2017.

## Techniques used

- **T1404 Exploitation for Privilege Escalation** — Skygofree has the capability to exploit several known vulnerabilities and escalate privileges.
- **T1407 Download New Code at Runtime** — Skygofree can download executable code from the C2 server after the implant starts or after a specific command.
- **T1409 Stored Application Data** — Skygofree has a capability to obtain files from other installed applications.
- **T1429 Audio Capture** — Skygofree can record audio via the microphone when an infected device is in a specified location.
- **T1430 Location Tracking** — Skygofree can track the device's location.
- **T1437.001 Application Layer Protocol: Web Protocols** — Skygofree can be controlled via HTTP, XMPP, FirebaseCloudMessaging, or GoogleCloudMessaging in older versions.
- **T1512 Video Capture** — Skygofree can record video or capture photos when an infected device is in a specified location.
- **T1644 Out of Band Data** — Skygofree can be controlled via binary SMS.

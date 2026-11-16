# S0292 — AndroRAT

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0292
- **Last modified:** 2024-11-17

## Description

AndroRAT is an open-source remote access tool for Android devices. AndroRAT is capable of collecting data, such as device location, call logs, etc., and is capable of executing actions, such as sending SMS messages and taking pictures. It is originally available through the `The404Hacking` Github repository.

## Techniques used

- **T1422 System Network Configuration Discovery** — AndroRAT collects the device’s location through GPS or through network settings.
- **T1429 Audio Capture** — AndroRAT gathers audio from the microphone.
- **T1430 Location Tracking** — AndroRAT tracks the device location.
- **T1512 Video Capture** — AndroRAT can take photos and videos using the device cameras.
- **T1582 SMS Control** — AndroRAT can send SMS messages.
- **T1616 Call Control** — AndroRAT can make phone calls.
- **T1636.002 Protected User Data: Call Log** — AndroRAT collects call logs.
- **T1636.003 Protected User Data: Contact List** — AndroRAT collects contact list information.
- **T1636.004 Protected User Data: SMS Messages** — AndroRAT captures SMS messages.
- **T1655.001 Masquerading: Match Legitimate Name or Location** — AndroRAT masquerades as legitimate applications.

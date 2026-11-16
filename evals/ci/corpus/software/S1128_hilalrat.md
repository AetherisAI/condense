# S1128 — HilalRAT

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S1128
- **Last modified:** 2024-04-10

## Description

HilalRAT is a remote access-capable Android malware, developed and used by UNC788. HilalRAT is capable of collecting data, such as device location, call logs, etc., and is capable of executing actions, such as activating a device's camera and microphone.

## Techniques used

- **T1409 Stored Application Data** — HilalRAT can access and retrieve files on a device.
- **T1429 Audio Capture** — HilalRAT can activate a device’s microphone.
- **T1430 Location Tracking** — HilalRAT can access a device’s location.
- **T1512 Video Capture** — HilalRAT can activate a device’s camera.
- **T1636.003 Protected User Data: Contact List** — HilalRAT can retrieve a device’s contact list.
- **T1636.004 Protected User Data: SMS Messages** — HilalRAT can retrieve a device’s SMS messages.

## Used by

- **G1029 UNC788** (group)

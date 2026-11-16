# S0301 — Dendroid

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0301
- **Last modified:** 2025-04-25

## Description

Dendroid is an Android remote access tool (RAT) primarily targeting Western countries. The RAT was available for purchase for $300 and came bundled with a utility to inject the RAT into legitimate applications.

## Techniques used

- **T1417.002 Input Capture: GUI Input Capture** — Dendroid can open a dialog box to ask the user for passwords.
- **T1429 Audio Capture** — Dendroid can record audio and outgoing calls.
- **T1512 Video Capture** — Dendroid can take photos and record videos.
- **T1533 Data from Local System** — Dendroid can collect the device’s photos, browser history, bookmarks, and accounts stored on the device.
- **T1582 SMS Control** — Dendroid can send and block SMS messages.
- **T1633.001 Virtualization/Sandbox Evasion: System Checks** — Dendroid can detect if it is being ran on an emulator.
- **T1636.004 Protected User Data: SMS Messages** — Dendroid can intercept SMS messages.
- **T1655.001 Masquerading: Match Legitimate Name or Location** — Dendroid can be bound to legitimate applications prior to installation on devices.

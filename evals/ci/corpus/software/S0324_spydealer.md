# S0324 — SpyDealer

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0324
- **Last modified:** 2025-04-25

## Description

SpyDealer is Android malware that exfiltrates sensitive data from Android devices.

## Techniques used

- **T1404 Exploitation for Privilege Escalation** — SpyDealer uses the commercial rooting app Baidu Easy Root to gain root privilege and maintain persistence on the victim.
- **T1407 Download New Code at Runtime** — SpyDealer downloads and executes root exploits from a remote server.
- **T1409 Stored Application Data** — SpyDealer exfiltrates data from over 40 apps such as WeChat, Facebook, WhatsApp, Skype, and others.
- **T1422 System Network Configuration Discovery** — SpyDealer harvests the device phone number, IMEI, and IMSI.
- **T1429 Audio Capture** — SpyDealer can record phone calls and surrounding audio.
- **T1430 Location Tracking** — SpyDealer harvests location data from victims.
- **T1512 Video Capture** — SpyDealer can record video and take photos via front and rear cameras.
- **T1513 Screen Capture** — SpyDealer abuses Accessibility features to steal messages from popular apps such as WeChat, Skype, Viber, and QQ.
- **T1624.001 Event Triggered Execution: Broadcast Receivers** — SpyDealer registers the broadcast receiver to listen for events related to device boot-up.
- **T1636.002 Protected User Data: Call Log** — SpyDealer harvests phone call history from victims.
- **T1636.003 Protected User Data: Contact List** — SpyDealer harvests contact lists from victims.
- **T1636.004 Protected User Data: SMS Messages** — SpyDealer harvests SMS and MMS messages from victims.
- **T1644 Out of Band Data** — SpyDealer enables remote control of the victim through SMS channels.
- **T1645 Compromise Client Software Binary** — SpyDealer maintains persistence by installing an Android application package (APK) on the system partition.

# T1453 — Abuse Accessibility Features

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Collection, Credential Access
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1453
- **Last modified:** 2026-05-12

## Description

Adversaries may abuse accessibility features in Android devices to steal sensitive data and to spread malware to other devices. Accessibility features in Android are designed to assist users with disabilities, performing a variety of tasks, such as using Action Blocks to control lightbulbs, and changing the device’s user interface, such as changing the font size and adjusting contract or colors. 

One example of how adversaries abuse accessibility features is overlaying an HTML object mimicking a legitimate login screen. The user types their credentials in the overlay HTML object, which is then sent to the adversaries. 

Another example is a malicious accessibility feature acting as a keylogger. The keylogger monitors changes on the EditText fields and sends it to the adversaries. This method of attack is also described in Keylogging; whereas Abuse Accessibility Features captures the overall abuse of accessibility features.

## Mitigations

- **M1011 User Guidance** — First, users should be wary of clicking on suspicious text messages, links and emails. Secondly, users should be wary of granting applications accessibility features. Users may check applications that have been granted accessibility features by going to Settings, then Accessibility. Finally, users should be wary of downloading applications; although applications may be on the Google Play Store, they may not be benign (see Application Versioning).

## Detection strategies

- **DET0697 Detection of Abuse Accessibility Features**
  - AN1812 (Android): For Android, detect Abuse Accessibility Features by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate API Calls via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: AccessibilityService receiving events from dc(source_app) > $AccessibilityTargetThreshold$ distinct apps INCLUDING apps IN $TargetAppList$ — broad monitoring across apps distinguishes malware from single-purpose assistive tech]; Network Traffic Content via Enterprise Secure Web Gateway / Proxy [DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed]; Permissions Request via Android Enterprise DPC / Application Vetting [DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:DynamicAnalysis (Dynamic API/runtime trace: AccessibilityService receiving events from dc(source_app) > $AccessibilityTargetThreshold$ distinct apps INCLUDING apps IN $TargetAppList$ — broad monitoring across apps distinguishes malware from single-purpose assistive tech); webproxy:applog (DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed); android:DevicePolicyManager (DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review).

## Procedure examples

- **S0422 Anubis** (software) — After accessibility service is granted, Anubis lures the victim into changing the Accessibility settings on the device, disabling application removal, and executes screen taps and other commands without the victim’s knowledge.
- **S1067 FluBot** (software) — FluBot abuses accessibility features in three ways: steal application credentials, evade detection and removal, and send SMS for lateral movement.
- **S1083 Chameleon** (software) — After accessibility permissions are granted, Chameleon has used the Accessibility Service to perform a variety of actions, such as switching from biometric authentication to PIN authentication, automatically granting additional permissions, preventing uninstallation, disabling Play Protect.
- **S1225 CherryBlos** (software) — After accessibility permissions are granted, CherryBlos has used the Accessibility Service to monitor when a wallet application launches and to steal credentials.
- **S1231 GodFather** (software) — GodFather has abused the accessibility service to prevent the user from uninstalling GodFather, to exfiltrate Google Authenticator one-time passwords and to steal credentials.
- **S9004 Crocodilus** (software) — Crocodilus has requested for Accessibility Service to be enabled. Upon approval, Crocodilus has connected to the C2 server to receive instructions, has continuously monitored Accessibility events, and has captured elements, such as wallet keys, displayed on the device screen.
- **S9005 DocSwap** (software) — Once accessibility permissions are granted, DocSwap has abused the Accessibility Service to execute a keylogging capability.
- **S9006 VajraSpy** (software) — VajraSpy has exploited accessibility features to intercept and exfiltrate communication from WhatsApp, WhatsApp Business and Signal and to automatically enable necessary permissions on the user’s behalf.

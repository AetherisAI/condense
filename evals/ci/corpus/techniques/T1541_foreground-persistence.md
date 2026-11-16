# T1541 — Foreground Persistence

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Defense Evasion, Persistence
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1541
- **Last modified:** 2026-05-12

## Description

Adversaries may abuse Android's `startForeground()` API method to maintain continuous sensor access. Beginning in Android 9, idle applications running in the background no longer have access to device sensors, such as the camera, microphone, and gyroscope. Applications can retain sensor access by running in the foreground, using Android’s `startForeground()` API method. This informs the system that the user is actively interacting with the application, and it should not be killed. The only requirement to start a foreground service is showing a persistent notification to the user.

Malicious applications may abuse the `startForeground()` API method to continue running in the foreground, while presenting a notification to the user pretending to be a genuine application. This would allow unhindered access to the device’s sensors, assuming permission has been previously granted.

Malicious applications may also abuse the `startForeground()` API to inform the Android system that the user is actively interacting with the application, thus preventing it from being killed by the low memory killer.

## Mitigations

- **M1011 User Guidance** — If a user sees a persistent notification they do not recognize, they should uninstall the source application and look for other unwanted applications or anomalies.

## Detection strategies

- **DET0637 Detection of Foreground Persistence**
  - AN1711 (Android): For Android, detect Foreground Persistence by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Application State via Android Enterprise / EMM [Managed package inventory/status and package metadata]; OS API Execution via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: App invokes startForegroundService() or startForeground() NOT IN $ApprovedForegroundServiceApps$]; System Settings via Android Enterprise DPC [DevicePolicyManager policy/compliance/security-state queries and SecurityLog events where supported]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: android:EMM (Managed package inventory/status and package metadata); mobile:DynamicAnalysis (Dynamic API/runtime trace: App invokes startForegroundService() or startForeground() NOT IN $ApprovedForegroundServiceApps$); android:DevicePolicyManager (DevicePolicyManager policy/compliance/security-state queries and SecurityLog events where supported).

## Procedure examples

- **S0485 Mandrake** (software) — Mandrake uses foreground persistence to keep a service running. It shows the user a transparent notification to evade detection.
- **S0545 TERRACOTTA** (software) — TERRACOTTA has utilized foreground services.
- **S0558 Tiktok Pro** (software) — Tiktok Pro has shown a persistent notification to maintain access to device sensors.
- **S1054 Drinik** (software) — Drinik has C2 commands that can move the malware in and out of the foreground.
- **S1225 CherryBlos** (software) — CherryBlos has utilized foreground services by showing a notification to evade detection.
- **S9005 DocSwap** (software) — DocSwap has checked for the `FOREGROUND_SERVICE` permission. DocSwap has also used the StartForeground API to generate a notification saying “Tap to view more details or stop the app” in Korean and to maintain persistence.

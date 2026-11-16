# T1670 — Virtualization Solution

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Defense Evasion
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1670
- **Last modified:** 2025-03-14

## Description

Adversaries may carry out malicious operations using virtualization solutions to escape from Android sandboxes and to avoid detection. Android uses sandboxes to separate resources and code execution between applications and the operating system. There are a few virtualization solutions available on Android, such as the Android Virtualization Framework (AVF). 

 

Through virtualization solutions, adversaries may execute malicious operations without user knowledge. For example, adversaries may mimic a legitimate banking application’s functionalities in a virtual environment, thanks to the virtualization solution, while malicious code captures credentials.

## Mitigations

- **M1011 User Guidance** — Users should be encouraged to only install apps from authorized app stores, which are less likely to contain malicious applications.

## Detection strategies

- **DET0606 Detection of Virtualization Solution**
  - AN1656 (Android): For Android, detect Virtualization Solution by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Application Permission via Android Enterprise DPC / Application Vetting [DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review]; Application State via Android Enterprise / EMM [Managed package inventory/status and package metadata]; Network Traffic Flow via Android Enterprise Network Logging / Enterprise VPN [DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: android:DevicePolicyManager (DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review); android:EMM (Managed package inventory/status and package metadata); android:EnterpriseNetworkLog (DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata).

## Procedure examples

- **S1208 FjordPhantom** (software) — FjordPhantom uses a virtualization solution to steal credentials.
- **S1231 GodFather** (software) — GodFather has used virtualization to create a separate virtual environment that mimicked legitimate banking and cryptocurrency applications.

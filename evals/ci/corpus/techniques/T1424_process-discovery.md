# T1424 — Process Discovery

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Discovery
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1424
- **Last modified:** 2025-10-24

## Description

Adversaries may attempt to get information about running processes on a device. Information obtained could be used to gain an understanding of common software/applications running on devices within a network. Adversaries may use the information from Process Discovery during automated discovery to shape follow-on behaviors, including whether or not the adversary fully infects the target and/or attempts specific actions. 

 

Recent Android security enhancements have made it more difficult to obtain a list of running processes. On Android 7 and later, there is no way for an application to obtain the process list without abusing elevated privileges. This is due to the Android kernel utilizing the `hidepid` mount feature. Prior to Android 7, applications could utilize the `ps` command or examine the `/proc` directory on the device. 

 

In iOS, applications have previously been able to use the `sysctl` command to obtain a list of running processes. This functionality has been removed in later iOS versions.

## Mitigations

- **M1002 Attestation** — Attestation can typically detect rooted devices. For MDM-enrolled devices, action can be taken if a device fails an attestation check.
- **M1006 Use Recent OS Version** — Android 7 and later iOS versions introduced changes that prevent applications from performing Process Discovery without elevated privileges.

## Detection strategies

- **DET0692 Detection of Process Discovery**
  - AN1804 (Android): For Android, detect Process Discovery by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate File Access via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: opendir('/proc/') with recursive listdir by app NOT IN $ProcessDiscoveryAllowList$ on device with android_version < $HidepidVersion$]; Network Connection Creation via Android Enterprise Network Logging / Enterprise VPN [DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata]; Process Metadata via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: running process names read from /proc/<PID>/status or /proc/<PID>/cmdline by app NOT IN $ProcessDiscoveryAllowList$]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: opendir('/proc/') with recursive listdir by app NOT IN $ProcessDiscoveryAllowList$ on device with android_version < $HidepidVersion$); android:EnterpriseNetworkLog (DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata); mobile:DynamicAnalysis (Dynamic API/runtime trace: running process names read from /proc/<PID>/status or /proc/<PID>/cmdline by app NOT IN $ProcessDiscoveryAllowList$).
  - AN1805 (iOS): For iOS, detect Process Discovery by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Application State via Apple MDM [InstalledApplicationList / ManagedApplicationList]; Host Status via Apple MDM [DeviceInformation / SecurityInfo / ProfileList / restrictions and compliance queries]; Network Traffic Flow via Apple Network Extension / Enterprise VPN [NEFilterFlow / per-app VPN / secure-web-gateway flow metadata]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: iOS:MDM (InstalledApplicationList / ManagedApplicationList); iOS:MDM (DeviceInformation / SecurityInfo / ProfileList / restrictions and compliance queries); iOS:NetworkExtension (NEFilterFlow / per-app VPN / secure-web-gateway flow metadata).

## Procedure examples

- **C0054 Operation Triangulation** (campaign) — During Operation Triangulation, the threat actors have obtained a list of processes.
- **S0311 YiSpecter** (software) — YiSpecter has collected information about running processes.
- **S0411 Rotexy** (software) — Rotexy collects information about running processes.
- **S0421 GolfSpy** (software) — GolfSpy can obtain a list of running processes.
- **S0422 Anubis** (software) — Anubis can collect a list of running processes.
- **S0440 Agent Smith** (software) — Agent Smith checks if a targeted application is running in user-space prior to infection.
- **S0489 WolfRAT** (software) — WolfRAT uses `dumpsys` to determine if certain applications are running.
- **S0544 HenBox** (software) — HenBox can obtain a list of running processes.
- **S1055 SharkBot** (software) — SharkBot can use Accessibility Services to detect which process is in the foreground.
- **S1185 LightSpy** (software) — LightSpy has collected a list of running processes.
- **S1215 Binary Validator** (software) — Binary Validator has obtained a list of running processes.
- **S1216 TriangleDB** (software) — TriangleDB has collected a list of running processes.
- **S1225 CherryBlos** (software) — CherryBlos has used the Accessibility Service to monitor when a wallet application has launched.

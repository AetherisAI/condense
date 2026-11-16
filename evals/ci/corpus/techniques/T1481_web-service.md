# T1481 — Web Service

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Command and Control
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1481
- **Last modified:** 2025-10-24

## Description

Adversaries may use an existing, legitimate external Web service as a means for relaying data to/from a compromised system. Popular websites and social media, acting as a mechanism for C2, may give a significant amount of cover. This is due to the likelihood that hosts within a network are already communicating with them prior to a compromise. Using common services, such as those offered by Google or Twitter, makes it easier for adversaries to hide in expected noise. Web service providers commonly use SSL/TLS encryption, giving adversaries an added level of protection. 

 

Use of Web services may also protect back-end C2 infrastructure from discovery through malware binary analysis, or enable operational resiliency (since this infrastructure may be dynamically changed).

## Sub-techniques

- **T1481.001 Web Service: Dead Drop Resolver**
- **T1481.002 Web Service: Bidirectional Communication**
- **T1481.003 Web Service: One-Way Communication**

## Detection strategies

- **DET0672 Detection of Web Service**
  - AN1770 (Android): For Android, detect Web Service by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Application Permission via Android Enterprise DPC / Application Vetting [DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review]; Application State via Android Enterprise / EMM [Managed package inventory/status and package metadata]; File Creation via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: App stages or caches content retrieved from web-service platform locally before initiating secondary network connection]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: android:DevicePolicyManager (DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review); android:EMM (Managed package inventory/status and package metadata); mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: App stages or caches content retrieved from web-service platform locally before initiating secondary network connection); webproxy:applog (DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed); mobile:DynamicAnalysis (Dynamic API/runtime trace: App uses background work scheduler, JobScheduler, or persistent service to trigger web-service resolver fetch without user interaction).
  - AN1771 (iOS): For iOS, detect Web Service by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Application Permission via Application Vetting [Code-signing entitlements and Info.plist privacy usage-description keys]; Application State via Apple MDM [InstalledApplicationList / ManagedApplicationList]; Network Traffic Content via Enterprise Secure Web Gateway / Proxy [DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:ApplicationVetting (Code-signing entitlements and Info.plist privacy usage-description keys); iOS:MDM (InstalledApplicationList / ManagedApplicationList); webproxy:applog (DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed); mobile:DynamicAnalysis (Dynamic API/runtime trace: Background task or networking subsystem event occurs immediately before web-service resolver fetch).

## Procedure examples

- **S1214 Android/SpyAgent** (software) — Android/SpyAgent’s payload has obtained the C2 address via Twitter accounts.

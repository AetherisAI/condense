# T1532 — Archive Collected Data

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Collection
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1532
- **Last modified:** 2025-10-24

## Description

Adversaries may compress and/or encrypt data that is collected prior to exfiltration. Compressing data can help to obfuscate its contents and minimize use of network resources. Encryption can be used to hide information that is being exfiltrated from detection or make exfiltration less conspicuous upon inspection by a defender. 

 

Both compression and encryption are done prior to exfiltration, and can be performed using a utility, programming library, or custom algorithm.

## Detection strategies

- **DET0670 Detection of Archive Collected Data**
  - AN1767 (Android): For Android, detect Archive Collected Data from documented management, network, or vetting evidence; treat state queries as periodic observations rather than real-time events. Correlate Application Permission via Android Enterprise DPC / Application Vetting [DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review]; File Creation via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: App reads files across multiple directories or databases in background state (collection phase) then invokes archive or compression routines on collected content — read-then-archive sequence is the staging chain]; File Creation via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: App writes archive-like container, high-entropy packaged blob, or .zip/.gz output to app-private or cache path after bulk data collection — archive artifact in private storage is the staging evidence]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: android:DevicePolicyManager (DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review); mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: App reads files across multiple directories or databases in background state (collection phase) then invokes archive or compression routines on collected content — read-then-archive sequence is the staging chain); mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: App writes archive-like container, high-entropy packaged blob, or .zip/.gz output to app-private or cache path after bulk data collection — archive artifact in private storage is the staging evidence); mobile:DynamicAnalysis (Dynamic API/runtime trace: App invokes ZIP, GZIP, or bulk-buffer packaging routines (ZipOutputStream, DeflaterOutputStream, similar) on previously accessed local data in background state); mobile:DynamicAnalysis (Dynamic API/runtime trace: App applies encryption to newly created archive or staged data blob before network transmission — encrypt-after-archive confirms adversary-controlled packing for exfil).
  - AN1768 (iOS): For iOS, detect Archive Collected Data from documented management, network, or vetting evidence; treat state queries as periodic observations rather than real-time events. Correlate Application Permission via Application Vetting [Code-signing entitlements and Info.plist privacy usage-description keys]; Application State via Apple MDM [InstalledApplicationList / ManagedApplicationList]; File Creation via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: App writes large container, temp package, or high-entropy blob to container-local storage after clustered data access — staged archive artifact]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:ApplicationVetting (Code-signing entitlements and Info.plist privacy usage-description keys); iOS:MDM (InstalledApplicationList / ManagedApplicationList); mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: App writes large container, temp package, or high-entropy blob to container-local storage after clustered data access — staged archive artifact); mobile:DynamicAnalysis (Dynamic API/runtime trace: App performs bulk data transformation or packaging-like processing on collected records prior to outbound transfer on supervised device).

## Procedure examples

- **C0033 C0033** (campaign) — During C0033, PROMETHIUM used StrongPity to exfiltrate encrypted data to the C2 server.
- **S0405 Exodus** (software) — Exodus One encrypts data using XOR prior to exfiltration.
- **S0421 GolfSpy** (software) — GolfSpy encrypts data using a simple XOR operation with a pre-configured key prior to exfiltration.
- **S0422 Anubis** (software) — Anubis exfiltrates data encrypted (with RC4) by its ransomware module.
- **S0424 Triada** (software) — Triada encrypts data prior to exfiltration.
- **S0505 Desert Scorpion** (software) — Desert Scorpion can encrypt exfiltrated data.
- **S0535 Golden Cup** (software) — Golden Cup has encrypted exfiltrated data using AES in ECB mode.
- **S0540 Asacub** (software) — Asacub has encrypted C2 communications using Base64-encoded RC4.
- **S0577 FrozenCell** (software) — FrozenCell has compressed and encrypted data before exfiltration using password protected .7z archives.
- **S1079 BOULDSPY** (software) — BOULDSPY can encrypt its data before exfiltration.
- **S1082 Sunbird** (software) — Sunbird can exfiltrate collected data as a ZIP file.
- **S1094 BRATA** (software) — BRATA has compressed data with the `zlib` library before exfiltration.
- **S1185 LightSpy** (software) — LightSpy collects and compresses data to be exfiltrated using SSZipArchive.
- **S1243 DCHSpy** (software) — DCHSpy has compressed and encrypted collected data with a password from the C2 server.
- **S9048 KoSpy** (software) — KoSpy has encrypted collected data with a hardcoded AES key.

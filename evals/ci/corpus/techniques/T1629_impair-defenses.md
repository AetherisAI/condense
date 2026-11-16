# T1629 — Impair Defenses

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Defense Evasion
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1629
- **Last modified:** 2025-10-24

## Description

Adversaries may maliciously modify components of a victim environment in order to hinder or disable defensive mechanisms. This not only involves impairing preventative defenses, such as anti-virus, but also detection capabilities that defenders can use to audit activity and identify malicious behavior. This may span both native defenses as well as supplemental capabilities installed by users or mobile endpoint administrators.

## Sub-techniques

- **T1629.001 Impair Defenses: Prevent Application Removal**
- **T1629.002 Impair Defenses: Device Lockout**
- **T1629.003 Impair Defenses: Disable or Modify Tools**

## Mitigations

- **M1001 Security Updates** — Security updates often contain patches for vulnerabilities that could be exploited for root access. Root access is often a requirement to impairing defenses.
- **M1004 System Partition Integrity** — System partition integrity mechanisms, such as Verified Boot, can detect the unauthorized modification of system files.
- **M1010 Deploy Compromised Device Detection Method** — Mobile security software can typically detect if a device has been rooted or jailbroken and can inform the user, who can then take appropriate action.
- **M1011 User Guidance** — Providing user guidance around commonly abused features, such as the modal that requests for administrator permissions, should aid in preventing impairing defenses.
- **M1012 Enterprise Policy** — An EMM/MDM can use the Android `DevicePolicyManager.setPermittedAccessibilityServices` method to set an explicit list of applications that are allowed to use Android's accessibility features.

## Detection strategies

- **DET0687 Detection of Impair Defenses**
  - AN1797 (Android): For Android, detect Impair Defenses from documented management, network, or vetting evidence; treat state queries as periodic observations rather than real-time events. Correlate Application Permission via Android Enterprise DPC / Application Vetting [DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review]; OS API Execution via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: App invokes package management, DevicePolicyManager, or settings operations capable of disabling security tooling — API invocation to disable security control]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: android:DevicePolicyManager (DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review); mobile:DynamicAnalysis (Dynamic API/runtime trace: App invokes package management, DevicePolicyManager, or settings operations capable of disabling security tooling — API invocation to disable security control).

## Procedure examples

- **S1225 CherryBlos** (software) — CherryBlos has sent the victim back to the home screen when the victim navigates to the malicious application's settings and has automatically approved any permission requests by clicking on the "Allow" button when a system dialogue appears.
- **S1231 GodFather** (software) — GodFather has intercepted API returns from banking apps that detect malicious services, and modifies the methods to return back an empty list hiding the presence of the malware and other active services.

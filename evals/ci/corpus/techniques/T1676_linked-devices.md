# T1676 — Linked Devices

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Collection, Persistence
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1676
- **Last modified:** 2025-05-19

## Description

Adversaries may abuse the “linked devices” feature on messaging applications, such as Signal and WhatsApp, to register the user’s account to an adversary-controlled device. By abusing the “linked devices” feature, adversaries may achieve and maintain persistence through the user’s account, may collect information, such as the user’s messages and contacts list, and may send future messages from the linked device.

Signal is a messaging application that uses the open-source Signal Protocol to encrypt messages and calls; similarly, WhatsApp is a messaging application that has end-to-end encryption and other security measures to protect messages and calls. Both applications have a “linked devices” feature that allows users to access their Signal and/or WhatsApp accounts from different devices, such as a Windows or Mac desktop, an iPad or an Android tablet.

Adversaries may use Phishing techniques to trick the user into scanning a quick-response (QR) code, which is used to link the user’s Signal and/or WhatsApp account to an adversary-controlled device. For example, adversaries may masquerade QR codes as group invites, security alerts or as legitimate instructions for pairing linked devices. 
Upon scanning the QR code in Signal, users may click on the “Transfer Message History” option to sync the linked devices, which may allow adversaries to collect more information about the user. Upon scanning the QR code in WhatsApp, the user’s device will automatically send an end-to-end encrypted copy of recent message history to the adversary-controlled device.

## Mitigations

- **M1011 User Guidance** — For Android devices, users should be advised to enable Google Play Protect, which checks the device itself and the applications for malicious behavior. For iOS devices, users who are concerned about being targeted should consider enabling Lockdown Mode, which provides extreme protection of the device as well as data stored and transmitted. In general, users should be advised against scanning QR codes and/or clicking on suspicious links or text messages, which may masquerade as device-linking instructions by Signal or WhatsApp.

## Detection strategies

- **DET0716 Detection of Linked Devices**
  - AN1845 (Android): For Android, detect Linked Devices by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate API Calls via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: camera activated within app IN $MessagingAppList$ — QR scan requires camera access; activation in messaging app context is the trigger signal]; Network Connection Creation via Android Enterprise Network Logging / Enterprise VPN [DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata]; Network Traffic Content via Enterprise Secure Web Gateway / Proxy [DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:DynamicAnalysis (Dynamic API/runtime trace: camera activated within app IN $MessagingAppList$ — QR scan requires camera access; activation in messaging app context is the trigger signal); android:EnterpriseNetworkLog (DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata); webproxy:applog (DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed).
  - AN1846 (iOS): For iOS, detect Linked Devices by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Network Connection Creation via Apple Network Extension / Enterprise VPN [NEFilterFlow / per-app VPN / secure-web-gateway flow metadata]; Network Traffic Content via Enterprise Secure Web Gateway / Proxy [DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed]; Permissions Request via Application Vetting [Code-signing entitlements and Info.plist privacy usage-description keys]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: iOS:NetworkExtension (NEFilterFlow / per-app VPN / secure-web-gateway flow metadata); webproxy:applog (DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed); mobile:ApplicationVetting (Code-signing entitlements and Info.plist privacy usage-description keys).

## Procedure examples

- **G0034 Sandworm Team** (group) — Sandworm Team has used the linked devices feature to connect Signal accounts on devices captured on the battlefield to adversary-controlled infrastructure for follow-on exploitation.
- **G1033 Star Blizzard** (group) — Star Blizzard has used the linked devices feature to connect WhatsApp accounts to adversary-controlled infrastructure and/or the WhatsApp Web portal for message exfiltration.

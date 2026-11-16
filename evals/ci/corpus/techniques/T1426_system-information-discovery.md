# T1426 — System Information Discovery

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Discovery
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1426
- **Last modified:** 2026-05-12

## Description

Adversaries may attempt to get detailed information about a device’s operating system and hardware, including versions, patches, and architecture. Adversaries may use the information from System Information Discovery during automated discovery to shape follow-on behaviors, including whether or not to fully infects the target and/or attempts specific actions. 

 

On Android, much of this information is programmatically accessible to applications through the `android.os.Build` class. iOS is much more restrictive with what information is visible to applications. Typically, applications will only be able to query the device model and which version of iOS it is running.

## Detection strategies

- **DET0601 Detection of System Information Discovery**
  - AN1648 (Android): For Android, detect System Information Discovery by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate API Calls via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: android.os.Build field reads > $SysInfoFieldThreshold$ distinct fields within $SysInfoWindow$ by app NOT IN $SysInfoAllowList$ at launch or in background]; Application State via Android Enterprise / EMM [Managed package inventory/status and package metadata]; Network Connection Creation via Android Enterprise Network Logging / Enterprise VPN [DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:DynamicAnalysis (Dynamic API/runtime trace: android.os.Build field reads > $SysInfoFieldThreshold$ distinct fields within $SysInfoWindow$ by app NOT IN $SysInfoAllowList$ at launch or in background); android:EMM (Managed package inventory/status and package metadata); android:EnterpriseNetworkLog (DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata).
  - AN1649 (iOS): For iOS, detect System Information Discovery by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate API Calls via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: UIDevice.current.model]; Application State via Apple MDM [InstalledApplicationList / ManagedApplicationList]; Network Connection Creation via Apple Network Extension / Enterprise VPN [NEFilterFlow / per-app VPN / secure-web-gateway flow metadata]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:DynamicAnalysis (Dynamic API/runtime trace: UIDevice.current.model); iOS:MDM (InstalledApplicationList / ManagedApplicationList); iOS:NetworkExtension (NEFilterFlow / per-app VPN / secure-web-gateway flow metadata).

## Procedure examples

- **C0033 C0033** (campaign) — During C0033, PROMETHIUM used StrongPity to collect the device’s information, such as SIM serial number, SIM serial number, etc.
- **C0054 Operation Triangulation** (campaign) — During Operation Triangulation, the threat actors collected device and user information.
- **G0112 Windshift** (group) — Windshift has included system information enumeration in the malicious apps deployed as part of Operation BULL and Operation ROCK.
- **S0288 KeyRaider** (software) — Most KeyRaider samples search to find the Apple account's username, password and device's GUID in data being transferred.
- **S0289 Pegasus for iOS** (software) — Pegasus for iOS monitors the victim for status and disables other access to the phone by other jailbreaking software.
- **S0304 Android/Chuli.A** (software) — Android/Chuli.A gathered system information including phone number, OS version, phone model, and SDK version.
- **S0310 ANDROIDOS_ANSERVER.A** (software) — ANDROIDOS_ANSERVER.A gathers the device OS version, device build version, manufacturer, and model.
- **S0311 YiSpecter** (software) — YiSpecter has collected the device UUID.
- **S0313 RuMMS** (software) — RuMMS gathers device model and operating system version information and transmits it to a command and control server.
- **S0318 XLoader for Android** (software) — XLoader for Android collects the device’s Android ID and serial number.
- **S0326 RedDrop** (software) — RedDrop exfiltrates details of the victim device operating system and manufacturer.
- **S0399 Pallas** (software) — Pallas queries the device for metadata, such as device ID, OS version, and the number of cameras.
- **S0403 Riltok** (software) — Riltok can query various details about the device, including phone number, country, mobile operator, model, root availability, and operating system version.
- **S0406 Gustuff** (software) — Gustuff gathers information about the device, including the default SMS application, if SafetyNet is enabled, the battery level, the operating system version, and if the malware has elevated permissions.
- **S0407 Monokle** (software) — Monokle queries the device for metadata such as make, model, and power levels.
- **S0411 Rotexy** (software) — Rotexy collects information about the compromised device, including phone number, network operator, OS version, device model, and the device registration country.
- **S0418 ViceLeaker** (software) — ViceLeaker collects device information, including the device model and OS version.
- **S0420 Dvmap** (software) — Dvmap checks the Android version to determine which system library to patch.
- **S0421 GolfSpy** (software) — GolfSpy can obtain the device’s battery level, network operator, connection information, sensor information, and information about the device’s storage and memory.
- **S0422 Anubis** (software) — Anubis can collect the device’s ID.
- **S0425 Corona Updates** (software) — Corona Updates can collect various pieces of device information, including OS version, phone model, and manufacturer.
- **S0427 TrickMo** (software) — TrickMo can collect device information such as network operator, model, brand, and OS version.
- **S0463 INSOMNIA** (software) — INSOMNIA can collect the device’s name, serial number, iOS version, total disk space, and free disk space.
- **S0478 EventBot** (software) — EventBot can collect system information such as OS version, device vendor, and the type of screen lock that is active on the device.
- **S0480 Cerberus** (software) — Cerberus can collect device information, such as the default SMS app and device locale.
- **S0485 Mandrake** (software) — Mandrake can access device configuration information and status, including Android version, battery level, device model, country, and SIM operator.
- **S0490 XLoader for iOS** (software) — XLoader for iOS can obtain the device’s UDID, version number, and product number.
- **S0505 Desert Scorpion** (software) — Desert Scorpion can collect device metadata and can check if the device is rooted.
- **S0506 ViperRAT** (software) — ViperRAT can collect system information, including brand, manufacturer, and serial number.
- **S0507 eSurv** (software) — eSurv’s iOS version can collect device information.
- **S0509 FakeSpy** (software) — FakeSpy can collect device information, including OS version and device model.
- **S0522 Exobot** (software) — Exobot can obtain the device’s country and carrier name.
- **S0525 Android/AdDisplay.Ashas** (software) — Android/AdDisplay.Ashas can collect information about the device including device type, OS version, language, free storage space, battery status, device root, and if *developer mode* is enabled.
- **S0529 CarbonSteal** (software) — CarbonSteal has gathered device metadata, including model, manufacturer, SD card size, disk usage, memory, CPU, and serial number.
- **S0535 Golden Cup** (software) — Golden Cup can collect various pieces of device information, such as serial number and product information.
- **S0536 GPlayed** (software) — GPlayed can collect the device’s model, country, and Android version.
- **S0540 Asacub** (software) — Asacub can collect various pieces of device information, including device model and OS version.
- **S0544 HenBox** (software) — HenBox can collect device information and can check if the device is running MIUI on a Xiaomi device.
- **S0550 DoubleAgent** (software) — DoubleAgent has accessed common system information.
- **S0551 GoldenEagle** (software) — GoldenEagle has checked for system root.
- **S0555 CHEMISTGAMES** (software) — CHEMISTGAMES has fingerprinted devices to uniquely identify them.
- **S0558 Tiktok Pro** (software) — Tiktok Pro can check the device’s battery status.
- **S0577 FrozenCell** (software) — FrozenCell has gathered the device manufacturer, model, and serial number.
- **S1056 TianySpy** (software) — TianySpy can gather device UDIDs.
- **S1061 AbstractEmu** (software) — AbstractEmu can collect device information such as manufacturer, model, version, serial number, and telephone number.
- **S1062 S.O.V.A.** (software) — S.O.V.A. can gather data about the device.
- **S1077 Hornbill** (software) — Hornbill can collect the device ID, model, manufacturer, and Android version. It can also check available storage space and if the screen is locked.
- **S1079 BOULDSPY** (software) — BOULDSPY can collect system information, such as Android version and device identifiers.
- **S1082 Sunbird** (software) — Sunbird can exfiltrate the victim device ID, model, manufacturer, and Android version.
- **S1083 Chameleon** (software) — Chameleon has the ability to gather basic device information, such as version, model, root status, and country. Chameleon has also checked the restricted settings status of the device. If the Android 13 Restricted Settings status is present, an HTML page with instructions on how to enable the Accessibility Service will be shown to the user. Additionally, Chameleon has checked the keyguard’s status regarding how the device is locked (e.g. pattern, PIN or password).
- **S1094 BRATA** (software) — BRATA can retrieve Android system and hardware information.
- **S1095 AhRat** (software) — AhRat can obtain device info such as manufacturer, device ID, OS version, and country.
- **S1126 Phenakite** (software) — Phenakite can collect device metadata.
- **S1185 LightSpy** (software) — LightSpy collects device information, including the phone number, IMEI, CPU details, screen specifications, and memory information.
- **S1231 GodFather** (software) — GodFather has the ability to gain remote control of the victim device and to gather data associated with the device, including battery level, sound settings, and device brightness. GodFather has also obtained the phone's state, including network information, phone number, and serial number.
- **S1241 RatMilad** (software) — RatMilad has collected device information such as model, brand, buildId, Android version and manufacturer.
- **S9005 DocSwap** (software) — DocSwap has checked for the `LOCAL_MAC_ADDRESS` permission and has the ability to send system information.
- **S9006 VajraSpy** (software) — VajraSpy has requested for `android.permission.READ_PHONE_STATE` to collect information about the device.

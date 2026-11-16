# T1429 — Audio Capture

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Collection
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1429
- **Last modified:** 2026-05-12

## Description

Adversaries may capture audio to collect information by leveraging standard operating system APIs of a mobile device. Examples of audio information adversaries may target include user conversations, surroundings, phone calls, or other sensitive information. 

 

Android and iOS, by default, require that applications request device microphone access from the user. 

 

On Android devices, applications must hold the `RECORD_AUDIO` permission to access the microphone or the `CAPTURE_AUDIO_OUTPUT` permission to access audio output. Because Android does not allow third-party applications to hold the `CAPTURE_AUDIO_OUTPUT` permission by default, only privileged applications, such as those distributed by Google or the device vendor, can access audio output. However, adversaries may be able to gain this access after successfully elevating their privileges. With the `CAPTURE_AUDIO_OUTPUT` permission, adversaries may pass the `MediaRecorder.AudioSource.VOICE_CALL` constant to `MediaRecorder.setAudioOutput`, allowing capture of both voice call uplink and downlink. 

 

On iOS devices, applications must include the `NSMicrophoneUsageDescription` key in their `Info.plist` file to access the microphone.

## Mitigations

- **M1006 Use Recent OS Version** — Android 9 and above restricts access to microphone, camera, and other sensors from background applications.
- **M1011 User Guidance** — Users should be wary of granting applications dangerous or privacy-intrusive permissions, such as access to microphone or audio output.

## Detection strategies

- **DET0673 Detection of Audio Capture**
  - AN1772 (Android): For Android, detect Audio Capture by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate API Calls via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: AudioRecord.startRecording() or MediaRecorder.start() called by app NOT IN $AudioAllowList$]; File Creation via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: open() with O_CREAT for file with audio MIME type (audio/mp4, audio/aac, audio/3gpp) in /data/data/<app>/files/ within $AudioCaptureWindow$ of recording API start]; Network Traffic Flow via Android Enterprise Network Logging / Enterprise VPN [DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:DynamicAnalysis (Dynamic API/runtime trace: AudioRecord.startRecording() or MediaRecorder.start() called by app NOT IN $AudioAllowList$); mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: open() with O_CREAT for file with audio MIME type (audio/mp4, audio/aac, audio/3gpp) in /data/data/<app>/files/ within $AudioCaptureWindow$ of recording API start); android:EnterpriseNetworkLog (DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata); android:DevicePolicyManager (DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review).
  - AN1773 (iOS): For iOS, detect Audio Capture by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Application Permission via Application Vetting [Code-signing entitlements and Info.plist privacy usage-description keys]; Network Traffic Flow via Apple Network Extension / Enterprise VPN [NEFilterFlow / per-app VPN / secure-web-gateway flow metadata]; Permissions Request via Application Vetting [Code-signing entitlements and Info.plist privacy usage-description keys]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:ApplicationVetting (Code-signing entitlements and Info.plist privacy usage-description keys); iOS:NetworkExtension (NEFilterFlow / per-app VPN / secure-web-gateway flow metadata); mobile:ApplicationVetting (Code-signing entitlements and Info.plist privacy usage-description keys).

## Procedure examples

- **C0033 C0033** (campaign) — During C0033, PROMETHIUM used StrongPity to record phone calls.
- **C0054 Operation Triangulation** (campaign) — During Operation Triangulation, the threat actors used a microphone-recording module.
- **G0112 Windshift** (group) — Windshift has included phone call and audio recording capabilities in the malicious apps deployed as part of Operation BULL and Operation ROCK.
- **S0182 FinFisher** (software) — FinFisher uses the device microphone to record phone conversations.
- **S0289 Pegasus for iOS** (software) — Pegasus for iOS has the ability to record audio.
- **S0292 AndroRAT** (software) — AndroRAT gathers audio from the microphone.
- **S0295 RCSAndroid** (software) — RCSAndroid can record audio using the device microphone.
- **S0301 Dendroid** (software) — Dendroid can record audio and outgoing calls.
- **S0305 SpyNote RAT** (software) — SpyNote RAT can activate the victim's microphone.
- **S0316 Pegasus for Android** (software) — Pegasus for Android has the ability to record device audio.
- **S0318 XLoader for Android** (software) — XLoader for Android covertly records phone calls.
- **S0320 DroidJack** (software) — DroidJack is capable of recording device phone calls.
- **S0324 SpyDealer** (software) — SpyDealer can record phone calls and surrounding audio.
- **S0326 RedDrop** (software) — RedDrop captures live recordings of the device's surroundings.
- **S0327 Skygofree** (software) — Skygofree can record audio via the microphone when an infected device is in a specified location.
- **S0328 Stealth Mango** (software) — Stealth Mango can record audio using the device microphone.
- **S0329 Tangelo** (software) — Tangelo contains functionality to record calls as well as the victim device's environment.
- **S0399 Pallas** (software) — Pallas captures audio from the device microphone.
- **S0405 Exodus** (software) — Exodus Two can record audio from the compromised device's microphone and can record call audio in 3GP format.
- **S0407 Monokle** (software) — Monokle can record audio from the device's microphone and can record phone calls, specifying the output audio quality.
- **S0408 FlexiSpy** (software) — FlexiSpy can record both incoming and outgoing phone calls, as well as microphone audio.
- **S0418 ViceLeaker** (software) — ViceLeaker can record audio from the device’s microphone and can record phone calls together with the caller ID.
- **S0421 GolfSpy** (software) — GolfSpy can record audio and phone calls.
- **S0422 Anubis** (software) — Anubis can record phone calls and audio.
- **S0425 Corona Updates** (software) — Corona Updates can record MP4 files and monitor calls.
- **S0489 WolfRAT** (software) — WolfRAT can record call audio.
- **S0505 Desert Scorpion** (software) — Desert Scorpion can record audio from phone calls and the device microphone.
- **S0506 ViperRAT** (software) — ViperRAT can collect and record audio content.
- **S0507 eSurv** (software) — eSurv can record audio.
- **S0529 CarbonSteal** (software) — CarbonSteal can remotely capture device audio.
- **S0535 Golden Cup** (software) — Golden Cup can record audio from the microphone and phone calls.
- **S0544 HenBox** (software) — HenBox can access the device’s microphone.
- **S0550 DoubleAgent** (software) — DoubleAgent has captured audio and can record phone calls.
- **S0551 GoldenEagle** (software) — GoldenEagle has recorded calls and environment audio in .amr format.
- **S0558 Tiktok Pro** (software) — Tiktok Pro can capture audio from the device’s microphone and can record phone calls.
- **S0577 FrozenCell** (software) — FrozenCell has recorded calls.
- **S0655 BusyGasper** (software) — BusyGasper can record audio.
- **S1061 AbstractEmu** (software) — AbstractEmu can grant itself microphone permissions.
- **S1069 TangleBot** (software) — TangleBot can record audio using the device microphone.
- **S1077 Hornbill** (software) — Hornbill can record environmental and call audio.
- **S1079 BOULDSPY** (software) — BOULDSPY can access a device’s microphone to record audio, as well as cell and VoIP application calls.
- **S1080 Fakecalls** (software) — Fakecalls can turn on a device’s microphone to capture audio.
- **S1082 Sunbird** (software) — Sunbird can record environmental and call audio.
- **S1092 Escobar** (software) — Escobar can record audio from the device’s microphone.
- **S1095 AhRat** (software) — AhRat can record audio using a device’s microphone.
- **S1126 Phenakite** (software) — Phenakite can record phone calls.
- **S1128 HilalRAT** (software) — HilalRAT can activate a device’s microphone.
- **S1185 LightSpy** (software) — LightSpy has captured environment audio, phone calls and Voice over IP (VoIP) calls.
- **S1195 SpyC23** (software) — SpyC23 can record phone calls and audio.
- **S1231 GodFather** (software) — GodFather has requested for the `RECORD_AUDIO` permission to record audio with the microphone.
- **S1241 RatMilad** (software) — RatMilad has captured audio from the device.
- **S1243 DCHSpy** (software) — DCHSpy has captured audio from the device by taking control of the microphone.
- **S9005 DocSwap** (software) — DocSwap has the ability to start and stop audio recording.
- **S9006 VajraSpy** (software) — VajraSpy has recorded surrounding audio and phone calls from WhatsApp, WhatsApp Business, Signal, and Telegram by requesting `android.permission.RECORD_AUDIO`.
- **S9048 KoSpy** (software) — KoSpy has recorded audio using dynamically loaded plugins.

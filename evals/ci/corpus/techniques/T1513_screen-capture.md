# T1513 — Screen Capture

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Collection
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1513
- **Last modified:** 2026-05-12

## Description

Adversaries may use screen capture to collect additional information about a target device, such as applications running in the foreground, user data, credentials, or other sensitive information. Applications running in the background can capture screenshots or videos of another application running in the foreground by using the Android `MediaProjectionManager` (generally requires the device user to grant consent). Background applications can also use Android accessibility services to capture screen contents being displayed by a foreground application. An adversary with root access or Android Debug Bridge (adb) access could call the Android `screencap` or `screenrecord` commands.

## Mitigations

- **M1011 User Guidance** — Users should be advised not to grant consent for screen captures to occur unless expected. Users should avoid enabling USB debugging (Android Debug Bridge) unless explicitly required.
- **M1012 Enterprise Policy** — Enterprise policies should block access to the Android Debug Bridge (ADB) by preventing users from enabling USB debugging on Android devices unless specifically needed (e.g., if the device is used for application development). An EMM/MDM can use the Android `DevicePolicyManager.setPermittedAccessibilityServices` method to set an explicit list of applications that are allowed to use Android's accessibility features.
- **M1013 Application Developer Guidance** — Application developers can apply the `FLAG_SECURE` property to sensitive screens within their apps to make it more difficult for the screen contents to be captured.

## Detection strategies

- **DET0668 Detection of Screen Capture**
  - AN1764 (Android): For Android, detect Screen Capture from documented management, network, or vetting evidence; treat state queries as periodic observations rather than real-time events. Correlate Application Permission via Android Enterprise DPC / Application Vetting [DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review]; Application State via Android Enterprise / EMM [Managed package inventory/status and package metadata]; OS API Execution via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: MediaProjection capture session, accessibility-based foreground content observation, or privileged screencap/screenrecord invocation from app while different app is foregrounded — cross-app screen content access]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: android:DevicePolicyManager (DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review); android:EMM (Managed package inventory/status and package metadata); mobile:DynamicAnalysis (Dynamic API/runtime trace: MediaProjection capture session, accessibility-based foreground content observation, or privileged screencap/screenrecord invocation from app while different app is foregrounded — cross-app screen content access).

## Procedure examples

- **S0324 SpyDealer** (software) — SpyDealer abuses Accessibility features to steal messages from popular apps such as WeChat, Skype, Viber, and QQ.
- **S0405 Exodus** (software) — Exodus Two can take screenshots of any application in the foreground.
- **S0407 Monokle** (software) — Monokle can record the screen as the user unlocks the device and can take screenshots of any application in the foreground. Monokle can also abuse accessibility features to read the screen to capture data from a large number of popular applications.
- **S0408 FlexiSpy** (software) — FlexiSpy can take screenshots of other applications.
- **S0421 GolfSpy** (software) — GolfSpy can take screenshots.
- **S0422 Anubis** (software) — Anubis can take screenshots.
- **S0423 Ginp** (software) — Ginp can capture device screenshots and stream them back to the C2.
- **S0427 TrickMo** (software) — TrickMo can use the `MediaRecorder` class to record the screen when the targeted application is presented to the user, and can abuse accessibility features to record targeted applications to intercept transaction authorization numbers (TANs) and to scrape on-screen text.
- **S0478 EventBot** (software) — EventBot can abuse Android’s accessibility service to capture data from installed applications.
- **S0479 DEFENSOR ID** (software) — DEFENSOR ID can abuse the accessibility service to read any text displayed on the screen.
- **S0485 Mandrake** (software) — Mandrake can record the screen.
- **S0489 WolfRAT** (software) — WolfRAT can record the screen and take screenshots to capture messages from Line, Facebook Messenger, and WhatsApp.
- **S0551 GoldenEagle** (software) — GoldenEagle has taken screenshots.
- **S0558 Tiktok Pro** (software) — Tiktok Pro can take screenshots.
- **S0655 BusyGasper** (software) — BusyGasper can use its keylogger module to take screenshots of the area of the screen that the user tapped.
- **S1054 Drinik** (software) — Drinik can record the screen via the `MediaProjection` library to harvest user credentials, including biometric PINs.
- **S1062 S.O.V.A.** (software) — S.O.V.A. can take screenshots and abuse the Android Screen Cast feature to capture screen data.
- **S1069 TangleBot** (software) — TangleBot can record the screen and stream the data off the device.
- **S1077 Hornbill** (software) — Hornbill can take screenshots and can abuse accessibility services to scrape WhatsApp messages, contacts, and notifications.
- **S1079 BOULDSPY** (software) — BOULDSPY can take and exfiltrate screenshots.
- **S1082 Sunbird** (software) — Sunbird can take screenshots and abuse accessibility services to scrape BlackBerry Messenger and WhatsApp messages, contacts, and notifications
- **S1083 Chameleon** (software) — Chameleon has captured the device’s screen.
- **S1094 BRATA** (software) — BRATA can capture and send real-time screen output.
- **S1095 AhRat** (software) — AhRat can record the screen.
- **S1185 LightSpy** (software) — LightSpy has a plugin that can take screenshots.
- **S1195 SpyC23** (software) — SpyC23 can take record and take screenshots of the victim device.
- **S9004 Crocodilus** (software) — Crocodilus has taken a screenshot of the Google Authenticator application using its Accessibility Logging feature. The authentication codes are then sent to the C2 server.
- **S9048 KoSpy** (software) — KoSpy has captured screenshots and recordings of the device screen using dynamically loaded plugins.

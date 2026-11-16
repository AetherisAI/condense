# T1512 — Video Capture

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Collection
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1512
- **Last modified:** 2026-05-12

## Description

An adversary can leverage a device’s cameras to gather information by capturing video recordings. Images may also be captured, potentially in specified intervals, in lieu of video files. 

 

Malware or scripts may interact with the device cameras through an available API provided by the operating system. Video or image files may be written to disk and exfiltrated later. This technique differs from Screen Capture due to use of the device’s cameras for video recording rather than capturing the victim’s screen. 

 

In Android, an application must hold the `android.permission.CAMERA` permission to access the cameras. In iOS, applications must include the `NSCameraUsageDescription` key in the `Info.plist` file. In both cases, the user must grant permission to the requesting application to use the camera. If the device has been rooted or jailbroken, an adversary may be able to access the camera without knowledge of the user.

## Mitigations

- **M1006 Use Recent OS Version** — Android 9 and above restricts access to the mic, camera, and other device sensors from applications running in the background. iOS 14 and Android 12 introduced a visual indicator on the status bar (green dot) when an application is accessing the device’s camera.

## Detection strategies

- **DET0695 Detection of Video Capture**
  - AN1808 (Android): The defender correlates Android camera access by an app identity with app and device context showing that the capture is inconsistent with expected user-driven recording behavior. The strongest Android evidence is camera resource access followed by sustained capture duration, video or image artifact creation, buffer or cache growth, and optional outbound transfer, especially when the app is backgrounded, operating as a foreground service without visible user initiation, active while the device is locked, or capturing without recent user interaction. The detection is strengthened when the app is unmanaged, recently granted camera access, or not approved to record video. Log sources: MobileEDR:telemetry (Camera sensor access began from app identity and remained active for sustained capture interval in app context not mapped to approved video recording workflow); MobileEDR:telemetry (Camera sensor access occurred while AppState=background, foreground service active without visible user action, or DeviceLockState=locked during capture interval); MobileEDR:telemetry (LastUserInteractionDelta exceeded threshold before camera session start and no foreground transition occurred during sustained capture interval); MobileEDR:telemetry (Burst write to media, cache, temp, export, or staging path occurred during or immediately after camera session from same app identity); android:MDMLog (App identity performing camera session was unmanaged, recently granted camera permission, or not approved to use camera for video or interval image capture).
  - AN1809 (iOS): The defender correlates managed-app or supervised-device camera access with app and device context showing that the capture is inconsistent with expected user-driven recording behavior. The strongest iOS evidence is camera access or camera-adjacent capture activity followed by app-state evidence such as background or low-interaction operation, optional media artifact creation, and optional post-capture network transfer. Because direct low-level runtime visibility is weaker than Android for many enterprises, the primary iOS analytic should anchor on managed app context, device state, and downstream effects around camera use, with local subsystem telemetry treated as enrichment rather than sole proof. Log sources: MobileEDR:telemetry (LastUserInteractionDelta exceeded threshold before app-attributed session using non-standard protocol-to-port pairing); MobileEDR:telemetry (Background activity, low-interaction device state, or DeviceLockState=locked was observed during sustained camera session or immediately before camera access from same bundle context); iOS:unifiedlog (Camera, media capture, app-activation, or background-task subsystem event occurred immediately before or during sustained camera session from same managed-app or device context); iOS:MDMLog (Bundle performing camera session was not present in approved managed-app baseline or was not permitted to use camera for video or interval image capture).

## Procedure examples

- **G0112 Windshift** (group) — Windshift has included video recording in the malicious apps deployed as part of Operation BULL.
- **S0292 AndroRAT** (software) — AndroRAT can take photos and videos using the device cameras.
- **S0295 RCSAndroid** (software) — RCSAndroid can capture photos using the front and back cameras.
- **S0301 Dendroid** (software) — Dendroid can take photos and record videos.
- **S0316 Pegasus for Android** (software) — Pegasus for Android has the ability to take pictures using the device camera.
- **S0320 DroidJack** (software) — DroidJack can capture video using device cameras.
- **S0324 SpyDealer** (software) — SpyDealer can record video and take photos via front and rear cameras.
- **S0327 Skygofree** (software) — Skygofree can record video or capture photos when an infected device is in a specified location.
- **S0328 Stealth Mango** (software) — Stealth Mango can record and take pictures using the front and back cameras.
- **S0399 Pallas** (software) — Pallas can take pictures with both the front and rear-facing cameras.
- **S0405 Exodus** (software) — Exodus Two can take pictures with the device cameras.
- **S0407 Monokle** (software) — Monokle can take photos and videos.
- **S0408 FlexiSpy** (software) — FlexiSpy can record video.
- **S0418 ViceLeaker** (software) — ViceLeaker can take photos from both the front and back cameras.
- **S0421 GolfSpy** (software) — GolfSpy can record video.
- **S0425 Corona Updates** (software) — Corona Updates can take pictures using the camera and can record MP4 files.
- **S0426 Concipit1248** (software) — Concipit1248 requests permissions to use the device camera.
- **S0489 WolfRAT** (software) — WolfRAT can take photos and videos.
- **S0505 Desert Scorpion** (software) — Desert Scorpion can record videos.
- **S0506 ViperRAT** (software) — ViperRAT can take photos with the device camera.
- **S0535 Golden Cup** (software) — Golden Cup can take pictures with the camera.
- **S0544 HenBox** (software) — HenBox can access the device’s camera.
- **S0549 SilkBean** (software) — SilkBean can access the camera on the device.
- **S0551 GoldenEagle** (software) — GoldenEagle has taken photos with the device camera.
- **S0558 Tiktok Pro** (software) — Tiktok Pro can capture photos and videos from the device’s camera.
- **S0655 BusyGasper** (software) — BusyGasper can record from the device’s camera.
- **S1061 AbstractEmu** (software) — AbstractEmu can grant itself camera permissions.
- **S1069 TangleBot** (software) — TangleBot can record video from the device camera.
- **S1077 Hornbill** (software) — Hornbill can access a device’s camera and take photos.
- **S1079 BOULDSPY** (software) — BOULDSPY can take photos using the device cameras.
- **S1080 Fakecalls** (software) — Fakecalls can request camera permissions.
- **S1082 Sunbird** (software) — Sunbird can access a device’s camera and take photos.
- **S1092 Escobar** (software) — Escobar can take photos using the device cameras.
- **S1126 Phenakite** (software) — Phenakite can capture pictures and videos.
- **S1128 HilalRAT** (software) — HilalRAT can activate a device’s camera.
- **S1185 LightSpy** (software) — LightSpy has the ability to take one picture, continuous pictures or event-related pictures using the device’s camera. For iOS devices, the default file type for pictures is in High Efficiency Image Format (HEIC); for Android devices, the default file type for pictures is in JPEG format.
- **S1195 SpyC23** (software) — SpyC23 can capture pictures and videos.
- **S1241 RatMilad** (software) — RatMilad has taken photos and videos using the device’s camera.
- **S1243 DCHSpy** (software) — DCHSpy has captured photos from the device by taking control of the camera.
- **S9004 Crocodilus** (software) — Crocodilus has the ability to start and stop image streaming from the device’s front camera.
- **S9005 DocSwap** (software) — DocSwap has the ability to start and stop camera recording.
- **S9006 VajraSpy** (software) — VajraSpy has captured pictures using the device’s camera by requesting for `android.permission.CAMERA`.
- **S9048 KoSpy** (software) — KoSpy has taken pictures with the device’s cameras using dynamically loaded plugins.

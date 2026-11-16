# T1430 — Location Tracking

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Collection, Discovery
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1430
- **Last modified:** 2026-05-12

## Description

Adversaries may track a device’s physical location through use of standard operating system APIs via malicious or exploited applications on the compromised device. 

 

On Android, applications holding the `ACCESS_COAURSE_LOCATION` or `ACCESS_FINE_LOCATION` permissions provide access to the device’s physical location. On Android 10 and up, declaration of the `ACCESS_BACKGROUND_LOCATION` permission in an application’s manifest will allow applications to request location access even when the application is running in the background. Some adversaries have utilized integration of Baidu map services to retrieve geographical location once the location access permissions had been obtained. 

 

On iOS, applications must include the `NSLocationWhenInUseUsageDescription`, `NSLocationAlwaysAndWhenInUseUsageDescription`, and/or `NSLocationAlwaysUsageDescription` keys in their `Info.plist` file depending on the extent of requested access to location information. On iOS 8.0 and up, applications call `requestWhenInUseAuthorization()` to request access to location information when the application is in use or `requestAlwaysAuthorization()` to request access to location information regardless of whether the application is in use. With elevated privileges, an adversary may be able to access location data without explicit user consent with the `com.apple.locationd.preauthorized` entitlement key.

## Sub-techniques

- **T1430.001 Location Tracking: Remote Device Management Services**
- **T1430.002 Location Tracking: Impersonate SS7 Nodes**

## Mitigations

- **M1006 Use Recent OS Version** — On Android 11 and up, users are not prompted with the option to select “Allow all the time” and must navigate to the settings page to manually select this option. On iOS 14 and up, users can select whether to provide Precise Location for each installed application.
- **M1011 User Guidance** — Users should be wary of granting applications dangerous or privacy-intrusive permissions, such as access to location information. Users should also protect their account credentials and enable multi-factor authentication options when available.
- **M1012 Enterprise Policy** — If devices are enrolled using Apple User Enrollment or using a profile owner enrollment mode for Android, device controls prevent the enterprise from accessing the device’s physical location. This is typically used for a Bring Your Own Device (BYOD) deployment.
- **M1014 Interconnection Filtering** — Filtering requests by checking request origin information may provide some defense against spurious operators.

## Detection strategies

- **DET0675 Detection of Location Tracking**
  - AN1776 (Android): For Android, detect Location Tracking by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate API Calls via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: LocationManager.requestLocationUpdates() called with minTime < $LocationUpdateFreqThreshold$ by app NOT IN $LocationAllowList$]; Network Traffic Content via Enterprise Secure Web Gateway / Proxy [DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed]; Permissions Request via Android Enterprise DPC / Application Vetting [DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:DynamicAnalysis (Dynamic API/runtime trace: LocationManager.requestLocationUpdates() called with minTime < $LocationUpdateFreqThreshold$ by app NOT IN $LocationAllowList$); webproxy:applog (DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed); android:DevicePolicyManager (DevicePolicyManager.getPermissionGrantState(); PackageManager manifest/requested-permission review).
  - AN1777 (iOS): For iOS, detect Location Tracking by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Application Permission via Application Vetting [Code-signing entitlements and Info.plist privacy usage-description keys]; Network Traffic Flow via Apple Network Extension / Enterprise VPN [NEFilterFlow / per-app VPN / secure-web-gateway flow metadata]; Permissions Request via Application Vetting [Code-signing entitlements and Info.plist privacy usage-description keys]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:ApplicationVetting (Code-signing entitlements and Info.plist privacy usage-description keys); iOS:NetworkExtension (NEFilterFlow / per-app VPN / secure-web-gateway flow metadata); mobile:ApplicationVetting (Code-signing entitlements and Info.plist privacy usage-description keys).

## Procedure examples

- **C0033 C0033** (campaign) — During C0033, PROMETHIUM used StrongPity to access the device’s location.
- **C0054 Operation Triangulation** (campaign) — During Operation Triangulation, the threat actors monitored the device’s geolocation.
- **G0112 Windshift** (group) — Windshift has included location tracking capabilities in the malicious apps deployed as part of Operation BULL and Operation ROCK.
- **S0182 FinFisher** (software) — FinFisher tracks the latitude and longitude coordinates of the infected device.
- **S0289 Pegasus for iOS** (software) — Pegasus for iOS update and sends the location of the phone.
- **S0291 PJApps** (software) — PJApps has the capability to collect and leak the victim's location.
- **S0292 AndroRAT** (software) — AndroRAT tracks the device location.
- **S0295 RCSAndroid** (software) — RCSAndroid can record location.
- **S0304 Android/Chuli.A** (software) — Android/Chuli.A stole geo-location data.
- **S0305 SpyNote RAT** (software) — SpyNote RAT collects the device's location.
- **S0309 Adups** (software) — Adups transmitted location information.
- **S0314 X-Agent for Android** (software) — X-Agent for Android was believed to have been used to obtain locational data of Ukrainian artillery forces.
- **S0323 Charger** (software) — Charger checks the local settings of the device and does not run its malicious logic if the device is located in Ukraine, Russia, or Belarus.
- **S0324 SpyDealer** (software) — SpyDealer harvests location data from victims.
- **S0327 Skygofree** (software) — Skygofree can track the device's location.
- **S0328 Stealth Mango** (software) — Stealth Mango can perform GPS location tracking as well as capturing coordinates as when an SMS message or call is received.
- **S0329 Tangelo** (software) — Tangelo contains functionality to gather GPS coordinates.
- **S0399 Pallas** (software) — Pallas tracks the latitude and longitude coordinates of the infected device.
- **S0405 Exodus** (software) — Exodus Two can extract the GPS coordinates of the device.
- **S0407 Monokle** (software) — Monokle can track the device's location.
- **S0408 FlexiSpy** (software) — FlexiSpy can track the device's location.
- **S0418 ViceLeaker** (software) — ViceLeaker can collect location information, including GPS coordinates.
- **S0421 GolfSpy** (software) — GolfSpy can track the device’s location.
- **S0422 Anubis** (software) — Anubis can retrieve the device’s GPS location.
- **S0425 Corona Updates** (software) — Corona Updates can track the device’s location.
- **S0463 INSOMNIA** (software) — INSOMNIA can track the device’s location.
- **S0480 Cerberus** (software) — Cerberus can collect the device’s location.
- **S0485 Mandrake** (software) — Mandrake can collect the device’s location.
- **S0505 Desert Scorpion** (software) — Desert Scorpion can track the device’s location.
- **S0506 ViperRAT** (software) — ViperRAT can track the device’s location.
- **S0507 eSurv** (software) — eSurv can track the device’s location.
- **S0529 CarbonSteal** (software) — CarbonSteal can access the device’s location and track the device over time.
- **S0535 Golden Cup** (software) — Golden Cup can track the device’s location.
- **S0536 GPlayed** (software) — GPlayed can request the device’s location.
- **S0544 HenBox** (software) — HenBox can track the device’s location.
- **S0549 SilkBean** (software) — SilkBean has access to the device’s location.
- **S0551 GoldenEagle** (software) — GoldenEagle has tracked location.
- **S0555 CHEMISTGAMES** (software) — CHEMISTGAMES has collected the device’s location.
- **S0558 Tiktok Pro** (software) — Tiktok Pro can track the device’s location.
- **S0577 FrozenCell** (software) — FrozenCell has used an online cell tower geolocation service to track targets.
- **S0655 BusyGasper** (software) — BusyGasper can collect the device’s location information based on cellular network or GPS coordinates.
- **S1061 AbstractEmu** (software) — AbstractEmu can access a device's location.
- **S1069 TangleBot** (software) — TangleBot can request location permissions.
- **S1077 Hornbill** (software) — Hornbill can access a device’s location and check if GPS is enabled. Hornbill has logic to only log location changes greater than 70 meters.
- **S1079 BOULDSPY** (software) — BOULDSPY can get a device’s location using GPS or network.
- **S1080 Fakecalls** (software) — Fakecalls can access a device’s location.
- **S1082 Sunbird** (software) — Sunbird can access a device’s location.
- **S1083 Chameleon** (software) — Chameleon has gathered device location data.
- **S1092 Escobar** (software) — Escobar can request coarse and fine location permissions to track the device.
- **S1093 FlyTrap** (software) — FlyTrap can collect device geolocation data.
- **S1094 BRATA** (software) — BRATA can track the device's location.
- **S1095 AhRat** (software) — AhRat can track the device’s location.
- **S1128 HilalRAT** (software) — HilalRAT can access a device’s location.
- **S1185 LightSpy** (software) — LightSpy has accessed the device’s GPS location.
- **S1195 SpyC23** (software) — SpyC23 can access the device's location.
- **S1216 TriangleDB** (software) — TriangleDB has monitored the device’s geolocation, which includes coordinates, altitude, bearing and speed.
- **S1241 RatMilad** (software) — RatMilad has collected the device’s last known location.
- **S1243 DCHSpy** (software) — DCHSpy has collected location data.
- **S9005 DocSwap** (software) — DocSwap has the ability to collect location information and to start/stop location information from being sent to the C2 server.
- **S9006 VajraSpy** (software) — VajraSpy has exfiltrated the device’s location. VajraSpy has also requested for `android.permission.ACCESS_FINE_LOCATION` and `android.permission.ACCESS_COARSE_LOCATION` to obtain the device’s location.
- **S9048 KoSpy** (software) — KoSpy has collected the device’s location using dynamically loaded plugins.

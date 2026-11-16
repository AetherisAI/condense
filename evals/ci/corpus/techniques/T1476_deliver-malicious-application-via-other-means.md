# T1476 — Deliver Malicious Application via Other Means

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Initial Access
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1476
- **Last modified:** 2026-09-03

## Description

Adversaries may direct victims to download malicious applications via ways that avoid an authorized application store (e.g. Google Play Store or Apple App Store). For example, victims may be directed to downloading a malicious APK directly from a domain. Adversaries may wish to avoid placing malicious applications in an authorized application store due to increased potential risk of detection or other reasons.

Delivery methods for malicious applications include:

* Spearphishing Attachment: including the mobile application package as an attachment to an email
* Spearphishing Link: including a link to the mobile application package within an email, text message (e.g. SMS, iMessage, WhatsApp, etc.), web site, QR code, or other means.
* Third-Party Application Store: installing the mobile application package from a third-party application store, as opposed to an authorized app store that the device implicitly trusts as part of its default behavior. Third-party application stores may not apply the same level of scrutiny to applications as enforced by an authorized application store. 

Some Android malware comes with functionality to install additional applications, either automatically or when the adversary instructs it to.

## Detection strategies

- **DET0940 Detection of Mobile Application Delivery Outside Authorized Distribution Channels**
  - AN2290 (Android): On managed Android devices with the necessary network and security telemetry enabled, identify an application package retrieved through a browser, messaging application, third-party store, or another external delivery mechanism. Correlate the package retrieval with a subsequent installation event on the same device, using package identity, delivery source, timing, and installer provenance where available. Prioritize cases where the delivery source is outside approved distribution channels, the installer is inconsistent with authorized workflows, and the application is not approved for the device or user. Exclude sanctioned enterprise deployments, approved testing, and documented alternative distribution channels. Log sources: android:EnterpriseNetworkLog (DevicePolicyManager.retrieveNetworkLogs(): DnsEvent / ConnectEvent; VPN flow metadata); VPN:MobileProxy (Inspected HTTP transaction showing APK/package retrieval, including URL, response content type, or validated payload type); MobileEDR:telemetry (Monitored creation of an APK or application-package staging artifact following external retrieval); android:DevicePolicyManager (Managed security state and policy information, including supported installation-related settings); android:EMM (Managed package inventory/status and package metadata).
  - AN2291 (iOS): On managed iOS devices, identify observable delivery of an application package or distribution link through an external website, messaging channel, or other non-approved distribution mechanism. Where managed network inspection exposes the transaction, identify application-package retrieval or a distribution workflow outside the organization's approved channels. Correlate this with an application newly appearing in device inventory or with a managed-app lifecycle change, using bundle identifier, distribution attributes, and timing where available. Prioritize cases where the distribution evidence is independently observed and inconsistent with authorized enterprise distribution, alternative marketplaces, or approved testing workflows. Log sources: iOS:NetworkExtension (NEFilterFlow, per-app VPN, or secure web gateway flow metadata); VPN:MobileProxy (Inspected application-package retrieval transaction, where authorized content inspection exposes the URL, response, or package type); iOS:MDM (Declarative Management app.managed.list status changes, where collected); iOS:MDM (InstalledApplicationList / ManagedApplicationList).

## Procedure examples

- **G0070 Dark Caracal** (group) — Dark Caracal has distributed Pallas via trojanized applications hosted on watering hole websites.
- **G0097 Bouncing Golf** (group) — Bouncing Golf has delivered GolfSpy via a hosted application binary advertised on social media.
- **G0112 Windshift** (group) — Windshift has distributed malicious applications via their own websites during Operation BULL.
- **S0287 ZergHelper** (software) — ZergHelper has abused enterprise and personal certificates to sign and distribute applications.
- **S0302 Twitoor** (software) — Twitoor has the ability to install adversary-specified applications.
- **S0303 MazarBOT** (software) — MazarBOT has been delivered via an unsolicited text message containing a link to a web download URI.
- **S0304 Android/Chuli.A** (software) — Android/Chuli.A has been delivered via a spearphishing message containing a malicious Android application as an attachment.
- **S0311 YiSpecter** (software) — YiSpecter has been signed with iOS enterprise certificates issued by Apple to allow the malicious applications to be installed as enterprise applications on non-jailbroken iOS devices.
- **S0313 RuMMS** (software) — RuMMS has been delivered via an SMS message containing a link to an APK (Android application package).
- **S0318 XLoader for Android** (software) — XLoader for Android has been distributed via phishing websites.
- **S0326 RedDrop** (software) — RedDrop has used advertisements or other links within websites to encourage users to download the malicious applications using a complex content distribution network (CDN) and series of network redirects. RedDrop also downloads additional components (APKs, JAR files) from different C2 servers.
- **S0399 Pallas** (software) — Pallas has the ability to download and install attacker-specified applications.
- **S0403 Riltok** (software) — Riltok has been distributed via phishing SMS messages from infected devices.
- **S0406 Gustuff** (software) — Gustuff has been distributed via SMS phishing messages to phone numbers exfiltrated from compromised devices’ contact lists.
- **S0411 Rotexy** (software) — Rotexy has been distributed through phishing links sent in SMS messages as `AvitoPay.apk`.
- **S0418 ViceLeaker** (software) — ViceLeaker has been primarily distributed via Telegram and WhatsApp messages.
- **S0419 SimBad** (software) — SimBad has the ability to install adversary-specified applications.
- **S0421 GolfSpy** (software) — GolfSpy has the ability to install adversary-specified applications.
- **S0422 Anubis** (software) — Anubis has been distributed via a phishing link in an email.
- **S0432 Bread** (software) — Bread has the ability to install additional applications.
- **S0440 Agent Smith** (software) — Agent Smith has been distributed through the 9apps application store.
- **S0480 Cerberus** (software) — Cerberus has been delivered to the victim device via websites that prompt the user to “[…] install Adobe Flash Player,” downloading the malicious APK to the device.
- **S0490 XLoader for iOS** (software) — XLoader for iOS has been distributed via phishing SMS messages, which link to a malicious website hosting a device profile.
- **S0491 StrongPity** (software) — StrongPity has been distributed via a domain containing the word “dutch” and via a website impersonating the legitimate website shagle[.]com.
- **S0506 ViperRAT** (software) — ViperRAT has been distributed through third party websites.
- **S0507 eSurv** (software) — eSurv has been distributed via phishing websites with geo-restrictions that allow access to only Italian and Turkmenistani mobile carriers. eSurv also has the ability to install applications via malicious iOS provisioning profiles containing the developer’s certificate.
- **S0509 FakeSpy** (software) — FakeSpy has been distributed via direct download links in SMS phishing messages.
- **S0522 Exobot** (software) — Exobot has been distributed using direct download links.
- **S0524 AndroidOS/MalLocker.B** (software) — AndroidOS/MalLocker.B has been distributed using direct download links.
- **S0539 Red Alert 2.0** (software) — Red Alert 2.0 has been distributed via webpages designed to look like the Play Store.
- **S0540 Asacub** (software) — Asacub has been delivered via phishing SMS messages that contain a link to a website that hosts the malicious APK file.
- **S0544 HenBox** (software) — HenBox has been distributed via third-party application stores.
- **S0558 Tiktok Pro** (software) — Tiktok Pro has been distributed via direct download on third party websites, with the link sent in phishing SMS messages.
- **S9040 NGate** (software) — NGate has been distributed via files[.]fm and through fake websites that mimic legitimate services, such as banking websites and Rio de Prêmios, a lottery website.
- **S9048 KoSpy** (software) — KoSpy has been distributed via the third-party application store Apkpure.

# T1456 — Drive-By Compromise

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Initial Access
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1456
- **Last modified:** 2025-10-24

## Description

Adversaries may gain access to a system through a user visiting a website over the normal course of browsing. With this technique, the user's web browser is typically targeted for exploitation, but adversaries may also use compromised websites for non-exploitation behavior such as acquiring an Application Access Token.

Multiple ways of delivering exploit code to a browser exist, including:

* A legitimate website is compromised where adversaries have injected some form of malicious code such as JavaScript, iFrames, and cross-site scripting.
* Malicious ads are paid for and served through legitimate ad providers.
* Built-in web application interfaces are leveraged for the insertion of any other kind of object that can be used to display web content or contain a script that executes on the visiting client (e.g. forum posts, comments, and other user controllable web content).

Often the website used by an adversary is one visited by a specific community, such as government, a particular industry, or region, where the goal is to compromise a specific user or set of users based on a shared interest. This kind of targeted attack is referred to a strategic web compromise or watering hole attack. There are several known examples of this occurring.

Typical drive-by compromise process:

1. A user visits a website that is used to host the adversary controlled content.
2. Scripts automatically execute, typically searching versions of the browser and plugins for a potentially vulnerable version. 
 * The user may be required to assist in this process by enabling scripting or active website components and ignoring warning dialog boxes.
3. Upon finding a vulnerable version, exploit code is delivered to the browser.
4. If exploitation is successful, then it will give the adversary code execution on the user's system unless other protections are in place.
 * In some cases a second visit to the website after the initial scan is required before exploit code is delivered.

## Mitigations

- **M1001 Security Updates** — Security updates frequently contain patches for known exploits.

## Detection strategies

- **DET0614 Detection of Drive-By Compromise**
  - AN1669 (Android): For Android, detect Drive-By Compromise by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate File Creation via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: open() with O_CREAT for APK or binary file in /sdcard/ or /data/local/tmp/ by browser process within $DriveByWindow$ — payload drop confirms exploit code execution]; Network Traffic Content via Enterprise Secure Web Gateway / Proxy [DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed]; Process Creation via Application Vetting / Managed Device Telemetry [execve()]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: open() with O_CREAT for APK or binary file in /sdcard/ or /data/local/tmp/ by browser process within $DriveByWindow$ — payload drop confirms exploit code execution); webproxy:applog (DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed); mobile:DynamicAnalysis (execve()).
  - AN1670 (iOS): For iOS, detect Drive-By Compromise by correlating analyst-visible device/network evidence and management state; use streaming or batched telemetry only where the documented collector is deployed. Correlate Network Connection Creation via Apple Network Extension / Enterprise VPN [NEFilterFlow / per-app VPN / secure-web-gateway flow metadata]; Network Traffic Content via Enterprise Secure Web Gateway / Proxy [DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed]; Process Creation via Application Vetting / Managed Device Telemetry [com.apple.WebKit or com.apple.WebContent process fault at level=fault within $DriveByWindow$ of navigation to flagged URL — kernel fault in WebKit subsystem is the exploit-execution signal]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: iOS:NetworkExtension (NEFilterFlow / per-app VPN / secure-web-gateway flow metadata); webproxy:applog (DNS/HTTP(S) inspection or proxy transaction metadata where enterprise decryption/inspection is deployed); mobile:DynamicAnalysis (com.apple.WebKit or com.apple.WebContent process fault at level=fault within $DriveByWindow$ of navigation to flagged URL — kernel fault in WebKit subsystem is the exploit-execution signal).

## Procedure examples

- **C0033 C0033** (campaign) — During C0033, PROMETHIUM distributed StrongPity through the compromised official Syrian E-Gov website.
- **S0289 Pegasus for iOS** (software) — Pegasus for iOS was distributed through a web site by exploiting vulnerabilities in the Safari web browser on iOS devices.
- **S0311 YiSpecter** (software) — YiSpecter is believed to have initially infected devices using internet traffic hijacking to generate abnormal popups.
- **S0328 Stealth Mango** (software) — Stealth Mango is delivered via a a watering hole website that mimics the third-party Android app store APKMonk. In at least one case, the watering hole URL was distributed through Facebook Messenger.
- **S0463 INSOMNIA** (software) — INSOMNIA has utilized malicious JavaScript and iframes to exploit WebKit running on vulnerable iOS 12 devices.
- **S1185 LightSpy** (software) — LightSpy gains initial execution when a victim visits a compromised or adversary-controlled website, including those mimicking legitimate sources such as a Hong Kong newspaper. Upon loading `index.html`, a Safari WebKit exploit is triggered, leading to the download of a Mach-O binary disguised with a `.png` extension.

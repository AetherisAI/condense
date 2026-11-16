# T1189 — Drive-by Compromise

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Initial Access
- **Platforms:** Identity Provider, Linux, macOS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1189
- **Last modified:** 2025-10-24

## Description

Adversaries may gain access to a system through a user visiting a website over the normal course of browsing. Multiple ways of delivering exploit code to a browser exist (i.e., Drive-by Target), including:

* A legitimate website is compromised, allowing adversaries to inject malicious code
* Script files served to a legitimate website from a publicly writeable cloud storage bucket are modified by an adversary
* Malicious ads are paid for and served through legitimate ad providers (i.e., Malvertising)
* Built-in web application interfaces that allow user-controllable content are leveraged for the insertion of malicious scripts or iFrames (e.g., cross-site scripting)

Browser push notifications may also be abused by adversaries and leveraged for malicious code injection via User Execution. By clicking "allow" on browser push notifications, users may be granting a website permission to run JavaScript code on their browser.

Often the website used by an adversary is one visited by a specific community, such as government, a particular industry, or a particular region, where the goal is to compromise a specific user or set of users based on a shared interest. This kind of targeted campaign is often referred to a strategic web compromise or watering hole attack. There are several known examples of this occurring.

Typical drive-by compromise process:

1. A user visits a website that is used to host the adversary controlled content.
2. Scripts automatically execute, typically searching versions of the browser and plugins for a potentially vulnerable version. The user may be required to assist in this process by enabling scripting, notifications, or active website components and ignoring warning dialog boxes.
3. Upon finding a vulnerable version, exploit code is delivered to the browser.
4. If exploitation is successful, the adversary will gain code execution on the user's system unless other protections are in place. In some cases, a second visit to the website after the initial scan is required before exploit code is delivered.

Unlike Exploit Public-Facing Application, the focus of this technique is to exploit software on a client endpoint upon visiting a website. This will commonly give an adversary access to systems on the internal network instead of external systems that may be in a DMZ.

## Mitigations

- **M1017 User Training** — Train users to be aware of access or manipulation attempts by an adversary to reduce the risk of successful spearphishing, social engineering, and other techniques that involve user interaction.
- **M1021 Restrict Web-Based Content** — Adblockers can help prevent malicious code served through ads from executing in the first place. Script blocking extensions can also help to prevent the execution of JavaScript. Consider disabling browser push notifications from certain applications and browsers.
- **M1048 Application Isolation and Sandboxing** — Browser sandboxes can be used to mitigate some of the impact of exploitation, but sandbox escapes may still exist. Other types of virtualization and application microsegmentation may also mitigate the impact of client-side exploitation. The risks of additional exploits and weaknesses in implementation may still exist for these types of systems.
- **M1050 Exploit Protection** — Security applications that look for behavior used during exploitation such as Windows Defender Exploit Guard (WDEG) and the Enhanced Mitigation Experience Toolkit (EMET) can be used to mitigate some exploitation behavior. Control flow integrity checking is another way to potentially identify and stop a software exploit from occurring. Many of these protections depend on the architecture and target application binary for compatibility.
- **M1051 Update Software** — Ensuring that all browsers and plugins are kept updated can help prevent the exploit phase of this technique. Use modern browsers with security features turned on.

## Detection strategies

- **DET0176 Drive-by Compromise — Behavior-based, Multi-platform Detection Strategy (T1189)**
  - AN0498 (Windows): Correlated evidence of anomalous browser/network behavior (suspicious external resource fetches and script injection patterns) followed by atypical child processes, ephemeral execution contexts, memory modification or process injection, and unexpected file drops. Defender sees network requests to previously unseen/suspicious domains or resources + browser process spawning unusual children or loading unsigned modules + file writes or registry changes shortly after those requests. Log sources: WinEventLog:Security (EventCode=4624, 4648); WinEventLog:Security (EventCode=4688); WinEventLog:Sysmon (EventCode=3, 22); WinEventLog:Application (Browser or plugin/application logs showing script errors, plugin enumerations, or unusual extension load events); etw:Microsoft-Windows-Kernel-Process (Memory Modification / Unmapped module load or suspicious RWX allocations in the process space of a browser process); WinEventLog:Sysmon (EventCode=11); NSM:Flow (http.request: HTTP requests and responses for specific script resources, unexpected content-types (application/octet-stream for script URLs), suspicious referrers, or obfuscated javascript resources).
  - AN0499 (Linux): Correlated evidence of browser or webview fetches to uncommon domains or mutated JS resources (proxy/NGFW logs + Zeek/HTTP logs) followed by unexpected interpreters or script engines executing (python, ruby, sh) spawned from browser processes or user sessions, rapid on-disk staging in /tmp, and outbound connections that deviate from baseline. Defender sees: uncommon resource fetch → short-lived child process executions from user browser context → file writes in temp directories → anomalous outbound C2-like connections. Log sources: auditd:SYSCALL (execve: execve calls where a browser/webview process is parent and child is interpreter (python, sh, ruby) or downloader (curl, wget)); linux:syslog (Application or browser logs (webview errors, plugin enumerations) indicating suspicious script evaluation or plugin loads); NSM:Flow (http::response: HTTP responses with suspicious content-type for scripts, long obfuscated javascript bodies, or redirects to exploit kit domains); linux:Sysmon (New files in /tmp, /var/tmp, $HOME/.cache, executed within TimeWindow after browser HTTP fetch); NSM:Connections (Outbound connections from newly spawned child processes or from the browser to uncommon endpoints or on anomalous ports).
  - AN0500 (macOS): Correlated evidence where Safari/Chrome/WebKit-based processes issue network requests for uncommon or obfuscated JS resources followed by spawning of script interpreters, launchd or ad-hoc binaries, unusual child processes, or dynamic library loads into browser processes. Defender sees: proxy/HTTP logs with suspicious resource content + unifiedlogs/ASL showing browser/plugin crashes or extension loads + process events indicating child process creation and file writes to /var/folders or /tmp shortly after the fetch. Log sources: macos:unifiedlog (Logs from unifiedlogging that show browser crashes, plugin enumerations, extension installs or errors around the same time as suspicious network fetches); macos:unifiedlog (process_create: Process creation where parent is Safari/Google Chrome and child is script interpreter or signed-but-unusual helper binary); macos:unifiedlog (New files written to /var/folders, /tmp, ~/Library/Caches, or ~/Downloads by browser context or its children); NSM:Flow (HTTP/HTTPS requests for script resources flagged by content inspection (excessive obfuscation, eval usage, unusual redirects)); macos:unifiedlog (Anomalous dyld dynamic library loads or RWX memory mappings in browser process).
  - AN0501 (Identity Provider): Post-compromise identity & session anomalies that follow a drive-by compromise: token reuse from new/unfamiliar IPs, anomalous sign-in patterns for previously inactive users, unexpected consent/grant events, or provisioning changes. Defender sees an endpoint/browser compromise (network + endpoint signals) followed by unusual IdP events: new refresh token issuance, consent/consent-grant events, odd MFA bypass patterns, or unusual OAuth client registrations. Log sources: azure:signinlogs (SignIn: Sign-ins flagged as atypical (new geographic region, unfamiliar device id) shortly after correlated endpoint/browser compromise times); m365:unified (Application Consent grants, new OAuth client registrations, or unusual admin-level activities executed by a user account shortly after suspected drive-by compromise); saas:auth (Refresh token issuance or refresh token usage from new IPs or user agents); AWS:CloudTrail (ConsoleLogin: If IdP backed by cloud provider, Console login from new IP/agent after correlated endpoint compromise).

## Procedure examples

- **C0010 C0010** (campaign) — During C0010, UNC3890 actors likely established a watering hole that was hosted on a login page of a legitimate Israeli shipping company that was active until at least November 2021.
- **C0016 Operation Dust Storm** (campaign) — During Operation Dust Storm, the threat actors used a watering hole attack on a popular software reseller to exploit the then-zero-day Internet Explorer vulnerability CVE-2014-0322.
- **C0057 3CX Supply Chain Attack** (campaign) — During the 3CX Supply Chain Attack, AppleJeus compromised the `www.tradingtechnologies[.]com` website hosting a hidden IFRAME to exploit visitors, two months before the site was known to deliver a compromised version of the X_TRADER software package.
- **G0001 Axiom** (group) — Axiom has used watering hole attacks to gain access.
- **G0007 APT28** (group) — APT28 has compromised targets via strategic web compromise utilizing custom exploit kits. APT28 used reflected cross-site scripting (XSS) against government websites to redirect users to phishing webpages.
- **G0010 Turla** (group) — Turla has infected victims using watering holes.
- **G0012 Darkhotel** (group) — Darkhotel used embedded iframes on hotel login portals to redirect selected victims to download malware.
- **G0027 Threat Group-3390** (group) — Threat Group-3390 has extensively used strategic web compromises to target victims.
- **G0032 Lazarus Group** (group) — Lazarus Group delivered RATANKBA and other malicious code to victims via a compromised legitimate website.
- **G0035 Dragonfly** (group) — Dragonfly has compromised targets via strategic web compromise (SWC) utilizing a custom exploit kit.
- **G0040 Patchwork** (group) — Patchwork has used watering holes to deliver files with exploits to initial victims.
- **G0048 RTM** (group) — RTM has distributed its malware via the RIG and SUNDOWN exploit kits, as well as online advertising network `Yandex.Direct`.
- **G0050 APT32** (group) — APT32 has infected victims by tricking them into visiting compromised watering hole websites.
- **G0056 PROMETHIUM** (group) — PROMETHIUM has used watering hole attacks to deliver malicious versions of legitimate installers.
- **G0059 Magic Hound** (group) — Magic Hound has conducted watering-hole attacks through media and magazine websites.
- **G0060 BRONZE BUTLER** (group) — BRONZE BUTLER compromised three Japanese websites using a Flash exploit to perform watering hole attacks.
- **G0065 Leviathan** (group) — Leviathan has infected victims using watering holes.
- **G0066 Elderwood** (group) — Elderwood has delivered zero-day exploits and malware to victims by injecting malicious code into specific public Web pages visited by targets within a particular sector.
- **G0067 APT37** (group) — APT37 has used strategic web compromises, particularly of South Korean websites, to distribute malware. The group has also used torrent file-sharing sites to more indiscriminately disseminate malware to victims. As part of their compromises, the group has used a Javascript based profiler called RICECURRY to profile a victim's web browser and deliver malicious code accordingly.
- **G0068 PLATINUM** (group) — PLATINUM has sometimes used drive-by attacks against vulnerable browser plugins.
- **G0070 Dark Caracal** (group) — Dark Caracal leveraged a watering hole to serve up malicious code.
- **G0073 APT19** (group) — APT19 performed a watering hole attack on forbes.com in 2014 to compromise targets.
- **G0077 Leafminer** (group) — Leafminer has infected victims using watering holes.
- **G0082 APT38** (group) — APT38 has conducted watering holes schemes to gain initial access to victims.
- **G0095 Machete** (group) — Machete has distributed Machete through a fake blog website.
- **G0112 Windshift** (group) — Windshift has used compromised websites to register custom URL schemes on a remote system.
- **G0124 Windigo** (group) — Windigo has distributed Windows malware via drive-by downloads.
- **G0134 Transparent Tribe** (group) — Transparent Tribe has used websites with malicious hyperlinks and iframes to infect targeted victims with Crimson, njRAT, and other malicious tools.
- **G0138 Andariel** (group) — Andariel has used watering hole attacks, often with zero-day exploits, to gain initial access to victims within a specific IP range.
- **G1006 Earth Lusca** (group) — Earth Lusca has performed watering hole attacks.
- **G1012 CURIUM** (group) — CURIUM has used strategic website compromise to infect victims with malware such as IMAPLoader.
- **G1020 Mustard Tempest** (group) — Mustard Tempest has used drive-by downloads for initial infection, often using fake browser updates as a lure.
- **G1034 Daggerfly** (group) — Daggerfly has used strategic website compromise for initial access against victims.
- **G1035 Winter Vivern** (group) — Winter Vivern created dedicated web pages mimicking legitimate government websites to deliver malicious fake anti-virus software.
- **S0215 KARAE** (software) — KARAE was distributed through torrent file-sharing websites to South Korean victims, using a YouTube video downloader application as a lure.
- **S0216 POORAIM** (software) — POORAIM has been delivered through compromised sites acting as watering holes.
- **S0451 LoudMiner** (software) — LoudMiner is typically bundled with pirated copies of Virtual Studio Technology (VST) for Windows and macOS.
- **S0482 Bundlore** (software) — Bundlore has been spread through malicious advertisements on websites.
- **S0483 IcedID** (software) — IcedID has cloned legitimate websites/applications to distribute the malware.
- **S0496 REvil** (software) — REvil has infected victim machines through compromised websites and exploit kits.
- **S0531 Grandoreiro** (software) — Grandoreiro has used compromised websites and Google Ads to bait victims into downloading its installer.
- **S0606 Bad Rabbit** (software) — Bad Rabbit spread through watering holes on popular sites by injecting JavaScript into the HTML body or a `.js` file.
- **S1086 Snip3** (software) — Snip3 has been delivered to targets via downloads from malicious domains.
- **S1124 SocGholish** (software) — SocGholish has been distributed through compromised websites with malicious content often masquerading as browser updates.
- **S9050 Vidar** (software) — Vidar has been distributed via malicious advertisements when users searched for “Notepad++.”

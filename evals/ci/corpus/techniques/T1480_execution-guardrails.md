# T1480 — Execution Guardrails

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Stealth
- **Platforms:** ESXi, Linux, macOS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1480
- **Last modified:** 2026-05-12

## Description

Adversaries may use execution guardrails to constrain execution or actions based on adversary supplied and environment specific conditions that are expected to be present on the target. Guardrails ensure that a payload only executes against an intended target and reduces collateral damage from an adversary’s campaign. Values an adversary can provide about a target system or environment to use as guardrails may include specific network share names, attached physical devices, files, joined Active Directory (AD) domains, and local/external IP addresses.

Guardrails can be used to prevent exposure of capabilities in environments that are not intended to be compromised or operated within. This use of guardrails is distinct from typical Virtualization/Sandbox Evasion. While use of Virtualization/Sandbox Evasion may involve checking for known sandbox values and continuing with execution only if there is no match, the use of guardrails will involve checking for an expected target-specific value and only continuing with execution if there is such a match.

Adversaries may identify and block certain user-agents to evade defenses and narrow the scope of their attack to victims and platforms on which it will be most effective. A user-agent self-identifies data such as a user's software application, operating system, vendor, and version. Adversaries may check user-agents for operating system identification and then only serve malware for the exploitable software while ignoring all other operating systems.

## Sub-techniques

- **T1480.001 Execution Guardrails: Environmental Keying**
- **T1480.002 Execution Guardrails: Mutual Exclusion**

## Mitigations

- **M1055 Do Not Mitigate** — Execution Guardrails likely should not be mitigated with preventative controls because it may protect unintended targets from being compromised. If targeted, efforts should be focused on preventing adversary tools from running earlier in the chain of activity and on identifying subsequent malicious behavior if compromised.

## Detection strategies

- **DET0562 Multi-Platform Execution Guardrails Environmental Validation Detection Strategy**
  - AN1551 (Windows): Windows environmental validation behavioral chain: (1) Rapid system discovery reconnaissance through WMI queries, registry enumeration, and network share discovery, (2) Environment-specific artifact collection (hostname, domain, IP addresses, installed software, hardware identifiers), (3) Cryptographic operations or conditional logic based on collected environmental values, (4) Selective payload execution contingent on environmental validation results, (5) Temporal correlation between discovery activities and subsequent execution or network communication Log sources: WinEventLog:Security (EventCode=4688); WinEventLog:Security (EventCode=4648); WinEventLog:Security (EventCode=4624, 4648); WinEventLog:Sysmon (EventCode=3, 22); WinEventLog:Sysmon (EventCode=7); WinEventLog:Sysmon (EventCode=8); WinEventLog:Sysmon (EventCode=11); WinEventLog:Sysmon (EventCode=13, 14); WinEventLog:WMI (EventCode=5857, 5858, 5860, 5861); WinEventLog:PowerShell (EventCode=4103, 4104, 4105, 4106).
  - AN1552 (Linux): Linux environmental validation behavioral chain: (1) Intensive system enumeration through command execution (uname, hostname, ifconfig, lsblk, mount), (2) File system reconnaissance targeting specific paths, network configurations, and installed packages, (3) Process and user enumeration to validate target environment characteristics, (4) Conditional script execution or binary activation based on environmental criteria, (5) Network connectivity validation and external IP address resolution for geolocation verification Log sources: auditd:SYSCALL (execve); auditd:SYSCALL (open); auditd:SYSCALL (openat,connect -k discovery); auditd:PROCTITLE (command-line execution patterns for system discovery utilities (uname, hostname, ifconfig, netstat, lsof, ps, mount)); linux:syslog (authentication and authorization events during environmental validation phase).
  - AN1553 (macOS): macOS environmental validation behavioral chain: (1) System profiling through system_profiler, sysctl, and hardware discovery commands, (2) Network interface and configuration enumeration for geolocation and network environment validation, (3) Application installation and version discovery for software environment fingerprinting, (4) Security feature detection (SIP, Gatekeeper, XProtect status), (5) Conditional payload execution based on macOS-specific environmental criteria and System Integrity Protection bypass validation Log sources: macos:unifiedlog (process execution events for system discovery utilities (system_profiler, sysctl, networksetup, ioreg) with parameter analysis); fs:fileevents (File system access events with kFSEventStreamEventFlagItemRemoved, kFSEventStreamEventFlagItemRenamed flags for environmental artifact collection (/System/Library, /usr/sbin, plist files)).
  - AN1554 (ESXi): ESXi hypervisor environmental validation behavioral chain: (1) Virtual machine inventory and configuration enumeration through vim-cmd and esxcli commands, (2) Host hardware and network configuration discovery for hypervisor environment validation, (3) Datastore and storage configuration reconnaissance, (4) vCenter connectivity and cluster membership validation, (5) Selective malware deployment based on virtualization infrastructure characteristics and target VM validation Log sources: esxi:shell (shell command execution for system discovery (vim-cmd, esxcli, vmware-cmd) targeting VM inventory and host configuration); esxi:hostd (host daemon events related to VM operations and configuration queries during reconnaissance).

## Procedure examples

- **C0047 RedDelta Modified PlugX Infection Chain Operations** (campaign) — Mustang Panda included the use of Cloudflare geofencing mechanisms to limit payload download activity during RedDelta Modified PlugX Infection Chain Operations.
- **G0047 Gamaredon Group** (group) — Gamaredon Group has used geoblocking to limit downloads of the malicious file to specific geographic locations.
- **G0082 APT38** (group) — APT38 has leveraged file discovery actions to determine if a predetermined file is present prior to execution to prevent redundant execution on a compromised device.
- **G0099 APT-C-36** (group) — APT-C-36 has used geolocation filtering in malware delivery to redirect traffic not coming from a targeted region or country, such as Ecuador or Colombia, to legitimate sites.
- **G1043 BlackByte** (group) — BlackByte stopped execution if identified language settings on victim machines was Russian or one of several language associated with former Soviet republics. BlackByte has used ransomware variants requiring a key passed on the command line for the malware to execute.
- **G1052 Contagious Interview** (group) — Contagious Interview has configured C2 endpoints to review IP geolocation, request headers, victim environment details and runtime conditions prior to delivering payloads.
- **S0504 Anchor** (software) — Anchor can terminate itself if specific execution flags are not present.
- **S0562 SUNSPOT** (software) — SUNSPOT only replaces SolarWinds Orion source code if the MD5 checksums of both the original source code file and backdoored replacement source code match hardcoded values.
- **S0570 BitPaymer** (software) — BitPaymer compares file names and paths to a list of excluded names and directory names during encryption.
- **S0603 Stuxnet** (software) — Stuxnet checks for specific operating systems on 32-bit machines, Registry keys, and dates for vulnerabilities, and will exit execution if the values are not met.
- **S0634 EnvyScout** (software) — EnvyScout can call `window.location.pathname` to ensure that embedded files are being executed from the C: drive, and will terminate if they are not.
- **S0635 BoomBox** (software) — BoomBox can check its current working directory and for the presence of a specific file and terminate if specific values are not found.
- **S0636 VaporRage** (software) — VaporRage has the ability to check for the presence of a specific DLL and terminate if it is not found.
- **S0637 NativeZone** (software) — NativeZone can check for the presence of KM.EkeyAlmaz1C.dll and will halt execution unless it is in the same directory as the rest of the malware's components.
- **S0678 Torisma** (software) — Torisma is only delivered to a compromised host if the victim's IP address is on an allow-list.
- **S1035 Small Sieve** (software) — Small Sieve can only execute correctly if the word `Platypus` is passed to it on the command line.
- **S1052 DEADEYE** (software) — DEADEYE can ensure it executes only on intended systems by identifying the victim's volume serial number, hostname, and/or DNS domain.
- **S1111 DarkGate** (software) — DarkGate uses per-victim links for hosting malicious archives, such as ZIP files, in services such as SharePoint to prevent other entities from retrieving them.
- **S1130 Raspberry Robin** (software) — Raspberry Robin will check for the presence of several security products on victim machines and will avoid UAC bypass mechanisms if they are identified. Raspberry Robin can use specific cookie values in HTTP requests to command and control infrastructure to validate that requests for second stage payloads originate from the initial downloader script.
- **S1133 Apostle** (software) — Apostle's ransomware variant requires that a base64-encoded argument is passed when executed, that is used as the Public Key for subsequent encryption operations. If Apostle is executed without this argument, it automatically runs a self-delete function.
- **S1143 LunarLoader** (software) — LunarLoader can use the DNS domain name of a compromised host to create a decryption key to ensure a malicious payload can only execute against the intended targets.
- **S1149 CHIMNEYSWEEP** (software) — CHIMNEYSWEEP can execute a task which leads to execution if it finds a process name containing “creensaver.”
- **S1150 ROADSWEEP** (software) — ROADSWEEP requires four command line arguments to execute correctly, otherwise it will produce a message box and halt execution.
- **S1161 BPFDoor** (software) — BPFDoor creates a zero byte PID file at `/var/run/haldrund.pid`. BPFDoor uses this file to determine if it is already running on a system to ensure only one instance is executing at a time.
- **S1178 ShrinkLocker** (software) — ShrinkLocker will exit its "main" function if the victim domain name does not match provided criteria.
- **S1179 Exbyte** (software) — Exbyte checks for the presence of a configuration file before completing execution.
- **S1180 BlackByte Ransomware** (software) — BlackByte Ransomware creates a mutex value with a hard-coded name, and terminates if that mutex already exists on the victim system. BlackByte Ransomware checks the system language to see if it matches one of a list of hard-coded values; if a match is found, the malware will terminate.
- **S1183 StrelaStealer** (software) — StrelaStealer variants only execute if the keyboard layout or language matches a set list of variables.
- **S1184 BOLDMOVE** (software) — BOLDMOVE verifies it is executing from a specific path during execution.
- **S1185 LightSpy** (software) — On macOS, LightSpy checks the existence of a process identification number (PID) file, `/Users/Shared/irc.pid`, to verify if LightSpy is currently running.
- **S1194 Akira _v2** (software) — Akira _v2 will fail to execute if the targeted `/vmfs/volumes/` path does not exist or is not defined.
- **S1199 LockBit 2.0** (software) — LockBit 2.0 will not execute on hosts where the system language is set to a language spoken in the Commonwealth of Independent States region.
- **S1200 StealBit** (software) — StealBit will execute an empty infinite loop if it detects it is being run in the context of a debugger.
- **S1202 LockBit 3.0** (software) — LockBit 3.0 can make execution dependent on specific parameters including a unique passphrase and the system language of the targeted host not being found on a set exclusion list.
- **S1210 Sagerunex** (software) — Sagerunex uses a "servicemain" function to verify its environment to ensure it can only be executed as a service, as well as the existence of a configuration file in a specified directory.
- **S1212 RansomHub** (software) — RansomHub will terminate without proceeding to encryption if the infected machine is on a list of allowlisted machines specified in its configuration.
- **S1239 TONESHELL** (software) — TONESHELL has an exception handler that executes when ESET antivirus applications `ekrn.exe` and `egui.exe` are not found and directly injects its code into waitfor.exe using Native Windows API including `WriteProcessMemory` and `CreateRemoteThreadEx`.
- **S1240 RedLine Stealer** (software) — RedLine Stealer has built in settings to not operate based on geolocation or country of the victim host.
- **S1242 Qilin** (software) — Qilin can require a specific password to be passed by command-line argument during execution which must match a pre-defined value in the configuration in order for it to continue execution.
- **S9001 SystemBC** (software) — SystemBC has checked if the last characters of DNS server names end in .bit before initializing C2 communication. SystemBC has identified running processes associated with anti-virus solutions to include `a2guard.exe` to determine whether it executes or not.
- **S9003 evilginx2** (software) — evilginx2 can reject requests to phishing URLs if the User-Agent of the visitor doesn't match the allowlist REGEX filter for a specific lure.
- **S9010 GlassWorm** (software) — GlassWorm has utilized logic to avoid executing on Russian based devices.
- **S9019 PureCrypter** (software) — PureCrypter code contains an ExclusionRegionNames option where it can compare the results of `kernel32!GetGeoInfo` with a list of regions.
- **S9020 LODEINFO** (software) — LODEINFO can halt execution if the “en_US” locale is identified on a victim's machine.
- **S9023 HiddenFace** (software) — HiddenFace can check for the presence of specific analysis tools and will terminate itself if they are found.
- **S9026 ROAMINGHOUSE** (software) — ROAMINGHOUSE can change its execution method to create a batch file in the startup folder that executes a legitimate executable if a McAfee product is detected.
- **S9034 Tsundere Botnet** (software) — Tsundere Botnet has checked the victim machine’s location to avoid infecting in the Commonwealth of Independent States (CIS) region.
- **S9039 LazyWiper** (software) — LazyWiper can halt execution if `[System.Net.Dns]::GetHostName()` or `$env:COMPUTERNAME` contains `“pe-dc”`.
- **S9041 TeamPCP Cloud Stealer** (software) — TeamPCP Cloud Stealer has checked if it is running on a developer machine (rather than GitHub Actions) before executing a Python script for persistence. The script has also polled C2 every 50 minutes for additional payloads and aborted if the returned value contained YouTube.
- **S9042 CanisterWorm** (software) — CanisterWorm can base execution on specific conditions including halting its wiper component if Kubernetes is not found and if the target is not located in Iran.
- **S9043 Mini Shai-Hulud** (software) — Mini Shai-Hulud has utilized execution guardrails in order to prevent operating in restricted geolocations to include Russia by checking the devices language and terminating when a forbidden value is detected. Mini Shai-Hulud has also utilized designated instructions that execute when victim hosts match geolocations to include wiping victim devices when the device is determined to be located within Iran or Israel.
- **S9050 Vidar** (software) — If a debugger or analysis environment is detected, Vidar has triggered a memory access violation exception, terminating its process by calling `RtlExitUserProcess`.

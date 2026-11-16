# T1104 — Multi-Stage Channels

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Command and Control
- **Platforms:** Linux, macOS, Windows, ESXi
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1104
- **Last modified:** 2025-10-24

## Description

Adversaries may create multiple stages for command and control that are employed under different conditions or for certain functions. Use of multiple stages may obfuscate the command and control channel to make detection more difficult.

Remote access tools will call back to the first-stage command and control server for instructions. The first stage may have automated capabilities to collect basic host information, update tools, and upload additional files. A second remote access tool (RAT) could be uploaded at that point to redirect the host to the second-stage command and control server. The second stage will likely be more fully featured and allow the adversary to interact with the system through a reverse shell and additional RAT features.

The different stages will likely be hosted separately with no overlapping infrastructure. The loader may also have backup first-stage callbacks or Fallback Channels in case the original first-stage communication path is discovered and blocked.

## Mitigations

- **M1031 Network Intrusion Prevention** — Network intrusion detection and prevention systems that use network signatures to identify traffic for specific adversary malware can be used to mitigate activity at the network level.

## Detection strategies

- **DET0228 Detect Multi-Stage Command and Control Channels**
  - AN0637 (Windows): Initial process initiates outbound connection to first-stage C2, receives payloads or commands, then spawns or injects into a second process that establishes a new outbound connection to an unrelated destination (second-stage C2). Log sources: WinEventLog:Sysmon (EventCode=3, 22); WinEventLog:Sysmon (EventCode=1).
  - AN0638 (Linux): Shell script or binary initiates curl/wget request to staging domain, writes output to disk or memory, and shortly afterward launches another process that establishes new outbound connection to a different IP or hostname. Log sources: auditd:SYSCALL (execve, connect); iptables:LOG (OUTBOUND).
  - AN0639 (macOS): Initial process using NSURLSession or similar APIs reaches out to known staging domains, followed by creation of a reverse shell or RAT connecting to a second unrelated server. Log sources: macos:endpointsecurity (ES_EVENT_TYPE_NOTIFY_EXEC); macos:unifiedlog (tcp/udp).
  - AN0640 (ESXi): CLI-based or API-based network call from the hypervisor to external staging host, shortly followed by a connection to a second external IP by a spawned process or scheduled task. Log sources: esxi:hostd (CLI network calls); esxi:cron (process or cron activity).

## Procedure examples

- **C0056 RedPenguin** (campaign) — During RedPenguin, UNC3886 used malware with separate channels to request and carry out tasks from C2.
- **G0022 APT3** (group) — An APT3 downloader first establishes a SOCKS5 connection to 192.157.198[.]103 using TCP port 1913; once the server response is verified, it then requests a connection to 192.184.60[.]229 on TCP port 81.
- **G0032 Lazarus Group** (group) — Lazarus Group has used multi-stage malware components that inject later stages into separate processes.
- **G0069 MuddyWater** (group) — MuddyWater has used one C2 to obtain enumeration scripts and monitor web logs, but a different C2 to send data back.
- **G0096 APT41** (group) — APT41 used the storescyncsvc.dll BEACON backdoor to download a secondary backdoor.
- **S0022 Uroburos** (software) — Individual Uroburos implants can use multiple communication channels based on one of four available modes of operation.
- **S0031 BACKSPACE** (software) — BACKSPACE attempts to avoid detection by checking a first stage command and control server to determine if it should connect to the second stage server, which performs "louder" interactions with the malware.
- **S0069 BLACKCOFFEE** (software) — BLACKCOFFEE uses Microsoft’s TechNet Web portal to obtain an encoded tag containing the IP address of a command and control server and then communicates separately with that IP address for C2. If the C2 server is discovered or shut down, the threat actors can update the encoded IP address on TechNet to maintain control of the victims’ machines.
- **S0220 Chaos** (software) — After initial compromise, Chaos will download a second stage to establish a more permanent presence on the affected system.
- **S0476 Valak** (software) — Valak can download additional modules and malware capable of using separate C2 channels.
- **S0534 Bazar** (software) — The Bazar loader is used to download and execute the Bazar backdoor.
- **S1086 Snip3** (software) — Snip3 can download and execute additional payloads and modules over separate communication channels.
- **S1141 LunarWeb** (software) — LunarWeb can use one C2 URL for first contact and to upload information about the host computer and two additional C2 URLs for getting commands.
- **S1160 Latrodectus** (software) — Latrodectus has used a two-tiered C2 configuration with tier one nodes connecting to the victim and tier two nodes connecting to backend infrastructure.
- **S1206 JumbledPath** (software) — JumbledPath can communicate over a unique series of connections to send and retrieve data from exploited devices.

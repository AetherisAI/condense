# T1568 — Dynamic Resolution

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Command and Control
- **Platforms:** ESXi, Linux, macOS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1568
- **Last modified:** 2026-05-12

## Description

Adversaries may dynamically establish connections to command and control infrastructure to evade common detections and remediations. This may be achieved by using malware that shares a common algorithm with the infrastructure the adversary uses to receive the malware's communications. These calculations can be used to dynamically adjust parameters such as the domain name, IP address, or port number the malware uses for command and control.

Adversaries may use dynamic resolution for the purpose of Fallback Channels. When contact is lost with the primary command and control server malware may employ dynamic resolution as a means to reestablishing command and control.

## Sub-techniques

- **T1568.001 Dynamic Resolution: Fast Flux DNS**
- **T1568.002 Dynamic Resolution: Domain Generation Algorithms**
- **T1568.003 Dynamic Resolution: DNS Calculation**

## Mitigations

- **M1021 Restrict Web-Based Content** — In some cases a local DNS sinkhole may be used to help prevent behaviors associated with dynamic resolution.
- **M1031 Network Intrusion Prevention** — Network intrusion detection and prevention systems that use network signatures to identify traffic for specific adversary malware can be used to mitigate activity at the network level. Malware researchers can reverse engineer malware variants that use dynamic resolution and determine future C2 infrastructure that the malware will attempt to contact, but this is a time and resource intensive effort.

## Detection strategies

- **DET0039 Detection Strategy for Dynamic Resolution across OS Platforms**
  - AN0109 (Windows): Correlate high-frequency or anomalous DNS query activity with processes that do not normally generate network requests (e.g., Office apps, system utilities). Detect pseudo-random or high-entropy domain lookups indicative of domain generation algorithms (DGAs). Log sources: WinEventLog:Sysmon (EventCode=3, 22); WinEventLog:Sysmon (EventCode=1).
  - AN0110 (Linux): Monitor /var/log/audit/audit.log and DNS resolver logs for repeated failed lookups or connections to high-entropy domain names. Correlate suspicious DNS queries with process lineage (e.g., Python, bash, or unusual system daemons). Log sources: auditd:SYSCALL (socket/connect); linux:syslog (Query to suspicious domain with high entropy or low reputation).
  - AN0111 (macOS): Inspect unified logs for anomalous DNS resolutions triggered by non-network applications. Flag repeated connections to newly registered or algorithmically generated domains. Correlate with endpoint process telemetry. Log sources: macos:unifiedlog (DNS query with pseudo-random subdomain patterns); macos:unifiedlog (Unexpected applications generating outbound DNS queries).
  - AN0112 (ESXi): Monitor esxcli and syslog records for DNS resolver changes or repeated queries to unusual external domains by management agents. Detect unauthorized changes to VM or host network settings that redirect DNS lookups. Log sources: esxi:syslog (esxcli network vswitch or DNS resolver configuration updates).

## Procedure examples

- **C0002 Night Dragon** (campaign) — During Night Dragon, threat actors used dynamic DNS services for C2.
- **C0005 Operation Spalax** (campaign) — For Operation Spalax, the threat actors used dynamic DNS services, including Duck DNS and DNS Exit, as part of their C2 infrastructure.
- **C0016 Operation Dust Storm** (campaign) — For Operation Dust Storm, the threat actors used dynamic DNS domains from a variety of free providers, including No-IP, Oray, and 3322.
- **C0024 SolarWinds Compromise** (campaign) — During the SolarWinds Compromise, APT29 used dynamic DNS resolution to construct and resolve to randomly-generated subdomains for C2.
- **C0026 C0026** (campaign) — During C0026, the threat actors re-registered a ClouDNS dynamic DNS subdomain which was previously used by ANDROMEDA.
- **C0043 Indian Critical Infrastructure Intrusions** (campaign) — During Indian Critical Infrastructure Intrusions, RedEcho used dynamic DNS domains associated with malicious infrastructure.
- **G0016 APT29** (group) — APT29 has used Dynamic DNS providers for their malware C2 infrastructure.
- **G0047 Gamaredon Group** (group) — Gamaredon Group has incorporated dynamic DNS domains in its infrastructure.
- **G0094 Kimsuky** (group) — Kimsuky has used Dynamic DNS (DDNS) services, such as FreeDNS or No-IP DDNS, to include servers located in South Korea.
- **G0099 APT-C-36** (group) — APT-C-36 has used DDNS services such as DuckDNS, noip[.]com, and con-ip[.]com to redirect victims to sites or repositories hosting malware implants.
- **G0134 Transparent Tribe** (group) — Transparent Tribe has used dynamic DNS services to set up C2.
- **G1002 BITTER** (group) — BITTER has used DDNS for C2 communications.
- **G1018 TA2541** (group) — TA2541 has used dynamic DNS services for C2 infrastructure.
- **G1042 RedEcho** (group) — RedEcho used dynamic DNS domains associated with malicious infrastructure.
- **S0034 NETEAGLE** (software) — NETEAGLE can use HTTP to download resources that contain an IP address and port number pair to connect to for C2.
- **S0148 RTM** (software) — RTM has resolved Pony C2 server IP addresses by either converting Bitcoin blockchain transaction data to specific octets, or accessing IP addresses directly within the Namecoin blockchain.
- **S0268 Bisonal** (software) — Bisonal has used a dynamic DNS service for C2.
- **S0332 Remcos** (software) — Remcos has used dynamic DNS domains in C2 communications.
- **S0449 Maze** (software) — Maze has forged POST strings with a random choice from a list of possibilities including "forum", "php", "view", etc. while making connection with the C2, hindering detection efforts.
- **S0559 SUNBURST** (software) — SUNBURST dynamically resolved C2 infrastructure for randomly-generated subdomains within a parent domain.
- **S0666 Gelsemium** (software) — Gelsemium can use dynamic DNS domain names in C2.
- **S0671 Tomiris** (software) — Tomiris has connected to a signalization server that provides a URL and port, and then Tomiris sends a GET request to that URL to establish C2.
- **S1087 AsyncRAT** (software) — AsyncRAT can be configured to use dynamic DNS.
- **S9015 BRICKSTORM** (software) — BRICKSTORM has utilized DNS services sslip.io and nip.io to resolve C2 IP addresses.

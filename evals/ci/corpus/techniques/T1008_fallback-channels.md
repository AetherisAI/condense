# T1008 — Fallback Channels

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Command and Control
- **Platforms:** ESXi, Linux, macOS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1008
- **Last modified:** 2026-09-09

## Description

Adversaries may use fallback or alternate communication channels if the primary channel is compromised or inaccessible in order to maintain reliable command and control and to avoid data transfer thresholds.

## Mitigations

- **M1031 Network Intrusion Prevention** — Network intrusion detection and prevention systems that use network signatures to identify traffic for specific adversary malware can be used to mitigate activity at the network level. Signatures are often for unique indicators within protocols and may be based on the specific protocol used by a particular adversary or tool, and will likely be different across various malware families and versions. Adversaries will likely change tool C2 signatures over time or construct protocols in such a way as to avoid detection by common defensive tools.

## Detection strategies

- **DET0499 Behavioral Detection of Fallback or Alternate C2 Channels**
  - AN1376 (Windows): Establishing network connections on uncommon ports or protocols following C2 disruption or blocking. Often executed by processes that typically exhibit no network activity. Log sources: WinEventLog:Sysmon (EventCode=3, 22); NSM:Flow (uncommon ports).
  - AN1377 (Linux): Creation of outbound connections on alternate ports or using covert transport (e.g., ICMP, DNS) from non-network-intensive processes, following known disruption or blocked traffic. Log sources: auditd:SYSCALL (outbound connections); NSM:Flow (alternate ports).
  - AN1378 (macOS): Outbound fallback traffic from low-profile or background launch agents using unusual protocols or destinations after primary channel inactivity. Log sources: macos:unifiedlog (None); NSM:Flow (None).
  - AN1379 (ESXi): Outbound traffic from host management services or guest-to-host interactions over unusual interfaces (e.g., backdoor API endpoints or external VPN tunnels). Log sources: esxi:vmkernel (None); esxi:vpxd (None).

## Procedure examples

- **C0002 Night Dragon** (campaign) — During Night Dragon, threat actors used company extranet servers as secondary C2 servers.
- **G0032 Lazarus Group** (group) — Lazarus Group malware SierraAlfa sends data to one of the hard-coded C2 servers chosen at random, and if the transmission fails, chooses a new C2 server to attempt the transmission again.
- **G0046 FIN7** (group) — FIN7's Harpy backdoor malware can use DNS as a backup channel for C2 if HTTP fails.
- **G0049 OilRig** (group) — OilRig malware ISMAgent falls back to its DNS tunneling mechanism if it is unable to reach the C2 server over HTTP.
- **G0096 APT41** (group) — APT41 used the Steam community page as a fallback mechanism for C2.
- **G1048 UNC3886** (group) — UNC3886 has employed layers of redundancy to maintain access to compromised environments including network devices, hypervisors, and virtual machines.
- **S0017 BISCUIT** (software) — BISCUIT malware contains a secondary fallback command and control server that is contacted after the primary command and control server.
- **S0021 Derusbi** (software) — Derusbi uses a backup communication method with an HTTP beacon.
- **S0022 Uroburos** (software) — Uroburos can use up to 10 channels to communicate between implants.
- **S0023 CHOPSTICK** (software) — CHOPSTICK can switch to a new C2 channel if the current one is broken.
- **S0034 NETEAGLE** (software) — NETEAGLE will attempt to detect if the infected host is configured to a proxy. If so, NETEAGLE will send beacons via an HTTP POST request; otherwise it will send beacons via UDP/6000.
- **S0044 JHUHUGIT** (software) — JHUHUGIT tests if it can reach its C2 server by first attempting a direct connection, and if it fails, obtaining proxy settings and sending the connection through a proxy, and finally injecting code into a running browser if the proxy method fails.
- **S0051 MiniDuke** (software) — MiniDuke uses Google Search to identify C2 servers if its primary C2 method via Twitter is not working.
- **S0058 SslMM** (software) — SslMM has a hard-coded primary and backup C2 string.
- **S0059 WinMM** (software) — WinMM is usually configured with primary and backup domains for C2 communications.
- **S0062 DustySky** (software) — DustySky has two hard-coded domains for C2 servers; if the first does not respond, it will try the second.
- **S0084 Mis-Type** (software) — Mis-Type first attempts to use a Base64-encoded network protocol over a raw TCP socket for C2, and if that method fails, falls back to a secondary HTTP-based protocol to communicate to an alternate C2 server.
- **S0085 S-Type** (software) — S-Type primarily uses port 80 for C2, but falls back to ports 443 or 8080 if initial communication fails.
- **S0089 BlackEnergy** (software) — BlackEnergy has the capability to communicate over a backup channel via plus.google.com.
- **S0117 XTunnel** (software) — The C2 server used by XTunnel provides a port number to the victim to use as a fallback in case the connection closes on the currently used port.
- **S0211 Linfo** (software) — Linfo creates a backdoor through which remote attackers can change C2 servers.
- **S0236 Kwampirs** (software) — Kwampirs uses a large list of C2 servers that it cycles through until a successful connection is established.
- **S0260 InvisiMole** (software) — InvisiMole has been configured with several servers available for alternate C2 communications.
- **S0265 Kazuar** (software) — Kazuar can accept multiple URLs for C2 servers.
- **S0266 TrickBot** (software) — TrickBot can use secondary C2 servers for communication after establishing connectivity and relaying victim information to primary C2 servers.
- **S0269 QUADAGENT** (software) — QUADAGENT uses multiple protocols (HTTPS, HTTP, DNS) for its C2 server as fallback channels if communication with one is unsuccessful.
- **S0348 Cardinal RAT** (software) — Cardinal RAT can communicate over multiple C2 host and port combinations.
- **S0376 HOPLIGHT** (software) — HOPLIGHT has multiple C2 channels in place in case one fails.
- **S0377 Ebury** (software) — Ebury has implemented a fallback mechanism to begin using a DGA when the attacker hasn't connected to the infected system for three days.
- **S0401 Exaramel for Linux** (software) — Exaramel for Linux can attempt to find a new C2 server if it receives an error.
- **S0409 Machete** (software) — Machete has sent data over HTTP if FTP failed, and has also used a fallback server.
- **S0444 ShimRat** (software) — ShimRat has used a secondary C2 location if the first was unavailable.
- **S0476 Valak** (software) — Valak can communicate over multiple C2 hosts.
- **S0495 RDAT** (software) — RDAT has used HTTP if DNS C2 communications were not functioning.
- **S0501 PipeMon** (software) — PipeMon can switch to an alternate C2 domain when a particular date has been reached.
- **S0504 Anchor** (software) — Anchor can use secondary C2 servers for communication after establishing connectivity and relaying victim information to primary C2 servers.
- **S0512 FatDuke** (software) — FatDuke has used several C2 servers per targeted organization.
- **S0534 Bazar** (software) — Bazar has the ability to use an alternative C2 server if the primary server fails.
- **S0538 Crutch** (software) — Crutch has used a hardcoded GitHub repository as a fallback channel.
- **S0586 TAINTEDSCRIBE** (software) — TAINTEDSCRIBE can randomly pick one of five hard-coded IP addresses for C2 communication; if one of the IP fails, it will wait 60 seconds and then try another IP address.
- **S0603 Stuxnet** (software) — Stuxnet has the ability to generate new C2 domains.
- **S0610 SideTwist** (software) — SideTwist has primarily used port 443 for C2 but can use port 80 as a fallback.
- **S0622 AppleSeed** (software) — AppleSeed can use a second channel for C2 when the primary channel is in upload mode.
- **S0629 RainyDay** (software) — RainyDay has the ability to switch between TCP and HTTP for C2 if one method is not working.
- **S0666 Gelsemium** (software) — Gelsemium can use multiple domains and protocols in C2.
- **S0668 TinyTurla** (software) — TinyTurla can go through a list of C2 server IPs and will try to register with each until one responds.
- **S0674 CharmPower** (software) — CharmPower can change its C2 channel once every 360 loops by retrieving a new domain from the actors’ S3 bucket.
- **S0699 Mythic** (software) — Mythic can use a list of C2 URLs as fallback mechanisms in case one IP or domain gets blocked.
- **S1019 Shark** (software) — Shark can update its configuration to use a different C2 server.
- **S1020 Kevin** (software) — Kevin can assign hard-coded fallback domains for C2.
- **S1039 Bumblebee** (software) — Bumblebee can use backup C2 servers if the primary server fails.
- **S1084 QUIETEXIT** (software) — QUIETEXIT can attempt to connect to a second hard-coded C2 if the first hard-coded C2 address fails.
- **S1172 OilBooster** (software) — OilBooster can use a backup channel to request a new refresh token from its C2 server after 10 consecutive unsuccessful connections to the primary OneDrive C2 server.
- **S9010 GlassWorm** (software) — GlassWorm has utilized Google Calendar as backup C2.
- **S9023 HiddenFace** (software) — HiddenFace can use active and passive C2 modes that use different encryption algorithms and backdoor commands.
- **S9041 TeamPCP Cloud Stealer** (software) — TeamPCP Cloud Stealer can compress and encrypt data and exfiltrate it via POST to an attacker-controlled domain. If that method fails it can use the victim's own GitHub account to create a public repository and uploads the encrypted data as a release asset.
- **S9043 Mini Shai-Hulud** (software) — Mini Shai-Hulud has established Fallback Channels to exfiltrate data to Github when other configured infrastructure is found to be unreachable.
- **S9063 DEEPROOT** (software) — DEEPROOT has communicated with multiple C2 servers as a means of redundancy if one fails.

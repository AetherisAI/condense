# T1567 — Exfiltration Over Web Service

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Exfiltration
- **Platforms:** ESXi, Linux, macOS, Office Suite, SaaS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1567
- **Last modified:** 2026-05-12

## Description

Adversaries may use an existing, legitimate external Web service to exfiltrate data rather than their primary command and control channel. Popular Web services acting as an exfiltration mechanism may give a significant amount of cover due to the likelihood that hosts within a network are already communicating with them prior to compromise. Firewall rules may also already exist to permit traffic to these services.

Web service providers also commonly use SSL/TLS encryption, giving adversaries an added level of protection.

## Sub-techniques

- **T1567.001 Exfiltration Over Web Service: Exfiltration to Code Repository**
- **T1567.002 Exfiltration Over Web Service: Exfiltration to Cloud Storage**
- **T1567.003 Exfiltration Over Web Service: Exfiltration to Text Storage Sites**
- **T1567.004 Exfiltration Over Web Service: Exfiltration Over Webhook**

## Mitigations

- **M1021 Restrict Web-Based Content** — Web proxies can be used to enforce an external network communication policy that prevents use of unauthorized external services.
- **M1057 Data Loss Prevention** — Data loss prevention can be detect and block sensitive data being uploaded to web services via web browsers.

## Detection strategies

- **DET0548 Detection Strategy for Exfiltration Over Web Service**
  - AN1511 (Windows): Processes that normally do not initiate network communications suddenly making outbound HTTPS connections with high outbound-to-inbound data ratios. Defender view: correlation between process creation logs (e.g., Word, Excel, PowerShell) and subsequent anomalous network traffic volumes toward common web services (Dropbox, Google Drive, OneDrive). Log sources: WinEventLog:Security (EventCode=4688); WinEventLog:Sysmon (EventCode=3, 22); WinEventLog:Sysmon (EventCode=11).
  - AN1512 (Linux): Processes (tar, curl, python scripts) accessing large file sets and initiating outbound HTTPS POST requests with payload sizes inconsistent with baseline activity. Defender perspective: detect abnormal sequence of file archival followed by encrypted uploads to external web services. Log sources: auditd:EXECVE (curl or wget with POST/PUT options); auditd:SYSCALL (open/read of sensitive directories (/etc, /home/*)); NSM:Flow (sustained outbound HTTPS sessions with high data volume).
  - AN1513 (macOS): Office apps or scripts writing files followed by xattr manipulation (to evade quarantine) and subsequent HTTPS uploads. Defender perspective: anomalous file modification + outbound TLS traffic originating from non-networking apps (Word, Excel, Preview). Log sources: macos:unifiedlog (execution of Office binaries with network activity); macos:unifiedlog (read/write of user documents prior to upload); macos:unifiedlog (outbound TLS connections to cloud storage providers).
  - AN1514 (SaaS): Abnormal API calls from user accounts invoking file upload endpoints outside normal baselines (M365, Google Drive, Box). Defender perspective: monitor unified audit logs for elevated frequency of Upload, Create, or Copy operations from compromised accounts. Log sources: m365:unified (FileUploaded or FileCopied events); saas:box (API calls exceeding baseline thresholds).
  - AN1515 (ESXi): ESXi guest OS or management interface processes establishing unexpected external HTTPS connections. Defender perspective: monitor vmx or hostd processes making outbound web requests with significant data transfer. Log sources: esxi:vmkernel (network session initiation with external HTTPS services); esxi:hostd (file copy or datastore upload via HTTPS).

## Procedure examples

- **C0017 C0017** (campaign) — During C0017, APT41 used Cloudflare services for data exfiltration.
- **C0051 APT28 Nearest Neighbor Campaign** (campaign) — During APT28 Nearest Neighbor Campaign, APT28 exfiltrated data over public-facing webservers – such as Google Drive.
- **C0059 Salesforce Data Exfiltration** (campaign) — During Salesforce Data Exfiltration, threat actors exfiltrated data via legitimate Salesforce API communication channels including the Salesforce Data Loader application.
- **C0062 Anthropic AI-orchestrated Campaign** (campaign) — During the Anthropic AI-orchestrated Campaign, the adversary utilized Claude Code to generate a detailed summary report of collected data, which is then reviewed and approved by the adversary prior to exfiltration of data over Claude.
- **G0007 APT28** (group) — APT28 can exfiltrate data over Google Drive.
- **G0059 Magic Hound** (group) — Magic Hound has used the Telegram API `sendMessage` to relay data on compromised devices.
- **G0082 APT38** (group) — APT38 has exfiltrated stolen credentials to actor-controlled infrastructure leveraging Telegram Bot API.
- **G1043 BlackByte** (group) — BlackByte has used services such as `anonymfiles.com` and `file.io` to exfiltrate victim data.
- **G1052 Contagious Interview** (group) — Contagious Interview has leveraged Telegram API to exfiltrate stolen data.
- **G1057 ShinyHunters** (group) — ShinyHunters has used compromised Salesforce CRM (Customer Relationship Management) dashboards to exfiltrate bulk data. Additionally, ShinyHunters has used LimeWire, a file-sharing service, to showcase samples of stolen data.
- **S0508 ngrok** (software) — ngrok has been used by threat actors to configure servers for data exfiltration.
- **S0547 DropBook** (software) — DropBook has used legitimate web services to exfiltrate data.
- **S0622 AppleSeed** (software) — AppleSeed has exfiltrated files using web services.
- **S1168 SampleCheck5000** (software) — SampleCheck5000 can use the Microsoft Office Exchange Web Services API to access an actor-controlled account and retrieve files for exfiltration.
- **S1171 OilCheck** (software) — OilCheck can upload documents from compromised hosts to a shared Microsoft Office 365 Outlook email account for exfiltration.
- **S1179 Exbyte** (software) — Exbyte exfiltrates collected data to online file hosting sites such as `Mega.co.nz`.
- **S1245 InvisibleFerret** (software) — InvisibleFerret has leveraged Telegram chat to upload stolen data using the Telegram API with a bot token.
- **S9045 BACKUPOSINT v9.0 APEX PREDATOR** (software) — BACKUPOSINT v9.0 APEX PREDATOR has exfiltrated data using OpenAI’s GPT-4.1 API.

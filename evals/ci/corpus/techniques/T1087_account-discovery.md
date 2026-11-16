# T1087 — Account Discovery

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Discovery
- **Platforms:** ESXi, IaaS, Identity Provider, Linux, macOS, Office Suite, SaaS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1087
- **Last modified:** 2026-05-12

## Description

Adversaries may attempt to get a listing of valid accounts, usernames, or email addresses on a system or within a compromised environment. This information can help adversaries determine which accounts exist, which can aid in follow-on behavior such as brute-forcing, spear-phishing attacks, or account takeovers (e.g., Valid Accounts).

Adversaries may use several methods to enumerate accounts, including abuse of existing tools, built-in commands, and potential misconfigurations that leak account names and roles or permissions in the targeted environment.

For examples, cloud environments typically provide easily accessible interfaces to obtain user lists. On hosts, adversaries can use default PowerShell and other command line functionality to identify accounts. Information about email addresses and accounts may also be extracted by searching an infected system’s files.

## Sub-techniques

- **T1087.001 Account Discovery: Local Account**
- **T1087.002 Account Discovery: Domain Account**
- **T1087.003 Account Discovery: Email Account**
- **T1087.004 Account Discovery: Cloud Account**

## Mitigations

- **M1018 User Account Management** — Manage the creation, modification, use, and permissions associated to user accounts.
- **M1028 Operating System Configuration** — Prevent administrator accounts from being enumerated when an application is elevating through UAC since it can lead to the disclosure of account names. The Registry key is located `HKLM\ SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\CredUI\EnumerateAdministrators`. It can be disabled through GPO: Computer Configuration > [Policies] > Administrative Templates > Windows Components > Credential User Interface: E numerate administrator accounts on elevation.

## Detection strategies

- **DET0587 Enumeration of User or Account Information Across Platforms**
  - AN1612 (Windows): Detection of processes performing local or domain account enumeration by invoking account directory queries or security APIs followed by structured output of account lists. The defender observes command execution or API invocation patterns that retrieve account information and produce enumeration artifacts shortly afterward. Log sources: WinEventLog:Sysmon (EventCode=1); WinEventLog:Security (EventCode=4688); WinEventLog:Security (EventCode=4798, 4799).
  - AN1613 (Linux): Enumeration of users and groups through suspicious shell commands or unauthorized access to /etc/passwd or /etc/shadow. Log sources: auditd:SYSCALL (PATH); linux:Sysmon (EventCode=1).
  - AN1614 (macOS): Detection of account enumeration through directory service queries or system utilities accessing account metadata stores, followed by structured enumeration output. Log sources: macos:unifiedlog (process event); macos:unifiedlog (DirectoryService queries retrieving account information).
  - AN1615 (IaaS): Detection of enumeration of identity entities through cloud provider APIs where principals retrieve account metadata such as IAM users or roles in rapid succession. Log sources: AWS:CloudTrail (DescribeUsers / ListUsers / GetUser).
  - AN1616 (Identity Provider): Detection of identity directory enumeration through API calls or administrative queries retrieving multiple account objects within a short interval. Log sources: azure:signinlogs (Graph API Query); saas:okta (User Enumeration Events).
  - AN1617 (ESXi): Detection of enumeration activity when system processes query ESXi host account configuration or management APIs to retrieve user account listings. Log sources: esxi:vpxd (vCenter Management).
  - AN1618 (SaaS): Account enumeration via bulk access to user directory features or hidden APIs. Log sources: gcp:audit (Directory API Access).
  - AN1619 (Office Suite): Account discovery via VBA macros, COM objects, or embedded scripting. Log sources: m365:unified (Scripted Activity).

## Procedure examples

- **C0024 SolarWinds Compromise** (campaign) — During the SolarWinds Compromise, APT29 obtained a list of users and their roles from an Exchange server using `Get-ManagementRoleAssignment`.
- **C0062 Anthropic AI-orchestrated Campaign** (campaign) — During the Anthropic AI-orchestrated Campaign, the adversary used Claude Code to query internal database user account tables to enumerate accounts and identify high-privilege accounts within compromised environments.
- **C0064 AI-Assisted Breach of Mexico's Government Infrastructure** (campaign) — During the AI-Assisted Breach of Mexico's Government Infrastructure, the adversary tasked Claude Code to attempt to discover accounts by cycling through relative identifiers (RIDs).
- **G0143 Aquatic Panda** (group) — Aquatic Panda used the `last` command in Linux environments to identify recently logged-in users on victim machines.
- **G1015 Scattered Spider** (group) — Scattered Spider has identified vSphere administrator accounts.
- **G1016 FIN13** (group) — FIN13 has enumerated all users and their roles from a victim's main treasury system.
- **S0445 ShimRatReporter** (software) — ShimRatReporter listed all non-privileged and privileged accounts available on the machine.
- **S0658 XCSSET** (software) — XCSSET attempts to discover accounts from various locations such as a user's Evernote, AppleID, Telegram, Skype, and WeChat data.
- **S1065 Woody RAT** (software) — Woody RAT can identify administrator accounts on an infected machine.
- **S1229 Havoc** (software) — Havoc can identify privileged user accounts on infected systems.
- **S1239 TONESHELL** (software) — TONESHELL included functionality to retrieve a list of user accounts.

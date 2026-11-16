# T1114 — Email Collection

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Collection
- **Platforms:** Windows, macOS, Linux, Office Suite
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1114
- **Last modified:** 2025-10-24

## Description

Adversaries may target user email to collect sensitive information. Emails may contain sensitive data, including trade secrets or personal information, that can prove valuable to adversaries. Emails may also contain details of ongoing incident response operations, which may allow adversaries to adjust their techniques in order to maintain persistence or evade defenses. Adversaries can collect or forward email from mail servers or clients.

## Sub-techniques

- **T1114.001 Email Collection: Local Email Collection**
- **T1114.002 Email Collection: Remote Email Collection**
- **T1114.003 Email Collection: Email Forwarding Rule**

## Mitigations

- **M1032 Multi-factor Authentication** — Use of multi-factor authentication for public-facing webmail servers is a recommended best practice to minimize the usefulness of usernames and passwords to adversaries.
- **M1041 Encrypt Sensitive Information** — Use of encryption provides an added layer of security to sensitive information sent over email. Encryption using public key cryptography requires the adversary to obtain the private certificate along with an encryption key to decrypt messages.
- **M1047 Audit** — Enterprise email solutions have monitoring mechanisms that may include the ability to audit auto-forwarding rules on a regular basis. In an Exchange environment, Administrators can use Get-InboxRule to discover and remove potentially malicious auto-forwarding rules.
- **M1060 Out-of-Band Communications Channel** — Use secure out-of-band authentication methods to verify the authenticity of critical actions initiated via email, such as password resets, financial transactions, or access requests. For highly sensitive information, utilize out-of-band communication channels instead of relying solely on email to prevent adversaries from collecting data through compromised email accounts.

## Detection strategies

- **DET0476 Email Collection via Local Email Access and Auto-Forwarding Behavior**
  - AN1309 (Windows): Correlates creation of email forwarding rules or header anomalies (e.g., X-MS-Exchange-Organization-AutoForwarded) with suspicious process execution, file access of .pst/.ost files, and network connections to external SMTP servers. Log sources: WinEventLog:Security (EventCode=5145); WinEventLog:PowerShell (EventCode=4103, 4104, 4105, 4106); WinEventLog:Application (Exchange logs or header artifacts); WinEventLog:Sysmon (EventCode=3, 22).
  - AN1310 (Linux): Detects file access to mbox/maildir files in conjunction with curl/wget/postfix execution, or anomalous shell scripts harvesting user mail directories. Log sources: auditd:SYSCALL (open); linux:syslog (postfix/smtpd); linux:osquery (process_events).
  - AN1311 (macOS): Monitors Mail.app database or maildir file access, automation via AppleScript, and abnormal mail rule creation using scripting or UI automation frameworks. Log sources: macos:unifiedlog (Mail or AppleScript subsystem); macos:endpointsecurity (es_event_open, es_event_exec).
  - AN1312 (Office Suite): Correlates unusual auto-forwarding rule creation via Exchange Web Services or Outlook rules engine, presence of X-MS-Exchange-Organization-AutoForwarded headers, and logon session anomalies from abnormal IPs. Log sources: m365:unified (Set-Mailbox, New-InboxRule); m365:exchange (MessageTrace logs); azure:ad (SignInEvents).

## Procedure examples

- **G0059 Magic Hound** (group) — Magic Hound has compromised email credentials in order to steal sensitive data.
- **G0122 Silent Librarian** (group) — Silent Librarian has exfiltrated entire mailboxes from compromised accounts.
- **G1003 Ember Bear** (group) — Ember Bear attempts to collect mail from accessed systems and servers.
- **G1015 Scattered Spider** (group) — Scattered Spider searched the victim’s Microsoft Exchange for emails about the intrusion and incident response.
- **S0367 Emotet** (software) — Emotet has been observed leveraging a module that can scrape email addresses from Outlook.
- **S1201 TRANSLATEXT** (software) — TRANSLATEXT has exfiltrated collected email addresses to the C2 server.

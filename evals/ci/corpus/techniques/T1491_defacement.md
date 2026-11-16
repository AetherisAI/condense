# T1491 — Defacement

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Impact
- **Platforms:** Windows, IaaS, Linux, macOS, ESXi
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1491
- **Last modified:** 2026-09-02

## Description

Adversaries may modify visual content available internally or externally to an enterprise network, thus affecting the integrity of the original content. Reasons for Defacement include delivering messaging, intimidation, or claiming (possibly false) credit for an intrusion. Disturbing or offensive images may be used as a part of Defacement in order to cause user discomfort, or to pressure compliance with accompanying messages.

## Sub-techniques

- **T1491.001 Defacement: Internal Defacement**
- **T1491.002 Defacement: External Defacement**

## Mitigations

- **M1053 Data Backup** — Consider implementing IT disaster recovery plans that contain procedures for taking regular data backups that can be used to restore organizational data. Ensure backups are stored off system and is protected from common methods adversaries may use to gain access and destroy the backups to prevent recovery.

## Detection strategies

- **DET0238 Defacement via File and Web Content Modification Across Platforms**
  - AN0662 (Windows): Adversary modifies website or application-hosted content via unauthorized file changes or script injections, often by exploiting web servers or CMS access. Log sources: WinEventLog:Security (EventCode=4663, 4670, 4656); WinEventLog:Sysmon (EventCode=1); WinEventLog:Application (Unexpected web application errors or CMS logs showing modification to index.html, default.aspx, or other public-facing files).
  - AN0663 (Linux): Adversary gains shell access or uploads a malicious script to deface hosted web content in Nginx, Apache, or other services. Log sources: auditd:SYSCALL (write); apache:access_log (Unusual HTTP POST or PUT requests to paths such as '/uploads/', '/admin/', or CMS plugin folders); linux:syslog (Unauthorized sudo or shell access, especially leading to file changes in /var/www or /srv/http).
  - AN0664 (macOS): Adversary modifies internal or external site content through manipulated application bundles, hosted content, or web server configs. Log sources: macos:unifiedlog (Execution of unexpected terminal or web scripts modifying /Library/WebServer/Documents); macos:unifiedlog (File creation or overwrite in common web-hosting folders).
  - AN0665 (ESXi): Adversary defaces internal VM-hosted portals or web UIs by modifying static content on datastore-mounted paths. Log sources: esxi:vmkernel (Unauthorized file modifications within datastore volumes via shell access or vCLI).
  - AN0666 (IaaS): Adversary uses compromised instance credentials or web application access to deface content hosted in S3 buckets, Azure Blob Storage, or GCP Buckets. Log sources: CloudTrail:PutObject (PutObject); AWS:CloudTrail (GetObject, CopyObject).

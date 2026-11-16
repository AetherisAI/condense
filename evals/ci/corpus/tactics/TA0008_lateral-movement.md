# TA0008 — Lateral Movement

- **Type:** tactic
- **Domain:** Enterprise ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/tactics/TA0008
- **Last modified:** 2025-08-11

## Description

The adversary is trying to move through your environment.

Lateral Movement consists of techniques that adversaries use to enter and control remote systems on a network. Following through on their primary objective often requires exploring the network to find their target, then pivoting through multiple systems and accounts to gain access to it. Adversaries might install their own remote access tools to accomplish Lateral Movement or use legitimate credentials with native network and operating system tools, which may be stealthier.

## Techniques

- **T1021 Remote Services**
- **T1021.001 Remote Services: Remote Desktop Protocol**
- **T1021.002 Remote Services: SMB/Windows Admin Shares**
- **T1021.003 Remote Services: Distributed Component Object Model**
- **T1021.004 Remote Services: SSH**
- **T1021.005 Remote Services: VNC**
- **T1021.006 Remote Services: Windows Remote Management**
- **T1021.007 Remote Services: Cloud Services**
- **T1021.008 Remote Services: Direct Cloud VM Connections**
- **T1072 Software Deployment Tools**
- **T1080 Taint Shared Content**
- **T1091 Replication Through Removable Media**
- **T1210 Exploitation of Remote Services**
- **T1534 Internal Spearphishing**
- **T1550 Use Alternate Authentication Material**
- **T1550.001 Use Alternate Authentication Material: Application Access Token**
- **T1550.002 Use Alternate Authentication Material: Pass the Hash**
- **T1550.003 Use Alternate Authentication Material: Pass the Ticket**
- **T1550.004 Use Alternate Authentication Material: Web Session Cookie**
- **T1563 Remote Service Session Hijacking**
- **T1563.001 Remote Service Session Hijacking: SSH Hijacking**
- **T1563.002 Remote Service Session Hijacking: RDP Hijacking**
- **T1570 Lateral Tool Transfer**

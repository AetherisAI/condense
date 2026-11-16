# T1221 — Template Injection

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Stealth
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1221
- **Last modified:** 2026-11-03

## Description

Adversaries may create or modify references in user document templates to conceal malicious code or force authentication attempts. For example, Microsoft’s Office Open XML (OOXML) specification defines an XML-based format for Office documents (.docx, xlsx, .pptx) to replace older binary formats (.doc, .xls, .ppt). OOXML files are packed together ZIP archives compromised of various XML files, referred to as parts, containing properties that collectively define how a document is rendered.

Properties within parts may reference shared public resources accessed via online URLs. For example, template properties may reference a file, serving as a pre-formatted document blueprint, that is fetched when the document is loaded.

Adversaries may abuse these templates to initially conceal malicious code to be executed via user documents. Template references injected into a document may enable malicious payloads to be fetched and executed when the document is loaded. These documents can be delivered via other techniques such as Phishing and/or Taint Shared Content and may evade static detections since no typical indicators (VBA macro, script, etc.) are present until after the malicious payload is fetched. Examples have been seen in the wild where template injection was used to load malicious code containing an exploit.

Adversaries may also modify the `*\template` control word within an .rtf file to similarly conceal then download malicious code. This legitimate control word value is intended to be a file destination of a template file resource that is retrieved and loaded when an .rtf file is opened. However, adversaries may alter the bytes of an existing .rtf file to insert a template control word field to include a URL resource of a malicious payload.

This technique may also enable Forced Authentication by injecting an SMB/HTTPS (or other credential prompting) URL and triggering an authentication attempt.

## Mitigations

- **M1017 User Training** — Train users to identify social engineering techniques and spearphishing emails that could be used to deliver malicious documents.
- **M1031 Network Intrusion Prevention** — Network/Host intrusion prevention systems, antivirus, and detonation chambers can be employed to prevent documents from fetching and/or executing malicious payloads.
- **M1042 Disable or Remove Feature or Program** — Consider disabling Microsoft Office macros/active content to prevent the execution of malicious payloads in documents, though this setting may not mitigate the Forced Authentication use for this technique.
- **M1049 Antivirus/Antimalware** — Network/Host intrusion prevention systems, antivirus, and detonation chambers can be employed to prevent documents from fetching and/or executing malicious payloads.

## Detection strategies

- **DET0566 Template Injection Detection - Windows**
  - AN1564 (Windows): Detection of Office or document viewer processes (e.g., winword.exe) initiating network connections to remote templates or executing scripts due to manipulated template references (e.g., embedded in .docx, .rtf, or .dotm files), followed by suspicious child process creation (e.g., PowerShell). Log sources: WinEventLog:Sysmon (EventCode=1); WinEventLog:Sysmon (EventCode=3, 22).

## Procedure examples

- **C0001 Frankenstein** (campaign) — During Frankenstein, the threat actors used trojanized documents that retrieved remote templates from an adversary-controlled website.
- **C0022 Operation Dream Job** (campaign) — During Operation Dream Job, Lazarus Group used DOCX files to retrieve a malicious document template/DOTM file.
- **G0007 APT28** (group) — APT28 used weaponized Microsoft Word documents abusing the remote template function to retrieve a malicious macro.
- **G0035 Dragonfly** (group) — Dragonfly has injected SMB URLs into malicious Word spearphishing attachments to initiate Forced Authentication.
- **G0047 Gamaredon Group** (group) — Gamaredon Group has used DOCX files to download malicious DOT document templates and has used RTF template injection to download malicious payloads. Gamaredon Group can also inject malicious macros or remote templates into documents already present on compromised systems.
- **G0079 DarkHydrus** (group) — DarkHydrus used an open-source tool, Phishery, to inject malicious remote template URLs into Microsoft Word documents and then sent them to victims to enable Forced Authentication.
- **G0081 Tropic Trooper** (group) — Tropic Trooper delivered malicious documents with the XLSX extension, typically used by OpenXML documents, but the file itself was actually an OLE (XLS) document.
- **G0100 Inception** (group) — Inception has used decoy documents to load malicious remote payloads via HTTP.
- **G0142 Confucius** (group) — Confucius has used a weaponized Microsoft Word document with an embedded RTF exploit.
- **G1054 MirrorFace** (group) — MirrorFace has used remote template injection to retrieve malicious payloads from the C2.
- **S0631 Chaes** (software) — Chaes changed the template target of the settings.xml file embedded in the Word document and populated that field with the downloaded URL of the next payload.
- **S0670 WarzoneRAT** (software) — WarzoneRAT has been install via template injection through a malicious DLL embedded within a template RTF in a Word document.

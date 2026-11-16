# C0054 — Operation Triangulation

- **Type:** campaign
- **Domain:** Mobile ATT&CK
- **First seen:** 2019-01-01
- **Last seen:** 2023-06-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0054
- **Last modified:** 2026-07-31

## Description

Operation Triangulation is a mobile campaign targeting iOS devices. The unidentified actors used zero-click exploits in iMessage attachments to gain Initial Access, then executed exploits and validators, such as Binary Validator before finally executing the TriangleDB implant.

## Techniques used

- **T1404 Exploitation for Privilege Escalation** — During Operation Triangulation, the threat actors exploited a kernel vulnerability to obtain root privileges.
- **T1409 Stored Application Data** — During Operation Triangulation, the threat actors have collected and exfiltrated data from WhatsApp and Telegram.
- **T1418 Software Discovery** — During Operation Triangulation, the threat actors have obtained a list of installed applications.
- **T1420 File and Directory Discovery** — During Operation Triangulation, the threat actors have obtained a list of files in a specified directory using the `fts` API.
- **T1422 System Network Configuration Discovery** — During Operation Triangulation, the threat actors use the heartbeat beacons from the implant to obtain device information, such as the IMEI, MEID, and the serial number.
- **T1424 Process Discovery** — During Operation Triangulation, the threat actors have obtained a list of processes.
- **T1426 System Information Discovery** — During Operation Triangulation, the threat actors collected device and user information.
- **T1429 Audio Capture** — During Operation Triangulation, the threat actors used a microphone-recording module.
- **T1430 Location Tracking** — During Operation Triangulation, the threat actors monitored the device’s geolocation.
- **T1437 Application Layer Protocol** — During Operation Triangulation, the threat actors used HTTPS POST requests for C2 communication.
- **T1521.001 Encrypted Channel: Symmetric Cryptography** — During Operation Triangulation, the threat actors used 3DES and AES to encrypt C2 communication and data.
- **T1521.002 Encrypted Channel: Asymmetric Cryptography** — During Operation Triangulation, the threat actors used RSA to encrypt C2 communication.
- **T1533 Data from Local System** — During Operation Triangulation, the threat actors stole data from SQLite databases.
- **T1544 Ingress Tool Transfer** — During Operation Triangulation, the threat actors downloaded subsequent stages from the C2.
- **T1575 Native API** — During Operation Triangulation, the threat actors use the Audio Queue API to record audio.
- **T1630 Indicator Removal on Host** — During Operation Triangulation, the threat actors deleted the initial exploitation message and exploit attachment.
- **T1630.002 Indicator Removal on Host: File Deletion** — During Operation Triangulation, the threat actors removed files from the device.
- **T1634.001 Credentials from Password Store: Keychain** — During Operation Triangulation, the threat actors have dumped the device’s keychain.
- **T1636.004 Protected User Data: SMS Messages** — During Operation Triangulation, the threat actors have collected and exfiltrated SMS messages.
- **T1658 Exploitation for Client Execution** — During Operation Triangulation, the threat actors sent iMessage messages with malicious exploits that executed without user interaction. Additionally, the threat actors have used various exploits, such as CVE-2023-41990, CVE-2023-32435, CVE-2023-32434 and CVE-2023-38606, to obtain privilege escalation.

## Software used

- **S1215 Binary Validator**
- **S1216 TriangleDB**

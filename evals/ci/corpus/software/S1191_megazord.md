# S1191 — Megazord

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S1191
- **Last modified:** 2025-03-11

## Description

Megazord is a Rust-based variant of Akira ransomware that has been in use since at least August 2023 to target Windows environments. Megazord has been attributed to the Akira group based on overlapping infrastructure though is possibly not exclusive to the group.

## Techniques used

- **T1057 Process Discovery** — Megazord can terminate a list of specified services and processes.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — Megazord can execute multiple commands post infection via `cmd.exe`.
- **T1083 File and Directory Discovery** — Megazord can ignore specified directories for encryption.
- **T1486 Data Encrypted for Impact** — Megazord can encrypt files on targeted Windows hosts leaving them with a ".powerranges" file extension.
- **T1489 Service Stop** — Megazord has the ability to terminate a list of services and processes.
- **T1654 Log Enumeration** — Megazord has the ability to print the trace, debug, error, info, and warning logs.

## Used by

- **G1024 Akira** (group)

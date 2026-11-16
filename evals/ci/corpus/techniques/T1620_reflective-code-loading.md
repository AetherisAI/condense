# T1620 — Reflective Code Loading

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Stealth
- **Platforms:** Linux, macOS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1620
- **Last modified:** 2026-05-12

## Description

Adversaries may reflectively load code into a process in order to conceal the execution of malicious payloads. Reflective loading involves allocating then executing payloads directly within the memory of the process, vice creating a thread or process backed by a file path on disk (e.g., Shared Modules).

Reflectively loaded payloads may be compiled binaries, anonymous files (only present in RAM), or just snubs of fileless executable code (ex: position-independent shellcode). For example, the `Assembly.Load()` method executed by PowerShell may be abused to load raw code into the running process.

Reflective code injection is very similar to Process Injection except that the “injection” loads code into the processes’ own memory instead of that of a separate process. Reflective loading may evade process-based detections since the execution of the arbitrary code may be masked within a legitimate or otherwise benign process. Reflectively loading payloads directly into memory may also avoid creating files or other artifacts on disk, while also enabling malware to keep these payloads encrypted (or otherwise obfuscated) until execution.

## Detection strategies

- **DET0300 Detection Strategy for Reflective Code Loading**
  - AN0838 (Windows): Detect anomalous chains of memory allocation and execution inside the same process (e.g., VirtualAlloc → memcpy → VirtualProtect → CreateThread). Unlike process injection, reflective code loading does not perform cross-process memory writes — the suspicious activity occurs entirely within the process’s own PID context. Log sources: WinEventLog:Sysmon (EventCode=1); WinEventLog:Sysmon (EventCode=7); etw:Microsoft-Windows-DotNETRuntime (AssemblyLoad/ModuleLoad (Loader keyword) from Microsoft-Windows-DotNETRuntime); etw:Microsoft-Antimalware-Scan-Interface (Amsi/Script content + API verdicts during in-memory staging); WinEventLog:Sysmon (EventCode=10).
  - AN0839 (Linux): Monitor for in-process mmap + mprotect + execve/execveat activity where memory permissions are changed from writable to executable inside the same process without a corresponding ELF on disk. Log sources: auditd:SYSCALL (execve); auditd:MMAP (memory region with RWX permissions allocated).
  - AN0840 (macOS): Suspicious calls to dlopen(), dlsym(), or mmap with RWX flags in processes that do not typically perform dynamic module loading. Monitor anonymous memory regions executed by user processes. Log sources: macos:unifiedlog (execve or dylib load from memory without backing file); macos:unifiedlog (suspicious dlopen/dlsym usage in non-development processes).

## Procedure examples

- **C0057 3CX Supply Chain Attack** (campaign) — During the 3CX Supply Chain Attack, AppleJeus leverages the publicly available open-source project DAVESHELL to convert PE-COFF files to position-independent code to reflectively load the payload into memory.
- **C0058 SharePoint ToolShell Exploitation** (campaign) — During SharePoint ToolShell Exploitation, threat actors reflectively loaded payloads using `System.Reflection.Assembly.Load`.
- **G0032 Lazarus Group** (group) — Lazarus Group has changed memory protection permissions then overwritten in memory DLL function code with shellcode, which was later executed via KernelCallbackTable hijacking. Lazarus Group has also used shellcode within macros to decrypt and manually map DLLs into memory at runtime.
- **G0046 FIN7** (group) — FIN7 has loaded a .NET assembly into the currect execution context via `Reflection.Assembly::Load`.
- **G0047 Gamaredon Group** (group) — Gamaredon Group has used an obfuscated PowerShell script that used `System.Reflection.Assembly` to gather and send victim information to the C2.
- **G0082 APT38** (group) — APT38 has configured malicious payloads to reflectively load using the macOS `NSCreateObjectFileImageFromMemory` API. APT38 has also reflectively loaded .NET DLLs to bypass disk-based detection.
- **G0094 Kimsuky** (group) — Kimsuky has used the Invoke-Mimikatz PowerShell script to reflectively load a Mimikatz credential stealing DLL into memory. Kimsuky has also used reflective loading through .NET assembly using `[System.Reflection.Assembly]::Load`.
- **S0013 PlugX** (software) — PlugX has loaded its payload into memory.
- **S0022 Uroburos** (software) — Uroburos has the ability to load new modules directly into memory using its `Load Modules Mem` command.
- **S0154 Cobalt Strike** (software) — Cobalt Strike's `execute-assembly` command can run a .NET executable within the memory of a sacrificial process by loading the CLR.
- **S0194 PowerSploit** (software) — PowerSploit reflectively loads a Windows PE file into a process.
- **S0367 Emotet** (software) — Emotet has reflectively loaded payloads into memory.
- **S0447 Lokibot** (software) — Lokibot has reflectively loaded the decoded DLL into memory.
- **S0595 ThiefQuest** (software) — ThiefQuest uses various API functions such as `NSCreateObjectFileImageFromMemory` to load and link in-memory payloads.
- **S0625 Cuba** (software) — Cuba loaded the payload into memory using PowerShell.
- **S0661 FoggyWeb** (software) — FoggyWeb's loader has reflectively loaded .NET-based assembly/payloads into memory.
- **S0666 Gelsemium** (software) — Gelsemium can use custom shellcode to map embedded DLLs into memory.
- **S0681 Lizar** (software) — Lizar has used the Reflective DLL injection module from Github to inject itself into a process’s memory.
- **S0689 WhisperGate** (software) — WhisperGate's downloader can reverse its third stage file bytes and reflectively load the file as a .NET assembly.
- **S0692 SILENTTRINITY** (software) — SILENTTRINITY can run a .NET executable within the memory of a sacrificial process by loading the CLR.
- **S0695 Donut** (software) — Donut can generate code modules that enable in-memory execution of VBScript, JScript, EXE, DLL, and dotNET payloads.
- **S1022 IceApple** (software) — IceApple can use reflective code loading to load .NET assemblies into `MSExchangeOWAAppPool` on targeted Exchange servers.
- **S1059 metaMain** (software) — metaMain has reflectively loaded a DLL to read, decrypt, and load an orchestrator file.
- **S1063 Brute Ratel C4** (software) — Brute Ratel C4 has used reflective loading to execute malicious DLLs.
- **S1081 BADHATCH** (software) — BADHATCH can copy a large byte array of 64-bit shellcode into process memory and execute it with a call to `CreateThread`.
- **S1085 Sardonic** (software) — Sardonic has a plugin system that can load specially made DLLs into memory and execute their functions.
- **S1143 LunarLoader** (software) — LunarLoader can use reflective loading to decrypt and run malicious executables in a new thread.
- **S1145 Pikabot** (software) — Pikabot reflectively loads stored, previously encrypted components of the PE file into memory of the currently executing process to avoid writing content to disk on the executing machine.
- **S1213 Lumma Stealer** (software) — Lumma Stealer has used reflective loading techniques to load content into memory during execution.
- **S9001 SystemBC** (software) — SystemBC has downloaded a text file into memory and set the area of memory via the VirtualProtect call. Then, SystemBC has executed the file via the CreateThread call.
- **S9011 BRUSHFIRE** (software) — BRUSHFIRE has executed its commands within memory and is not saved on disk.
- **S9032 MuddyViper** (software) — MuddyViper has reflectively loaded the decrypted HackBrowserData tool in a new thread.
- **S9033 Fooder** (software) — Fooder has reflectively loaded a payload into memory.

# S0603 — Stuxnet

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **Also known as:** W32.Stuxnet
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0603
- **Last modified:** 2026-04-24

## Description

Stuxnet was the first publicly reported malware to specifically target industrial control systems devices. Stuxnet is a large and complex malware that utilized multiple behaviors, including numerous zero-day vulnerabilities, a sophisticated Windows rootkit, and network infection routines. Stuxnet was discovered in 2010, with some components being used as early as November 2008.

## Techniques used

- **T0801 Monitor Process State** — Stuxnet examines fields recorded by the DP_RECV monitor to determine if the target system is in a particular state of operation.
- **T0821 Modify Controller Tasking** — Stuxnet infects OB1 so that its malicious code sequence is executed at the start of a cycle. It also infects OB35. OB35 acts as a watchdog, and on certain conditions, it can stop the execution of OB1.
- **T0831 Manipulation of Control** — Stuxnet can reprogram a PLC and change critical parameters in such a way that legitimate commands can be overridden or intercepted. In addition, Stuxnet can apply inappropriate command sequences or parameters to cause damage to property.
- **T0832 Manipulation of View** — Stuxnet manipulates the view of operators replaying process input and manipulating the I/O image to evade detection and inhibit protection functions.
- **T0834 Native API** — Stuxnet calls system function blocks which are part of the operating system running on the PLC. Theyre used to execute system tasks, such as reading the system clock (SFC1) and generating data blocks on the fly.
- **T0835 Manipulate I/O Image** — When the peripheral output is written to, sequence C intercepts the output and ensures it is not written to the process image output. The output is the instructions the PLC sends to a device to change its operating behavior. By intercepting the peripheral output, Stuxnet prevents an operator from noticing unauthorized commands sent to the peripheral.
- **T0836 Modify Parameter** — In states 3 and 4 Stuxnet sends two network bursts (done through the DP_SEND primitive). The data in the frames are instructions for the frequency converter drives. For example one of the frames contains records that change the maximum frequency (the speed at which the motor will operate). The frequency converter drives consist of parameters, which can be remotely configured via Profibus. One can write new values to these parameters changing the behavior of the device.
- **T0842 Network Sniffing** — DP_RECV is the name of a standard function block used by network coprocessors. It is used to receive network frames on the Profibus a standard industrial network bus used for distributed I/O. The original block is copied to FC1869, and then replaced by a malicious block. Each time the function is used to receive a packet, the malicious Stuxnet block takes control: it will call the original DP_RECV in FC1869 and then perform postprocessing on the packet data. The replaced DP_RECV block (later on referred to as the DP_RECV monitor) is meant to monitor data sent by the frequency converter drives to the 315-2 CPU via CP 342-5 Profibus communication modules.
- **T0843 Program Download** — Stuxnet's infection sequence consists of code blocks and data blocks that will be downloaded to the PLC to alter its behavior.
- **T0847 Replication Through Removable Media** — Stuxnet was able to self-replicate by being spread through removable drives. A willing insider or unknown third party, such as a contractor, may have brought the removable media into the target environment. The earliest version of Stuxnet relied on physical installation, infecting target systems when an infected configuration file carried by a USB stick was opened.
- **T0849 Masquerading** — Stuxnet renames s7otbxdx.dll, a dll responsible for handling communications with a PLC. It replaces this dll file with its own version that allows it to intercept any calls that are made to access the PLC.
- **T0851 Rootkit** — One of Stuxnet's rootkits is contained entirely in the fake s7otbxdx.dll. In order to continue existing undetected on the PLC it needs to account for at least the following situations: read requests for its own malicious code blocks, read requests for infected blocks (OB1, OB35, DP_RECV), and write requests that could overwrite Stuxnets own code. Stuxnet contains code to monitor and intercept these types of requests. The rootkit modifies these requests so that Stuxnets PLC code is not discovered or damaged.
- **T0863 User Execution** — Stuxnet infects DLL's associated with the WinCC Simatic manager which are responsible for opening project files. If a user opens an uninfected project file using a compromised manager, the file will be infected with Stuxnet code. If an infected project is opened with the Simatic manager, the modified data file will trigger a search for the `xyz.dll` file. If the `xyz.dll` file is not found in any of the specified locations, the malicious DLL will be loaded and executed by the manager.
- **T0866 Exploitation of Remote Services** — Stuxnet executes malicious SQL commands in the WinCC database server to propagate to remote systems. The malicious SQL commands include xp_cmdshell, sp_dumpdbilog, and sp_addextendedproc.
- **T0867 Lateral Tool Transfer** — Stuxnet sends an SQL statement that creates a table and inserts a binary value into the table. The binary value is a hex string representation of the main Stuxnet DLL as an executable file (formed using resource 210) and an updated configuration data block.
- **T0869 Standard Application Layer Protocol** — Stuxnet uses a thread to monitor a data block DB890 of sequence A or B. This thread is constantly running and probing this block (every 5 minutes). On an infected PLC, if block DB890 is found and contains a special magic value (used by Stuxnet to identify his own block DB890), this blocks data can be read and written. This thread is likely used to optimize the way sequences A and B work, and modify their behavior when the Step7 editor is opened.
- **T0873.001 Project File Infection: Siemens Project File Format** — Stuxnet copies itself into Step 7 projects in such a way that it automatically executes when the Step 7 project is loaded.
- **T0874 Hooking** — Stuxnet modifies the Import Address Tables DLLs to hook specific APIs that are used to open project files.
- **T0877 I/O Image** — Stuxnet copies the input area of an I/O image into data blocks with a one second interval between copies, forming a 21 second recording of the input area. The input area contains information being passed to the PLC from a peripheral. For example, the current state of a valve or the temperature of a device.
- **T0885 Commonly Used Port** — Stuxnet attempts to contact command and control servers on port 80 to send basic information about the computer it has compromised.
- **T0886 Remote Services** — Stuxnet executes malicious SQL commands in the WinCC database server to propagate to remote systems. The malicious SQL commands include xp_cmdshell, sp_dumpdbilog, and sp_addextendedproc.
- **T0888 Remote System Information Discovery** — Stuxnet enumerates and parses the System Data Blocks (SDB) using the s7blk_findfirst and s7blk_findnext API calls in s7otbxdx.dll. Stuxnet must find an SDB with the DWORD at offset 50h equal to 0100CB2Ch. This specifies that the system uses the Profibus communications processor module CP 342-5. In addition, specific values are searched for and counted: 7050h and 9500h. 7050h is assigned to part number KFC750V3 which appears to be a frequency converter drive (also known as variable frequency drive) manufactured by Fararo Paya in Teheran, Iran. 9500h is assigned to Vacon NX frequency converter drives manufactured by Vacon based in Finland. Stuxnet was specifically targeting CPUs 6ES7-315-2 (Series 300) with special system data block characteristics for sequence A or B and 6ES7-315-2 for sequence C. The PLC type can also be checked using the s7ag_read_szl API.
- **T0889 Modify Program** — Stuxnet infects PLCs with different code depending on the characteristics of the target system. An infection sequence consists of code blocks and data blocks that will be downloaded to the PLC to alter its behavior.
- **T1008 Fallback Channels** — Stuxnet has the ability to generate new C2 domains.
- **T1012 Query Registry** — Stuxnet searches the Registry for indicators of security programs.
- **T1014 Rootkit** — Stuxnet uses a Windows rootkit to mask its binaries and other relevant files.
- **T1016 System Network Configuration Discovery** — Stuxnet collects the IP address of a compromised system.
- **T1021 Remote Services** — Stuxnet can propagate via peer-to-peer communication and updates using RPC.
- **T1021.002 Remote Services: SMB/Windows Admin Shares** — Stuxnet propagates to available network shares.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — Stuxnet uses encrypted configuration blocks and writes encrypted files to disk.
- **T1041 Exfiltration Over C2 Channel** — Stuxnet sends compromised victim information via HTTP.
- **T1047 Windows Management Instrumentation** — Stuxnet used WMI with an `explorer.exe` token to execute on a remote share.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — Stuxnet schedules a network job to execute two minutes after host infection.
- **T1055.001 Process Injection: Dynamic-link Library Injection** — Stuxnet injects an entire DLL into an existing, newly created, or preselected trusted process.
- **T1068 Exploitation for Privilege Escalation** — Stuxnet used MS10-073 and an undisclosed Task Scheduler vulnerability to escalate privileges on local Windows machines.
- **T1070 Indicator Removal** — Stuxnet can delete OLE Automation and SQL stored procedures used to store malicious payloads.
- **T1070.004 Indicator Removal: File Deletion** — Stuxnet uses an RPC server that contains a routine for file deletion and also removes itself from the system through a DLL export by deleting specific files.
- **T1070.006 Indicator Removal: Timestomp** — Stuxnet extracts and writes driver files that match the times of other legitimate files.
- **T1071.001 Application Layer Protocol: Web Protocols** — Stuxnet uses HTTP to communicate with a command and control server.
- **T1078.001 Valid Accounts: Default Accounts** — Stuxnet infected WinCC machines via a hardcoded database server password.
- **T1078.002 Valid Accounts: Domain Accounts** — Stuxnet attempts to access network resources with a domain account’s credentials.
- **T1080 Taint Shared Content** — Stuxnet infects remote servers via network shares and by infecting WinCC database views with malicious code.
- **T1082 System Information Discovery** — Stuxnet collects system information including computer and domain names, OS version, and S7P paths.
- **T1083 File and Directory Discovery** — Stuxnet uses a driver to scan for specific filesystem driver objects.
- **T1087.001 Account Discovery: Local Account** — Stuxnet enumerates user accounts of the local host.
- **T1087.002 Account Discovery: Domain Account** — Stuxnet enumerates user accounts of the domain.
- **T1090.001 Proxy: Internal Proxy** — Stuxnet installs an RPC server for P2P communications.
- **T1091 Replication Through Removable Media** — Stuxnet can propagate via removable media using an autorun.inf file or the CVE-2010-2568 LNK vulnerability.
- **T1106 Native API** — Stuxnet uses the SetSecurityDescriptorDacl API to reduce object integrity levels.
- **T1112 Modify Registry** — Stuxnet can create registry keys to load driver files.
- **T1120 Peripheral Device Discovery** — Stuxnet enumerates removable drives for infection.
- **T1124 System Time Discovery** — Stuxnet collects the time and date of a system when it is infected.
- **T1129 Shared Modules** — Stuxnet calls LoadLibrary then executes exports from a DLL.
- **T1132.001 Data Encoding: Standard Encoding** — Stuxnet transforms encrypted binary data into an ASCII string in order to use it as a URL parameter value.
- **T1134.001 Access Token Manipulation: Token Impersonation/Theft** — Stuxnet attempts to impersonate an anonymous token to enumerate bindings in the service control manager.
- **T1135 Network Share Discovery** — Stuxnet enumerates the directories of a network resource.
- **T1140 Deobfuscate/Decode Files or Information** — Stuxnet decrypts resources that are loaded into memory and executed.
- **T1210 Exploitation of Remote Services** — Stuxnet propagates using the MS10-061 Print Spooler and MS08-067 Windows Server Service vulnerabilities.
- **T1480 Execution Guardrails** — Stuxnet checks for specific operating systems on 32-bit machines, Registry keys, and dates for vulnerabilities, and will exit execution if the values are not met.
- **T1505.001 Server Software Component: SQL Stored Procedures** — Stuxnet used xp_cmdshell to store and execute SQL code.
- **T1518.001 Software Discovery: Security Software Discovery** — Stuxnet enumerates the currently running processes related to a variety of security products.
- **T1543.003 Create or Modify System Process: Windows Service** — Stuxnet uses a driver registered as a boot start service as the main load-point.
- **T1553.002 Subvert Trust Controls: Code Signing** — Stuxnet used a digitally signed driver with a compromised Realtek certificate.
- **T1560.003 Archive Collected Data: Archive via Custom Method** — Stuxnet encrypts exfiltrated data via C2 with static 31-byte long XOR keys.
- **T1570 Lateral Tool Transfer** — Stuxnet uses an RPC server that contains a file dropping routine and support for payload version updates for P2P communications within a victim network.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — Stuxnet encodes the payload of system information sent to the command and control servers using a one byte 0xFF XOR key. Stuxnet also uses a 31-byte long static byte string to XOR data sent to command and control servers. The servers use a different static key to encrypt replies to the implant.
- **T1685 Disable or Modify Tools** — Stuxnet reduces the integrity level of objects to allow write actions.
- **T1694.002 Insecure Credentials: Hardcoded Credentials** — Stuxnet uses a hardcoded password in the WinCC software's database server as one of the mechanisms used to propagate to nearby systems.
- **T1701.002 Command and Scripting Interpreter: Windows Command Shell** — Stuxnet will store and execute SQL code that will extract and execute Stuxnet from the saved CAB file using xp_cmdshell with the following command: `set @s = master..xp _ cmdshell extrac32 /y +@t+ +@t+x; exec(@s);`

# T1611 — Escape to Host

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Privilege Escalation
- **Platforms:** Windows, Linux, Containers, ESXi
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1611
- **Last modified:** 2025-10-24

## Description

Adversaries may break out of a container or virtualized environment to gain access to the underlying host. This can allow an adversary access to other containerized or virtualized resources from the host level or to the host itself. In principle, containerized / virtualized resources should provide a clear separation of application functionality and be isolated from the host environment.

There are multiple ways an adversary may escape from a container to a host environment. Examples include creating a container configured to mount the host’s filesystem using the bind parameter, which allows the adversary to drop payloads and execute control utilities such as cron on the host; utilizing a privileged container to run commands or load a malicious kernel module on the underlying host; or abusing system calls such as `unshare` and `keyctl` to escalate privileges and steal secrets.

Additionally, an adversary may be able to exploit a compromised container with a mounted container management socket, such as `docker.sock`, to break out of the container via a Container Administration Command. Adversaries may also escape via Exploitation for Privilege Escalation, such as exploiting vulnerabilities in global symbolic links in order to access the root directory of a host machine.

In ESXi environments, an adversary may exploit a vulnerability in order to escape from a virtual machine into the hypervisor.

Gaining access to the host may provide the adversary with the opportunity to achieve follow-on objectives, such as establishing persistence, moving laterally within the environment, accessing other containers or virtual machines running on the host, or setting up a command and control channel on the host.

## Mitigations

- **M1026 Privileged Account Management** — Ensure containers are not running as root by default and do not use unnecessary privileges or mounted components. In Kubernetes environments, consider defining Pod Security Standards that prevent pods from running privileged containers.
- **M1038 Execution Prevention** — Use read-only containers, read-only file systems, and minimal images when possible to prevent the running of commands. Where possible, also consider using application control and software restriction tools (such as those provided by SELinux) to restrict access to files, processes, and system calls in containers.
- **M1042 Disable or Remove Feature or Program** — Remove unnecessary tools and software from containers.
- **M1048 Application Isolation and Sandboxing** — Consider utilizing seccomp, seccomp-bpf, or a similar solution that restricts certain system calls such as mount. In Kubernetes environments, consider defining Pod Security Standards that limit container access to host process namespaces, the host network, and the host file system.
- **M1051 Update Software** — Ensure that hosts are kept up-to-date with security patches.

## Detection strategies

- **DET0219 Detection Strategy for Escape to Host**
  - AN0612 (Containers): Detection of container escape attempts via bind mounts, privileged containers, or abuse of docker.sock. Defenders may observe anomalous volume mount configurations (e.g., hostPath to / or /proc), unexpected privileged container launches, or use of container administration commands to access host resources. These events typically correlate with subsequent process execution on the host outside of normal container isolation. Log sources: docker:daemon (container create/start with privileged flag or host volume mount); kubernetes:apiserver (Pod spec with hostPath or privileged securityContext).
  - AN0613 (Linux): Detection of Linux container escape attempts via syscalls (`unshare`, `keyctl`, `mount`) or process execution outside container namespaces. Defenders may correlate unusual system calls from containerized processes with subsequent process creation on the host or modification of host resources. Log sources: auditd:SYSCALL (unshare, mount, keyctl, setns syscalls executed by containerized processes); linux:Sysmon (process creation events linked to container namespaces executing host-level binaries).
  - AN0614 (Windows): Detection of Windows container escape attempts by observing processes accessing host directories, symbolic link abuse, or privilege escalation attempts. Defenders may detect anomalous process execution with access to system-level directories outside of container boundaries. Log sources: WinEventLog:Security (EventCode=4688); WinEventLog:Sysmon (EventCode=11).
  - AN0615 (ESXi): Detection of ESXi escape attempts by monitoring for anomalies in hypervisor logs such as unexpected VM operations, privilege escalation events, or attempts to load malicious kernel modules within the hypervisor environment. Log sources: esxi:vmkernel (VM exit/entry anomalies, unexpected hypercalls, or kernel module loading).

## Procedure examples

- **G0139 TeamTNT** (group) — TeamTNT has deployed privileged containers that mount the filesystem of victim machine.
- **S0600 Doki** (software) — Doki’s container was configured to bind the host root directory.
- **S0601 Hildegard** (software) — Hildegard has used the BOtB tool that can break out of containers.
- **S0623 Siloscape** (software) — Siloscape maps the host’s C drive to the container by creating a global symbolic link to the host through the calling of `NtSetInformationSymbolicLink`.
- **S0683 Peirates** (software) — Peirates can gain a reverse shell on a host node by mounting the Kubernetes hostPath.

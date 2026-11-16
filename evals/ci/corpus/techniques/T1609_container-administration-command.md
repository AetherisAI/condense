# T1609 — Container Administration Command

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Execution
- **Platforms:** Containers
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1609
- **Last modified:** 2025-10-24

## Description

Adversaries may abuse a container administration service to execute commands within a container. A container administration service such as the Docker daemon, the Kubernetes API server, or the kubelet may allow remote management of containers within an environment.

In Docker, adversaries may specify an entrypoint during container deployment that executes a script or command, or they may use a command such as `docker exec` to execute a command within a running container. In Kubernetes, if an adversary has sufficient permissions, they may gain remote execution in a container in the cluster via interaction with the Kubernetes API server, the kubelet, or by running a command such as `kubectl exec`.

## Mitigations

- **M1018 User Account Management** — Enforce authentication and role-based access control on the container service to restrict users to the least privileges required. When using Kubernetes, avoid giving users wildcard permissions or adding users to the `system:masters` group, and use `RoleBindings` rather than `ClusterRoleBindings` to limit user privileges to specific namespaces.
- **M1026 Privileged Account Management** — Ensure containers are not running as root by default. In Kubernetes environments, consider defining Pod Security Standards that prevent pods from running privileged containers and using the `NodeRestriction` admission controller to deny the kublet access to nodes and pods outside of the node it belongs to.
- **M1035 Limit Access to Resource Over Network** — Limit communications with the container service to managed and secured channels, such as local Unix sockets or remote access via SSH. Require secure port access to communicate with the APIs over TLS by disabling unauthenticated access to the Docker API and Kubernetes API Server. In Kubernetes clusters deployed in cloud environments, use native cloud platform features to restrict the IP ranges that are permitted to access to API server. Where possible, consider enabling just-in-time (JIT) access to the Kubernetes API to place additional restrictions on access.
- **M1038 Execution Prevention** — Use read-only containers, read-only file systems, and minimal images when possible to prevent the execution of commands. Where possible, also consider using application control and software restriction tools (such as those provided by SELinux) to restrict access to files, processes, and system calls in containers.
- **M1042 Disable or Remove Feature or Program** — Remove unnecessary tools and software from containers.

## Detection strategies

- **DET0065 Detection Strategy for Container Administration Command Abuse**
  - AN0177 (Containers): Defenders may detect abuse of container administration commands by observing anomalous use of management utilities (`docker exec`, `kubectl exec`, or API calls to kubelet) correlated with unexpected process creation inside containers. Behavioral chains include unauthorized API requests followed by command execution within running pods or containers, often originating from unusual user accounts, automation scripts, or IP addresses outside the expected cluster management plane. Log sources: docker:daemon (docker exec or docker run with unexpected command/entrypoint); kubernetes:apiserver (kubectl exec or kubelet API calls targeting running pods).

## Procedure examples

- **G0139 TeamTNT** (group) — TeamTNT executed Hildegard through the kubelet API run command and by executing commands on running containers.
- **S0599 Kinsing** (software) — Kinsing was executed with an Ubuntu container entry point that runs shell scripts.
- **S0601 Hildegard** (software) — Hildegard was executed through the kubelet API run command and by executing commands on running containers.
- **S0623 Siloscape** (software) — Siloscape can send kubectl commands to victim clusters through an IRC channel and can run kubectl locally to spread once within a victim cluster.
- **S0683 Peirates** (software) — Peirates can use `kubectl` or the Kubernetes API to run commands.
- **S9041 TeamPCP Cloud Stealer** (software) — TeamPCP Cloud Stealer can use `kubectl get secrets` to extract credentials from Kubernetes.
- **S9042 CanisterWorm** (software) — CanisterWorm can deploy privileged DaemonSets in Kubernetes clusters for data wiping using kubectl.
- **S9043 Mini Shai-Hulud** (software) — Mini Shai-Hulud has utilized container administration commands to gather details of compromised hosts and gather credentials to include Kubernetes command-line utilities `kubectl get secrets`.
- **S9045 BACKUPOSINT v9.0 APEX PREDATOR** (software) — BACKUPOSINT v9.0 APEX PREDATOR can interact with and execute Docker and Kerberos commands.

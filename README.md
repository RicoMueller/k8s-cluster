# Kubernetes Cluster - GitOps Infrastructure

A production-grade Kubernetes cluster (codename **Pantheon**) managed through GitOps
principles using Flux CD. This repository is the single source of truth for the
cluster's bootstrap, infrastructure controllers, and workloads. The underlying
nodes run **Talos Linux**, provisioned and managed with **Omni**.

## Overview

All cluster state is defined declaratively in Git and continuously reconciled by
Flux CD. Machine configuration (Talos) lives alongside the workload manifests, so
the entire stack — from the OS layer up to the applications — is version-controlled.

> **Migration note:** The cluster was rebuilt as *Pantheon*. The previous setup is
> retained under `legacy/` and `*/legacy/` for reference and is **not reconciled** by
> Flux. Workloads are being migrated to Pantheon app-by-app.

### Key Features

- **Declarative from the OS up** — Talos machine config (via Omni) + Flux-managed workloads
- **Automated GitOps Workflow** — Flux CD continuously reconciles cluster state from `main`
- **Cilium Networking** — CNI with L2 announcements, LoadBalancer IP pools, and Gateway API
- **Highly-Available PostgreSQL** — CloudNativePG operator with a 2-instance cluster
- **Encrypted Secrets** — SOPS with Age encryption for all sensitive data
- **Automated Dependency Updates** — Self-hosted Renovate bot for images and Helm charts

## Architecture

### Platform

| Layer | Technology | Version |
|-------|-----------|---------|
| OS | Talos Linux | v1.12.7 |
| Machine Management | Omni | — |
| Kubernetes | kubelet/kube-apiserver | v1.35.4 |
| CNI / Networking | Cilium (Gateway API, L2/LB) | v1.19.3 |
| GitOps Controller | Flux CD | v2.8 |
| Configuration | Kustomize | Native |
| Package Management | Helm | v3 |
| Secrets Encryption | SOPS + Age | — |
| Databases | CloudNativePG (PostgreSQL) | PG 18 |
| Storage | QNAP iSCSI CSI (Trident) | v1.6.0 |
| Dependency Automation | Renovate (self-hosted) | latest |

Node topology: 5 Talos nodes (2 control-plane, 3 workers).

### Repository Structure

```
k8s-cluster/
├── clusters/
│   ├── pantheon/             # Active production cluster (Flux bootstrap + Kustomizations)
│   │   ├── flux-system/      # Flux CD components
│   │   ├── infrastructure-databases.yaml
│   │   ├── infrastructure-databases-cluster.yaml
│   │   ├── infrastructure-networking.yaml
│   │   ├── infrastructure-storage.yaml
│   │   └── infrastructure-renovate.yaml
│   └── legacy/               # Archived pre-Pantheon setup (not reconciled)
├── apps/                     # Application deployments
│   ├── pantheon/             # Active cluster overlays (migration in progress)
│   └── legacy/               # Archived apps (audiobookshelf, linkding)
├── infrastructure/
│   └── controllers/
│       ├── databases/        # CloudNativePG operator + pantheon-pg cluster
│       ├── networking/       # Cilium L2 / LB pools + pantheon-gateway
│       ├── storage/          # QNAP iSCSI (Trident) CSI
│       ├── renovate/         # Self-hosted Renovate CronJob
│       └── legacy/           # Archived (reference only)
├── omni/                     # Talos / Omni machine config & manifests
├── legacy/                   # Archived monitoring stack (kube-prometheus-stack)
├── renovate.json             # Renovate configuration
└── .sops.yaml                # SOPS encryption rules
```

## Deployed Services (Pantheon)

Pantheon currently reconciles the infrastructure layer. Each item below maps to a
Flux Kustomization under `clusters/pantheon/`.

### Databases — `infrastructure-databases` / `infrastructure-databases-cluster`
- **Operator:** CloudNativePG (installed via Helm from `cloudnative-pg.github.io/charts`)
- **Cluster `pantheon-pg`:** PostgreSQL 18 (pinned via `ImageCatalog`, `ghcr.io/cloudnative-pg/postgresql:18.4`)
- **High Availability:** 2 instances
- **Storage:** 10Gi on the `qnap-iscsi` storage class
- **Backups:** `ScheduledBackup` (`pantheon-pg-backup`)

### Networking — `infrastructure-networking`
- **CNI:** Cilium
- **LoadBalancer:** `CiliumLoadBalancerIPPool` (`192.168.178.224/28`)
- **L2 Announcements:** `CiliumL2AnnouncementPolicy` (LB + external IPs)
- **Ingress:** Gateway API `pantheon-gateway` (`gatewayClassName: cilium`, HTTP/80)

### Storage — `infrastructure-storage`
- **Driver:** QNAP iSCSI CSI (NetApp Trident–based), deployed as a Helm chart
- **Storage Class:** `qnap-iscsi`

### Renovate — `infrastructure-renovate`
- **Schedule:** Hourly via CronJob
- **Purpose:** Automated dependency updates for Docker images and Helm charts
- **Target:** This repository (`RicoMueller/k8s-cluster`)
- **Auth:** GitHub token stored as a SOPS-encrypted Secret

### Pending Migration (Legacy)
Retained under `legacy/` / `apps/legacy/`, not yet on Pantheon:
- **Applications:** AudiobookShelf, Linkding
- **Monitoring:** Kube-Prometheus-Stack (Prometheus, Grafana, Alertmanager)

## GitOps Workflow

### How It Works

1. **Configuration Changes** → Commit and push to `main`
2. **Flux Detection** → Flux polls the Git repository and detects the new revision
3. **Reconciliation** → Flux applies the manifests under `clusters/pantheon/`
4. **Self-Healing** → Flux continuously ensures cluster state matches Git

### Kustomization Layout

The Pantheon cluster bootstrap (`clusters/pantheon/`) defines one Flux
`Kustomization` per concern, each pointing at a self-contained directory under
`infrastructure/controllers/`:

- `infrastructure-databases` → CloudNativePG operator
- `infrastructure-databases-cluster` → `pantheon-pg` (depends on the operator)
- `infrastructure-networking` → Cilium LB/L2 + Gateway
- `infrastructure-storage` → QNAP iSCSI CSI
- `infrastructure-renovate` → Renovate CronJob

Kustomizations that consume secrets enable SOPS decryption via the in-cluster
`sops-age` key.

### Dependency Updates

Renovate (`renovate.json` extends `config:recommended`) automatically monitors:
- Docker image tags (Kubernetes manifests + Helm `values.yaml`)
- Helm chart and Flux source versions
- Opens pull requests and maintains a Dependency Dashboard

Where versions can't be auto-detected, inline `# renovate:` markers annotate the
source (e.g. the CloudNativePG `ImageCatalog` and the QNAP chart values).

## Security & Best Practices

- **Encrypted Secrets:** SOPS with Age; only `data`/`stringData` is encrypted
- **Immutable OS:** Talos Linux (API-managed, no SSH/shell on nodes)
- **SSH-Based Git Auth:** Flux pulls the repository over SSH with a deploy key
- **Declarative Audit Trail:** Every change is a Git commit
- **Separation of Concerns:** One Flux Kustomization per infrastructure domain

## Maintenance

### Dependency Updates
Review and merge Renovate pull requests to keep images and charts current.

### Backup Strategy
- **Configuration:** Version-controlled in Git (this repository)
- **Secrets:** SOPS-encrypted in Git
- **Databases:** CloudNativePG `ScheduledBackup` for `pantheon-pg`
- **Persistent Data:** PersistentVolumeClaims on the `qnap-iscsi` storage class

### Disaster Recovery
1. Provision Talos nodes via Omni
2. Bootstrap Flux pointing at this repository (`clusters/pantheon`)
3. Create the SOPS Age secret (`sops-age`) so Flux can decrypt secrets
4. Flux restores the entire cluster state from Git
5. Restore database/PVC data from backups if needed

## About This Project

A portfolio project showcasing modern platform-engineering practices: declarative
infrastructure from the OS layer (Talos/Omni) through to GitOps-managed workloads
(Flux CD), Cilium networking with the Gateway API, highly-available PostgreSQL via
CloudNativePG, encrypted secrets with SOPS/Age, and automated dependency management
with Renovate.

## License

This configuration is provided as-is for reference purposes.

---

**Maintained by:** Rico Mueller
**Repository:** [RicoMueller/k8s-cluster](https://github.com/RicoMueller/k8s-cluster)
**GitOps Tool:** Flux CD v2.8 · **OS:** Talos Linux · **Kubernetes:** v1.35.4
**Last Updated:** June 2026

# Kubernetes Cluster - GitOps Infrastructure

A production-grade Kubernetes cluster configuration managed through GitOps principles using Flux CD. This repository serves as the single source of truth for all cluster resources, applications, and infrastructure components.

## Overview

This project demonstrates Infrastructure-as-Code (IaC) best practices by managing a complete Kubernetes environment declaratively through Git. All cluster state, application deployments, and configuration changes are version-controlled and automatically synchronized using Flux CD's GitOps toolkit.

### Key Features

- **Fully Declarative Infrastructure** - All resources defined as code in Git
- **Automated GitOps Workflow** - Flux CD continuously reconciles cluster state
- **Encrypted Secrets Management** - SOPS with Age encryption for sensitive data
- **Automated Dependency Updates** - Renovate bot for Docker images and Helm charts
- **Complete Observability Stack** - Prometheus and Grafana for monitoring
- **Multi-Environment Ready** - Base/overlay pattern supporting multiple environments

## Architecture

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| GitOps Controller | Flux CD | v2.7.5 |
| Configuration Management | Kustomize | Native |
| Package Management | Helm | v3 |
| Secrets Encryption | SOPS with Age | Latest |
| Monitoring | Kube-Prometheus-Stack | v66.2.2 |
| Ingress Controller | Traefik | Latest |
| Dependency Automation | Renovate | Latest |

### Repository Structure

```
k8s-cluster/
├── clusters/
│   └── staging/              # Cluster bootstrap configuration
│       ├── flux-system/      # Flux CD components
│       ├── infrastructure.yaml
│       ├── apps.yaml
│       └── monitoring.yaml
├── apps/                     # Application deployments
│   ├── base/                 # Environment-agnostic templates
│   │   ├── audiobookshelf/
│   │   └── linkding/
│   └── staging/              # Staging environment overlays
│       ├── audiobookshelf/
│       └── linkding/
├── infrastructure/           # Infrastructure components
│   └── controllers/
│       ├── base/
│       └── staging/
├── monitoring/               # Observability stack
│   ├── configs/             # Monitoring configurations
│   └── controllers/         # Prometheus & Grafana
└── renovate.json            # Automated update configuration
```

## Deployed Services

### Applications

#### AudiobookShelf
- **Purpose:** Personal audiobook and podcast server
- **Version:** v2.31.0
- **Port:** 3005
- **Storage:**
  - Configuration: 1Gi
  - Metadata: 1Gi
  - Audiobooks: 10Gi

#### Linkding
- **Purpose:** Bookmark management and link archival
- **Version:** v1.44.2
- **Port:** 9090
- **Domain:** lds.rm-it.org
- **Storage:** 1Gi

### Infrastructure Services

#### Renovate Bot
- **Schedule:** Hourly via CronJob
- **Purpose:** Automated dependency updates for Docker images and Helm charts
- **Target:** This repository (RicoMueller/k8s-cluster)

### Monitoring Stack

#### Kube-Prometheus-Stack
- **Prometheus:** Metrics collection and alerting
- **Grafana:** Visualization and dashboards
- **Domain:** grs.rm-it.org
- **Components:**
  - Prometheus Operator
  - Node Exporter
  - Alertmanager

## GitOps Workflow

### How It Works

1. **Configuration Changes** → Commit changes to Git repository
2. **Flux Detection** → Flux polls repository every 1 minute
3. **Reconciliation** → Flux automatically applies changes to cluster
4. **Self-Healing** → Flux ensures cluster state matches Git state

### Kustomization Layers

The repository uses a three-tier Kustomization structure:

1. **Infrastructure Controllers** → Base system components (Renovate)
2. **Applications** → User-facing services (AudiobookShelf, Linkding)
3. **Monitoring** → Observability stack (Prometheus, Grafana)

Each layer follows the base/overlay pattern:
- `base/` - Environment-agnostic resource definitions
- `staging/` - Environment-specific configurations and secrets

### Update Process

Renovate automatically monitors:
- Docker image tags in deployments
- Helm chart versions in HelmReleases
- Creates pull requests for version updates
- Maintains dependency freshness

## Security & Best Practices

### Security Measures

- **Encrypted Secrets:** SOPS with Age encryption for all sensitive data
- **Non-Root Containers:** Security contexts enforce non-privileged execution
- **SSH-Based Git Auth:** Secure repository access for Flux
- **TLS Certificates:** Encrypted traffic for exposed services
- **Network Policies:** Traffic segmentation for monitoring stack

### Operational Patterns

- **Immutable Infrastructure:** All changes through Git commits
- **Separation of Concerns:** Apps, infrastructure, and monitoring isolated
- **Version Control:** Full audit trail of all configuration changes
- **Automated Testing:** Renovate PRs validated before merge
- **Self-Documenting:** Declarative YAML serves as living documentation

## Project Highlights

This repository demonstrates:

- **Production-Ready GitOps:** Complete Flux CD implementation with automated reconciliation
- **Infrastructure as Code:** All cluster state declaratively managed in version control
- **Automated Operations:** Self-healing infrastructure and automated dependency updates
- **Security First:** Encrypted secrets, non-root containers, and secure authentication
- **Scalable Architecture:** Multi-environment support with base/overlay pattern
- **Complete Observability:** Full monitoring stack with Prometheus and Grafana

## Maintenance

### Dependency Updates

Renovate automatically creates pull requests for:
- Docker image updates
- Helm chart updates
- Dependency security patches

Review and merge Renovate PRs to keep cluster up-to-date.

### Backup Strategy

- **Configuration:** Version-controlled in Git (this repository)
- **Secrets:** Encrypted with SOPS in repository
- **Persistent Data:** PersistentVolumeClaims for application data
  - AudiobookShelf: Audiobooks, metadata, config
  - Linkding: Bookmark database

### Disaster Recovery

1. Fresh Kubernetes cluster
2. Bootstrap Flux pointing to this repository
3. Create SOPS Age secret
4. Flux restores entire cluster state
5. Restore PVC data from backups if needed

## About This Project

This repository is a portfolio project showcasing modern DevOps and platform engineering practices. It demonstrates my expertise in:

- **GitOps Methodologies:** Production-ready Flux CD implementation
- **Infrastructure as Code:** Declarative Kubernetes resource management
- **Cloud-Native Technologies:** Kubernetes, Helm, Kustomize, and container orchestration
- **Security Best Practices:** Secrets encryption, secure authentication, and security contexts
- **Automation & CI/CD:** Automated dependency management and self-healing infrastructure
- **System Architecture:** Multi-environment design patterns and separation of concerns

The repository serves as a practical example of building and maintaining production-grade Kubernetes infrastructure using industry best practices. Feel free to explore the code and architecture as a reference for similar implementations.

## License

This configuration is provided as-is for reference purposes.

---

**Maintained by:** Rico Mueller
**Repository:** [RicoMueller/k8s-cluster](https://github.com/RicoMueller/k8s-cluster)
**GitOps Tool:** Flux CD v2.7.5
**Last Updated:** December 2025

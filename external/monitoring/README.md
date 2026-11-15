# Monitoring-Stack (außerhalb Pantheon) — Quelle der LXC-Konfigurationen

CT 110 prometheus · CT 111 alertmanager · CT 112 grafana (community-scripts/ProxmoxVE).
Ausrollen von Hand per `pct push` (Interim bis Terraform/Proxmox-Projekt).

| Datei | Ziel |
|---|---|
| `prometheus/prometheus.yml` | CT 110 `/etc/prometheus/prometheus.yml` |
| `prometheus/rules/*.rules.yml`, `*.test.yml` | CT 110 `/etc/prometheus/rules/` |
| `alertmanager/alertmanager.yml` | CT 111 `/etc/alertmanager/alertmanager.yml` |
| `grafana/provisioning/datasources.yaml` | CT 112 `/etc/grafana/provisioning/datasources/pantheon.yaml` |
| `grafana/provisioning/dashboards.yaml` | CT 112 `/etc/grafana/provisioning/dashboards/pantheon.yaml` |
| `grafana/dashboards/*.json` | CT 112 `/var/lib/grafana/dashboards/` |

Nicht enthalten (nur auf den Containern, `0600` bzw. `0640`, und im Passwort-Manager):
`web-config.yml` (bcrypt-Hashes), `smtp.password`, `pushover.user`, `pushover.token`,
`prometheus-grafana.password` (Grafana liest es per `$__file{}`).
Skripte und systemd-Units liegen außerhalb dieses Repositorys.

Siehe rezept-monitoring-pantheon.md.

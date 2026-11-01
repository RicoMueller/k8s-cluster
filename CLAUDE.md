# Pantheon — Arbeitsanweisungen für Claude Code

Dieses Repository (`github.com/RicoMueller/k8s-cluster`) ist die einzige Quelle der Wahrheit für den Kubernetes-Cluster **Pantheon**: 7 Talos-Nodes (3 Control Plane, 4 Worker), verwaltet über Sidero Omni, Cilium mit Gateway API, Flux CD mit SOPS/age, CloudNativePG-Cluster `pantheon-pg`, Storage über QNAP (iSCSI/NFS), externer Zugang über Cloudflare Tunnel + Access, Renovate läuft im Cluster. Pantheon ist zugleich ein DevOps-Portfolio: Nachvollziehbarkeit und Dokumentation zählen so viel wie die Infrastruktur.

Sprache im Gespräch: **Deutsch**. Abkürzungen ausschreiben (z.B. „Pull Request", nicht „PR"); nur „MVP" darf abgekürzt bleiben.

## Rollenverteilung

| Rico | Claude Code |
|---|---|
| Secrets erzeugen, verschlüsseln, ändern | Manifeste anlegen und ändern |
| `git push` freigeben (Push auf `main` = Flux spielt ein) | Build-Checks, Commits |
| Weboberflächen: Omni-Anmeldung, Cloudflare-Dashboard, Admin-Oberflächen von Apps | Lesende Prüfungen im Cluster (`kubectl get/describe/logs`, `flux get`) |
| Entscheidungen bei Abweichungen vom Rezept | Abweichungen erkennen, beschreiben, Vorschlag machen |

## Harte Regeln

1. **Nur GitOps.** Den Cluster nie direkt verändern: kein `kubectl apply/delete/edit/patch/replace`. Jede Änderung läuft über Commit → Push (Rico gibt frei) → `flux reconcile kustomization flux-system --with-source`.
2. **Secrets nie anfassen.** Kein `sops` ausführen, keine Datei mit `kind: Secret` anlegen oder ändern, kein `kubectl get secret`. Verschlüsselte Dateien darf ich lesen und prüfen, ob jede Wertzeile mit `ENC[` beginnt. Braucht ein Schritt ein Secret: anhalten und Rico einen vollständigen, kopierfertigen Befehlsblock geben.
3. **Pushen nur mit Freigabe.** Vorher immer `git pull --rebase`. Nie `--force`, nie `git reset --hard` auf geteilte Historie.
4. **Keine Renovate-Branches mergen** und keine Renovate-Pull-Requests bearbeiten, außer Rico verlangt es ausdrücklich. Für gevendorte Manifeste gelten eigene Abläufe (siehe Repository-Karte).
5. **Verify-then-document.** Erfolg nie aus Logs oder grünen Statusanzeigen ableiten, sondern am Ziel prüfen (Ressource existiert, Wert stimmt, Datei ist da). Ergebnisse immer als *Ist vs. Erwartung* berichten.
6. **Rezept folgen, nicht improvisieren.** Weicht ein Ergebnis vom Rezept ab: anhalten, Befund beschreiben, Vorschlag machen, auf Rico warten. Bestätigte Abweichungen als Korrektur ins Rezept (Changelog) übernehmen.
7. **Kein spekulatives Tooling.** Nur hinzufügen, was der aktuelle Schritt braucht.

## Arbeitsweise

- Sitzungen sind kurz (~30 Minuten, ein „Abend" je Sitzung) und **sequenziell**: ein Vorhaben zur Zeit.
- Zu Beginn: `git status -sb` und `git pull --rebase`; offene fremde Änderungen nicht anfassen, sondern melden.
- Am Ende eines Abends: Stand zusammenfassen (erledigt, offen, Befunde) und im Rezept in der Abendtabelle ✅ + Datum setzen.
- **Befehle für Rico** ohne Platzhalter wie `<VERSION>` (bash liest `<` als Umleitung). Stattdessen Variablen oben im Block setzen.
- **Keine endlosen Befehle:** kein `-w`/`--watch`/`logs -f`. Stattdessen `kubectl rollout status … --timeout=…`, `kubectl wait … --timeout=…` oder einmalige Abfragen. `kubectl run`/`exec` ohne `-t`.
- `kubectl` läuft über Omni (OIDC). Meldet `kubectl` einen Anmeldefehler oder will einen Browser öffnen: Rico um die Anmeldung bitten, nicht umgehen.

## Konventionen für Manifeste

- Image-Tags immer konkret pinnen (nie `latest`, `stable`, `beta`, `canary`), `imagePullPolicy: IfNotPresent`, darüber den Marker `# renovate: datasource=docker depName=<image>`. Der Marker ist Konvention — Renovates Kubernetes-Manager erfasst jede `image:`-Zeile in `*.yaml` ohnehin.
- Workloads in `apps/pantheon/<name>/` mit eigener `kustomization.yaml`; **pro App eine Flux-Kustomization** `clusters/pantheon/apps-<name>.yaml` (Vorlage: `apps-paperless.yaml`: `interval: 10m`, `prune: true`, `wait: false`, `decryption: sops/sops-age`). Eine gemeinsame `apps/pantheon/kustomization.yaml` gibt es nicht.
- Datenbanken deklarativ über CNPG-CRDs (`DatabaseRole`, `Database`) in `infrastructure/controllers/databases/pantheon-pg/`; in deren `kustomization.yaml` Secret und Rolle **vor** der Datenbank.
- PodSecurity: `restricted`-konform, wo das Image es zulässt; sonst Namespace auf `baseline` mit Begründung im Kommentar.
- Routing über `HTTPRoute` an `pantheon-gateway` (Namespace `default`).
- **Keine `Job`-Objekte mit Renovate-erfassten Images** in Flux-Pfaden: `Job.spec.template` ist unveränderlich, ein Tag-Bump blockiert dann den Sync. Migrationen als initContainer.
- Vor jedem Commit: `kubectl kustomize <verzeichnis> > /dev/null && echo BUILD_OK`; JSON mit `python3 -m json.tool` prüfen.

## Commits

- Conventional Commits wie in der bestehenden Historie: `feat(<scope>): …`, `fix(<scope>): …`, `chore(<scope>): …`, `docs(<scope>): …`. Betreffzeile Englisch, Imperativ, höchstens 72 Zeichen; Body darf Deutsch sein.
- Scope = Komponente (`affine`, `databases`, `renovate`, `paperless`, …).
- Ein Commit je in sich geschlossenem Rezeptschritt. Nur die Dateien des Schritts stagen, nie `git add -A`.
- Vor dem Push Rico die Commit-Message und `git show --stat HEAD` zeigen.

## Repository-Karte

| Pfad | Inhalt | Hinweis |
|---|---|---|
| `clusters/pantheon/` | Flux-Bootstrap und eine Flux-Kustomization je Komponente | `flux-system` liest dieses Verzeichnis |
| `apps/pantheon/<name>/` | Workloads (homepage, paperless, paperless-test, …) | |
| `infrastructure/controllers/<bereich>/<komponente>/` | Controller und Plattform | flache Struktur |
| `infrastructure/controllers/databases/pantheon-pg/` | CNPG-Cluster, ImageCatalog, Backups, Rollen, Datenbanken | Änderungen hier wirken sofort auf den Shared-Cluster |
| `infrastructure/controllers/barman-plugin/` | gevendortes Release-Manifest | nie nur den Tag anheben; Re-Vendor nach `rezept-cnpg-backup` B.7 |
| `infrastructure/controllers/storage/qnap-iscsi/` | gevendortes Trident-Chart | Image-Bump wirkt nur mit `version`-Bump in `Chart.yaml` |
| `omni/` | Talos-/Omni-Konfiguration, gerenderte Manifeste | nicht anfassen ohne Auftrag; Wartungsfenster-Thema |
| `legacy/`, `*/legacy/` | Altbestand vor Pantheon | wird nicht reconciled, nicht ändern |
| `docs/rezepte/` | ausführbare Rezepte | Rezept des laufenden Vorhabens ist die Arbeitsgrundlage |
| `renovate.json` | Renovate-Regeln | Regeln mit `description` im bestehenden Stil |
| `tls.key`, `tls.crt` | lokal, ignoriert | nie lesen |

## Laufendes Vorhaben

**AFFiNE** (Whiteboard statt Apple Freeform): `docs/rezepte/rezept-affine-pantheon.md`. Der Stand steht in der Abendtabelle des Rezepts. Steps mit **[Rico]** nicht selbst ausführen, sondern Rico mit kopierfertigem Block oder genauem Klickpfad übergeben.

# Kochrezept: AFFiNE auf Pantheon (Whiteboard statt Apple Freeform)

> Schnell-Rezept für einen Nachmittag: AFFiNE als kollaboratives Whiteboard auf dem Pantheon-Cluster, von außen über Cloudflare Tunnel + Access erreichbar, gemeinsam mit einer zweiten Person live bearbeitbar. Datenbank im Shared-Cluster `pantheon-pg` (automatisch im Barman-Backup), Updates ausschließlich über Renovate-PRs und Flux.
>
> Bewusst schlank: Alles, was die Nutzung verhindern oder stark einschränken würde, ist drin. Komfort- und Härtungsthemen stehen gesammelt unter **„Bewusst zurückgestellt"** — jeweils mit dem Risiko, das man bis dahin trägt.

*Rezeptversion: 1.1.1 — November 2026 · Cluster: Pantheon · Zielversion: AFFiNE 0.27.4*

> **Status:** Teil 0 am 27.10.2026 und Teil A am 01.11.2026 live verifiziert (Ergebnisse jeweils im Teil eingetragen). Teile B–F noch nicht live verifiziert. Alle Annahmen sind gegen den AFFiNE-Quellcode (Tag `v0.27.4`: `self-host-predeploy.js`, `prelude.ts`, Setup-Controller, Config-Module) und die CNPG-1.30-Doku geprüft. Nach jedem Abend die Erwartungswerte mit den echten Ausgaben abgleichen und Abweichungen hier nachtragen.

> **Umsetzung mit Claude Code.** Dieses Rezept ist so geschrieben, dass Claude Code (VS Code, Repo `~/k8s-cluster`, Leitplanken in `CLAUDE.md` und `.claude/settings.json`) alle Manifeste anlegt, prüft und committet. Rico greift nur an den mit **[Rico]** markierten Stellen ein: Secrets erzeugen und verschlüsseln, `git push` freigeben, Weboberflächen (Omni-Anmeldung, Cloudflare, AFFiNE-Admin). Alles mit **[Claude Code]** markierte erledigt Claude Code selbständig.

---

## Inhalt

- **Zweck** · **Umsetzung in Abendsitzungen** · **Voraussetzungen** · **Hintergrund**
- **Architekturentscheidungen 1–4** (Datenbank · Migration · Konfiguration · Zugang)
- **Repository-Struktur**
- **Teil 0** — Vorab-Checks (Abend 1, ✅)
- **Teil A** — Secrets und Datenbank (Abend 2)
- **Teil B** — App-Manifeste (Abend 3 und 4)
- **Teil C** — Flux-Kustomization, Rollout, interne Verifikation (Abend 5)
- **Teil D** — Externer Zugriff und Admin-Konto (Abend 6)
- **Teil E** — Partner-Zugang und Kollaborationstest (Abend 7)
- **Teil F** — Betrieb: Backup und Updates (Abend 8)
- **Definition of Done** · **Bewusst zurückgestellt** · **Changelog**

---

## Zweck

Apple Freeform durch AFFiNE ablösen: unendliches Canvas („Edgeless"), Notizzettel, Formen, Verbinder, Bilder, Stift — plus Dokumente und Datenbanken im selben Workspace. Ergebnis dieses Rezepts:

1. AFFiNE läuft unter `https://affine.rm-it.org`, abgesichert durch Cloudflare Access (E-Mail-OTP) **vor** dem AFFiNE-Login.
2. Ein Admin-Konto (Rico) und ein Partner-Konto existieren; Selbstregistrierung ist geschlossen.
3. Ein gemeinsamer Server-Workspace, in dem beide gleichzeitig am selben Whiteboard arbeiten.
4. Die Datenbank liegt in `pantheon-pg` und ist damit ohne Zusatzaufwand im WAL-Archiving und den täglichen Barman-Backups nach Hetzner.
5. Image-Updates kommen als Renovate-PR, werden per Flux ausgerollt und migrieren die DB automatisch.

## Umsetzung in Abendsitzungen

Acht Abende à etwa 30 Minuten. Nach jedem Abend kann man aufhören: Die Manifeste unter `apps/pantheon/affine/` werden erst wirksam, wenn am fünften Abend `clusters/pantheon/apps-affine.yaml` entsteht. Nur die Datenbank-Rolle und die Datenbank (Abend 2) gehen sofort live — gewollt, sie laufen über `infrastructure-databases-cluster`.

| Abend | Inhalt | Rezept | Rico | Claude Code | Wirkung im Cluster |
|---|---|---|---|---|---|
| 1 ✅ 27.10. | Vorab-Checks | Teil 0 | Befehle ausgeführt | — | keine |
| 2 ✅ 01.11. | Beide Secrets, Datenbank-Rolle, Datenbank mit pgvector | A.1–A.3 | A.1 im eigenen Terminal, Push freigeben | A.2, A.3, Commit, Verifikation | Rolle + Datenbank live |
| 3 | Namespace, Konfiguration, Speicher, Redis | B.1, B.3–B.5 | Push freigeben | Manifeste, Build-Check, Commit | keine |
| 4 | Deployment, Service, Route, lokale Kustomization, Renovate-Regel | B.6–B.9 | Push freigeben | Manifeste, Build-Check, Commit | keine |
| 5 | Flux-Kustomization `apps-affine`, Rollout, Migrationslog, `/info` | Teil C | Push freigeben, ggf. Omni-Anmeldung | Datei anlegen, Commit, Verifikation | AFFiNE läuft intern |
| 6 | Access-Application, DNS-Eintrag, Admin-Konto — **ohne Pause dazwischen** | Teil D | Cloudflare-Dashboard, `cloudflared`-CLI, Admin anlegen | Gegenproben | extern erreichbar |
| 7 | Partner-Konto, Workspace, Live-Test | Teil E | AFFiNE-Admin, Access-Policy, Test | Datenbank-Gegenprobe | Partner arbeitet mit |
| 8 | Backup-Nachweis, Update-Regeln, Rezept fortschreiben | Teil F | On-Demand-Backup freigeben | Verifikation, Rezeptversion 1.2 | — |

**Gesamtaufwand:** ≈ 3 h reine Arbeitszeit.

## Voraussetzungen

| Voraussetzung | Herkunft |
|---|---|
| Flux CD, SOPS/age, Repo-Struktur `apps/pantheon/` | Phase 4 |
| StorageClass `qnap-iscsi` | Phase 5 |
| `pantheon-pg` (PG 18, Image `18.x-standard-trixie` via ImageCatalog), CNPG ≥ 1.26 (Pantheon: 1.30) | Phase 5.5 |
| Barman Cloud Plugin aktiv, WAL-Archiving `OK` | `rezept-cnpg-backup-pantheon.md` |
| `pantheon-gateway` (Cilium Gateway API, HTTP-Listener) | Phase 3.5 / AP 6.0 |
| `cloudflared` (Tunnel `pantheon-apps`, Catch-all aufs Gateway) und One-time PIN als IdP | `rezept-paperless-ngx-pantheon.md`, Teil A |
| `kubectl-cnpg`-Plugin, `cloudflared`-CLI, `openssl` lokal | — |
| Eine Flux-Kustomization **pro App** in `clusters/pantheon/apps-<name>.yaml` (SOPS-Entschlüsselung, `wait: false`) | Repo-Konvention, in Teil 0.4 verifiziert |
| Für die Umsetzung mit Claude Code: VS Code mit Erweiterung „Claude Code", `CLAUDE.md` und `.claude/settings.json` im Repo | `CLAUDE.md` |

**Offizielle Dokumentation:**
- [AFFiNE Self-Host — Installation](https://docs.affine.pro/self-host-affine)
- [AFFiNE Self-Host — Environment Variables](https://docs.affine.pro/self-host-affine/references/environment-variables)
- [AFFiNE Self-Host — After Installation](https://docs.affine.pro/self-host-affine/install/after-installation)
- [AFFiNE Self-Host — User Management](https://docs.affine.pro/self-host-affine/administer/user-management)
- [CloudNativePG — Declarative Database Management](https://cloudnative-pg.io/docs/1.30/declarative_database_management)
- [AFFiNE Container-Tags (ghcr.io)](https://github.com/toeverything/AFFiNE/pkgs/container/affine)

---

## Hintergrund — was AFFiNE braucht

| Komponente | Rolle in Pantheon |
|---|---|
| `ghcr.io/toeverything/affine` | Server **und** Web-Client in einem Image, Port 3010. Läuft als root (`HOME=/root`). |
| Migrations-Skript | `node ./scripts/self-host-predeploy.js` — Prisma-Schema-Migrationen, Daten-Migrationen, legt bei Bedarf `private.key` an. Muss vor jedem Serverstart erfolgreich laufen. |
| PostgreSQL **mit pgvector** | Seit AFFiNE 0.21 Pflicht — das Schema enthält `vector`-Spalten, auch bei abgeschalteter KI. Ein PostgreSQL ohne pgvector lässt die Migration scheitern. |
| Redis | Cache, Queue, Pub/Sub. Keine Persistenz nötig, nichts zu sichern. |

| Pfad im Container | Inhalt | Storage in Pantheon |
|---|---|---|
| `/root/.affine/config/config.json` | Server-Konfiguration (externe URL, Signup …) | ConfigMap (Git) |
| `/root/.affine/config/private.key` | Signatur-/Verschlüsselungsschlüssel des Servers | SOPS-Secret (Git) |
| `/root/.affine/storage` | **Blobs**: Bilder, Anhänge, Avatare | `qnap-iscsi`-PVC |
| — | **Whiteboard- und Dokumentinhalte** (Snapshots, Updates), Konten, Workspaces | Datenbank `affine` in `pantheon-pg` |

> **Merksatz für das Backup:** Die Whiteboards selbst stecken in der Datenbank — die ist über Barman gesichert. Eingefügte **Bilder und Dateien** liegen im Blob-Storage auf der QNAP und sind in Version 1.0 **nicht** off-site gesichert (siehe „Bewusst zurückgestellt", Punkt 1).

---

## Architekturentscheidung 1: Datenbank im Shared-Cluster `pantheon-pg`

> **Problemstellung.** Das offizielle Compose-File bringt einen eigenen Container `pgvector/pgvector:pg16` mit. AFFiNE braucht zwingend die Extension `vector`.
>
> **Entscheidung: eigene Datenbank `affine` im Shared-Cluster `pantheon-pg`, Extension deklarativ über die `Database`-CR.** Das Pantheon-Image `ghcr.io/cloudnative-pg/postgresql:18.x-standard-trixie` enthält pgvector bereits (die `standard`-Images bringen PGAudit, Failover Slots und pgvector mit). CNPG führt `CREATE EXTENSION IF NOT EXISTS vector` mit Superuser-Rechten aus — der App-User `affine` braucht keine erhöhten Rechte. Die Prisma-Migration von AFFiNE findet die Extension dann vor, ihr eigenes `CREATE EXTENSION IF NOT EXISTS` wird zum No-op.
>
> **Konsequenz für das Backup:** Die Datenbank ist ab der ersten Sekunde Teil von WAL-Archiving und Base-Backups nach Hetzner Object Storage. Es entsteht **keine** neue Backup-Pflicht für die DB.
>
> **Verworfene Alternative — eigener pgvector-Pod (wie im Compose-File):** ungesicherte Datenbank neben einem gesicherten Cluster, eigener Lifecycle, eigenes Major-Upgrade-Problem (pg16 → pg17 geht laut AFFiNE-Doku nur per Dump/Restore). Widerspricht der Pantheon-Datenbankstrategie.

## Architekturentscheidung 2: Migration als initContainer statt als Job

> **Problemstellung.** Compose startet die Migration als eigenen One-shot-Container. Das naheliegende Kubernetes-Pendant wäre ein `Job`.
>
> **Entscheidung: initContainer im AFFiNE-Deployment, gleiches Image, gleicher Tag.**
> - **Renovate-Kompatibilität:** `Job.spec.template` ist unveränderlich. Hebt Renovate den Image-Tag in einem Job-Manifest an, scheitert das Apply — dasselbe Muster wie die 83-Tage-Blockade durch den unveränderlichen Job im Omni-Sync. Ein initContainer ist Teil des Deployments und rollt mit jedem Tag-Bump einfach neu.
> - **Reihenfolge garantiert:** Der Server startet erst, wenn die Migration mit Exit 0 endet — exakt die Semantik von `service_completed_successfully` im Compose-File.
> - **Idempotent:** Das Skript läuft bei jedem Pod-Start; ohne ausstehende Migrationen dauert es Sekunden.
>
> **Verworfene Alternative — Job mit Flux-Annotation `kustomize.toolkit.fluxcd.io/force: enabled`:** funktioniert, verschiebt aber das Ordnungsproblem (Server könnte vor der Migration starten) und braucht eine Sonderregel, die man beim nächsten Workload wieder vergisst.

## Architekturentscheidung 3: Konfiguration aus Git — `config.json` + `private.key` als projiziertes Volume

> **Problemstellung — zwei Fakten aus dem Quellcode (v0.27.4):**
> 1. `self-host-predeploy.js` prüft, ob `/root/.affine/config/private.key` existiert, und **schreibt** andernfalls einen neu generierten EC-Schlüssel dorthin.
> 2. `prelude.ts` lädt diesen Schlüssel beim Serverstart als `AFFINE_PRIVATE_KEY`. Der Server signiert damit Tokens und verschlüsselt Daten. Fehlt die Datei, erzeugt der Server bei **jedem Start** einen neuen Schlüssel.
>
> Ein `emptyDir` als Config-Verzeichnis hieße also: neuer Schlüssel nach jedem Pod-Neustart (ungültige Tokens/Links). Ein schreibgeschützter ConfigMap-Mount ohne `private.key` hieße: Die Migration crasht beim Schreibversuch.
>
> **Entscheidung:** Den Schlüssel **selbst erzeugen** (`openssl`, gleiches Format wie das Skript: SEC1-PEM auf `prime256v1`), als SOPS-Secret ins Repo legen und zusammen mit der `config.json` aus einer ConfigMap als **projiziertes Volume** nach `/root/.affine/config` mounten. Das Skript findet die Datei vor und schreibt nichts; der Schlüssel ist über Git gesichert und überlebt jeden Neustart.
>
> **Verworfene Alternative — Config-Verzeichnis als PVC:** Schlüssel wäre persistent, aber `config.json` läge außerhalb von Git, und der Schlüssel wäre nur so gut gesichert wie das PVC.
>
> **Hinweis:** Einstellungen, die man im Admin-Panel ändert, landen in der **Datenbank**, nicht in `config.json`. Für GitOps-Treue alles Dauerhafte in `config.json` pflegen; das Admin-Panel nur für Konten und Einmalaktionen nutzen.

## Architekturentscheidung 4: Zugang — Access-Gate, geschlossene Registrierung, kein SMTP

> **Problemstellung.** Drei Eigenheiten von AFFiNE treffen aufeinander:
> - **Der erste Besucher von `/admin` wird Administrator** — ohne Token oder Einladungscode (`/api/setup/create-admin-user` ist öffentlich, bis der erste User existiert).
> - **Registrierung ist per Default offen** (`auth.allowSignup: true`), E-Mail-Verifikation per Default an.
> - **Einladungen per E-Mail brauchen SMTP**, das in Pantheon nicht existiert.
>
> **Entscheidung:**
> 1. **Cloudflare Access (E-Mail-OTP) vor AFFiNE**, Access-Application **vor** dem DNS-Eintrag anlegen (Paperless-Lehre 1.20). Damit erreicht nur eine freigegebene Adresse überhaupt `/admin` — das Erster-Besucher-Risiko ist geschlossen, bevor der Hostname auflöst. Policy zunächst nur mit Ricos Adresse, Partner erst nach Admin-Anlage.
> 2. **`auth.allowSignup: false`** in `config.json` ab dem ersten Start. Das Admin-Setup ist davon unabhängig (eigener Endpunkt).
> 3. **Partner-Konto per CSV-Import** im Admin-Panel (Username, E-Mail, Passwort) — kein Mailversand nötig.
> 4. **Workspace-Einladung über In-App-Benachrichtigung oder Einladungslink** — beides existiert serverseitig (`createInviteLink`, Notification-Typ `Invitation`), kein SMTP nötig.
>
> **Verworfene Alternativen:**
> - *Admin-Setup per `kubectl port-forward`:* Der Browser-Origin wäre `http://localhost:3010`, AFFiNE erlaubt aber nur den Origin der `externalUrl` — Schreib-Requests würden abgelehnt. Zusätzlich sind Port-Forwards über den Omni-Proxy unzuverlässig.
> - *Offene Registrierung + SMTP:* zusätzlicher Dienst (Mail-Relay, Zugangsdaten, SPF) für zwei Nutzer — „kein spekulatives Tooling".

---

## Repository-Struktur

```
clusters/pantheon/
└── apps-affine.yaml             ← Flux-Kustomization (Schalter, erst Abend 5)

infrastructure/controllers/databases/pantheon-pg/
├── affine-db-role-secret.yaml   ← SOPS-verschlüsselt (Namespace databases) — von Rico erzeugt
├── affine-role.yaml             ← DatabaseRole
├── affine-database.yaml         ← Database inkl. Extension vector
└── kustomization.yaml           ← drei Einträge ergänzen

apps/pantheon/affine/
├── kustomization.yaml
├── namespace.yaml
├── affine-secret.yaml           ← SOPS-verschlüsselt: db-password + private.key — von Rico erzeugt
├── configmap.yaml               ← config.json
├── pvc.yaml                     ← Blob-Storage (qnap-iscsi)
├── redis.yaml
├── deployment.yaml              ← initContainer migrate + Server
├── service.yaml
└── httproute.yaml

renovate.json                    ← packageRule für AFFiNE-Tags (Abend 4)
```

> **Korrektur ggü. 1.0:** Es gibt in Pantheon **keine** gemeinsame Kustomization über `apps/pantheon/`. Jede App hat eine eigene Flux-Kustomization in `clusters/pantheon/apps-<name>.yaml`, die `flux-system` einliest (verifiziert in 0.4). Eine `apps/pantheon/kustomization.yaml` würde von niemandem gelesen.

---

# Teil 0 — Vorab-Checks (10 Min) — ✅ 27.10.2026

**0.1 — pgvector im Pantheon-Image verfügbar?** *[Claude Code]*

```bash
kubectl cnpg psql pantheon-pg -n databases -- -tAc \
  "SELECT default_version FROM pg_available_extensions WHERE name = 'vector';"
# Erwartung: eine Versionsnummer
```

> **Ergebnis 27.10.2026:** `0.8.6` (ImageCatalog: `ghcr.io/cloudnative-pg/postgresql:18.6-standard-trixie`).
>
> **Leere Ausgabe = STOPP.** Dann läuft `pantheon-pg` nicht auf einem `standard`-Image (`grep image infrastructure/controllers/databases/pantheon-pg/imagecatalog.yaml`). Den Wechsel auf `-standard-` *nicht* nebenbei erledigen — er rollt den Shared-Cluster für alle Apps neu (Switchover) und ist ein eigener Schritt.

**0.2 — Aktuelle AFFiNE-Stable ermitteln.** *[Claude Code]* Zwei Schritte, ohne Platzhalter kopierbar:

```bash
# 1. Neuestes stabiles GitHub-Release (Pre-Releases werden ausgelassen)
curl -sI https://github.com/toeverything/AFFiNE/releases/latest | grep -i '^location'
# Erwartung: .../releases/tag/v0.27.x

# 2. Gegenprobe: zeigen "stable" und diese Version auf dasselbe Image?
#    V auf die Zahl aus Schritt 1 setzen (ohne führendes "v")
V=0.27.4
TOKEN=$(curl -s "https://ghcr.io/token?scope=repository:toeverything/affine:pull" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
for t in stable "$V"; do
  printf "%-8s " "$t"
  curl -sI -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.oci.image.index.v1+json" \
    "https://ghcr.io/v2/toeverything/affine/manifests/$t" | grep -i docker-content-digest
done
# Erwartung: zweimal derselbe sha256-Digest
```

> **Ergebnis 27.10.2026:** neuestes Release `v0.27.4`. Niemals `stable`, `beta`, `canary` oder `candidate-…` ins Manifest schreiben — das sind wandernde bzw. Pipeline-Tags. Der Installationsbefehl auf der GitHub-Paketseite zeigt nur den zuletzt hochgeladenen Tag (z.B. `candidate-40523579716-1`, ein Build aus der Release-Pipeline) und sagt nichts über die stabile Version.

**0.3 — Gateway nimmt neue Routen an?** *[Claude Code]* (Stolperstein S aus dem Paperless-Rezept: eingefrorener Cilium-Operator)

```bash
kubectl get httproute -A --no-headers | wc -l
kubectl get gateway -n default pantheon-gateway \
  -o jsonpath='{.status.listeners[*].attachedRoutes}{"\n"}'
# Erwartung: beide Zahlen gleich
# Weniger angebunden? -> Rico: kubectl rollout restart deployment/cilium-operator -n kube-system
```

> **Ergebnis 27.10.2026:** 3 Routen, 3 angebunden.

**0.4 — Wie rendert Flux die Apps, und ist SOPS-Entschlüsselung aktiv?** *[Claude Code]*

```bash
kubectl get kustomizations -n flux-system \
  -o custom-columns=NAME:.metadata.name,PATH:.spec.path,SOPS:.spec.decryption.provider
ls clusters/pantheon/
```

> **Ergebnis 27.10.2026:** eine Flux-Kustomization pro App (`apps-homepage`, `apps-paperless`, `apps-paperless-test`), jeweils mit `sops`; Vorlage `clusters/pantheon/apps-paperless.yaml`: `interval: 10m`, `prune: true`, `wait: false`, keine `dependsOn`. AFFiNE bekommt daher `clusters/pantheon/apps-affine.yaml` (C.1). `infrastructure-databases-cluster` hat ebenfalls `sops` — das Rollen-Secret in Teil A wird also entschlüsselt.

---

# Teil A — Secrets und Datenbank (Abend 2, 30 Min) — ✅ 01.11.2026

> Gleiches Muster wie Paperless B.3: Rolle, Datenbank und Passwort-Secret als CNPG-CRDs im Verzeichnis von `pantheon-pg`. Neu ist der `extensions`-Block.
>
> **Änderung ggü. 1.0:** Beide Secrets (Rolle in `databases`, App in `affine`) entstehen jetzt in **einem** Lauf (A.1, seit 1.1.1 als lokales Skript). In 1.0 hing B.2 an einer Shell-Variable aus A.1, die eine ganze Sitzung von A bis B überleben musste — mit 30-Minuten-Abenden nicht machbar.

## A.1 — Beide Secrets erzeugen und verschlüsseln *[Rico, im eigenen Terminal]*

Dieses Skript **nicht** von Claude Code ausführen lassen. Es erzeugt Passwort und Server-Schlüssel, schreibt beide Secrets und verschlüsselt sie, bevor irgendetwas davon in einer Claude-Sitzung sichtbar wird. Die Klartexte existieren nur in einer Variable und einer temporären Datei, die am Ende gelöscht werden.

```bash
bash ~/k8s-cluster/wartung/scripts/affine-a1-secrets.sh
# Erwartung am Ende: ENC-Zähler je Datei >= 3, Klartext-Prüfung "OK", "FERTIG."
```

Das Skript liegt **bewusst nur lokal** (`wartung/scripts/` ist über `.git/info/exclude` ausgeschlossen) und gehört nicht ins Repository. Es schreibt `infrastructure/controllers/databases/pantheon-pg/affine-db-role-secret.yaml` (Namespace `databases`) und `apps/pantheon/affine/affine-secret.yaml` (Namespace `affine`, Schlüssel `db-password` und `private.key`) und
- bricht beim ersten Fehler ab und prüft vorab `openssl`, `sops`, `.sops.yaml` und das Zielverzeichnis,
- überschreibt nichts: Existiert eine der beiden Dateien schon, bricht es ab (für einen Neulauf beide Dateien vorher entfernen),
- entfernt bei einem Abbruch unverschlüsselte Dateien wieder (`trap`) und gibt weder Passwort noch Schlüssel aus.

Danach in Claude Code: „Secrets für AFFiNE liegen bereit, weiter mit A.2."

> **⚠️ Stolperstein 1 — Passwort muss URL-sicher sein.** AFFiNE liest die Datenbank ausschließlich aus `DATABASE_URL` (`postgresql://user:passwort@host/db`). Das Paperless-übliche `openssl rand -base64` erzeugt `/`, `+` und `=` — diese Zeichen zerbrechen die URL, und die Migration scheitert mit einem irreführenden Verbindungsfehler. `-hex` liefert nur `0-9a-f`.

> **Warum ein Skript für beide Secrets?** Das Passwort wird zweimal gebraucht (Rolle in `databases`, App in `affine`), weil Secrets namespace-gebunden sind. Aus derselben Variable im selben Lauf erzeugt, können die beiden Stellen nicht auseinanderlaufen.

> **Wo liegen Passwort und Schlüssel danach?** Nur noch SOPS-verschlüsselt im Repo — Git ist ihre Sicherung, wie bei allen Pantheon-Secrets. Bei Bedarf liest Rico sie mit `sops -d` aus. Der Schlüssel hat dasselbe Format, das AFFiNEs eigenes Skript erzeugen würde (SEC1-PEM auf `prime256v1`, siehe ADR 3); `-----BEGIN EC PRIVATE KEY-----` steht vor der Verschlüsselung in der ersten Zeile.

> **Was das Skript bewusst nicht tut:** committen. Den Commit macht Claude Code in A.3 zusammen mit Rolle und Datenbank — so landen Secret und Verbraucher im selben Commit.

## A.2 — Rolle und Datenbank *[Claude Code]*

**Prüfung vorab:** Beide Secret-Dateien existieren und sind verschlüsselt:

```bash
grep -c 'ENC\[' infrastructure/controllers/databases/pantheon-pg/affine-db-role-secret.yaml \
  apps/pantheon/affine/affine-secret.yaml
grep -E '^\s+(password|db-password|private\.key):' \
  infrastructure/controllers/databases/pantheon-pg/affine-db-role-secret.yaml \
  apps/pantheon/affine/affine-secret.yaml
# Erwartung: jede Wertzeile beginnt mit ENC[ — kein Klartext
```

`infrastructure/controllers/databases/pantheon-pg/affine-role.yaml`:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: DatabaseRole
metadata:
  name: affine
  namespace: databases
spec:
  cluster:
    name: pantheon-pg
  name: affine
  ensure: present
  login: true
  passwordSecret:
    name: affine-db-role
```

`infrastructure/controllers/databases/pantheon-pg/affine-database.yaml`:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: affine
  namespace: databases
spec:
  cluster:
    name: pantheon-pg
  name: affine
  owner: affine
  # AFFiNE >= 0.21 braucht pgvector (vector-Spalten im Schema, auch ohne KI).
  # CNPG legt die Extension mit Superuser-Rechten an -> der App-User braucht
  # kein CREATE-EXTENSION-Recht.
  extensions:
    - name: vector
      ensure: present
```

In `infrastructure/controllers/databases/pantheon-pg/kustomization.yaml` am Ende anhängen — **Secret und Role vor der Database**:

```yaml
  - affine-db-role-secret.yaml
  - affine-role.yaml
  - affine-database.yaml
```

Build-Check:

```bash
kubectl kustomize infrastructure/controllers/databases/pantheon-pg/ > /dev/null && echo BUILD_OK
```

## A.3 — Committen und verifizieren *[Claude Code; Push: Rico gibt frei]*

```bash
D=infrastructure/controllers/databases/pantheon-pg
git add "$D/affine-db-role-secret.yaml" "$D/affine-role.yaml" "$D/affine-database.yaml" \
  "$D/kustomization.yaml" apps/pantheon/affine/affine-secret.yaml
git commit -m "feat(affine): add database role, database with pgvector and app secret"
git show --stat HEAD                     # Rico Message + Dateiliste zeigen, Freigabe abwarten
git pull --rebase && git push            # erst nach Ricos Freigabe
flux reconcile kustomization flux-system --with-source
flux reconcile kustomization infrastructure-databases-cluster

kubectl get database,databaserole -n databases | grep affine
kubectl get database affine -n databases -o jsonpath='{.status.applied}{"\n"}'
# Erwartung: true   (kurz false ist normal, bis die Rolle existiert)
kubectl cnpg psql pantheon-pg -n databases -- -d affine -tAc \
  "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
# Erwartung: vector|0.8.6
```

> `apps/pantheon/affine/affine-secret.yaml` liegt ab jetzt im Repo, ist aber **inaktiv**: Noch liest keine Flux-Kustomization `apps/pantheon/affine/` (Schalter erst in C.1).

> **Ergebnis 01.11.2026:** Commit `94e9f99`, Flux `infrastructure-databases-cluster` Ready auf dieser Revision. DatabaseRole und Database `affine` nach knapp einer Minute `applied: true`; in PostgreSQL Rolle `affine` (Login ja, Superuser nein), Datenbank `affine` mit Owner `affine`, `vector|0.8.6`.
>
> **Erwartbare Übergangsmeldung (Wettlauf beim RBAC):** Direkt nach dem Reconcile zeigte die DatabaseRole `secrets "affine-db-role" is forbidden: User "system:serviceaccount:databases:pantheon-pg" cannot get resource "secrets"`, und die Database folgerichtig `role "affine" does not exist`. Ursache: Der Instanzmanager las das Secret, bevor der Operator es in die Role `pantheon-pg` (`resourceNames`) eingetragen hatte. Selbstheilend — nicht eingreifen, sondern begrenzt warten:
> ```bash
> kubectl wait databaserole/affine -n databases --for=jsonpath='{.status.applied}'=true --timeout=180s
> kubectl wait database/affine -n databases --for=jsonpath='{.status.applied}'=true --timeout=180s
> ```
> Erst wenn das nach drei Minuten noch scheitert: `kubectl get role pantheon-pg -n databases -o yaml | grep affine-db-role` — fehlt der Eintrag, anhalten.

> **⚠️ Stolperstein 2 — Signatur einer fehlenden Extension.** Steht im Migrationslog später `permission denied to create extension "vector"`, hat CNPG die Extension nicht angelegt (Datenbank-CR prüfen: `kubectl describe database affine -n databases`, Feld `status.message`). Nicht dem User `affine` Superuser-Rechte geben — die Extension gehört in die CR.

---

# Teil B — App-Manifeste (Abend 3 und 4) *[Claude Code; Push: Rico gibt frei]*

## B.1 — Namespace

`apps/pantheon/affine/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: affine
  labels:
    # Das AFFiNE-Image läuft als root (HOME=/root, Pfade unter /root/.affine).
    # 'restricted' würde das verhindern -> 'baseline' (dokumentierter Trade-off,
    # analog Paperless). Härtung: siehe "Bewusst zurückgestellt".
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/warn: baseline
```

## B.2 — App-Secret

Bereits in A.1 von Rico erzeugt und in A.3 committet (`apps/pantheon/affine/affine-secret.yaml`). Nichts zu tun.

## B.3 — Server-Konfiguration

`apps/pantheon/affine/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: affine-config
  namespace: affine
data:
  config.json: |
    {
      "server": {
        "name": "Pantheon Whiteboard",
        "externalUrl": "https://affine.rm-it.org"
      },
      "auth": {
        "allowSignup": false,
        "requireEmailVerification": false
      },
      "copilot": {
        "enabled": false
      }
    }
```

| Schlüssel | Warum |
|---|---|
| `server.externalUrl` | Basis für Einladungs- und Share-Links **und** für die Origin-Prüfung. Bleibt sie leer, baut AFFiNE Links auf `http://localhost:3010`. |
| `auth.allowSignup: false` | Keine Selbstregistrierung; Konten nur über Admin-Setup und CSV-Import (ADR 4). |
| `auth.requireEmailVerification: false` | Ohne SMTP käme nie eine Verifikationsmail an. Vertretbar, weil Access vorgeschaltet und Signup geschlossen ist. |
| `copilot.enabled: false` | Keine KI-Funktionen ohne konfigurierten Provider. |

> **Hinweis:** Unbekannte Schlüssel ignoriert AFFiNE stillschweigend (kein Startfehler). Ein Tippfehler in einem Schlüssel fällt deshalb nur am **Verhalten** auf — nach dem Start gezielt prüfen (Teil D/E).

## B.4 — PVC für den Blob-Storage

`apps/pantheon/affine/pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: affine-storage
  namespace: affine
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: qnap-iscsi
  resources:
    requests:
      storage: 10Gi      # Bilder/Anhänge; erweiterbar, falls allowVolumeExpansion gesetzt (Paperless D.2)
```

## B.5 — Redis

`apps/pantheon/affine/redis.yaml` — wie Paperless B.9, ohne Persistenz:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: affine-redis
  namespace: affine
spec:
  replicas: 1
  selector:
    matchLabels:
      app: affine-redis
  template:
    metadata:
      labels:
        app: affine-redis
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        fsGroup: 999
      containers:
        - name: redis
          # renovate: datasource=docker depName=redis
          image: docker.io/library/redis:7.4-alpine
          imagePullPolicy: IfNotPresent
          args: ["--save", "", "--appendonly", "no"]
          ports:
            - containerPort: 6379
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            seccompProfile:
              type: RuntimeDefault
          resources:
            requests:
              memory: 64Mi
              cpu: 25m
            limits:
              memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: affine-redis
  namespace: affine
spec:
  selector:
    app: affine-redis
  ports:
    - port: 6379
      targetPort: 6379
```

**Abschluss Abend 3** (B.1, B.3–B.5): eine vorläufige `apps/pantheon/affine/kustomization.yaml` mit den bis hierhin vorhandenen Dateien anlegen — so funktioniert der Build-Check schon heute; B.8 ergänzt sie an Abend 4.

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - affine-secret.yaml
  - configmap.yaml
  - pvc.yaml
  - redis.yaml
```

```bash
kubectl kustomize apps/pantheon/affine/ > /dev/null && echo BUILD_OK
git add apps/pantheon/affine/
git commit -m "feat(affine): add namespace, config, storage and redis (not yet reconciled)"
git pull --rebase && git push            # Rico gibt den Push frei
```

## B.6 — Deployment (initContainer + Server)

`apps/pantheon/affine/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: affine
  namespace: affine
spec:
  replicas: 1
  strategy:
    type: Recreate            # RWO-Blob-PVC: alter Pod muss erst loslassen
  selector:
    matchLabels:
      app: affine
  template:
    metadata:
      labels:
        app: affine
    spec:
      # Paperless-Lehre (Stolperstein B): Service-Link-Variablen abschalten.
      # Der Service "affine" würde sonst AFFINE_PORT, AFFINE_SERVICE_HOST, …
      # injizieren — Namensraum-Kollisionsgefahr mit AFFiNEs eigenen AFFINE_*-Variablen.
      enableServiceLinks: false
      securityContext:
        seccompProfile:
          type: RuntimeDefault
      initContainers:
        - name: migrate
          # Gleicher Tag wie der Server-Container — Renovate hebt beide in einem PR.
          # renovate: datasource=docker depName=ghcr.io/toeverything/affine
          image: ghcr.io/toeverything/affine:0.27.4
          imagePullPolicy: IfNotPresent
          command: ["node", "./scripts/self-host-predeploy.js"]
          env:
            - name: DEPLOYMENT_TYPE
              value: selfhosted
            # Reihenfolge wichtig: $(AFFINE_DB_PASSWORD) wird nur expandiert,
            # wenn die Variable VOR DATABASE_URL definiert ist (Stolperstein 3).
            - name: AFFINE_DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: affine-secret
                  key: db-password
            - name: DATABASE_URL
              value: postgresql://affine:$(AFFINE_DB_PASSWORD)@pantheon-pg-rw.databases.svc.cluster.local:5432/affine
            - name: REDIS_SERVER_HOST
              value: affine-redis
            - name: AFFINE_INDEXER_ENABLED
              value: "false"
          securityContext:
            allowPrivilegeEscalation: false
          volumeMounts:
            - name: config
              mountPath: /root/.affine/config
              readOnly: true
            - name: storage
              mountPath: /root/.affine/storage
          resources:
            requests:
              memory: 256Mi
              cpu: 100m
            limits:
              memory: 1Gi
      containers:
        - name: affine
          # renovate: datasource=docker depName=ghcr.io/toeverything/affine
          image: ghcr.io/toeverything/affine:0.27.4
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 3010
          env:
            - name: DEPLOYMENT_TYPE
              value: selfhosted
            - name: AFFINE_DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: affine-secret
                  key: db-password
            - name: DATABASE_URL
              value: postgresql://affine:$(AFFINE_DB_PASSWORD)@pantheon-pg-rw.databases.svc.cluster.local:5432/affine
            - name: REDIS_SERVER_HOST
              value: affine-redis
            # Serverseitige Volltextsuche bräuchte einen Manticore/Elasticsearch-
            # Container -> aus. Suche im Client funktioniert weiterhin.
            - name: AFFINE_INDEXER_ENABLED
              value: "false"
          securityContext:
            allowPrivilegeEscalation: false
          volumeMounts:
            - name: config
              mountPath: /root/.affine/config
              readOnly: true
            - name: storage
              mountPath: /root/.affine/storage
          # /info ist öffentlich, prüft keinen Host-Header und liefert die Version
          # (anders als Paperless kein Host-Header-Workaround nötig).
          startupProbe:
            httpGet:
              path: /info
              port: 3010
            periodSeconds: 10
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /info
              port: 3010
            periodSeconds: 15
          # Bewusst keine livenessProbe: Das Zusammenführen großer Dokumente kann
          # den Event-Loop kurz blockieren -> Neustart mitten in der Arbeit vermeiden.
          resources:
            requests:
              memory: 768Mi
              cpu: 250m
            limits:
              memory: 3Gi     # Doku: 2 GB Minimum, Merge-Spitzen ~1 GB zusätzlich
              cpu: "2"
      volumes:
        - name: config
          projected:
            sources:
              - configMap:
                  name: affine-config
                  items:
                    - key: config.json
                      path: config.json
              - secret:
                  name: affine-secret
                  items:
                    - key: private.key
                      path: private.key
        - name: storage
          persistentVolumeClaim:
            claimName: affine-storage
```

> **⚠️ Stolperstein 3 — `$(VAR)`-Expansion hängt an der Reihenfolge.** Kubernetes ersetzt `$(AFFINE_DB_PASSWORD)` nur, wenn die Variable **weiter oben** in derselben `env`-Liste steht. Steht `DATABASE_URL` davor, landet der Literal-String `$(AFFINE_DB_PASSWORD)` als Passwort in der URL → `password authentication failed for user "affine"`.

> **⚠️ Stolperstein 4 — `DEPLOYMENT_TYPE=selfhosted` nicht vergessen.** Ohne die Variable verhält sich der Server wie AFFiNE Cloud (Lizenz-/Quota-Logik der Cloud). Sie gehört in **beide** Container. Prüfung in C.3: `/info` muss `"type":"selfhosted"` melden.

## B.7 — Service und HTTPRoute

`apps/pantheon/affine/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: affine
  namespace: affine
spec:
  selector:
    app: affine
  ports:
    - port: 80
      targetPort: 3010
```

`apps/pantheon/affine/httproute.yaml` — nur der externe Hostname:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: affine
  namespace: affine
spec:
  parentRefs:
    - name: pantheon-gateway
      namespace: default
  hostnames:
    - affine.rm-it.org
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: affine
          port: 80
```

> **Warum kein `affine.pantheon.local`?** AFFiNE akzeptiert schreibende Browser-Requests nur vom Origin der `externalUrl`. Ein zweiter Hostname bräuchte `server.hosts` in `config.json` und verdoppelt die Testfläche. Im LAN geht der Weg ebenfalls über Cloudflare — für ein Whiteboard ohne Nachteil.

## B.8 — Lokale Kustomization

`apps/pantheon/affine/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - affine-secret.yaml
  - configmap.yaml
  - pvc.yaml
  - redis.yaml
  - deployment.yaml
  - service.yaml
  - httproute.yaml
```

Die vorläufige Fassung von Abend 3 um `deployment.yaml`, `service.yaml` und `httproute.yaml` ergänzen.

> **Korrektur ggü. 1.0:** Kein Eintrag in eine `apps/pantheon/kustomization.yaml` — die gibt es nicht. Wirksam wird das Verzeichnis erst durch die Flux-Kustomization `clusters/pantheon/apps-affine.yaml` in C.1.

Lokaler Build-Check (findet Einrückungs- und Referenzfehler; das verschlüsselte Secret baut kustomize ohne Entschlüsselung mit):

```bash
kubectl kustomize apps/pantheon/affine/ > /dev/null && echo BUILD_OK
```

## B.9 — Renovate-Regel für AFFiNE-Tags

**Hintergrund (verifiziert 27.10.2026):** `renovate.json` aktiviert den Kubernetes-Manager für alle `*.yaml`; er erfasst jede `image:`-Zeile. Einen Regex-Manager für `# renovate:`-Kommentare gibt es **nicht** — der Marker über den `image:`-Zeilen ist Pantheon-Konvention und Lesehilfe, technisch Dokumentation. Renovate sieht die AFFiNE-Manifeste daher ab dem Commit an Abend 3/4, nicht erst nach C.1 — ein früher Renovate-PR ist nur ein Hinweis auf eine neue Version.

AFFiNE veröffentlicht neben `X.Y.Z` auch `X.Y.Z-beta.N`, `stable-<hash>`, `canary-<hash>`, `YYYY.M.D-canary.N` und `candidate-<lauf>-<versuch>`. Die Docker-Versionierung von Renovate sollte diese nicht vorschlagen; die Regel macht es explizit. In `renovate.json` unter `packageRules` anhängen:

```json
{
  "description": "AFFiNE veroeffentlicht neben X.Y.Z auch beta-, canary-, stable-<hash>- und candidate-<lauf>-Tags. Nur reine Release-Versionen zulassen. Beide image-Zeilen (initContainer migrate + Server) stehen im selben Deployment und werden gemeinsam angehoben.",
  "matchPackageNames": ["ghcr.io/toeverything/affine"],
  "allowedVersions": "/^\\d+\\.\\d+\\.\\d+$/"
}
```

Prüfung, dass die Datei gültiges JSON bleibt:

```bash
python3 -m json.tool renovate.json > /dev/null && echo JSON_OK
```

**Commit Abend 4:**

```bash
git add apps/pantheon/affine/ renovate.json
git commit -m "feat(affine): add deployment, service, route and renovate rule (not yet reconciled)"
git pull --rebase && git push            # Rico gibt den Push frei
```

---

# Teil C — Rollout und interne Verifikation (Abend 5) *[Claude Code; Push: Rico gibt frei]*

## C.1 — Flux-Kustomization anlegen und ausrollen

Das ist der Schalter: Erst mit dieser Datei liest Flux `apps/pantheon/affine/`. Abgeleitet aus `clusters/pantheon/apps-paperless.yaml` (0.4).

`clusters/pantheon/apps-affine.yaml`:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps-affine
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./apps/pantheon/affine
  prune: true
  wait: false
  decryption:
    provider: sops
    secretRef:
      name: sops-age
```

```bash
git add clusters/pantheon/apps-affine.yaml
git commit -m "feat(affine): reconcile affine 0.27.4 via flux (pantheon-pg backed, migrate as initContainer)"
git pull --rebase && git push            # Rico gibt den Push frei
flux reconcile kustomization flux-system --with-source
flux get kustomizations apps-affine
# Erwartung: READY True, Revision = soeben gepushter Commit
kubectl rollout status deploy/affine -n affine --timeout=10m
# Erwartung: deployment "affine" successfully rolled out
kubectl get pods -n affine
```

> **Kein `kubectl get pods -w`:** Ein Watch endet nie und blockiert eine Claude-Code-Sitzung. `rollout status` wartet mit Zeitlimit und endet mit einem eindeutigen Ergebnis.

Erwarteter Verlauf, falls man zwischendurch `kubectl get pods -n affine` aufruft:

```
affine-redis-…   1/1   Running
affine-…         0/1   Init:0/1          ← Migration läuft
affine-…         0/1   PodInitializing
affine-…         0/1   Running           ← startupProbe wartet
affine-…         1/1   Running
```

> Ein oder zwei `Init:Error`/`Init:CrashLoopBackOff` direkt nach dem ersten Apply sind unkritisch, wenn Redis noch nicht bereit war — der initContainer wird neu gestartet. Dauerhaft im Init-Zustand oder `rollout status` läuft ins Zeitlimit → C.2.

## C.2 — Migrationslog lesen

```bash
kubectl logs -n affine deploy/affine -c migrate | grep -vE "^\s*$" | tail -25
```

Erwartung (sinngemäß):
- `fixing failed migrations.` → `running prisma migrations.` → Liste angewandter Migrationen bzw. `All migrations have been successfully applied.`
- `running data migrations.` ohne Stacktrace

**Und — das ist der Prüfpunkt für ADR 3 — die folgende Zeile darf NICHT erscheinen:**

```
creating config file [/root/.affine/config/private.key].
```

Erscheint sie, kam der Schlüssel nicht aus dem Secret an (Projektion prüfen: `kubectl exec -n affine deploy/affine -- ls -la /root/.affine/config/`). Bei einem read-only Mount würde das Skript dann ohnehin mit `EROFS` abbrechen.

| Fehlerbild im Log | Ursache |
|---|---|
| `password authentication failed for user "affine"` | Stolperstein 3 (Reihenfolge) oder Passwörter der beiden Secrets weichen ab |
| `permission denied to create extension "vector"` | Stolperstein 2 — Extension fehlt in der DB |
| `ENOTFOUND affine-redis` / Redis-Timeout | Redis noch nicht bereit — abwarten |
| `Invalid … DATABASE_URL` | Sonderzeichen im Passwort — Stolperstein 1 |

## C.3 — Server antwortet und meldet die richtige Version

```bash
kubectl run curltest --rm -i --quiet --image=curlimages/curl --restart=Never -n affine -- \
  curl -s http://affine/info
# Erwartung: {"compatibility":"0.27.4","message":"AFFiNE 0.27.4 Server","type":"selfhosted",…}

kubectl get httproute -n affine affine \
  -o jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}{"\n"}'
# Erwartung: True
```

> `-i` ohne `-t`: läuft auch ohne Terminal (Claude Code). `kubectl run` fragt in Claude Code nach Freigabe. Der `curltest`-Pod im `baseline`-Namespace ist unkritisch. Ohne Status-Block an der HTTPRoute → Teil 0.3 (Cilium-Operator).

---

# Teil D — Externer Zugriff und Admin-Konto (Abend 6) *[Rico; Gegenproben: Claude Code]*

> **Reihenfolge ist hier sicherheitsrelevant:** erst die Access-Application, dann der DNS-Eintrag, dann sofort das Admin-Konto. Sobald der CNAME steht, ist AFFiNE über den gesunden Tunnel erreichbar — und der erste Besucher von `/admin` wird Administrator (ADR 4).

## D.1 — Access-Application anlegen

**Zero Trust Dashboard → Access → Applications → Add an application → Self-hosted**:

1. **Application name:** `AFFiNE`. **Session duration:** z.B. 24 h (siehe Stolperstein 6).
2. **Public hostname:** Subdomain `affine`, Domain `rm-it.org`.
3. **Identity providers:** **One-time PIN**.
4. **Policy:** Name `affine-allow`, **Action: Allow**, **Include → Emails:** **vorerst nur Ricos Adresse**.
5. Speichern.

## D.2 — DNS-Route setzen

```bash
cloudflared tunnel route dns pantheon-apps affine.rm-it.org
```

Kontrolle von einem Gerät außerhalb (Mobilfunk): `https://affine.rm-it.org` → Cloudflare fragt die E-Mail ab → OTP → AFFiNE lädt.

## D.3 — Admin-Konto anlegen (sofort)

1. `https://affine.rm-it.org/admin` öffnen — AFFiNE leitet auf „Create admin account".
2. Name, E-Mail, Passwort vergeben.
3. Danach erscheint das Admin-Panel. Unter **Settings** gegenprüfen: Server-Name `Pantheon Whiteboard`, Signup deaktiviert, externe URL korrekt — damit ist bestätigt, dass `config.json` gelesen wurde.

> **⚠️ Stolperstein 5 — Passwortlänge maximal 32 Zeichen.** AFFiNEs Default ist `min: 8, max: 32`. Passwortmanager-Generatoren mit 40+ Zeichen werden abgelehnt. Auf 32 Zeichen begrenzen (gilt auch für das Partner-Konto in E.1).

> **Passkeys erst jetzt sinnvoll:** Passkeys sind an den Hostnamen gebunden. Da `affine.rm-it.org` der endgültige Name ist, kann man sie ab hier bedenkenlos einrichten.

## D.4 — Gegenprobe: Registrierung ist geschlossen

In einem privaten Browserfenster (nach Access-OTP) auf der Login-Seite eine neue, unbekannte E-Mail eingeben. Erwartung: **kein** Registrierungsweg. Erscheint ein Registrierungsformular, wurde `auth.allowSignup` nicht übernommen → ConfigMap-JSON prüfen (Tippfehler werden still ignoriert, siehe B.3).

---

# Teil E — Partner-Zugang und Kollaborationstest (Abend 7) *[Rico; Datenbank-Gegenprobe: Claude Code]*

## E.1 — Partner-Konto per CSV-Import

1. Lokal eine Datei `affine-users.csv` anlegen (Spaltenreihenfolge wie die Vorlage im Import-Dialog — dort im Zweifel die Vorlage herunterladen):
   ```
   Username,Email,Password
   <Name>,<partner@example.org>,<Passwort max. 32 Zeichen>
   ```
2. **Admin-Panel → Accounts → Import** → Datei hochladen.
3. Datei lokal löschen (`rm affine-users.csv`) — sie enthält ein Klartext-Passwort.
4. Das Passwort dem Partner auf sicherem Weg geben; er kann es nach dem ersten Login im Profil ändern.

> **Passwort vergessen ohne SMTP:** Admin-Panel → Accounts → Menü am User → **Reset Password** zeigt einen Reset-Link zum manuellen Weitergeben.

## E.2 — Partner in Access freischalten

**Zero Trust → Access → Applications → AFFiNE → Policy `affine-allow`** → Partner-Adresse unter **Include → Emails** ergänzen.

> Mail-Scanning-Falle wie bei Paperless (A.4): Nutzt der Partner ein Postfach mit Link-Scanner, `noreply@notify.cloudflare.com` dort auf die Allowlist — sonst ist der PIN „bereits verwendet".

## E.3 — Server-Workspace anlegen (nicht lokal!)

> **⚠️ Stolperstein 7 — lokale Workspaces werden nicht geteilt.** AFFiNE kennt lokale Workspaces (nur im Browser-Speicher des Geräts) und Server-Workspaces. Echtzeit-Kollaboration gibt es **nur** im Server-Workspace. Ein versehentlich lokal angelegter Workspace lässt sich weder teilen noch sieht der Partner ihn — und er wäre auch nicht in der Datenbank, also nicht im Backup.

1. Als Rico in AFFiNE einloggen → Workspace-Liste oben links → **neuen Workspace** anlegen und dabei den Server **Pantheon Whiteboard** als Speicherort wählen.
2. Kontrolle: In den **Workspace-Einstellungen** muss der Workspace dem Server zugeordnet sein. Steht er auf lokal, dort die Synchronisation mit dem Server aktivieren.
3. Gegenprobe Datenbank:
   ```bash
   kubectl cnpg psql pantheon-pg -n databases -- -d affine -tAc "SELECT count(*) FROM workspaces;"
   # Erwartung: >= 1
   ```

## E.4 — Partner einladen

**Workspace-Einstellungen → Members → Invite**, eine der beiden Varianten:
- **Per E-Mail-Adresse** des importierten Partner-Kontos → der Partner sieht die Einladung über die **Benachrichtigungsglocke** in AFFiNE und nimmt sie dort an.
- **Einladungslink** mit Ablaufzeit erzeugen und dem Partner schicken.

Beide Wege funktionieren ohne Mailversand. Free-Self-Hosting erlaubt bis zu 10 Mitglieder pro Workspace.

## E.5 — Live-Test: das eigentliche Ziel

1. Rico und Partner (oder Rico in einem zweiten Browser) öffnen **dieselbe** Seite im **Edgeless**-Modus.
2. Einer zeichnet eine Form, setzt einen Notizzettel, fügt ein Bild ein.
3. **Erwartung:** Alles erscheint beim anderen innerhalb von 1–2 Sekunden, inklusive Cursor-Präsenz.
4. **Bild-Test:** Seite in einem frischen privaten Fenster öffnen — das Bild muss laden (beweist den Blob-Pfad PVC → Server → Browser).

**WebSocket prüfen** (Safari: Entwickler → Web-Inspector → Netzwerk; Chrome: DevTools → Network → Filter `WS`):

- Erwartet: eine `socket.io`-Verbindung mit Status **101 Switching Protocols**, die offen bleibt.

> **⚠️ Stolperstein 8 — Sync läuft, aber nur über Polling.** AFFiNE akzeptiert per Default `websocket` **und** `polling`. Scheitert der WebSocket-Upgrade irgendwo auf der Strecke (Cloudflare → cloudflared → Envoy → Pod), fällt socket.io still auf HTTP-Long-Polling zurück: Die Zusammenarbeit funktioniert, aber spürbar träger. Im Netzwerk-Tab sieht man dann viele `socket.io/?…transport=polling`-Requests statt einer 101-Verbindung. Prüfreihenfolge:
> 1. Cloudflare-Dashboard → Zone `rm-it.org` → **Network → WebSockets** muss **an** sein (Default).
> 2. Bricht die 101-Verbindung regelmäßig nach kurzer Zeit ab: Request-Timeout der Route abschalten und erneut testen:
>    ```yaml
>    rules:
>      - matches: [...]
>        timeouts:
>          request: "0s"     # Gateway API: 0s = kein Timeout
>        backendRefs: [...]
>    ```
>    Erst einbauen, wenn das Symptom auftritt — nicht vorsorglich.

> **⚠️ Stolperstein 6 — Access-Session läuft ab.** Endet die Cloudflare-Access-Session während der Arbeit, kann der WebSocket nicht neu verbinden (kein gültiges Access-Cookie) — die Seite lädt neu und fragt das OTP ab. Nichts geht verloren (AFFiNE puffert lokal), aber die Session-Dauer in D.1 nicht zu kurz wählen.

---

# Teil F — Betrieb: Backup und Updates (Abend 8) *[Claude Code; Backup-Auslösung: Rico gibt frei]*

## F.1 — Was ist wo gesichert?

| Datenart | Ort | Sicherung | Status |
|---|---|---|---|
| Whiteboards, Dokumente, Konten, Workspaces, Admin-Panel-Settings | DB `affine` in `pantheon-pg` | Barman Plugin: WAL-Archiving + tägliches Base-Backup → Hetzner Object Storage | ✅ automatisch ab Teil A |
| `config.json` | ConfigMap | Git | ✅ |
| `private.key`, DB-Passwort | SOPS-Secrets | Git (verschlüsselt) | ✅ |
| Bilder, Anhänge, Avatare | PVC `affine-storage` (QNAP-iSCSI) | nur lokal auf der QNAP | ⚠️ zurückgestellt (Punkt 1) |

**Verifikation — die neue Datenbank ist im Backup:** Ein On-Demand-Base-Backup des Shared-Clusters auslösen (wie `rezept-cnpg-backup-pantheon.md`, Teil E):

```bash
kubectl cnpg status pantheon-pg -n databases | grep -A6 "Continuous Backup"
# Erwartung: Working WAL archiving: OK
kubectl cnpg backup pantheon-pg -n databases \
  --method plugin --plugin-name barman-cloud.cloudnative-pg.io
kubectl get backup -n databases --sort-by=.metadata.creationTimestamp | tail -2
# Erwartung: neuestes Backup "completed"
```

> Ein Barman-Base-Backup ist **physisch** und umfasst den ganzen Cluster — die Datenbank `affine` ist damit enthalten, ohne dass irgendetwas pro App konfiguriert werden muss. Das ist der Kern von ADR 1.

## F.2 — Update-Regeln (GitOps, Renovate)

**Grundsätze:**
- Image ist auf einen konkreten Stable-Tag gepinnt (`0.27.4`), `imagePullPolicy: IfNotPresent`, Renovate-Marker (Konvention, siehe B.9). **Nie** `stable` ins Manifest.
- Die `packageRule` aus B.9 lässt nur `X.Y.Z`-Tags zu.
- initContainer und Server tragen **immer denselben Tag**. Renovate erfasst beide `image:`-Zeilen im selben Deployment und hebt sie in einem PR an — beim manuellen Editieren beide ändern.
- Die Prisma-Migrationen im initContainer **ändern das Schema ohne Rückweg**. Ein Image-Rollback allein repariert eine fehlgeschlagene Migration nicht.

**Ablauf je Renovate-PR:**

| Schritt | Patch (`0.27.4 → 0.27.5`) | Minor (`0.27.x → 0.28.0`) |
|---|---|---|
| 1. Release-Notes lesen | auf Breaking-Hinweise prüfen | **Pflicht:** Breaking Changes, Client-Kompatibilität, Konfig-Änderungen |
| 2. Backup-Lage | letztes Backup `completed` | zusätzlich **On-Demand-Backup** (F.1) direkt vor dem Merge |
| 3. Partner informieren | — | kurz Bescheid geben (kurze Downtime, Neuladen) |
| 4. Merge + Reconcile | `git pull --rebase && flux reconcile kustomization flux-system --with-source` | dito |
| 5. Verifikation | C.2 (Migrationslog), C.3 (`/info` = neue Version), Whiteboard mit Bild öffnen | dito + E.5 (Live-Test) |

> **Beispiel aus 0.27:** Ab Server 0.27 synchronisieren nur noch Clients ab 0.26. Für den Browser irrelevant (der Web-Client kommt vom Server und hat immer dieselbe Version) — für native Apps wäre es ein Bruch. Genau solche Zeilen sind der Grund für Schritt 1.

> **Renovate und AFFiNE-Tags:** Neben `0.27.4` existieren `0.27.5-beta.1`, `2026.10.x-canary.NNN`, `stable-<hash>` und `candidate-<lauf>-<versuch>`. Die Regel aus B.9 lässt nur `X.Y.Z` zu. Den **ersten** AFFiNE-PR trotzdem bewusst ansehen: Er muss auf eine reine `X.Y.Z`-Version zeigen und **beide** `image:`-Zeilen im Deployment anheben.

**Rückweg bei misslungener Migration (nur beschrieben, im Notfall anwenden):**
1. `kubectl scale deploy/affine -n affine --replicas=0` (verhindert weitere Schreibvorgänge).
2. Restore-Cluster aus Barman in einen Wegwerf-Namespace (`rezept-cnpg-backup-pantheon.md`, Teil F), Zielzeitpunkt vor dem Merge (PITR).
3. Aus dem Restore-Cluster `pg_dump -Fc -d affine`, in `pantheon-pg` Datenbank `affine` leeren und per `pg_restore` einspielen.
4. Image-Tag per Git-Revert auf die alte Version, reconcilen, hochskalieren.

> Der Weg über den Restore-Cluster ist nötig, weil ein PITR-Restore direkt am Shared-Cluster **alle** Apps zurücksetzen würde.

---

## Definition of Done

**Sechs-Punkte-Checkliste (Pantheon-Standard):**

| # | Punkt | Umsetzung |
|---|---|---|
| 1 | Routing über Gateway API | `httproute.yaml` → `pantheon-gateway`, `Accepted: True` (C.3) |
| 2 | StorageClass `qnap-iscsi` | Blob-PVC `affine-storage` (B.4) |
| 3 | PostgreSQL-Connection | `pantheon-pg-rw…:5432`, eigene DB `affine`, Rolle + DB deklarativ (Teil A) |
| 4 | Frische SOPS-Secrets | `affine-db-role` (databases), `affine-secret` (affine) |
| 5 | PodSecurity | Redis `restricted`-konform; AFFiNE-Namespace `baseline` (root-Image, dokumentierter Trade-off); `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false` |
| 6 | Renovate | Marker über AFFiNE (beide Container) und Redis; `packageRule` nur `X.Y.Z` (B.9) |

**AFFiNE-spezifisch:**

| # | Punkt | Nachweis |
|---|---|---|
| 6a | Flux-Kustomization | `clusters/pantheon/apps-affine.yaml` mit SOPS, `wait: false`, `READY True` (C.1) |
| 7 | pgvector deklarativ | `extensions` in der `Database`-CR, `pg_extension` zeigt `vector` (A.3) |
| 8 | Server-Schlüssel stabil | Migrationslog ohne `creating config file […private.key]` (C.2) |
| 9 | Admin hinter Access angelegt | Access-App vor DNS, Admin-Setup erledigt (D.1–D.3) |
| 10 | Registrierung geschlossen | Gegenprobe D.4 |
| 11 | Partner kann mitarbeiten | Konto importiert, in Access freigeschaltet, Workspace-Mitglied (E.1–E.4) |
| 12 | Live-Kollaboration | E.5 grün, WebSocket `101` |
| 13 | DB im Backup verifiziert | On-Demand-Backup `completed` nach Anlage der DB (F.1) |
| 14 | Update-Weg definiert | F.2, erster Renovate-PR bewusst geprüft |

---

## Bewusst zurückgestellt

Jeder Punkt mit dem Risiko, das bis zur Umsetzung besteht. Reihenfolge = empfohlene Priorität.

1. **Off-site-Sicherung des Blob-Storage.** *Risiko:* Bilder und Anhänge liegen nur auf der QNAP; ein NAS-Totalausfall ließe die Whiteboards ohne eingefügte Bilder zurück (Formen, Text, Notizen in der DB bleiben erhalten). *Interim:* das iSCSI-LUN von `affine-storage` in die QNAP-Snapshot-Planung aufnehmen. *Umsetzung später:* rclone-CronJob nach dem Muster Paperless E.6 (eigener Storage-Box-Sub-Account, Ziel-Unterverzeichnis statt Wurzel — Stolperstein U, `podAffinity` wegen RWO wie Paperless E.3) **oder** Blob-Provider `aws-s3` auf einen eigenen Hetzner-Bucket (dann gehört `config.json` in ein SOPS-Secret statt in eine ConfigMap).
2. **SMTP / Mailer.** *Risiko:* keine Benachrichtigungsmails, Passwort-Reset nur über den Admin-Link (E.1). Für zwei Nutzer akzeptabel.
3. **Native Apps (iPad, macOS-Desktop) über Access.** *Risiko:* Die Apps haben keine Browser-Session und scheitern am Access-Gate. *Interim:* AFFiNE im Browser nutzen — auch auf dem iPad in Safari. *Später:* Access-Service-Token oder Bypass-Policy für die API-Pfade; vorher Client-Kompatibilität (≥ 0.26 bei Server 0.27) prüfen.
4. **Serverseitige Volltextsuche** (Indexer mit Manticore). Ohne: Suche läuft clientseitig, bei vielen Workspaces langsamer.
5. **Freeform-Bestand.** Freeform hat kein offenes Exportformat; bestehende Boards nur als PDF/Bild exportieren und als Anhang/Bild in AFFiNE ablegen.
6. **`restricted`-Härtung.** Das Image läuft als root; ob es mit `runAsNonRoot` und umgebogenem `HOME` startet, ist ungeprüft — eigenes Vorhaben, nicht nebenbei.
7. **Monitoring.** Fehlgeschlagene Migrationen fallen nur beim Öffnen auf. Fügt sich in den Observability-Einstieg (Paperless E.7 / Monitoring-Rezept CT 110–112) ein: `kube_pod_init_container_status_restarts_total{namespace="affine"}`.
8. **OIDC über Keycloak**, sobald der OpenCloud-Stack steht (AFFiNE unterstützt OIDC im Admin-Panel).
9. **Homepage-Kachel** (Block B).

---

## Rezept-Changelog

**1.1.1 (01.11.2026)** — Erkenntnisse aus Abend 2 (Teil A live).
- **A.1 als lokales Skript:** Statt des eingefügten Befehlsblocks verweist A.1 auf `wartung/scripts/affine-a1-secrets.sh`. Das Skript liegt bewusst nur lokal (`.git/info/exclude`), bricht beim ersten Fehler ab, überschreibt nichts und entfernt unverschlüsselte Reste. Befund dazu: Nach dem ersten Versuch an Abend 2 lagen weder die beiden Dateien noch `apps/pantheon/affine/` im Repository (Ursache nicht geklärt); der Lauf mit dem Skript war erfolgreich.
- **A.3 Staging und Push:** Dateien einzeln stagen statt `git add` auf das ganze Verzeichnis (CLAUDE.md: nur die Dateien des Schritts); vor dem Push Commit-Message und `git show --stat HEAD` zeigen und Ricos Freigabe abwarten. Von Rico am 01.11.2026 bestätigt.
- **A.3 Übergangsmeldung dokumentiert:** `secrets "affine-db-role" is forbidden` an der DatabaseRole direkt nach dem Reconcile ist ein Wettlauf mit der RBAC-Aktualisierung des Operators und heilt sich selbst; `kubectl wait` statt Eingreifen. Ergebnisse von Teil A eingetragen.

**1.1 (01.11.2026)** — Erkenntnisse aus Abend 1 (Teil 0 live) und Umstellung auf Umsetzung mit Claude Code.
- **Korrektur Flux-Struktur:** Pantheon hat eine Flux-Kustomization pro App (`clusters/pantheon/apps-<name>.yaml`), keine gemeinsame über `apps/pantheon/`. B.8 ohne Eintrag in `apps/pantheon/kustomization.yaml`; neuer Schalter `clusters/pantheon/apps-affine.yaml` in C.1 (abgeleitet aus `apps-paperless.yaml`). Repository-Struktur und Definition of Done (6a) angepasst.
- **Secrets in einem Block (A.1):** Beide Secrets entstehen in einem Befehlsblock, den Rico im eigenen Terminal ausführt; die alte B.2 hing an einer Shell-Variable über Teil A und B hinweg. Klartexte nur in Variablen und `mktemp`-Datei, danach gelöscht. Claude Code prüft nur `ENC[`.
- **Abendplan mit Rollen:** acht Abende, Kennzeichnung [Rico] / [Claude Code] an jedem Teil; vorläufige `kustomization.yaml` an Abend 3, damit der Build-Check jeden Abend läuft.
- **0.2 ohne Platzhalter:** `<VERSION>` in einer `for`-Schleife führte zu `syntax error near unexpected token '<'`. Jetzt `V=0.27.4` und Release-`latest` + Digest-Vergleich. Hinweis: Der Installationsbefehl der Paketseite (`candidate-…`) zeigt nicht die stabile Version.
- **Renovate (B.9):** Kein Regex-Manager in `renovate.json` — der `# renovate:`-Marker ist Konvention, der Kubernetes-Manager erfasst jede `image:`-Zeile. Neue `packageRule` lässt für AFFiNE nur `X.Y.Z` zu.
- **Agenten-taugliche Befehle:** `kubectl rollout status --timeout` statt `get pods -w`; `kubectl run … -i` statt `-it`.
- **Teil-0-Ergebnisse eingetragen:** pgvector `0.8.6` (ImageCatalog `18.6-standard-trixie`), Gateway 3/3, Release `v0.27.4`.

**1.0 (17.10.2026)** — Erstfassung als Schnell-Rezept.
- ADR 1–4: DB in `pantheon-pg` mit deklarativer pgvector-Extension; Migration als initContainer (Renovate-/Immutable-Job-Lehre); `config.json` + selbst erzeugter `private.key` als projiziertes Volume; Access-Gate vor DNS, geschlossene Registrierung, Partner per CSV-Import, Einladung ohne SMTP.
- Faktenbasis gegen AFFiNE-Quellcode `v0.27.4` geprüft: `self-host-predeploy.js` (schreibt `private.key`, wenn sie fehlt), `prelude.ts` (lädt sie als `AFFINE_PRIVATE_KEY`), Setup-Controller (erster User wird Admin), Auth-Defaults (`allowSignup: true`, Passwort max. 32), WebSocket-Transports (`websocket` + `polling`), GraphQL-Schema (`createInviteLink`, In-App-Einladungen).
- Stolpersteine 1–8 vorab eingebettet (URL-sicheres Passwort, fehlende Extension, `$(VAR)`-Reihenfolge, `DEPLOYMENT_TYPE`, Passwortlänge, Access-Session, lokale Workspaces, Polling-Fallback).
- **Noch nicht live verifiziert** — Erwartungswerte nach dem ersten Durchlauf abgleichen (→ 1.1).

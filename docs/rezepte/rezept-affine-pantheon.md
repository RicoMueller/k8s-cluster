# Kochrezept: AFFiNE auf Pantheon (Whiteboard statt Apple Freeform)

> Schnell-Rezept für einen Nachmittag: AFFiNE als kollaboratives Whiteboard auf dem Pantheon-Cluster, von außen über Cloudflare Tunnel erreichbar (Access-Gate seit 04.11.2026 per Bypass gelockert, ADR 4), gemeinsam mit einer zweiten Person live bearbeitbar. Datenbank im Shared-Cluster `pantheon-pg` (automatisch im Barman-Backup), Updates ausschließlich über Renovate-PRs und Flux. Seit Version 1.5 verschickt AFFiNE Systemmails über IONOS als `noreply@rm-it.org` (ADR 5, Teil G).
>
> Bewusst schlank: Alles, was die Nutzung verhindern oder stark einschränken würde, ist drin. Komfort- und Härtungsthemen stehen gesammelt unter **„Bewusst zurückgestellt"** — jeweils mit dem Risiko, das man bis dahin trägt.

*Rezeptversion: 1.5.2 — November 2026 · Cluster: Pantheon · Zielversion: AFFiNE 0.27.4*

> **Status:** Teil 0 am 27.10.2026 und Teil A am 01.11.2026 live verifiziert (Ergebnisse jeweils im Teil eingetragen). Teile B und C am 01.11.2026 mit dem Rollout live verifiziert, Teil D am 01.11.2026, Teil E am 08.11.2026 abgeschlossen (E.1–E.3 und Einladungslink am 01.11.2026, E.4 Beitritt per Link am 04.11.2026, E.5 Live-Test und E.6 native Apps am 08.11.2026). **Rezept am 08.11.2026 abgeschlossen**; offen ist nur noch der erste Renovate-Pull-Request für AFFiNE (F.2) und die Punkte unter „Bewusst zurückgestellt". Teil F am 01.11.2026 live verifiziert (erster Renovate-Pull-Request für AFFiNE steht noch aus). **Teil G (Systemmails über IONOS) am 12.11.2026 ergänzt und am 13.11.2026 live verifiziert** (G.1–G.6; SPF, DKIM mit `s1-ionos` und DMARC `pass`, Verifikationsmail aus AFFiNE angekommen). Alle Annahmen sind gegen den AFFiNE-Quellcode (Tag `v0.27.4`: `self-host-predeploy.js`, `prelude.ts`, Setup-Controller, Config-Module) und die CNPG-1.30-Doku geprüft. Nach jedem Abend die Erwartungswerte mit den echten Ausgaben abgleichen und Abweichungen hier nachtragen.

> **Umsetzung mit Claude Code.** Dieses Rezept ist so geschrieben, dass Claude Code (VS Code, Repo `~/k8s-cluster`, Leitplanken in `CLAUDE.md` und `.claude/settings.json`) alle Manifeste anlegt, prüft und committet. Rico greift nur an den mit **[Rico]** markierten Stellen ein: Secrets erzeugen und verschlüsseln, `git push` freigeben, Weboberflächen (Omni-Anmeldung, Cloudflare, AFFiNE-Admin, IONOS). Alles mit **[Claude Code]** markierte erledigt Claude Code selbständig.

---

## Inhalt

- **Zweck** · **Umsetzung in Abendsitzungen** · **Voraussetzungen** · **Hintergrund**
- **Architekturentscheidungen 1–5** (Datenbank · Migration · Konfiguration · Zugang · Systemmails)
- **Repository-Struktur**
- **Teil 0** — Vorab-Checks (Abend 1, ✅)
- **Teil A** — Secrets und Datenbank (Abend 2)
- **Teil B** — App-Manifeste (Abend 3 und 4)
- **Teil C** — Flux-Kustomization, Rollout, interne Verifikation (Abend 5)
- **Teil D** — Externer Zugriff und Admin-Konto (Abend 6)
- **Teil E** — Partner-Zugang und Kollaborationstest (Abend 7)
- **Teil F** — Betrieb: Backup und Updates (Abend 8)
- **Teil G** — Systemmails über IONOS-SMTP (Abend 9)
- **Definition of Done** · **Bewusst zurückgestellt** · **Changelog**

---

## Zweck

Apple Freeform durch AFFiNE ablösen: unendliches Canvas („Edgeless"), Notizzettel, Formen, Verbinder, Bilder, Stift — plus Dokumente und Datenbanken im selben Workspace. Ergebnis dieses Rezepts:

1. AFFiNE läuft unter `https://affine.rm-it.org`. Bis 04.11.2026 abgesichert durch Cloudflare Access (E-Mail-OTP) **vor** dem AFFiNE-Login; seitdem per Bypass gelockert, damit die nativen Apps funktionieren (ADR 4, Nachtrag).
2. Ein Admin-Konto (Rico) und ein Partner-Konto existieren; Selbstregistrierung ist geschlossen.
3. Ein gemeinsamer Server-Workspace, in dem beide gleichzeitig am selben Whiteboard arbeiten.
4. Die Datenbank liegt in `pantheon-pg` und ist damit ohne Zusatzaufwand im WAL-Archiving und den täglichen Barman-Backups nach Hetzner.
5. Image-Updates kommen als Renovate-PR, werden per Flux ausgerollt und migrieren die DB automatisch.
6. *(ab 1.5)* AFFiNE verschickt Systemmails (Passwort ändern/vergessen, E-Mail verifizieren, Einladungen) als `Pantheon Whiteboard <noreply@rm-it.org>` über IONOS — Nutzer setzen ihr Passwort selbst zurück (Teil G).

## Umsetzung in Abendsitzungen

Acht Abende à etwa 30 Minuten, seit 1.5 ein neunter für die Systemmails. Nach jedem Abend kann man aufhören: Die Manifeste unter `apps/pantheon/affine/` werden erst wirksam, wenn am fünften Abend `clusters/pantheon/apps-affine.yaml` entsteht. Nur die Datenbank-Rolle und die Datenbank (Abend 2) gehen sofort live — gewollt, sie laufen über `infrastructure-databases-cluster`.

| Abend | Inhalt | Rezept | Rico | Claude Code | Wirkung im Cluster |
|---|---|---|---|---|---|
| 1 ✅ 27.10. | Vorab-Checks | Teil 0 | Befehle ausgeführt | — | keine |
| 2 ✅ 01.11. | Beide Secrets, Datenbank-Rolle, Datenbank mit pgvector | A.1–A.3 | A.1 im eigenen Terminal, Push freigeben | A.2, A.3, Commit, Verifikation | Rolle + Datenbank live |
| 3 ✅ 01.11. | Namespace, Konfiguration, Speicher, Redis | B.1, B.3–B.5 | Push freigeben | Manifeste, Build-Check, Commit | keine |
| 4 ✅ 01.11. | Deployment, Service, Route, lokale Kustomization, Renovate-Regel | B.6–B.9 | Push freigeben | Manifeste, Build-Check, Commit | keine |
| 5 ✅ 01.11. | Flux-Kustomization `apps-affine`, Rollout, Migrationslog, `/info` | Teil C | Push freigeben, ggf. Omni-Anmeldung | Datei anlegen, Commit, Verifikation | AFFiNE läuft intern |
| 6 ✅ 01.11. | Access-Application, DNS-Eintrag, Admin-Konto — **ohne Pause dazwischen** | Teil D | Cloudflare-Dashboard, `cloudflared`-CLI, Admin anlegen | Gegenproben | extern erreichbar |
| 7 ✅ 08.11. | Partner-Konto, Workspace, Live-Test — E.1–E.3 ✅ 01.11., Einladungssperre per Variante B behoben (Stolperstein 9); E.4 ✅ 04.11.; E.5 und E.6 ✅ 08.11. | Teil E | AFFiNE-Admin, Access-Policy, Test | Datenbank-Gegenprobe | Partner arbeitet mit |
| 8 ✅ 01.11. | Backup-Nachweis, Update-Regeln, Rezept fortschreiben | Teil F | On-Demand-Backup freigeben | Verifikation, Rezeptversion 1.2 | — |
| 9 ✅ 13.11. | Systemmails über IONOS: DNS (SPF, DKIM, ggf. MX), SMTP-Test, Secret, Mailer-Variablen, Funktionstest | Teil G | Cloudflare-DNS, SMTP-Test und Secret im eigenen Terminal, Push freigeben, Funktionstest | DNS-Prüfung, Manifest, Commit, Verifikation | AFFiNE verschickt Mails |

**Gesamtaufwand:** ≈ 3,5 h reine Arbeitszeit.

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
| *(nur Teil G)* Postfach `noreply@rm-it.org` (IONOS Mail Basic, 2 GB, im Domainvertrag inklusive), Weiterleitung an Ricos private Adresse; DNS-Zone `rm-it.org` bei Cloudflare | IONOS-Kundenkonto, angelegt 12.11.2026 |

**Offizielle Dokumentation:**
- [AFFiNE Self-Host — Installation](https://docs.affine.pro/self-host-affine)
- [AFFiNE Self-Host — Environment Variables](https://docs.affine.pro/self-host-affine/references/environment-variables)
- [AFFiNE Self-Host — After Installation](https://docs.affine.pro/self-host-affine/install/after-installation)
- [AFFiNE Self-Host — User Management](https://docs.affine.pro/self-host-affine/administer/user-management)
- [CloudNativePG — Declarative Database Management](https://cloudnative-pg.io/docs/1.30/declarative_database_management)
- [AFFiNE Container-Tags (ghcr.io)](https://github.com/toeverything/AFFiNE/pkgs/container/affine)
- [IONOS — SPF bei externem DNS](https://www.ionos.co.uk/help/domains/configuring-mail-servers-and-other-related-records/using-ionos-spf-to-improve-email-delivery/) · [IONOS — DKIM](https://www.ionos.co.uk/help/domains/configuring-mail-servers-and-other-related-records/email-authentication-with-dkim/) · [IONOS — Mailserver Mail Basic](https://www.ionos.ca/help/index.php?id=14705)

---

## Hintergrund — was AFFiNE braucht

| Komponente | Rolle in Pantheon |
|---|---|
| `ghcr.io/toeverything/affine` | Server **und** Web-Client in einem Image, Port 3010. Läuft als root (`HOME=/root`). |
| Migrations-Skript | `node ./scripts/self-host-predeploy.js` — Prisma-Schema-Migrationen, Daten-Migrationen, legt bei Bedarf `private.key` an. Muss vor jedem Serverstart erfolgreich laufen. |
| PostgreSQL **mit pgvector** | Seit AFFiNE 0.21 Pflicht — das Schema enthält `vector`-Spalten, auch bei abgeschalteter KI. Ein PostgreSQL ohne pgvector lässt die Migration scheitern. |
| Redis | Cache, Queue, Pub/Sub. Keine Persistenz nötig, nichts zu sichern. |
| SMTP *(ab 1.5)* | Externer Dienst: `smtp.ionos.de:587` (STARTTLS), Postfach `noreply@rm-it.org`. Nur für ausgehende Systemmails (ADR 5). |

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
> **Hinweis:** Einstellungen, die man im Admin-Panel ändert, landen in der **Datenbank**, nicht in `config.json`. Für GitOps-Treue alles Dauerhafte in `config.json` pflegen; das Admin-Panel nur für Konten und Einmalaktionen nutzen. Zugangsdaten (SMTP-Passwort, ADR 5) gehören weder in die ConfigMap noch ins Admin-Panel, sondern in ein SOPS-Secret.

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
> - *Offene Registrierung + SMTP:* zusätzlicher Dienst (Mail-Relay, Zugangsdaten, SPF) für zwei Nutzer — „kein spekulatives Tooling". *(Nachtrag 12.11.2026: SMTP kommt mit ADR 5 doch — nicht für die Registrierung, die bleibt geschlossen, sondern weil Nutzer ohne SMTP ihr Passwort nicht selbst ändern können, Stolperstein 10.)*
>
> **Nachtrag 04.11.2026 — Access per Bypass gelockert (Entscheidung Rico).**
> - **Anlass:** Die nativen AFFiNE-Apps (macOS, iOS, iPadOS) haben keine Browser-Session; Cloudflare Access antwortet ihnen mit einer Umleitung zur Anmeldeseite, die Apps scheitern („Bewusst zurückgestellt", Punkt 3).
> - **Entscheidung, in Ricos Worten:** „Der Schutz ist für die App und deren Inhalte sowie die Anzahl an Nutzern unangemessen. Der Mehrwert, die App nutzen zu können, übersteigt den Verlust an Sicherheit deutlich. Bei Paperless ist es auf Grund der Art der Informationen angemessen."
> - **Umsetzung (Cloudflare-Dashboard, nicht im Repository):** Access-Application `AFFiNE` hat die Policy `affine-bypass` (Action **Bypass**, Include **Everyone**) an erster Stelle; `affine-allow` bleibt hinterlegt.
> - **Verbleibender Schutz:** geschlossene Registrierung (`auth.allowSignup: false`); Admin-Konto existiert, das Erster-Besucher-Risiko entfällt; AFFiNE-Login mit Passwort; Drosselung von Anmeldeversuchen durch AFFiNE; TLS am Cloudflare-Edge; keine Portfreigabe am Router (Tunnel).
> - **Abgrenzung:** Paperless bleibt hinter Access mit OTP — Schutzbedarf der Dokumente.
> - **Rücknahme:** Policy `affine-bypass` löschen → Access mit OTP greift sofort wieder (Browser ja, Apps dann nicht mehr).
> - **Neu bewerten, wenn** mehr als zwei Personen AFFiNE nutzen, sensiblere Inhalte dort landen oder die Registrierung geöffnet wird. Dann zugleich die Einladungssperre (B.3, `newAccountShareActionDelay`) wieder aktivieren.
> - **Ergebnis 04.11.2026** (von außen, ohne Anmeldung): `curl -sI https://affine.rm-it.org/` → `HTTP/2 200`; `/info` → `{"compatibility":"0.27.4","message":"AFFiNE 0.27.4 Server","type":"selfhosted","flavor":"allinone"}`; WebSocket-Upgrade auf `/socket.io/?EIO=4&transport=websocket` → `101`. Gegenprobe Paperless: weiterhin `HTTP/2 302` auf `rm-it.cloudflareaccess.com`. Native Apps: iPhone-App am 08.11.2026 erfolgreich mit dem Server verbunden und angemeldet (Weg siehe E.6); macOS-Desktop-App noch nicht bestätigt.
> - **Verworfene Alternativen:** *Cloudflare-Client (WARP) mit „WARP authentication identity"* auf jedem Gerät — voller Schutz, aber zusätzliche Software auf jedem Gerät, auch beim Geschäftspartner, und standardmäßig dessen gesamter Internetverkehr über Cloudflare. *Service-Token* — scheidet aus, weil die AFFiNE-Apps keine eigenen Header (`CF-Access-Client-Id`) senden können. *Bypass nur für API-Pfade* — bringt praktisch nichts, weil die Weboberfläche dieselben Schnittstellen nutzt.

> **⚠️ Stolperstein 11 — „Allow + Everyone" ist kein Bypass.** Bei Cloudflare Access heißt **Allow** mit Include **Everyone**: Jeder darf rein, *nachdem* er sich angemeldet hat — die OTP-Abfrage bleibt, und jede beliebige E-Mail-Adresse kommt per OTP durch. Nur die Action **Bypass** schaltet die Anmeldung ab. Zweite Falle der aktuellen Oberfläche: Policies, die in der **Policy-Liste** angelegt werden, gelten erst, wenn sie der **Application zugeordnet** sind (Application → Policies → vorhandene Policy auswählen → an erste Stelle → Application speichern).
> - **Signatur:** `curl -sI https://affine.rm-it.org/` liefert weiterhin `HTTP/2 302` auf `…cloudflareaccess.com/cdn-cgi/access/login/affine.rm-it.org`; im `meta`-Token der Umleitung steht `"hostname":"affine.rm-it.org"` und `"auth_status":"NONE"`. Der WebSocket-Upgrade liefert `302` statt `101`.
> - **Befund 04.11.2026:** Erster Versuch mit Action *Allow* → unverändert `302`; nach Umstellung auf *Bypass* sofort `200`/`101`.
> - **Prüfung nach jeder Änderung an Access:** die vier Tests aus dem Ergebnis oben (AFFiNE `/`, `/info`, WebSocket, Gegenprobe Paperless).

## Architekturentscheidung 5: Systemmails über das IONOS-Inklusivpostfach `noreply@rm-it.org`

> **Problemstellung.** Ohne SMTP können Nutzer ihr Passwort weder ändern noch selbst zurücksetzen; der einzige Weg ist ein Reset-Link aus dem Admin-Panel, den Rico von Hand weitergibt (Stolperstein 10). Das hat am 08.11.2026 bei Franz bereits einmal nicht funktioniert. Die Domain `rm-it.org` ist bei IONOS registriert; im Domainvertrag ist ein Postfach (Mail Basic, 2 GB) ohne Aufpreis enthalten. Die **DNS-Zone liegt bei Cloudflare** (Tunnel-Routen per `cloudflared tunnel route dns`) — IONOS setzt deshalb keine Mail-Einträge automatisch.
>
> **Entscheidung (Rico, 12.11.2026):**
> 1. **Postfach `noreply@rm-it.org`** bei IONOS als Absender aller AFFiNE-Systemmails. Eingehende Mails (Antworten, Unzustellbarkeitsmeldungen) leitet IONOS an Ricos private Adresse weiter — das wirkt nur, wenn der MX von `rm-it.org` auf IONOS zeigt (G.1).
> 2. **Versand über `smtp.ionos.de`, Port 587 mit STARTTLS**, Anmeldung mit Adresse und Postfach-Passwort. Port 587 statt 465, weil STARTTLS auf 587 ohne Sonderschalter funktioniert; ob AFFiNE für 465 von selbst implizites TLS wählt, ist nicht geprüft.
> 3. **Konfiguration über `MAILER_*`-Umgebungsvariablen** im Server-Container, Passwort als SOPS-Secret `affine-smtp`. Die Variablen haben Vorrang vor `mailer.SMTP` in `config.json`; die ConfigMap bleibt frei von Zugangsdaten (ADR 3).
> 4. **SPF und DKIM für IONOS in der Cloudflare-Zone** (G.2), DMARC im Beobachtungsmodus. Ohne SPF/DKIM landen Reset-Mails leicht im Spam oder werden abgewiesen.
> 5. **Registrierung bleibt geschlossen**, `auth.requireEmailVerification` bleibt `false` (Konten legt nur der Admin an). SMTP dient nur den Komfort- und Selbsthilfe-Funktionen.
>
> **Verhältnis zum Proton-Vorhaben (`claude/rezept-proton-pantheon.md`, Block D):** Das Proton-Rezept sieht denselben Absender über Proton-SMTP vor, ist aber noch nicht umgesetzt und setzt einen Proton-Tarif voraus. IONOS ist bereits bezahlt und sofort nutzbar. Zieht die Mail-Domain später zu Proton um, ändern sich für AFFiNE nur `MAILER_HOST` und das Secret; in der DNS-Zone müssen dann SPF (beide oder nur noch Proton), DKIM und MX gemeinsam umgestellt werden — sonst bricht entweder der Versand über IONOS oder der Empfang über Proton.
>
> **Verworfene Alternativen:**
> - *Weiter ohne SMTP:* Partner hängt bei jedem Passwortwechsel an Rico; Links laufen nach 30 Minuten ab.
> - *Eigener Mailserver oder Relay im Cluster:* Zustellbarkeit von einer privaten IP ist schlecht, eigener Betriebs- und Sicherheitsaufwand — „kein spekulatives Tooling".
> - *Privates Freemail-Konto als Absender:* Absender wäre nicht `@rm-it.org`; Freemail-Anbieter lassen fremde Absenderadressen nicht zu und begrenzen automatisierten Versand.

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
├── affine-smtp-secret.yaml      ← SOPS-verschlüsselt: mailer-password — von Rico erzeugt (Teil G)
├── configmap.yaml               ← config.json
├── pvc.yaml                     ← Blob-Storage (qnap-iscsi)
├── redis.yaml
├── deployment.yaml              ← initContainer migrate + Server (ab Teil G mit MAILER_*)
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
        "requireEmailVerification": false,
        "newAccountShareActionDelay": 0
      },
      "copilot": {
        "enabled": false
      }
    }
```

| Schlüssel | Warum |
|---|---|
| `server.externalUrl` | Basis für Einladungs- und Share-Links **und** für die Origin-Prüfung. Bleibt sie leer, baut AFFiNE Links auf `http://localhost:3010`. Gilt ab Teil G auch für die Links in Systemmails. |
| `auth.allowSignup: false` | Keine Selbstregistrierung; Konten nur über Admin-Setup und CSV-Import (ADR 4). |
| `auth.requireEmailVerification: false` | Ohne SMTP käme nie eine Verifikationsmail an. Vertretbar, weil Access vorgeschaltet und Signup geschlossen ist. Bleibt auch mit SMTP (Teil G) aus: Konten legt nur der Admin an (ADR 5). |
| `auth.newAccountShareActionDelay: 0` | Schaltet die Sperre ab, mit der AFFiNE Konten jünger als 24 h (Default `86400` s) keine Einladungslinks erstellen und keine Mitglieder einladen lässt (Stolperstein 9). Vertretbar, weil nur zwei Personen AFFiNE nutzen, die Registrierung geschlossen ist und Cloudflare Access mit OTP davorsitzt. |
| `copilot.enabled: false` | Keine KI-Funktionen ohne konfigurierten Provider. |

> **⚠️ Einladungssperre wieder aktivieren, sobald sich die Lage ändert.** `newAccountShareActionDelay: 0` ist nur für den Zwei-Personen-Betrieb bei geschlossener Registrierung gedacht (neue Konten legt nur der Admin an). Nutzen **mehr als zwei Personen** AFFiNE oder wird die **Registrierung geöffnet**, die Sperre wieder einschalten: den Eintrag entfernen (Default `86400` s) oder einen passenden Wert setzen. Sonst kann ein frisch angelegtes oder übernommenes Konto sofort Einladungs- und Share-Links verteilen. Siehe „Bewusst zurückgestellt", Punkt 10.

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

`apps/pantheon/affine/redis.yaml` — wie Paperless B.9, ohne Persistenz, gleicher Tag wie `apps/pantheon/paperless/redis.yaml` (dort von Renovate gepflegt):

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
          image: docker.io/library/redis:8.10-alpine
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
A=apps/pantheon/affine
git add "$A/namespace.yaml" "$A/configmap.yaml" "$A/pvc.yaml" "$A/redis.yaml" "$A/kustomization.yaml"
git commit -m "feat(affine): add namespace, config, storage and redis (not yet reconciled)"
git show --stat HEAD                     # Rico Message + Dateiliste zeigen, Freigabe abwarten
git pull --rebase && git push            # erst nach Ricos Freigabe
```

> **Ergebnis 01.11.2026:** Commit `5ff73c7`, `BUILD_OK` mit 6 Ressourcen (Namespace, Secret, ConfigMap, PVC, Deployment, Service), `config.json` gültig. StorageClass `qnap-iscsi` vorhanden (Trident, `allowVolumeExpansion: true`, `reclaimPolicy: Delete`). Im Cluster noch keine Wirkung (kein `apps-affine.yaml`).

## B.6 — Deployment (initContainer + Server)

`apps/pantheon/affine/deployment.yaml`:

> **Ab Teil G (1.5)** kommen im Container `affine` sechs `MAILER_*`-Variablen hinzu — siehe G.5. Der Stand unten ist der von Abend 4.

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

Die vorläufige Fassung von Abend 3 um `deployment.yaml`, `service.yaml` und `httproute.yaml` ergänzen. *(Ab Teil G zusätzlich `affine-smtp-secret.yaml`, siehe G.5.)*

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
A=apps/pantheon/affine
git add "$A/deployment.yaml" "$A/service.yaml" "$A/httproute.yaml" "$A/kustomization.yaml" renovate.json
git commit -m "feat(affine): add deployment, service, route and renovate rule (not yet reconciled)"
git show --stat HEAD                     # Rico Message + Dateiliste zeigen, Freigabe abwarten
git pull --rebase && git push            # erst nach Ricos Freigabe
```

> **Ergebnis 01.11.2026:** Commit `c2a1812`, `BUILD_OK` mit 9 Ressourcen (zusätzlich Deployment `affine`, Service `affine`, HTTPRoute `affine`); `AFFINE_DB_PASSWORD` steht in beiden Containern vor `DATABASE_URL`. `renovate.json` gültig; die Regex `^\d+\.\d+\.\d+$` lässt `0.27.4` zu und weist `0.28.0-beta.1`, `stable-<hash>`, `…-canary.N`, `candidate-…` und `latest` ab. Gegenproben im Cluster: Service `pantheon-pg-rw` (Port 5432) vorhanden, `pantheon-gateway` hat einen Listener `http`/80 mit `allowedRoutes: All`. Im Cluster noch keine Wirkung.

---

# Teil C — Rollout und interne Verifikation (Abend 5) *[Claude Code; Push: Rico gibt frei]* — ✅ 01.11.2026

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
git show --stat HEAD                     # Rico Message + Dateiliste zeigen, Freigabe abwarten
git pull --rebase && git push            # erst nach Ricos Freigabe
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
kubectl get --raw "/api/v1/namespaces/affine/services/affine:80/proxy/info"; echo
# Erwartung: {"compatibility":"0.27.4","message":"AFFiNE 0.27.4 Server","type":"selfhosted",…}

kubectl get httproute -n affine affine \
  -o jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}{"\n"}'
# Erwartung: True
```

> **Korrektur 1.1.1:** Der API-Server-Proxy (`get --raw …/services/affine:80/proxy/…`) ist eine rein lesende Abfrage — kein Test-Pod, kein ungepinntes `curlimages/curl`-Image. Ohne Status-Block an der HTTPRoute → Teil 0.3 (Cilium-Operator).

> **Ergebnis 01.11.2026 (C.1–C.3):** Commit `b1733a5`, `apps-affine` Ready auf dieser Revision. `rollout status` nach gut einer Minute erfolgreich; Pods `affine` und `affine-redis` je `1/1 Running`, 0 Neustarts, PVC `affine-storage` `Bound` (10Gi, `qnap-iscsi`). Migrationslog: `prisma migrate deploy` → `All migrations have been successfully applied.` → `running data migrations.` → `Done 10 migrations`, kein Stacktrace; die Zeile `creating config file […/private.key]` fehlt (ADR 3 bestätigt). `/info`: `{"compatibility":"0.27.4","message":"AFFiNE 0.27.4 Server","type":"selfhosted","flavor":"allinone"}`. HTTPRoute `Accepted=True`, `ResolvedRefs=True`; Gateway 4 Routen, 4 angebunden.
>
> Harmlos: `rollout status` gibt clientseitig `Warning: event bookmark expired` aus (kubectl-Watch, kein Cluster-Befund). Ein grobes `grep -i error` im Migrationslog trifft `fixing failed migrations.` und `ErrorModule dependencies initialized` — beides normale Meldungen.

---

# Teil D — Externer Zugriff und Admin-Konto (Abend 6) *[Rico; Gegenproben: Claude Code]* — ✅ 01.11.2026

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

## D.5 — Gegenproben *[Claude Code]*

Drei Prüfpunkte, die die sicherheitsrelevante Reihenfolge absichern. Alle rein lesend; keine E-Mail-Adressen ausgeben.

```bash
# Vor D.1: kein DNS-Eintrag, kein Wildcard, noch kein Benutzer
dig affine.rm-it.org @1.1.1.1 +noall +comments | grep -oE 'status: [A-Z]+'     # Erwartung: NXDOMAIN
dig test-xyz.rm-it.org @1.1.1.1 +noall +comments | grep -oE 'status: [A-Z]+'   # Erwartung: NXDOMAIN
kubectl cnpg psql pantheon-pg -n databases -- -d affine -tAc "SELECT count(*) FROM users;"   # Erwartung: 0

# Nach D.2, von außen ohne Anmeldung: Access sitzt vor dem ganzen Hostnamen
curl -sI https://affine.rm-it.org/ | grep -iE '^(HTTP|location)'
# Erwartung: HTTP/2 302, location: https://<team>.cloudflareaccess.com/cdn-cgi/access/login/affine.rm-it.org?…
curl -s https://affine.rm-it.org/info | grep -c '"compatibility"'               # Erwartung: 0

# Nach D.3/D.4
kubectl cnpg psql pantheon-pg -n databases -- -d affine -tAc "SELECT count(*) FROM users;"   # Erwartung: 1
kubectl cnpg psql pantheon-pg -n databases -- -d affine -tAc \
  "SELECT count(*) FROM user_features WHERE name = 'administrator';"                         # Erwartung: 1
```

> `dig +short` allein reicht vor D.1 nicht: Eine leere Ausgabe kann auch ein Timeout sein. Erst `status: NXDOMAIN` plus eine Positivkontrolle (z.B. `paperless.rm-it.org` löst auf) belegt, dass der Name wirklich fehlt.

> **Ergebnis 01.11.2026:**
> - **Vor D.1:** `affine.rm-it.org` und `test-xyz.rm-it.org` je `NXDOMAIN` (kein Wildcard), `rm-it.org` `NOERROR`, `paperless.rm-it.org` löst auf; `users` = 0; Pods `affine` und `affine-redis` `1/1 Running`.
> - **Nach D.1/D.2:** DNS `NOERROR` (Cloudflare-Adressen). `/` und `/info` antworten ohne Anmeldung mit `HTTP/2 302` auf `rm-it.cloudflareaccess.com/cdn-cgi/access/login/affine.rm-it.org`, Body ist die Cloudflare-Seite „302 Found", kein AFFiNE-JSON. `users` weiterhin 0 — niemand kam vor dem Admin durch.
> - **D.3/D.4 (Rico):** Admin-Konto angelegt; Settings zeigen Server-Name `Pantheon Whiteboard`, Signup deaktiviert, externe URL `https://affine.rm-it.org` → `config.json` wird gelesen. Im privaten Fenster kein Registrierungsweg.
> - **Nach D.3:** `users` = 1, `user_features` mit `name = 'administrator'` = 1.

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
4. Das Passwort dem Partner auf sicherem Weg geben (getrennt von Link und Benutzername, z.B. per Messenger). Selbst ändern kann er es ohne SMTP **nicht** — siehe Stolperstein 10. **Ab Teil G** ändert er es selbst in den Kontoeinstellungen (Link kommt per Mail).

> **Passwort vergessen ohne SMTP:** Admin-Panel → Accounts → Menü am User → **Reset Password** zeigt einen Reset-Link zum manuellen Weitergeben. **Ab Teil G** nutzt der Nutzer „Passwort vergessen" auf der Anmeldeseite; der Admin-Link bleibt Ausweichweg.

> **⚠️ Stolperstein 10 — Passwort ändern und E-Mail verifizieren brauchen SMTP.** *(Mit Teil G behoben, sobald G.6 grün ist; der Admin-Weg unten bleibt als Ausweichweg gültig, z.B. wenn IONOS nicht erreichbar ist.)* In AFFiNE laufen „Passwort ändern" und „E-Mail verifizieren" (Kontoeinstellungen) über einen Link per Mail. Ohne SMTP scheitert der Versand mit „Der Bestätigungslink konnte nicht gesendet werden" (Befund 04.11.2026, Geschäftspartner). **Weg:** Admin-Panel → Accounts → Menü am User → **Reset Password** → den angezeigten Link über einen sicheren Kanal weitergeben (wie ein Passwort behandeln); der Nutzer setzt sein Passwort darüber selbst, höchstens 32 Zeichen. „E-Mail verifizieren" ist unkritisch, weil `auth.requireEmailVerification: false` gesetzt ist. In der Anleitung für neue Nutzer darauf hinweisen.
>
> **Eigenschaften des Reset-Links** (Quellcode 0.27.4, `createChangePasswordUrl` / `changePassword` / `verification-token.ts`): **30 Minuten** gültig, **einmal** verwendbar, an das **Konto** gebunden (Parameter `userId` und `token`), nicht an eine Anmeldung — die Mutation `changePassword` ist öffentlich. Nach dem Wechsel beendet AFFiNE **alle Sitzungen** des Kontos (`changePasswordAndRevokeSessions`), auch in den Apps; der Nutzer meldet sich überall neu an, der Server bleibt in den Apps eingetragen.
>
> **Passwort hart neu vergeben (Admin):** Ein Admin-Panel-Feld „Passwort setzen" gibt es nicht (`ManageUserInput` kennt nur Name und E-Mail). Stattdessen: Reset-Link erzeugen und **sofort selbst** in einem privaten Browserfenster öffnen, das neue Passwort setzen (höchstens 32 Zeichen) und es dem Nutzer über einen sicheren Kanal geben. Kein Eingriff in die Datenbank nötig.
>
> **Befund 08.11.2026:** Der an Franz geschickte Reset-Link funktionierte nicht (wahrscheinlich abgelaufen, schon verbraucht oder vom Messenger beschädigt — nicht weiter untersucht). Der Weg „Admin setzt das Passwort über einen frischen Link selbst" war erfolgreich.

## E.2 — Partner in Access freischalten

> **Seit 04.11.2026 ohne Wirkung:** Access ist per Bypass gelockert (ADR 4, Nachtrag). Der Schritt bleibt dokumentiert, falls der Bypass zurückgenommen wird.

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
- **Per E-Mail-Adresse** des importierten Partner-Kontos → der Partner sieht die Einladung über die **Benachrichtigungsglocke** in AFFiNE und nimmt sie dort an. *(Ab Teil G zusätzlich als Mail — nicht verifiziert, siehe G.6 Punkt 5.)*
- **Einladungslink** mit Ablaufzeit erzeugen und dem Partner schicken.

Beide Wege funktionieren ohne Mailversand. Free-Self-Hosting erlaubt bis zu 10 Mitglieder pro Workspace.

> **Beitritt per Link = Beitrittsanfrage.** Öffnet der Partner den Einladungslink, legt AFFiNE nur eine **Anfrage** an („Anfrage erfolgreich gesendet … Der Workspace-Besitzer und die Team-Administratoren werden deine Anfrage prüfen.", Mitgliedsstatus „wartet auf Prüfung"). Der Besitzer muss sie unter **Workspace-Einstellungen → Mitglieder** (oder über die Glocke) **annehmen**; erst dann sieht der Partner den Workspace. Befund 04.11.2026.
>
> **Ergebnis 04.11.2026:** Anfrage angenommen. `workspace_members` pro Workspace (ohne E-Mail-Adressen):
> ```
> a60b8545|Rico|owner|active     ← gemeinsamer Workspace
> a60b8545|Franz|member|active
> f3701f72|Franz|owner|active    ← von Franz selbst angelegter Server-Workspace
> ```
> Prüfabfrage: `SELECT left(m.workspace_id, 8), u.name, m.role, m.state FROM workspace_members m JOIN users u ON u.id = m.user_id ORDER BY m.workspace_id, m.created_at;` — eine Zählung über `GROUP BY state` allein summiert über **alle** Workspaces und ist deshalb missverständlich. **Voraussetzung:** Die Einladungssperre für neue Konten ist aus (B.3) oder das einladende Konto ist älter als 24 h — sonst Stolperstein 9.

> **⚠️ Stolperstein 9 — Einladungen für Konten jünger als 24 h gesperrt.** AFFiNE 0.27.4 lässt Konten, die jünger sind als `auth.newAccountShareActionDelay` (Default `86400` s), weder Einladungslinks erstellen noch Mitglieder einladen. Signatur:
> - **Einladungslink:** Meldung „This feature is temporarily unavailable for you." Im Log `action_forbidden` aus `WorkspaceMemberResolver.assertCanInviteOrShare` / `createInviteLink` (HTTP 403).
> - **E-Mail-Invite:** Ohne SMTP endet er in einer **Endlos-Animation**, ohne Fehlermeldung in der Oberfläche. Im Log `WARN [InviteQuotaAssertService] Workspace invite quota rejected` mit `reason: 'quota_subject'`, `limit: 0`, `sourceTrusted: false`. Diese Prüfung liegt im nativen Modul (`server-native.x64.node`); ob `newAccountShareActionDelay: 0` auch sie freigibt, ist **nicht verifiziert** (am 01.11.2026 nicht erneut getestet).
>
> **Befund 01.11.2026** (Abend 7, Admin-Konto 26–35 min alt): `workspace_members` nur `active|1` (Eigentümer), **keine ausstehende Mitgliedschaft** aus dem E-Mail-Invite; im Log 2× `action_forbidden` (`createInviteLink`, 16:44 und 16:48 Uhr) und 1× `InviteQuotaAssertService … quota rejected` (16:45 Uhr). Gegenprobe im Image: `/app/dist/main.js` kennt `auth.newAccountShareActionDelay` („Minimum account age in seconds before new accounts can invite members or create share links.", `default: 86400`, `int().min(0)`), `assertCanInviteOrShare` rechnet direkt damit.
>
> **Lösung (Variante B, Commit `0fe316e`):** `"newAccountShareActionDelay": 0` unter `auth` in `config.json` (B.3), Push, Flux-Reconcile. AFFiNE liest `config.json` nur beim Start, daher Neustart — **von Rico im eigenen Terminal** (direkte Cluster-Änderung, Harte Regel 1):
> ```bash
> kubectl rollout restart deploy/affine -n affine
> ```
> Danach (Claude Code): `kubectl rollout status deploy/affine -n affine --timeout=10m`; Migrationslog fehlerfrei; `/info` wie C.3; `kubectl exec -n affine deploy/affine -c affine -- cat /root/.affine/config/config.json` zeigt den Eintrag (nur `config.json` lesen, nicht `private.key`). **Ergebnis 01.11.2026:** Neustart 18:03 Uhr, Rollout erfolgreich, `No pending migrations to apply.`, 0 Fehlerzeilen, `/info` `0.27.4`/`selfhosted`, `auth` enthält `"newAccountShareActionDelay": 0`; Einladungslink danach von Rico erfolgreich erzeugt, seit dem Neustart kein `action_forbidden` im Log.
>
> **Für künftige Durchläufe:** Abend 6 und 7 mit **mindestens 24 h Abstand** planen **oder** die Einstellung schon in B.3 setzen (so steht es seit 1.1.2 im Rezept).

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

> **⚠️ Stolperstein 6 — Access-Session läuft ab.** *(Entfällt seit 04.11.2026 durch den Bypass, ADR 4; gilt wieder, wenn der Bypass zurückgenommen wird.)* Endet die Cloudflare-Access-Session während der Arbeit, kann der WebSocket nicht neu verbinden (kein gültiges Access-Cookie) — die Seite lädt neu und fragt das OTP ab. Nichts geht verloren (AFFiNE puffert lokal), aber die Session-Dauer in D.1 nicht zu kurz wählen.

> **Ergebnis 08.11.2026:** Live-Test mit Franz erfolgreich — nach Ricos Rückmeldung haben alle offenen Tests funktioniert (gemeinsames Arbeiten im Workspace `a60b8545`). Einzelwerte (Latenz, Bild-Test, WebSocket im Browser) nicht gesondert festgehalten; der WebSocket-Upgrade (`101`) ist seit 04.11.2026 von außen belegt (ADR 4, Nachtrag).

---

## E.6 — Native Apps verbinden

Voraussetzung: Access für AFFiNE per Bypass gelockert (ADR 4, Nachtrag). Bezugsquellen:
- **macOS:** nicht im Mac App Store. `brew install --cask affine` (Homebrew-Cask, stabile Version, Apple Silicon und Intel) oder Download von [affine.pro/download](https://affine.pro/download). Die Desktop-App **aktualisiert sich selbst**, unabhängig von Homebrew und vom Server — siehe Betriebshinweis zur Client-Kompatibilität („Bewusst zurückgestellt", Punkt 3).
- **Windows:** [affine.pro/download](https://affine.pro/download).
- **iPhone/iPad:** App Store. **Android:** Play Store.

1. App öffnen, oben auf den **Namen des aktuellen Workspace** tippen → die Workspace-Liste öffnet sich (Workspace-Wechsler).
2. Dort das **Server-Symbol** bzw. „Server hinzufügen" wählen, `https://affine.rm-it.org` eintragen → **Verbinden**.
3. Mit dem **Konto vom eigenen Server** anmelden (E-Mail und Passwort aus Pantheon).
4. In der Workspace-Liste erscheint der Server „Pantheon Whiteboard" mit den freigegebenen Workspaces.

> **⚠️ Stolperstein 12 — der Server steht nicht in den Einstellungen.** In der iPhone-App gibt es unter *Einstellungen* keinen Eintrag für einen eigenen Server; die Auswahl liegt ausschließlich im **Workspace-Wechsler** (Befund 08.11.2026). Wer sich stattdessen auf dem Startbildschirm der App anmeldet, landet bei der **AFFiNE-Cloud** des Herstellers — ein separates Konto, dessen Workspaces nicht in Pantheon und damit nicht im Backup liegen. Dort nichts anlegen; bei Bedarf abmelden.

> **Bekannter Fehler (Upstream, Stand 08.11.2026):** Seit der iOS-App 0.26.5 melden Nutzer, dass die Anmeldung an selbst gehosteten Servern scheitert („Failed to sign in", `undefined is not an object (evaluating 'e.password')`, oder der Anmelde-Knopf reagiert nicht) — auch bei Servern, die im Browser und in der Desktop-App laufen ([#15169](https://github.com/toeverything/AFFiNE/issues/15169), [#15160](https://github.com/toeverything/AFFiNE/issues/15160)). Bei Pantheon trat das am 08.11.2026 **nicht** auf. Falls doch: App-Version notieren; Ausweichweg ist `https://affine.rm-it.org` in Safari → Teilen → **„Zum Home-Bildschirm"** (Weboberfläche mit App-Symbol, voll funktionsfähig).

> **Ergebnis 08.11.2026:** iPhone-App über den Workspace-Wechsler mit `https://affine.rm-it.org` verbunden, Anmeldung erfolgreich (Rico). Danach nach Ricos Rückmeldung alle offenen Tests erfolgreich, einschließlich der Geräte von Franz. Installationsweg der macOS-App (Homebrew oder Download) nicht festgehalten.

---

# Teil F — Betrieb: Backup und Updates (Abend 8) *[Claude Code; Backup-Auslösung: Rico im eigenen Terminal]* — ✅ 01.11.2026

## F.1 — Was ist wo gesichert?

| Datenart | Ort | Sicherung | Status |
|---|---|---|---|
| Whiteboards, Dokumente, Konten, Workspaces, Admin-Panel-Settings | DB `affine` in `pantheon-pg` | Barman Plugin: WAL-Archiving + tägliches Base-Backup → Hetzner Object Storage | ✅ automatisch ab Teil A |
| `config.json` | ConfigMap | Git | ✅ |
| `private.key`, DB-Passwort | SOPS-Secrets | Git (verschlüsselt) | ✅ |
| SMTP-Passwort `noreply@rm-it.org` *(ab Teil G)* | SOPS-Secret `affine-smtp` | Git (verschlüsselt); zusätzlich im Passwortmanager | ✅ mit G.4 |
| Bilder, Anhänge, Avatare | PVC `affine-storage` (QNAP-iSCSI, PV mit `reclaimPolicy: Delete`) | nur lokal auf der QNAP | ⚠️ zurückgestellt (Punkte 1 und 11) |

**Verifikation — die neue Datenbank ist im Backup:** Ein On-Demand-Base-Backup des Shared-Clusters auslösen (wie `rezept-cnpg-backup-pantheon.md`, Teil E):

```bash
# 1) Claude Code: Ausgangslage
kubectl cnpg status pantheon-pg -n databases | grep -A6 "Continuous Backup"
# Erwartung: Working WAL archiving: OK
kubectl get database affine -n databases -o jsonpath='{.metadata.creationTimestamp}{"\n"}'
# Liegt "Last Successful Backup" vor diesem Zeitpunkt, ist affine bisher nur per WAL gesichert.
```

```bash
# 2) Rico im eigenen Terminal (legt direkt ein Backup-Objekt an -> Harte Regel 1)
kubectl cnpg backup pantheon-pg -n databases \
  --method plugin --plugin-name barman-cloud.cloudnative-pg.io
# Ausgabe: backup/pantheon-pg-JJJJMMTTHHMMSS created  -> Namen an Claude Code geben
```

```bash
# 3) Claude Code: B auf den gemeldeten Namen setzen, begrenzt warten
B=pantheon-pg-20261101181813
kubectl wait backup/$B -n databases --for=jsonpath='{.status.phase}'=completed --timeout=15m
kubectl get backup $B -n databases -o jsonpath='{.status.phase} {.status.startedAt} {.status.error}{"\n"}'
# Erwartung: completed, Start nach der Anlage der Datenbank affine, kein Fehler
```

> **Ergebnis 01.11.2026:** Vorher `Working WAL archiving: OK`, 0 WALs wartend; letztes Base-Backup 03:00 Uhr — **vor** der Anlage von `affine` (16:42 Uhr), also bis dahin nur WAL-gesichert. On-Demand-Backup `pantheon-pg-20261101181813`: `completed`, Methode `plugin`, 18:18:14–18:18:25 Uhr, kein Fehler; `cnpg status` danach `Last Successful Backup: 2026-11-01 18:18:25 CET`.

> Ein Barman-Base-Backup ist **physisch** und umfasst den ganzen Cluster — die Datenbank `affine` ist damit enthalten, ohne dass irgendetwas pro App konfiguriert werden muss. Das ist der Kern von ADR 1.

## F.2 — Update-Regeln (GitOps, Renovate)

**Grundsätze:**
- Image ist auf einen konkreten Stable-Tag gepinnt (`0.27.4`), `imagePullPolicy: IfNotPresent`, Renovate-Marker (Konvention, siehe B.9). **Nie** `stable` ins Manifest.
- Die `packageRule` aus B.9 lässt nur `X.Y.Z`-Tags zu.
- initContainer und Server tragen **immer denselben Tag**. Renovate erfasst beide `image:`-Zeilen im selben Deployment und hebt sie in einem PR an — beim manuellen Editieren beide ändern.
- Die Prisma-Migrationen im initContainer **ändern das Schema ohne Rückweg**. Ein Image-Rollback allein repariert eine fehlgeschlagene Migration nicht.
- *(ab Teil G)* Bei Minor-Updates in den Release-Notes auf Änderungen an den `MAILER_*`-Variablen bzw. `mailer.SMTP` achten; nach dem Update G.6 Punkt 1 (Verifikationsmail) als Kurztest.

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
1. **[Rico]** `kubectl scale deploy/affine -n affine --replicas=0` (verhindert weitere Schreibvorgänge; direkte Cluster-Änderung → Harte Regel 1, daher Rico im eigenen Terminal).
2. Restore-Cluster aus Barman in einen Wegwerf-Namespace (`rezept-cnpg-backup-pantheon.md`, Teil F), Zielzeitpunkt vor dem Merge (PITR).
3. Aus dem Restore-Cluster `pg_dump -Fc -d affine`, in `pantheon-pg` Datenbank `affine` leeren und per `pg_restore` einspielen.
4. Image-Tag per Git-Revert auf die alte Version, reconcilen, hochskalieren.

> Der Weg über den Restore-Cluster ist nötig, weil ein PITR-Restore direkt am Shared-Cluster **alle** Apps zurücksetzen würde.

> **Ergebnis 01.11.2026:** Renovate (CronJob `renovate`, stündlich, Version 44.199.0) lief nach dem Commit von `deployment.yaml` fehlerfrei (`exitCode 0`), es gibt keine Branches für AFFiNE oder Redis. Passt: Neuestes AFFiNE-Release ist `v0.27.4`, Redis steht auf dem Paperless-Stand `8.10-alpine`. Der **erste** AFFiNE-Pull-Request steht damit noch aus und wird beim Eintreffen nach der Tabelle oben geprüft (Definition of Done 14). Nebenbefund außerhalb von AFFiNE: `Workflows update rejection - aborting branch` für `renovate/actions-checkout-7.x` — vermutlich fehlt dem Token das `workflow`-Recht; eigenes Vorhaben.

---

# Teil G — Systemmails über IONOS-SMTP (Abend 9) *[Rico: DNS, SMTP-Test, Secret, Funktionstest; Claude Code: Prüfungen, Manifest, Commit]*

> **Ziel:** AFFiNE verschickt „Passwort ändern", „Passwort vergessen", „E-Mail verifizieren" und E-Mail-Einladungen als `Pantheon Whiteboard <noreply@rm-it.org>` über IONOS (ADR 5). Danach gilt Stolperstein 10 nicht mehr.
>
> **Reihenfolge:** Erst DNS und Zugangsdaten **außerhalb** des Clusters beweisen (G.1–G.3), dann Secret und Manifest (G.4–G.5), dann der Test in AFFiNE (G.6). Scheitert G.3, ist der Cluster nicht beteiligt — die Fehlersuche bleibt klein.
>
> **Ausgangslage 12.11.2026 (Rico, IONOS-Kundenkonto):** Postfach `noreply@rm-it.org` angelegt, Typ Mail Basic, 0 von 2 GB belegt, Anti-Spam aktiv (Mittel), Weiterleitung an Ricos private Adresse, Abwesenheitsnotiz inaktiv, 2-Faktor-Authentifizierung nicht eingerichtet. Passwort im Passwortmanager.

## G.1 — Ausgangslage DNS *[Claude Code]*

Rein lesend, keine Änderung. `@1.1.1.1` umgeht AdGuard (CT 103) und zeigt, was die Welt sieht.

```bash
R=@1.1.1.1
echo "NS:";    dig +short NS rm-it.org $R
echo "MX:";    dig +short MX rm-it.org $R
echo "SPF:";   dig +short TXT rm-it.org $R | grep -i 'v=spf1' || echo "(kein SPF)"
echo "DMARC:"; dig +short TXT _dmarc.rm-it.org $R || true
for s in s1-ionos s2-ionos s42582890; do
  printf "DKIM %-10s CNAME: %s\n" "$s" "$(dig +short CNAME $s._domainkey.rm-it.org $R)"
done
```

**Auswertung:**

| Befund | Bedeutung | Vorgehen in G.2 |
|---|---|---|
| NS = `*.ns.cloudflare.com` | Zone liegt bei Cloudflare (erwartet) — IONOS setzt nichts automatisch | Einträge bei Cloudflare anlegen |
| MX leer | Mail an `@rm-it.org` ist nicht zustellbar; die IONOS-Weiterleitung greift nie | MX auf IONOS setzen (G.2 Schritt 3) — empfohlen, solange das Proton-Vorhaben nicht umgesetzt ist |
| MX = IONOS (`mx00.ionos.de`, `mx01.ionos.de`) | Empfang und Weiterleitung funktionieren | MX nicht anfassen |
| MX zeigt woanders hin (z.B. Proton) | Empfang läuft dort; `noreply@` bei IONOS empfängt nichts | MX nicht anfassen; nur Versand einrichten. Antworten an `noreply@` landen beim anderen Anbieter |
| SPF vorhanden | Pro Domain **genau ein** SPF-Eintrag | `include:_spf-eu.ionos.com` in den bestehenden Eintrag einfügen, keinen zweiten anlegen |
| SPF fehlt | — | neu anlegen |
| DKIM-CNAMEs fehlen | erwartet | anlegen |

Ergebnis an Rico melden, mit der Liste der Einträge, die in G.2 anzulegen sind.

> **Ergebnis 13.11.2026:** NS `cecelia.ns.cloudflare.com`, `chip.ns.cloudflare.com` → Zone bei Cloudflare. MX leer (`NOERROR`, keine Antwort), `rm-it.org` hat überhaupt keine TXT-Einträge (kein SPF), `_dmarc` und alle drei DKIM-Namen `NXDOMAIN`. Gegenprobe über `@8.8.8.8` identisch — kein Timeout, die Einträge fehlen wirklich. Folge für G.2: alle vier Schritte, zusammen 7 Einträge (SPF neu, 3 DKIM-CNAMEs, 2 MX, DMARC).

## G.2 — DNS-Einträge bei Cloudflare *[Rico]*

**Cloudflare-Dashboard → Account → `rm-it.org` → DNS → Records → Add record.** Nur die Einträge anlegen, die G.1 als fehlend gemeldet hat.

1. **SPF** — Typ `TXT`, Name `@`, TTL Auto:
   ```
   v=spf1 include:_spf-eu.ionos.com ~all
   ```
   Gibt es schon einen SPF-Eintrag, diesen **bearbeiten** und `include:_spf-eu.ionos.com` vor dem abschließenden `~all`/`-all` einfügen.
2. **DKIM** — drei Einträge, Typ `CNAME`, **Proxy status: DNS only (graue Wolke)**, TTL Auto:

   | Name | Target |
   |---|---|
   | `s1-ionos._domainkey` | `s1.dkim.ionos.com` |
   | `s2-ionos._domainkey` | `s2.dkim.ionos.com` |
   | `s42582890._domainkey` | `s42582890.dkim.ionos.com` |

   Werte laut IONOS-Hilfe „Email Authentication with DKIM" (Stand 11/2026). Zeigt das IONOS-Konto für `rm-it.org` andere Selektoren an, gelten die aus dem Konto.
3. **MX** — *nur wenn G.1 „MX leer" gemeldet hat* — zwei Einträge, Typ `MX`, Name `@`, Priorität `10`: `mx00.ionos.de` und `mx01.ionos.de`. *(Hostnamen vor dem Anlegen gegen die IONOS-Hilfe „MX-Einträge" bzw. die DNS-Ansicht im IONOS-Konto prüfen.)*
4. **DMARC** *(empfohlen, wenn G.1 keinen gefunden hat)* — Typ `TXT`, Name `_dmarc`:
   ```
   v=DMARC1; p=none
   ```
   Beobachtungsmodus: weist nichts ab, macht aber Gmail und Co. klar, dass die Domain Mail-Authentifizierung betreibt. Verschärfen (`p=quarantine`) erst, wenn alle Absender der Domain sauber signieren — Teil des Proton-Vorhabens.

> **⚠️ Stolperstein 13 — Cloudflare-Proxy an DKIM-CNAMEs.** Neue CNAMEs legt Cloudflare je nach Oberfläche mit orangener Wolke (**Proxied**) an. Ein proxied CNAME gibt nach außen Cloudflare-Adressen statt des Ziels heraus, die TXT-Abfrage auf den DKIM-Schlüssel läuft ins Leere. **Signatur:** `dig +short TXT s1-ionos._domainkey.rm-it.org @1.1.1.1` ist leer, im Mail-Header steht `dkim=neutral (no key)` oder `dkim=fail`. **Lösung:** Proxy status auf **DNS only** stellen.

**Gegenprobe** *[Claude Code]* — G.1 erneut ausführen, zusätzlich:

```bash
dig +short TXT s1-ionos._domainkey.rm-it.org @1.1.1.1 | head -c 80; echo
# Erwartung: ein Schlüssel ("v=DKIM1; … p=…" oder "k=rsa; p=…"), nicht leer
dig +short TXT rm-it.org @1.1.1.1 | grep -c 'v=spf1'
# Erwartung: 1 (genau ein SPF-Eintrag)
```

> **Ergebnis 13.11.2026:** Rico hat alle 7 Einträge angelegt. G.1 erneut: MX `10 mx00.ionos.de`, `10 mx01.ionos.de`; SPF `v=spf1 include:_spf-eu.ionos.com ~all`, `grep -c` = 1; DMARC `v=DMARC1; p=none`; DKIM-CNAMEs `s1-ionos` → `s1.dkim.ionos.com`, `s2-ionos` → `s2.dkim.ionos.com`, `s42582890` → `s42582890.dkim.ionos.com`. Alle CNAMEs liefern das IONOS-Ziel statt Cloudflare-Adressen → DNS only, Stolperstein 13 nicht aufgetreten. DKIM-TXT über `s1-ionos._domainkey` → `v=DKIM1; p=MIIBIjANBgkqhkiG…`, über `s2-ionos` ebenso.
> - **`s42582890` — Abweichung, bewusst belassen:** Der Selektor steht in der IONOS-DNS-Vorlage für `rm-it.org`, ist also kontospezifisch und richtig. Das Ziel `s42582890.dkim.ionos.com` löst (noch) nicht auf (`NXDOMAIN` über `1.1.1.1` und `8.8.8.8`); `s1`/`s2` haben Schlüssel. Der Eintrag bleibt bewusst stehen (Entscheidung Rico, 13.11.2026). G.3 zeigt im `DKIM-Signature`-Header (`s=`), mit welchem Selektor IONOS tatsächlich signiert.

## G.3 — SMTP-Zugang außerhalb des Clusters beweisen *[Rico, im eigenen Terminal]*

Dieser Test **nicht** in Claude Code ausführen — er fragt das Postfach-Passwort ab. `curl` fragt es interaktiv ab, wenn hinter `--user` kein Passwort steht; es landet weder in der Shell-History noch in einer Datei.

```bash
printf "Empfänger (private Adresse): "; read -r TO
cat > /tmp/smtp-test.eml <<EOF
From: Pantheon Whiteboard <noreply@rm-it.org>
To: <${TO}>
Subject: SMTP-Test Pantheon $(date '+%d.%m.%Y %H:%M')
Date: $(LC_ALL=C date -R)

Test ueber smtp.ionos.de:587 (STARTTLS).
EOF
curl --silent --show-error --url 'smtp://smtp.ionos.de:587' --ssl-reqd \
  --mail-from noreply@rm-it.org --mail-rcpt "$TO" \
  --user noreply@rm-it.org --upload-file /tmp/smtp-test.eml \
  && echo "SMTP_OK"
rm -f /tmp/smtp-test.eml; unset TO
```

**Erwartung:** Passwortabfrage, dann `SMTP_OK`. Die Mail kommt innerhalb von 1–2 Minuten an (Spam-Ordner mitprüfen).

**Header prüfen** (im Postfach der privaten Adresse: Mail öffnen → Quelltext/Kopfzeilen anzeigen), Zeile `Authentication-Results`:
- `spf=pass` (smtp.mailfrom=rm-it.org)
- `dkim=pass` (header.d=rm-it.org)

Fehlt eines davon, kurz warten (DNS-Verbreitung) und den Test wiederholen; bleibt es bei `fail`/`neutral` → Stolperstein 13 bzw. SPF-Eintrag prüfen.

| Fehlerbild | Ursache |
|---|---|
| `535` / `Login denied` | Benutzer oder Passwort falsch — Benutzername ist die **volle Adresse** |
| `550` … sender / `Sender address rejected` | `--mail-from` bzw. `From:` weicht vom Postfach ab — IONOS lässt nur die eigene Adresse als Absender zu |
| `Connection timed out` | Port 587 ausgehend gesperrt (Netz, Firewall) — im Heimnetz unüblich |

**Weiterleitung testen** *(nur wenn MX auf IONOS zeigt)*: von einer anderen Adresse eine Mail an `noreply@rm-it.org` schicken → sie kommt an der privaten Adresse an. Kommt sie nicht an: MX-Eintrag (G.2 Schritt 3) und die Weiterleitung im IONOS-Konto prüfen.

> **Hinweis 2-Faktor:** Wird später die 2-Faktor-Authentifizierung im IONOS-Webmail für dieses Postfach eingerichtet, G.3 danach wiederholen. Funktioniert die Anmeldung per SMTP dann nicht mehr mit dem Postfach-Passwort, braucht es ein eigenes Passwort für Mailprogramme; das Secret (G.4) entsprechend erneuern.

Danach in Claude Code: „SMTP-Test erfolgreich, SPF und DKIM pass, weiter mit G.4."

> **Ergebnis 13.11.2026 13:28 (Rico):** `SMTP_OK`, Mail an der privaten Adresse angekommen, ausgeliefert über `mout.kundenserver.de` (IONOS-Ausgang). `Authentication-Results`: `spf=pass`, `dmarc=pass`; `X-Spam-Flag: NO`. Weiterleitung geprüft: Antwort an `noreply@rm-it.org` kam über die IONOS-Weiterleitung an der privaten Adresse an (MX aus G.2 wirkt).
> - ~~**⚠️ Offen — DKIM, Neuprüfung nach 24 h:**~~ ✅ **Erledigt 13.11.2026:** Beim SMTP-Test um 13:28 noch `dkim=none`, im Header **keine** `DKIM-Signature` (kein Fehler in den Cloudflare-Einträgen; `dmarc=pass` kam über das SPF-Alignment). Bei der Verifikationsmail aus G.6 um 13:48 `dkim=pass` mit `header.s=s1-ionos` — IONOS signiert seit 13.11.2026 mit `s1-ionos`. Der Selektor `s42582890` wird nicht genutzt; der CNAME bleibt stehen (G.2).

## G.4 — Secret erzeugen und verschlüsseln *[Rico, im eigenen Terminal]*

Wie A.1: **nicht** von Claude Code ausführen lassen. `kubectl create secret … --dry-run=client` spricht nicht mit dem Cluster; es übernimmt das Maskieren, sodass Sonderzeichen im Passwort (`#`, `:`, `"`, `'`, `$`) kein YAML zerbrechen.

Der Block läuft als Subshell in runden Klammern: `umask 077`, `F` und das Passwort `P` bleiben nicht in der interaktiven Shell zurück, auch wenn ein Schritt abbricht.

```bash
(
cd ~/k8s-cluster || exit 1
F=apps/pantheon/affine/affine-smtp-secret.yaml
test -e "$F" && { echo "ABBRUCH: $F existiert schon"; } || {
  umask 077
  printf "Passwort noreply@rm-it.org: "; read -rs P; echo
  kubectl create secret generic affine-smtp -n affine \
    --from-literal=mailer-password="$P" --dry-run=client -o yaml > "$F"
  unset P
  sops --encrypt --in-place "$F" || { rm -f "$F"; echo "ABBRUCH: sops fehlgeschlagen, Datei entfernt"; }
}
grep -c 'ENC\[' "$F"
grep -E '^[[:space:]]+mailer-password:' "$F"
)
# Erwartung: Zähler >= 2; die Zeile mailer-password beginnt mit ENC[ — kein Klartext
```

> Die Datei enthält das Passwort nur als `data` (Base64) und nur bis zum `sops`-Aufruf unverschlüsselt. Fehlt `ENC[` in der Zeile `mailer-password`, greift die Regel in `.sops.yaml` für diesen Pfad nicht → Datei löschen, `.sops.yaml` prüfen, nicht committen.

Danach in Claude Code: „SMTP-Secret für AFFiNE liegt bereit, weiter mit G.5."

> **Ergebnis 13.11.2026:** `apps/pantheon/affine/affine-smtp-secret.yaml` von Rico erzeugt und verschlüsselt. Eingangsprüfung aus G.5 durch Claude Code: 2 Zeilen mit `ENC[`, `mailer-password` verschlüsselt, `name: affine-smtp` vorhanden, keine Klartextzeile unter `data`.

## G.5 — Mailer-Variablen, Kustomization, Rollout *[Claude Code; Push: Rico gibt frei]*

**Eingangsprüfung:**

```bash
F=apps/pantheon/affine/affine-smtp-secret.yaml
grep -c 'ENC\[' "$F"                                   # Erwartung: >= 2
grep -E '^\s+mailer-password:' "$F" | grep -c 'ENC\['  # Erwartung: 1
grep -E '^\s+name: affine-smtp$' "$F"                  # Erwartung: Treffer
```

In `apps/pantheon/affine/deployment.yaml`, Container **`affine`** (nicht im initContainer `migrate` — die Migration verschickt keine Mails), am Ende der `env`-Liste nach `AFFINE_INDEXER_ENABLED` ergänzen:

```yaml
            # Systemmails über IONOS (ADR 5, Teil G). MAILER_* hat Vorrang vor
            # mailer.SMTP in config.json -> Zugangsdaten bleiben im Secret.
            - name: MAILER_HOST
              value: smtp.ionos.de
            # 587 = STARTTLS. Für 465 (implizites TLS) ist ungeprüft, ob AFFiNE
            # die TLS-Variante selbst wählt -> bewusst 587.
            - name: MAILER_PORT
              value: "587"
            - name: MAILER_IGNORE_TLS
              value: "false"
            - name: MAILER_USER
              value: noreply@rm-it.org
            - name: MAILER_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: affine-smtp
                  key: mailer-password
            # IONOS akzeptiert als Absender nur die Postfach-Adresse selbst.
            - name: MAILER_SENDER
              value: "Pantheon Whiteboard <noreply@rm-it.org>"
```

In `apps/pantheon/affine/kustomization.yaml` direkt nach `affine-secret.yaml` aufnehmen:

```yaml
  - affine-smtp-secret.yaml
```

```bash
kubectl kustomize apps/pantheon/affine/ > /dev/null && echo BUILD_OK
kubectl kustomize apps/pantheon/affine/ | grep -c 'name: MAILER_'
# Erwartung: 6
kubectl kustomize apps/pantheon/affine/ | grep -A4 'name: MAILER_PASSWORD' | grep -c 'affine-smtp'
# Erwartung: 1   (-A4: kustomize sortiert key vor name -> name steht in der 4. Zeile)

A=apps/pantheon/affine
git add "$A/affine-smtp-secret.yaml" "$A/deployment.yaml" "$A/kustomization.yaml"
git commit -m "feat(affine): send system mail via ionos smtp as noreply@rm-it.org"
git show --stat HEAD                     # Rico Message + Dateiliste zeigen, Freigabe abwarten
git pull --rebase && git push            # erst nach Ricos Freigabe
flux reconcile kustomization flux-system --with-source
flux reconcile kustomization apps-affine
flux get kustomizations apps-affine
# Erwartung: READY True, Revision = soeben gepushter Commit
kubectl rollout status deploy/affine -n affine --timeout=10m
```

> **Kein `rollout restart` nötig:** Anders als bei der `config.json`-Änderung in Stolperstein 9 ändert sich hier das Pod-Template (neue `env`-Einträge) — Kubernetes rollt den Pod mit dem Flux-Apply von selbst neu. Wegen `strategy: Recreate` ist AFFiNE dabei etwa eine Minute nicht erreichbar; Franz kurz Bescheid geben, falls er gerade arbeitet.

**Verifikation:**

```bash
kubectl get pods -n affine
# Erwartung: affine 1/1 Running, keine CreateContainerConfigError (= Secret oder Schlüssel fehlt)
kubectl exec -n affine deploy/affine -c affine -- sh -c \
  'for v in MAILER_HOST MAILER_PORT MAILER_IGNORE_TLS MAILER_USER MAILER_SENDER; do echo "$v=$(printenv $v)"; done; test -n "$MAILER_PASSWORD" && echo "MAILER_PASSWORD gesetzt"'
# Erwartung: smtp.ionos.de / 587 / false / noreply@rm-it.org / Pantheon Whiteboard <noreply@rm-it.org> / "gesetzt"
#            (das Passwort selbst wird bewusst nicht ausgegeben)
kubectl get --raw "/api/v1/namespaces/affine/services/affine:80/proxy/info"; echo
# Erwartung: wie C.3
kubectl logs -n affine deploy/affine -c affine --since=10m | grep -iE 'mail|smtp' | head -20
# Erwartung: keine Fehlerzeilen (EAUTH, ECONNECTION, ETIMEDOUT, "Invalid login")
```

Danach an Rico: „Mailer aktiv, weiter mit G.6."

> **Ergebnis 13.11.2026:** Commits `5241f8e` (Rezept) und `8347fe8` (G.5), von Rico gepusht. Eingangsprüfung: 2 × `ENC[`, `mailer-password` verschlüsselt, `name: affine-smtp` vorhanden. Build: `BUILD_OK` mit 10 Ressourcen, 6 × `MAILER_`, nur im Container `affine` (initContainer `migrate`: 0). **Abweichung:** Die Prüfung `grep -A3 … | grep -c 'affine-smtp'` ergab 0 statt 1 — `kubectl kustomize` sortiert `key` vor `name`, `name: affine-smtp` steht in der 4. Zeile; Manifest korrekt, Prüfbefehl auf `-A4` korrigiert (ergibt 1).
> - **Rollout:** `apps-affine` READY True auf `main@sha1:8347fe8c`; `rollout status` nach gut einer Minute erfolgreich, ohne manuellen Neustart. Pods `affine` und `affine-redis` je `1/1 Running`, 0 Neustarts, kein `CreateContainerConfigError` → Secret `affine-smtp` und Schlüssel `mailer-password` vorhanden.
> - **Am Pod:** `MAILER_HOST=smtp.ionos.de`, `MAILER_PORT=587`, `MAILER_IGNORE_TLS=false`, `MAILER_USER=noreply@rm-it.org`, `MAILER_SENDER=Pantheon Whiteboard <noreply@rm-it.org>`, `MAILER_PASSWORD gesetzt`. `/info` wie C.3 (`AFFiNE 0.27.4 Server`). Log: `MailModule dependencies initialized`, `MailSender.onConfigInit` verarbeitet; 0 Zeilen mit `EAUTH`, `ECONNECTION`, `ETIMEDOUT` oder `Invalid login`. Migration ohne Fehler (`Done`). Ob der Versand wirklich klappt, zeigt erst G.6.

## G.6 — Funktionstest *[Rico; Log-Gegenprobe: Claude Code]*

1. **Verifikationsmail (harmlos, ändert nichts):** In AFFiNE im Browser als Rico → Kontoeinstellungen → **E-Mail verifizieren** bzw. „Bestätigungslink senden". **Erwartung:** keine Meldung „Der Bestätigungslink konnte nicht gesendet werden"; Mail von `Pantheon Whiteboard <noreply@rm-it.org>` innerhalb von 1–2 Minuten im Postfach der AFFiNE-Kontoadresse; der Link beginnt mit `https://affine.rm-it.org/` (nicht `localhost` — sonst `server.externalUrl` prüfen, B.3).
2. **Header prüfen** wie in G.3: `spf=pass`, `dkim=pass`. Landet die Mail im Spam: als „kein Spam" markieren; bei neuen Absenderdomains in den ersten Tagen normal.
3. **Passwort ändern (optional, mit Folgen):** Kontoeinstellungen → **Passwort ändern** → Link per Mail → neues Passwort (höchstens 32 Zeichen). Beendet **alle Sitzungen** des Kontos, auch in den Apps (Stolperstein 10). Nur ausführen, wenn ein Passwortwechsel ohnehin ansteht; sonst reicht Punkt 1 als Nachweis.
4. **Bei Fehler** — Claude Code liest das Log:
   ```bash
   kubectl logs -n affine deploy/affine -c affine --since=15m | grep -iE 'mail|smtp|EAUTH|ECONN' | tail -20
   ```
   | Fehlerbild | Ursache |
   |---|---|
   | `EAUTH` / `535` | Passwort im Secret falsch — G.3 bestätigt das Passwort, dann G.4 neu (alte Datei vorher entfernen) |
   | `550` / `Sender address rejected` | `MAILER_SENDER` weicht von `MAILER_USER` ab |
   | `ETIMEDOUT` / `ECONNECTION` | ausgehender Port 587 aus dem Cluster blockiert (Cilium-Policy, Router) |
   | Mail kommt nicht an, kein Fehler im Log | Spam-Ordner; Header bzw. Zustellbericht prüfen; SPF/DKIM (G.2) |
5. **E-Mail-Einladung (optional, offener Punkt aus Stolperstein 9):** Workspace-Einstellungen → Members → Invite per E-Mail an die Adresse eines bestehenden Kontos. Klärt, ob mit SMTP und `newAccountShareActionDelay: 0` noch `InviteQuotaAssertService … quota rejected` auftritt. Ergebnis hier nachtragen.
6. **Franz informieren:** Er kann sein Passwort jetzt selbst über „Passwort vergessen" bzw. Kontoeinstellungen ändern; Mails kommen von `noreply@rm-it.org`.

**Rückweg** (falls der Versand Probleme macht und erst später geklärt werden soll): Commit aus G.5 per `git revert` rückgängig machen, Push, Reconcile — AFFiNE läuft wieder ohne SMTP, Flux entfernt das Secret (`prune: true`), Stolperstein 10 gilt wieder. Die DNS-Einträge aus G.2 können stehen bleiben.

> **Ergebnis 13.11.2026 13:48 (Rico; Datenbank-Gegenprobe: Claude Code):** G.1–G.5 siehe die Ergebnisse dort (7 DNS-Einträge, SMTP-Test, Secret, Commit `8347fe8`).
> - **Punkt 1:** Verifikationsmail aus AFFiNE angekommen, Absender `Pantheon Whiteboard <noreply@rm-it.org>`, keine Fehlermeldung in AFFiNE. Der Link führt auf `https://affine.rm-it.org/auth/verify-…`; der Mailanbieter des Empfängers schaltet eine eigene Umleitung davor (`https://www.ui-deref.de/r/?to=…`). Das ist kein AFFiNE-Thema, `server.externalUrl` greift (kein `localhost`). Link angeklickt.
> - **Punkt 2:** `spf=pass`, `dkim=pass` (`header.s=s1-ionos`), `dmarc=pass`, `X-Spam-Flag: NO`.
> - **Datenbank-Gegenprobe** (rein lesend, ohne E-Mail-Adressen): `SELECT name, email_verified IS NOT NULL FROM users ORDER BY created_at;` → `Rico|t`, `Franz|f`. `email_verified` für Rico = 13.11.2026 13:48 (Europe/Berlin), also durch diesen Klick gesetzt. Franz unverändert. Unkritisch, weil `auth.requireEmailVerification: false`.
> - **Punkte 3, 5, 6** (Passwort ändern, E-Mail-Einladung, Franz informieren): nicht Teil dieses Durchlaufs.

---

## Definition of Done

**Sechs-Punkte-Checkliste (Pantheon-Standard):**

| # | Punkt | Umsetzung |
|---|---|---|
| 1 | Routing über Gateway API | `httproute.yaml` → `pantheon-gateway`, `Accepted: True` (C.3) |
| 2 | StorageClass `qnap-iscsi` | Blob-PVC `affine-storage` (B.4) |
| 3 | PostgreSQL-Connection | `pantheon-pg-rw…:5432`, eigene DB `affine`, Rolle + DB deklarativ (Teil A) |
| 4 | Frische SOPS-Secrets | `affine-db-role` (databases), `affine-secret` (affine), ab Teil G `affine-smtp` (affine) |
| 5 | PodSecurity | Redis `restricted`-konform; AFFiNE-Namespace `baseline` (root-Image, dokumentierter Trade-off); `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false` |
| 6 | Renovate | Marker über AFFiNE (beide Container) und Redis; `packageRule` nur `X.Y.Z` (B.9) |

**AFFiNE-spezifisch:**

| # | Punkt | Nachweis |
|---|---|---|
| 6a | Flux-Kustomization | `clusters/pantheon/apps-affine.yaml` mit SOPS, `wait: false`, `READY True` (C.1) |
| 7 | pgvector deklarativ | `extensions` in der `Database`-CR, `pg_extension` zeigt `vector` (A.3) |
| 8 | Server-Schlüssel stabil | Migrationslog ohne `creating config file […private.key]` (C.2) |
| 9 | Admin hinter Access angelegt | Access-App vor DNS, Admin-Setup erledigt (D.1–D.3); Access seit 04.11.2026 per Bypass gelockert (ADR 4, Nachtrag) |
| 10 | Registrierung geschlossen | Gegenprobe D.4 |
| 11 | Partner kann mitarbeiten | Konto importiert, Workspace-Mitglied (E.1–E.4) — ✅ 04.11.2026 (`a60b8545`: Rico `owner`, Franz `member`, beide `active`) |
| 12 | Live-Kollaboration | E.5 grün, WebSocket `101` — ✅ 08.11.2026 (Live-Test mit Franz; WebSocket `101` von außen belegt 04.11.) |
| 13 | DB im Backup verifiziert | On-Demand-Backup `completed` nach Anlage der DB (F.1) — ✅ 01.11. (`pantheon-pg-20261101181813`) |
| 14 | Update-Weg definiert | F.2, erster Renovate-PR bewusst geprüft — **offen**: Weg definiert, Renovate läuft; erster AFFiNE-Pull-Request steht noch aus |
| 15 | Systemmails | SPF und DKIM `pass` (G.3), Verifikationsmail aus AFFiNE kommt an, Link zeigt auf `affine.rm-it.org` (G.6) — ✅ 13.11.2026 (`spf`/`dkim`/`dmarc=pass`, DKIM mit `s1-ionos`; Verifikation für Rico in der Datenbank gesetzt) |

---

## Bewusst zurückgestellt

Jeder Punkt mit dem Risiko, das bis zur Umsetzung besteht. Reihenfolge = empfohlene Priorität.

1. **Off-site-Sicherung des Blob-Storage.** *Risiko:* Bilder und Anhänge liegen nur auf der QNAP; ein NAS-Totalausfall ließe die Whiteboards ohne eingefügte Bilder zurück (Formen, Text, Notizen in der DB bleiben erhalten). *Interim:* das iSCSI-LUN von `affine-storage` in die QNAP-Snapshot-Planung aufnehmen. *Umsetzung später:* rclone-CronJob nach dem Muster Paperless E.6 (eigener Storage-Box-Sub-Account, Ziel-Unterverzeichnis statt Wurzel — Stolperstein U, `podAffinity` wegen RWO wie Paperless E.3) **oder** Blob-Provider `aws-s3` auf einen eigenen Hetzner-Bucket (dann gehört `config.json` in ein SOPS-Secret statt in eine ConfigMap).
2. ~~**SMTP / Mailer.**~~ ✅ **Erledigt 13.11.2026** mit **Teil G (1.5)**: Versand über IONOS als `noreply@rm-it.org` (ADR 5), Definition of Done Punkt 15 grün. Der Admin-Link (Stolperstein 10) bleibt Ausweichweg.
3. ~~**Native Apps (iPad, macOS-Desktop) über Access.**~~ ✅ **Erledigt 04.11.2026** durch die Bypass-Policy `affine-bypass` (ADR 4, Nachtrag; verworfene Alternativen dort). *Betriebshinweis:* Server 0.27 akzeptiert Apps ab 0.26. Laufen die Apps aus dem App Store einer neuen Serverversion voraus, kann die Synchronisation stoppen — dann den nächsten AFFiNE-Pull-Request von Renovate zügig mergen.
4. **Serverseitige Volltextsuche** (Indexer mit Manticore). Ohne: Suche läuft clientseitig, bei vielen Workspaces langsamer.
5. **Freeform-Bestand.** Freeform hat kein offenes Exportformat; bestehende Boards nur als PDF/Bild exportieren und als Anhang/Bild in AFFiNE ablegen.
6. **`restricted`-Härtung.** Das Image läuft als root; ob es mit `runAsNonRoot` und umgebogenem `HOME` startet, ist ungeprüft — eigenes Vorhaben, nicht nebenbei.
7. **Monitoring.** Fehlgeschlagene Migrationen fallen nur beim Öffnen auf. Fügt sich in den Observability-Einstieg (Paperless E.7 / Monitoring-Rezept CT 110–112) ein: `kube_pod_init_container_status_restarts_total{namespace="affine"}`.
8. **OIDC über Keycloak**, sobald der OpenCloud-Stack steht (AFFiNE unterstützt OIDC im Admin-Panel).
9. **Homepage-Kachel** (Block B).
10. **Einladungssperre für neue Konten wieder aktivieren, sobald mehr als zwei Personen AFFiNE nutzen.** *Risiko:* Mit `auth.newAccountShareActionDelay: 0` (B.3, Stolperstein 9) kann jedes Konto ab der ersten Minute Einladungs- und Share-Links erzeugen. Bei geschlossener Registrierung und zwei bekannten Personen vertretbar. Hinter Access gelockert (seit 04.11.2026) weiterhin vertretbar, weil neue Konten nur der Admin anlegt. *Auslöser:* mehr als zwei Personen oder Registrierung geöffnet → Eintrag entfernen (Default `86400` s) oder passenden Wert setzen.
11. **Blob-PVC gegen Löschen absichern (gemeinsam mit Paperless).** *Risiko:* Das PV von `affine-storage` hat `reclaimPolicy: Delete` (StorageClass `qnap-iscsi`), `apps-affine` läuft mit `prune: true`. Fliegt `pvc.yaml` aus der `kustomization.yaml` oder wird `apps-affine` bzw. der Namespace entfernt, löscht Flux die PVC — Bilder und Anhänge wären weg (Whiteboards, Konten und Workspaces liegen in der DB und sind gesichert). Paperless hat dieselbe Lage. *Bewertung:* Die Flux-Annotation `kustomize.toolkit.fluxcd.io/prune: disabled` an der PVC schützt nur vor dem ersten Fall, nicht vor dem Löschen des Namespace; `Retain` ginge nur per direktem Patch am PV oder über eine eigene StorageClass (Shared-Infrastruktur). *Umsetzung später:* als eigenes Vorhaben für beide Apps, zusammen mit Punkt 1. Entscheidung Rico 01.11.2026.
12. **Mail-Domain zu Proton (Abstimmung mit `claude/rezept-proton-pantheon.md`).** *Risiko:* Zieht `rm-it.org` später zu Proton um, müssen SPF, DKIM und MX in einem Zug umgestellt werden; wird nur der MX geändert, landen Antworten an `noreply@` nicht mehr in der IONOS-Weiterleitung, wird nur SPF ersetzt, scheitert der AFFiNE-Versand über IONOS. *Umsetzung später:* im Proton-Rezept Block D für AFFiNE entweder auf Proton-SMTP umstellen (dann `MAILER_HOST` und Secret tauschen, IONOS-Einträge entfernen) oder IONOS als Versandweg behalten (dann bleibt `include:_spf-eu.ionos.com` im SPF und die IONOS-DKIM-Einträge bleiben stehen).
13. ~~**DKIM-Signatur durch IONOS nachprüfen.**~~ ✅ **Erledigt 13.11.2026:** IONOS signiert seit 13.11.2026 mit `s1-ionos` (`dkim=pass` in G.6); `s42582890` ungenutzt, der CNAME bleibt stehen. *Ursprünglich:* *Risiko:* Am 13.11.2026 kamen die Testmails ohne `DKIM-Signature` an (`dkim=none`, G.3); der kontospezifische Selektor `s42582890` löst bei IONOS noch nicht auf (G.2). Zustellung läuft über SPF und `dmarc=pass`, aber ohne DKIM steigt das Spam-Risiko bei strengen Empfängern, und `p=quarantine` (Proton-Vorhaben) wäre bei weitergeleiteten Mails riskant. *Vorgehen:* G.3 nach 24 h wiederholen. Bleibt es bei `dkim=none`, im IONOS-Konto bzw. beim IONOS-Support die DKIM-Aktivierung für Domains mit externen Nameservern (Cloudflare) klären.

---

## Rezept-Changelog

**1.5.2 (13.11.2026)** — Teil G abgeschlossen.
- **G.5:** Ergebnis eingetragen (Mailer im Pod aktiv, Rollout ohne Neustart). **Korrektur:** Prüfung `MAILER_PASSWORD` → `affine-smtp` von `grep -A3` auf `grep -A4`, weil `kubectl kustomize` die Schlüssel alphabetisch sortiert (`key` vor `name`).
- **G.6:** Ergebnis eingetragen. Verifikationsmail angekommen, `spf`/`dkim`/`dmarc=pass`; `email_verified` für Rico in der Datenbank gesetzt.
- **DKIM erledigt:** IONOS signiert seit 13.11.2026 mit `s1-ionos`; `s42582890` ungenutzt, CNAME bleibt stehen. G.3-Ergebnis und „Bewusst zurückgestellt" Punkt 13 als erledigt markiert.
- **Definition of Done Punkt 15 ✅**, „Bewusst zurückgestellt" Punkt 2 (SMTP) erledigt. Abend 9 in der Abendtabelle auf ✅, Status im Kopf nachgezogen.

**1.5.1 (13.11.2026)** — Teil G, Abend 9: G.1–G.4 durchlaufen.
- **G.1, G.2, G.3, G.4:** Ergebnisse eingetragen (7 DNS-Einträge angelegt, SMTP-Test erfolgreich, Secret bereit).
- **Korrektur G.3/G.4 (zsh):** `read -rp`/`read -rsp` funktionieren in zsh nicht → `printf "…: "; read -r TO` bzw. `printf "…: "; read -rs P; echo`. G.4 läuft als Subshell in runden Klammern; `\s` in `grep -E` durch `[[:space:]]` ersetzt (POSIX, unabhängig von der grep-Variante).
- **Abweichung DKIM:** Selektor `s42582890` aus der IONOS-DNS-Vorlage löst noch nicht auf, IONOS signiert noch nicht (`dkim=none`). CNAME bleibt bewusst stehen (Entscheidung Rico); Nachprüfung als „Bewusst zurückgestellt", Punkt 13.

**1.5 (12.11.2026)** — Systemmails über IONOS.
- **ADR 5 (neu):** Inklusivpostfach `noreply@rm-it.org` aus dem IONOS-Domainvertrag als Absender, Versand über `smtp.ionos.de:587` (STARTTLS), Passwort als SOPS-Secret `affine-smtp`, Konfiguration über `MAILER_*`; SPF/DKIM in der Cloudflare-Zone. Verhältnis zum Proton-Rezept und verworfene Alternativen dokumentiert. Entscheidung Rico.
- **Teil G (neu, Abend 9):** DNS-Ausgangslage (G.1), DNS-Einträge bei Cloudflare inkl. Entscheidung zum MX (G.2), SMTP-Test mit `curl` außerhalb des Clusters (G.3), Secret über `kubectl create secret --dry-run=client` + `sops` (G.4), Mailer-Variablen und Rollout ohne manuellen Neustart (G.5), Funktionstest mit harmloser Verifikationsmail zuerst (G.6), Rückweg.
- **Stolperstein 13 (neu):** Cloudflare-Proxy an DKIM-CNAMEs verhindert die Schlüsselabfrage.
- **Angepasst:** Kopf, Zweck (Punkt 6), Abendtabelle, Voraussetzungen, Hintergrund, ADR 3 (Hinweis auf Zugangsdaten), ADR 4 (Nachtrag zu SMTP), Repository-Struktur, B.3-Tabelle, B.6 und B.8 (Verweis auf G.5), E.1 und Stolperstein 10 (gelöst mit Teil G, Admin-Link bleibt Ausweichweg), E.4, F.1 (SMTP-Passwort), F.2 (Mailer bei Minor-Updates prüfen), Definition of Done (4, neu 15), „Bewusst zurückgestellt" (Punkt 2 → Teil G, neu Punkt 12 zur Proton-Abstimmung).
- **Status:** Teil G noch nicht live verifiziert.

**1.4 (08.11.2026)** — Rezept abgeschlossen.
- **E.5 erledigt, Definition of Done Punkt 12 ✅:** Live-Test mit Franz erfolgreich; Abend 7 in der Abendtabelle auf ✅.
- **E.6:** Bezugsquellen ergänzt — macOS-App nicht im Mac App Store, sondern Homebrew-Cask `affine` oder Download; Hinweis auf die Selbstaktualisierung der Desktop-App. Ergebnis: alle Geräte verbunden.
- **Stolperstein 10 erweitert:** Reset-Link 30 Minuten gültig, einmal verwendbar, an das Konto gebunden, beendet alle Sitzungen. Weg „Admin setzt das Passwort über einen frischen Link selbst" dokumentiert (kein Admin-Feld zum Setzen, kein Datenbank-Eingriff); Befund vom 08.11.2026.
- **Status:** Rezept abgeschlossen; offen bleiben der erste Renovate-Pull-Request für AFFiNE und „Bewusst zurückgestellt".

**1.3.1 (08.11.2026)** — iPhone-App verbunden.
- **E.6 (neu): Native Apps verbinden** — Weg über den Workspace-Wechsler, Ergebnis eingetragen (iPhone ✅, macOS offen).
- **Stolperstein 12 (neu):** Server-Auswahl nur im Workspace-Wechsler, nicht in den Einstellungen; Anmeldung auf dem Startbildschirm führt zur AFFiNE-Cloud. Bekannter Upstream-Fehler bei der iOS-Anmeldung an selbst gehosteten Servern samt Ausweichweg dokumentiert.
- **ADR 4, Nachtrag:** Ergebnis zu den nativen Apps nachgetragen.

**1.3 (04.11.2026)** — Native Apps, Beitritt per Link, Passwortwechsel ohne SMTP.
- **ADR 4, Nachtrag:** Access für AFFiNE per Bypass-Policy `affine-bypass` gelockert (Entscheidung Rico), damit die nativen Apps funktionieren. Begründung, verbleibender Schutz, Abgrenzung zu Paperless, Rücknahme, Auslöser zur Neubewertung und verworfene Alternativen (WARP, Service-Token, Bypass nur für API-Pfade). Kopf, Zweck, E.2, Stolperstein 6 und Definition of Done Punkt 9 angepasst.
- **Einladungssperre (B.3, Punkt 10):** Auslöser „Access-Gate entfernt" gestrichen; es bleibt bei Ricos ursprünglicher Regel — wieder aktivieren bei mehr als zwei Personen oder geöffneter Registrierung.
- **E.4:** Beitritt per Einladungslink erzeugt nur eine Beitrittsanfrage, die der Besitzer annehmen muss (Befund 04.11.2026).
- **Stolperstein 10 (neu):** „Passwort ändern" und „E-Mail verifizieren" brauchen SMTP; Weg über den Reset-Link im Admin-Panel. E.1 Punkt 4 korrigiert (Partner kann das Passwort nicht selbst im Profil ändern). „Bewusst zurückgestellt" Punkt 2 ergänzt.
- **„Bewusst zurückgestellt" Punkt 3:** native Apps erledigt; Betriebshinweis zur Client-Kompatibilität.
- **Stolperstein 11 (neu):** „Allow + Everyone" ist kein Bypass; Policies aus der Policy-Liste müssen der Application zugeordnet sein. Ergebnisse der Tests von außen eingetragen (AFFiNE `200`/`/info`/`101`, Paperless weiterhin `302`).
- **E.4 erledigt, Definition of Done Punkt 11 ✅:** Beitrittsanfrage angenommen, Mitgliedschaft pro Workspace belegt; Prüfabfrage pro Workspace statt Summe über alle.

**1.2 (01.11.2026)** — Erkenntnisse aus Abend 8 (Teil F live). Damit sind alle acht Abende durchlaufen; offen sind nur E.4/E.5 (nach Ricos Dienstreise) und der erste AFFiNE-Pull-Request von Renovate.
- **F.1 aufgeteilt nach Rollen:** Ausgangslage und Warten mit `kubectl wait … --timeout=15m` durch Claude Code, `kubectl cnpg backup` durch Rico im eigenen Terminal (legt direkt ein Objekt an → Harte Regel 1). Neue Prüfung: Liegt das letzte Base-Backup vor der Anlage der Datenbank, ist sie bis dahin nur WAL-gesichert. Ergebnis eingetragen (`pantheon-pg-20261101181813` `completed`).
- **F.2 Rückweg:** `kubectl scale` als [Rico] markiert (Harte Regel 1). Renovate-Lauf und Stand der Versionen eingetragen; Nebenbefund Workflow-Recht des Renovate-Tokens notiert.
- **„Bewusst zurückgestellt", Punkt 11 (neu):** Blob-PVC mit `reclaimPolicy: Delete` und `prune: true` — Risiko, Bewertung der Optionen, Lösung gemeinsam mit Paperless als eigenes Vorhaben (Entscheidung Rico).
- **Definition of Done:** 13 ✅; 14 offen bis zum ersten AFFiNE-Pull-Request; 11 und 12 weiter offen (E.4/E.5).

**1.1.2 (01.11.2026)** — Erkenntnisse aus Abend 7 (Teil E teilweise).
- **Stolperstein 9 (neu, E.4):** AFFiNE 0.27.4 sperrt Einladungen für Konten jünger als 24 h (`auth.newAccountShareActionDelay`, Default `86400` s). Einladungslink: „This feature is temporarily unavailable for you."; E-Mail-Invite ohne SMTP: Endlos-Animation (`InviteQuotaAssertService`, `quota_subject`). Befund, Gegenprobe im Image und Lösung eingetragen.
- **B.3:** `"newAccountShareActionDelay": 0` im `config.json`-Beispiel und in der Tabelle, Begründung (zwei Nutzer, Registrierung geschlossen, Access mit OTP) und Warnhinweis, die Sperre bei mehr Nutzern, offener Registrierung oder ohne Access-Gate wieder zu aktivieren. Umgesetzt mit Commit `0fe316e` (Variante B, Entscheidung Rico).
- **Neustart nach Konfigurationsänderung:** `kubectl rollout restart` führt Rico im eigenen Terminal aus (Harte Regel 1); Claude Code prüft danach Rollout, Migrationslog, `/info` und `config.json` im Pod.
- **Planungshinweis:** Abend 6 und 7 mit mindestens 24 h Abstand planen oder die Einstellung in B.3 setzen.
- **„Bewusst zurückgestellt", Punkt 10 (neu):** Einladungssperre wieder aktivieren, sobald mehr als zwei Personen AFFiNE nutzen.
- **Abend 7 teilweise:** E.1–E.3 ✅ 01.11., Einladungslink funktioniert; E.4 (Einladung annehmen) und E.5 (Live-Test mit dem Geschäftspartner) offen, nachzuholen nach Ricos Dienstreise. Definition of Done 11 und 12 als offen markiert. Abend 8 ist der nächste Schritt.
- **Offen:** E-Mail-Invite nach der Änderung nicht erneut getestet.

**1.1.1 (01.11.2026)** — Erkenntnisse aus Abend 2 (Teil A live), Abend 3 (B.1, B.3–B.5), Abend 4 (B.6–B.9), Abend 5 (Teil C live) und Abend 6 (Teil D live).
- **A.1 als lokales Skript:** Statt des eingefügten Befehlsblocks verweist A.1 auf `wartung/scripts/affine-a1-secrets.sh`. Das Skript liegt bewusst nur lokal (`.git/info/exclude`), bricht beim ersten Fehler ab, überschreibt nichts und entfernt unverschlüsselte Reste. Befund dazu: Nach dem ersten Versuch an Abend 2 lagen weder die beiden Dateien noch `apps/pantheon/affine/` im Repository (Ursache nicht geklärt); der Lauf mit dem Skript war erfolgreich.
- **A.3 Staging und Push:** Dateien einzeln stagen statt `git add` auf das ganze Verzeichnis (CLAUDE.md: nur die Dateien des Schritts); vor dem Push Commit-Message und `git show --stat HEAD` zeigen und Ricos Freigabe abwarten. Von Rico am 01.11.2026 bestätigt.
- **A.3 Übergangsmeldung dokumentiert:** `secrets "affine-db-role" is forbidden` an der DatabaseRole direkt nach dem Reconcile ist ein Wettlauf mit der RBAC-Aktualisierung des Operators und heilt sich selbst; `kubectl wait` statt Eingreifen. Ergebnisse von Teil A eingetragen.
- **B.5 Redis-Tag:** `7.4-alpine` → `8.10-alpine`. Die Begründung „wie Paperless B.9" stimmte nicht mehr: Paperless ist per Renovate auf `8.10-alpine` (`e1e42aa`, `51a8269`). Von Rico am 01.11.2026 entschieden.
- **Abschluss Abend 3:** Dateien einzeln stagen und Push-Freigabe wie in A.3. Ergebnisse von Abend 3 eingetragen.
- **Commit Abend 4:** ebenso Dateien einzeln stagen und Push-Freigabe; B.6–B.9 ohne inhaltliche Abweichung umgesetzt, Ergebnisse eingetragen.
- **D.5 Gegenproben (neu):** DNS-Status vor D.1 mit `NXDOMAIN` und Positivkontrolle statt nur `dig +short`, Access-Prüfung von außen per `curl` (302 auf `cloudflareaccess.com`, kein `/info`-JSON), Benutzer- und Admin-Zählung in der Datenbank ohne Ausgabe von E-Mail-Adressen. Ergebnisse von Teil D eingetragen.
- **C.3 ohne Test-Pod:** `/info` über den API-Server-Proxy (`kubectl get --raw`) statt `kubectl run` mit ungepinntem `curlimages/curl`. Von Rico am 01.11.2026 bestätigt. C.1 mit Push-Freigabe wie in A.3. Ergebnisse von Teil C eingetragen.

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

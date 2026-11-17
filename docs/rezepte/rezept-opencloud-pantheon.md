# Kochrezept: OpenCloud auf Pantheon (Dropbox-Ablösung)

> OpenCloud als Dateiablage auf dem Pantheon-Cluster, um die bestehende Dropbox abzulösen und anschließend zu kündigen — bedienbar wie Dropbox: Browser, Desktop-Client auf dem Mac, Apps auf iPhone/Android, innerhalb und außerhalb des Heimnetzes. Login über Keycloak (mit Zwei-Faktor), **ohne** Cloudflare-Access-OTP davor, damit die Apps funktionieren. Alle Systemmails (Keycloak: Passwort vergessen, Einladung von Gästen; OpenCloud: Freigabe-Benachrichtigungen) gehen als **`noreply@rm-it.org`** über das IONOS-Postfach, das AFFiNE bereits nutzt. Inklusive vollständiger, per Inhalts-Hash geprüfter Migration aus Dropbox und einem Backup, das den Verzicht auf Dropbox trägt.
>
> Das Rezept ist in **Blöcke** geschnitten, die Claude Code jeweils in einem Stück abarbeitet. Unterbrechungen gibt es nur an den markierten **⏸ HALT**-Punkten — dort, wo Rico eingreifen muss (Secrets, Weboberflächen, `cloudflared`, Geräte, unumkehrbare Entscheidungen). Ablageort im Repo: `docs/rezepte/rezept-opencloud-pantheon.md`.

*Rezeptversion: 1.2 — November 2026 · Cluster: Pantheon · Zielversion: OpenCloud 7.2.x (Production-Linie)*

> **Status:** Nicht live verifiziert. Version 1.2 enthält die Ergebnisse und Entscheidungen aus Teil 0 (16.11.2026, Details in `apps/pantheon/opencloud/UPSTREAM.md`). Version 1.1 ist gegen den Repository-Stand vom 16.11.2026 abgeglichen (Commit `1a72f8c`): Gateway nur mit HTTP-Listener `http`, cert-manager über `infrastructure-cert-manager`, Tunnel `pantheon-apps` mit Catch-all auf `cilium-gateway-pantheon-gateway:80`, `.sops.yaml` verschlüsselt `data`/`stringData` in jeder `*.yaml`, IONOS-SMTP für AFFiNE live seit 13.11.2026 (SPF, DKIM `s1-ionos`, DMARC `p=none`). Faktenbasis OpenCloud: Dokumentation 7.2 (Keycloak-, External-IdP-, PosixFS-, Notifications-, App-Token-, Link-Passwort-Seiten), README von `opencloud-eu/opencloud-compose`, Releases `opencloud-eu/opencloud` (7.2.3 vom 06.08.2026), rclone-WebDAV-Doku. Was sich nur aus den Compose-Dateien selbst ergibt (Images, Realm-Datei, LDAP-Seed, CSP), gleicht Claude Code in **Teil 0** gegen das Upstream-Repo ab und trägt es ein. Nach jedem Block die Erwartungswerte mit den echten Ausgaben abgleichen (Ergebnisprotokoll am Blockende).

> **Vorgeschichte.** Im Juni 2026 war OpenCloud als „Raw Manifests, decomposedS3 auf MinIO-on-QNAP" geplant und an zwei Voraussetzungen gebunden (Homepage Block B, MinIO). Dieses Rezept ersetzt die Architekturnotiz: MinIO ist als Community-Edition inzwischen archiviert, OpenCloud speichert seit 2.0 standardmäßig per PosixFS — die MinIO-Voraussetzung entfällt (Architekturentscheidung 1).

---

## Inhalt

- **Zweck** · **Abgleich mit AFFiNE** · **Arbeitsweise für Claude Code** · **Blockplan** · **Voraussetzungen** · **Hintergrund**
- **Architekturentscheidungen 1–8** (Speicher · Zugang ohne Access · Identität · Konfiguration · Topologie · Migration · Backup · Systemmails)
- **Repository-Struktur**
- **Teil 0** — Vorab-Checks und Upstream-Abgleich *(Claude Code)*
- **Block A** — Secrets *(Rico)*
- **Block B** — HTTPS am Gateway, LAN-Direktweg *(Claude Code, ohne HALT)*
- **Block C** — Identität: Keycloak-Datenbank, Keycloak *(1 HALT)*
- **Block D** — OpenCloud-Kern und Web-Office *(1 HALT)*
- **Block E** — Öffentlicher Zugang und Apps *(1 HALT)*
- **Block F** — Migration I: Vorbereitung und Kopie *(1 HALT)*
- **Block G** — Migration II: Abschluss und Inhaltsprüfung *(ohne HALT)*
- **Block H** — Backup *(1 HALT)*
- **Block I** — Umstieg *(2 HALTs)*
- **Block J** — Dropbox-Ablösung (Entscheidungstor) *(Rico)*
- **Block K** — Volltextsuche mit Tika *(nach der Migration, ohne HALT)*
- **Teil L** — Betrieb: Updates und Rückweg
- **Definition of Done** · **Bewusst zurückgestellt** · **Changelog**

---

## Zweck

1. OpenCloud läuft unter `https://cloud.rm-it.org`. Browser, OpenCloud-Desktop (macOS) und die Apps für iOS/Android melden sich über Keycloak an — mit Zwei-Faktor (TOTP), weil der Login der Apps im System-Browser stattfindet.
2. Im Heimnetz gehen alle Clients **direkt** auf das `pantheon-gateway` (gültiges Let's-Encrypt-Zertifikat), unterwegs über den Cloudflare-Tunnel. Gleiche URL überall.
3. Der Dropbox-Bestand liegt vollständig im persönlichen Space von Rico, geprüft per Dropbox-Inhalts-Hash gegen den Dateibaum auf dem Server.
4. Teilen mit Bandkollegen: öffentliche Links (Passwort per Default Pflicht) oder Gastkonten ohne eigenen Speicher. Gäste bekommen eine Einladungsmail von `noreply@rm-it.org`, setzen ihr Passwort selbst, melden sich einmal an (danach sind sie im Teilen-Dialog auffindbar) und können ihr Passwort selbst zurücksetzen.
5. Office-Dokumente im Browser (Collabora), Volltextsuche in Dokumenten (Tika, nach der Migration).
6. Backup: QNAP-Snapshots (vollständig, inkl. Metadaten) + nächtliche, verschlüsselte Off-site-Kopie auf die Storage Box; Keycloak-Datenbank im bestehenden Barman-Backup.
7. Updates ausschließlich über Renovate-Pull-Requests und Flux.
8. Dropbox ist abgelöst: Desktop-App deinstalliert, Abo gekündigt — erst nach einem Entscheidungstor (Block J).

---

## Abgleich mit AFFiNE — was übernommen wird, was bewusst anders ist

| Thema | AFFiNE 1.5.2 | OpenCloud 1.1 | Warum |
|---|---|---|---|
| Rollen Rico / Claude Code | [Rico] / [Claude Code] pro Teil | **Blöcke** mit ⏸ HALT, Claude Code arbeitet bis zum nächsten HALT durch | Wunsch: nur unterbrechen, wenn Eingreifen nötig ist |
| Secrets | Rico im eigenen Terminal; Subshell, `kubectl create secret … --dry-run=client`, `sops` (AFFiNE G.4) | übernommen (Block A); weitere Secrets genau dort, wo sie entstehen (F, H) | Sonderzeichen sicher maskiert, Klartext nie in Claude-Sitzungen |
| Systemmails | IONOS-Postfach `noreply@rm-it.org`, `smtp.ionos.de:587`, STARTTLS, Secret `affine-smtp` | **dasselbe Postfach**, eigenes Secret `opencloud-smtp` für Keycloak und OpenCloud | Ein Absender für alle Apps; IONOS kennt keine App-Tokens, ein Postfach-Passwort (Architekturentscheidung 8) |
| Flux | Eine Kustomization pro App, Schalter erst am Ende | `apps-opencloud` entsteht **früh** (Block C) und wächst blockweise | Schichtweise live verifizieren: Identität → Kern → Öffentlich |
| Datenbank | Eigene DB in `pantheon-pg` | übernommen — nur für Keycloak | OpenCloud selbst hat keine SQL-Datenbank |
| Einmal-Initialisierung | Migration als initContainer | `opencloud init` als initContainer, idempotent | Renovate-tauglich, kein unveränderlicher Job |
| Schlüsselmaterial | Selbst erzeugt, SOPS in Git | **von OpenCloud selbst erzeugt**, liegt auf dem Config-PVC, Sicherung verschlüsselt off-site | Liste der internen Secrets ändert sich zwischen Versionen (Architekturentscheidung 4) |
| Zugang von außen | Access per Bypass gelockert (04.11.2026), Schutz durch App-Login | **kein Access**, Absicherung in Keycloak (Zwei-Faktor, Brute-Force-Schutz) | Native Apps scheitern am Access-Gate; bei 2 TB persönlicher Daten braucht es mehr als ein App-Passwort |
| Admin-Risiko | Erster Besucher von `/admin` wird Admin → Access vor DNS | Konten nur aus Keycloak, Registrierung aus, **Demo-Konten entfernt** vor DNS | Gleiches Prinzip: Gate erst schließen, dann veröffentlichen |
| Agenten-Befehle | `rollout status --timeout`, `kubectl run -i` | übernommen; zusätzlich `curl --resolve` statt DNS-Abhängigkeit | Prüfungen funktionieren vor und nach DNS-Änderungen |
| Renovate | `packageRule` nur `X.Y.Z` | übernommen für OpenCloud, Keycloak, Collabora, Tika | Wandernde Tags (`rolling`, `latest`) ausgeschlossen |
| Prüfungen ohne `exec` | `kubectl get --raw …/services/…/proxy/…` | übernommen, wo möglich | `kubectl exec`/`run` verlangen in `.claude/settings.json` eine Freigabe |
| Route-Timeout | Erst bei Symptom | **vorsorglich `0s`** für OpenCloud und Collabora | Große Downloads und WebSocket-Sitzungen sind hier sicherer Normalfall, kein Verdacht |

---

## Arbeitsweise für Claude Code (gilt für alle Blöcke)

Es gelten die Regeln aus `CLAUDE.md` im Repo (Rollen, harte Regeln, Konventionen, Commits). Dieses Rezept ergänzt sie nur.

**Startprompt je Block** (in Claude Code, Repo `~/k8s-cluster`):

```text
Lies docs/rezepte/rezept-opencloud-pantheon.md: den Abschnitt „Arbeitsweise für
Claude Code" und Block X. Führe Block X vollständig aus. Halte nur an ⏸ HALT-Punkten
oder bei einer STOPP-Bedingung an. Trage die Ist-Werte ins Ergebnisprotokoll von
Block X ein, setze im Blockplan ✅ und Datum, und schließe mit einem Abschlussbericht.
```

(`X` durch den Buchstaben des Blocks ersetzen. Der Startprompt für Teil 0 steht in Teil 0.)

Claude Code trägt die Ist-Werte direkt in die Rezeptdatei ein und committet sie mit dem letzten Commit des Blocks (`docs(opencloud): …`).

**Regeln:**

1. **Reihenfolge.** Blöcke strikt nacheinander. Jeder Block beginnt mit einer **Eingangsprüfung**; schlägt sie fehl → STOPP.
2. **⏸ HALT.** Claude Code hält an, fasst zusammen, was erledigt ist, nennt Rico die Aufgaben aus dem HALT-Kasten wörtlich (mit kopierfertigen Befehlsblöcken) und wartet auf den dort genannten **Fortsetzungssatz**. Nicht vorgreifen, nichts „schon mal vorbereiten", was Cluster-Zustand ändert.
3. **STOPP-Bedingungen.** Weicht eine Ausgabe von der Erwartung ab: anhalten, Abweichung und Hypothese berichten, Vorschlag machen (CLAUDE.md, Regel 6). Erlaubt sind nur lesende Diagnosebefehle. Keine Reparatur außerhalb des Rezepts.
4. **Secrets** (CLAUDE.md, Regel 2). Kein `sops`, keine Datei mit `kind: Secret` anlegen oder ändern, kein `kubectl get secret`, kein `env`/`printenv` in Pods. Prüfung nur über `grep 'ENC\['`. Wo eine Prüfung im Pod ein Secret als Variable nutzt (C.4/4, C.6), wird der Wert nie ausgegeben, nur eine Zahl.
5. **`cloudflared`** ist für Claude Code gesperrt. DNS-Routen über den Tunnel legt Rico an (E.2).
6. **GitOps.** Clusteränderungen nur per Commit. Imperativ erlaubt sind: `flux reconcile`, `kubectl create job --from=cronjob/…`, Wegwerf-Pods mit `kubectl run --rm`, lesende `kubectl exec`-Befehle. `create`, `run`, `exec` verlangen eine Freigabe in `.claude/settings.json` — das ist ein Klick, kein HALT.
7. **Kein Endloswarten.** Kein `-w`, kein `logs -f`. Stattdessen `kubectl rollout status --timeout=…`, `kubectl wait --for=… --timeout=…`.
8. **Vor jedem Commit:** `kubectl kustomize <verzeichnis> > /dev/null && echo BUILD_OK` für jedes berührte Kustomize-Verzeichnis, und `grep -rn '__[A-Z_]*__' apps/pantheon/opencloud/ infrastructure/controllers/networking/certificates/` muss **leer** sein (offene Platzhalter → STOPP).
9. **Commit und Push** (CLAUDE.md, Abschnitt Commits): nur die Dateien des Schritts stagen, Rico Message und `git show --stat HEAD` zeigen, nach Freigabe `git pull --rebase && git push`.
10. **Abschlussbericht** je Block: geänderte Dateien, Commits, Prüfergebnisse als *Ist vs. Erwartung*, Abweichungen, offene Punkte.

**Platzhalter.** Werte, die erst Teil 0 ermittelt, stehen als `__NAME__` im Rezept (z. B. `__KEYCLOAK_TAG__`). Claude Code ersetzt sie beim Schreiben der Dateien durch die Ergebnisse aus `apps/pantheon/opencloud/UPSTREAM.md`.

---

## Blockplan

| Block | Inhalt | Rico aktiv | Claude Code | HALTs | Wirkung im Cluster |
|---|---|---|---|---|---|
| 0 ✅ 16.11.2026 (0.6 offen) | Rezept ins Repo, Vorab-Checks, Upstream-Abgleich, Versionen; **0.6 Speicher freiräumen** | 5 Min (Eingaben) + 0.6: ~1 h aktiv, spätestens vor Block F | ~25 Min | 0 | keine (0.6: nur QNAP) |
| A ✅ 16.11.2026 | Cloudflare-Token, alle Grund-Secrets inkl. SMTP | ~15 Min | Prüfung `ENC[` | — | keine |
| B ✅ 16.11.2026 | Wildcard-Zertifikat, HTTPS-Listener am Gateway | — | ~30 Min | 0 | HTTPS im LAN für `*.rm-it.org` |
| C ✅ 17.11.2026 | Keycloak-DB, Keycloak mit SMTP, Routen | ~15 Min | ~40 Min | 1 | Identität läuft (LAN), Keycloak sendet Mails |
| D | OpenCloud mit Mail-Benachrichtigungen, WOPI, Collabora, Routen, Renovate | ~10 Min | ~40 Min | 1 | OpenCloud im LAN nutzbar |
| E | Sicherheits-Gate, DNS-Routen, externe Prüfungen, Geräte | ~20 Min | ~20 Min | 2 | von außen + Apps |
| F | Dropbox-Zugang, Testkopie, Vollkopie starten | ~20 Min | ~30 Min + Laufzeit (Tage) | 1 | Kopie läuft im Hintergrund |
| G | Delta-Lauf, Hash-Prüfung, Bericht | — | ~30 Min | 0 | — |
| H | Off-site-Ziel, QNAP-Snapshots, Backup-Job, Restore-Probe | ~20 Min | ~40 Min + Erstlauf (Tage) | 1 | Backup aktiv |
| I | Dropbox einfrieren, Schlusskopie, Geräte umstellen, Freigaben | 30–60 Min | ~15 Min | 2 | Dropbox ruht |
| J | Entscheidungstor, Dropbox-App deinstallieren, Abo kündigen, Aufräumen | ~20 Min | ~10 Min | — | Migrationsreste entfernt |
| K | Tika (Volltextsuche), Nachindizierung | — | ~30 Min | 0 | Suche in Dokumentinhalten |

**Ricos aktive Zeit gesamt:** ≈ 3 h, verteilt auf zehn kurze Eingriffe. Lange Laufzeiten (Kopie, erster Off-site-Lauf) brauchen keine Anwesenheit.

> **Laufzeiten bei 1,5–3 TB.** Die Vollkopie (F) hängt an der Download-Bandbreite des Anschlusses, der erste Off-site-Lauf (H) an der Upload-Bandbreite. Faustregel: 100 Mbit/s ≈ 1 TB pro Tag. Bei 2 TB und 250 Mbit/s Download ≈ 1 Tag Kopie; bei 40 Mbit/s Upload ≈ 5 Tage Off-site-Erstlauf. Teil 0 rechnet das mit den echten Werten aus.

> **⚠️ Stolperstein 15 — Wartungsfenster während langer Läufe.** Während Vollkopie (F/G) und erstem Off-site-Lauf (H) keine Talos-/Node-Wartung einplanen. Ein Node-Drain beendet den Job-Pod; beide Läufe sind wiederaufsetzbar, verlieren aber Stunden. Vor dem nächsten Wartungsfenster prüfen: `kubectl get jobs -n opencloud`.

---

## Voraussetzungen

| Voraussetzung | Herkunft |
|---|---|
| Flux CD, SOPS/age, `apps/pantheon/<name>/`, eine Flux-Kustomization pro App | Phase 4, AFFiNE 1.1 Teil 0.4 |
| StorageClass `qnap-iscsi` (ext4, RWO) | Phase 5 |
| `pantheon-pg` (PG 18, CNPG 1.30), Barman-Plugin, WAL-Archiving `OK` | Phase 5.5, `rezept-cnpg-backup-pantheon.md` |
| `pantheon-gateway` (Cilium Gateway API v1.6.1), LB-IP `192.168.178.224`, Listener `http` | AP 6.0; Manifest `infrastructure/controllers/networking/pantheon-gateway.yaml`, Flux `infrastructure-networking` |
| cert-manager v1.20.x im Cluster | Flux `infrastructure-cert-manager`, `infrastructure/controllers/cert-manager/` |
| `cloudflared`-Tunnel `pantheon-apps`, Catch-all auf `http://cilium-gateway-pantheon-gateway.default.svc.cluster.local:80` | `infrastructure/controllers/networking/cloudflared/configmap.yaml` |
| AdGuard Home (CT 103) als DNS im LAN | Proxmox-Management-Plane |
| Hetzner Storage Box BX21 (`u620152`, laut Tarif 5 TB) | `rezept-paperless-ngx-pantheon.md`, Teil E.6 |
| **IONOS-Postfach `noreply@rm-it.org`** (Mail Basic), SMTP `smtp.ionos.de:587` STARTTLS, Weiterleitung an Ricos private Adresse; SPF/DKIM/DMARC in der Cloudflare-Zone | `docs/rezepte/rezept-affine-pantheon.md`, ADR 5 und Teil G (live seit 13.11.2026) |
| Lokal auf dem Mac: `kubectl`, `flux`, `sops`, `cloudflared` (eingeloggt), `rclone` (`brew install rclone`), `openssl`, `jq`, `dig` | — |
| Claude Code in VS Code mit `CLAUDE.md` und `.claude/settings.json` | Repo |

**Offizielle Dokumentation:**
- [OpenCloud — Keycloak Integration](https://docs.opencloud.eu/docs/admin/configuration/authentication-and-user-management/keycloak)
- [OpenCloud — External OpenID Connect Identity Provider](https://docs.opencloud.eu/docs/admin/configuration/authentication-and-user-management/external-idp)
- [OpenCloud — PosixFS Storage Driver](https://docs.opencloud.eu/docs/admin/configuration/storage/storage-posix)
- [OpenCloud — Backup](https://docs.opencloud.eu/docs/admin/maintenance/backup)
- [OpenCloud — App Tokens](https://docs.opencloud.eu/docs/user/admin/app-tokens)
- [OpenCloud — Public Links: Password Enforcement](https://docs.opencloud.eu/docs/admin/configuration/link-password-policy)
- [OpenCloud — Mail-Benachrichtigungen](https://docs.opencloud.eu/docs/admin/configuration/mail-notifications) · [Notifications — Umgebungsvariablen](https://docs.opencloud.eu/docs/next/dev/server/services/notifications/environment-variables)
- [Keycloak — Server Administration: E-Mail-Einstellungen eines Realms](https://www.keycloak.org/docs/latest/server_admin/#_email)
- [opencloud-compose (Verdrahtungs-Blaupause)](https://github.com/opencloud-eu/opencloud-compose)
- [rclone — Dropbox](https://rclone.org/dropbox/) · [rclone — WebDAV](https://rclone.org/webdav/) · [rclone — crypt](https://rclone.org/crypt/)

---

## Hintergrund — was OpenCloud braucht

| Komponente | Rolle | In Pantheon |
|---|---|---|
| `opencloudeu/opencloud` | Server, Web-Client, WebDAV, Graph-API, TUS-Uploads — Port 9200. Läuft als UID 1000. | Deployment `opencloud`, eine Replica |
| `opencloud collaboration` | WOPI-Server zwischen OpenCloud und Collabora | **Dienst im OpenCloud-Prozess** (`OC_ADD_RUN_SERVICES`), erreichbar unter `https://cloud.rm-it.org/wopi` (Architekturentscheidung 5) |
| Collabora Online (CODE) | Office im Browser — Port 9980 | Deployment `collabora`, zustandslos |
| Keycloak | OIDC-Provider, Zwei-Faktor, Brute-Force-Schutz | Deployment `keycloak`, DB `keycloak` in `pantheon-pg` |
| Eingebautes Verzeichnis `idm` | OpenCloud-Konten und -Gruppen; Konten entstehen bei der ersten Anmeldung aus Keycloak (Autoprovisioning) | Dienst im OpenCloud-Prozess, Datei `idm/idm.boltdb` auf PVC `opencloud-data` (Architekturentscheidung 3) |
| Apache Tika | Textextraktion für die Volltextsuche — Port 9998 | Deployment `tika`, zustandslos, erst Block K (nach der Migration) |
| SMTP (extern) | Systemmails von Keycloak und OpenCloud | IONOS `smtp.ionos.de:587`, Postfach `noreply@rm-it.org` (Architekturentscheidung 8) |

| Pfad im Container | Inhalt | Storage |
|---|---|---|
| `/etc/opencloud/opencloud.yaml` | Von `opencloud init` erzeugte interne Secrets und IDs | PVC `opencloud-config` (1 Gi) |
| `/etc/opencloud/csp.yaml` u. a. | Angepasste Konfigurationsdateien aus Upstream | ConfigMap (Git) |
| `/var/lib/opencloud/storage/users/…` | **Die Dateien selbst**, als lesbarer Ordnerbaum (PosixFS), Metadaten in Extended Attributes | PVC `opencloud-data` (`__DATA_SIZE__`) |
| `/var/lib/opencloud/…` (übrige) | NATS-KV (ID-Cache), Suchindex, Thumbnails | PVC `opencloud-data` |
| `/var/lib/opencloud/idm/idm.boltdb` | OpenCloud-Konten und -Gruppen (eingebautes Verzeichnis) | PVC `opencloud-data`; Keycloak-Konten, Passwörter, OTP, Clients, Sessions in DB `keycloak` |

> **Merksatz:** Es gibt keine Datenbank, die einen Index über die Dateien führt — der Dateibaum *ist* die Wahrheit. Darum: niemals am laufenden OpenCloud vorbei im Dateibaum schreiben (lesen ist erlaubt).

---

## Architekturentscheidung 1: PosixFS auf einem `qnap-iscsi`-PVC statt decomposedS3 auf MinIO

> **Problemstellung.** Die Juni-Planung sah Blobs in S3 (MinIO-on-QNAP) und Metadaten im decomposedFS vor. MinIO hat 2025 erst die Konsole aus der Community-Edition entfernt, im Oktober 2025 die Veröffentlichung von Images eingestellt und das Repository 2026 archiviert. Gleichzeitig ist in OpenCloud seit Version 2.0 **PosixFS** der Standard-Speichertreiber.
>
> **Entscheidung: PosixFS (nicht-kollaborativer Modus) auf einem `qnap-iscsi`-PVC.**
> - Keine zusätzliche Komponente, keine offene Voraussetzung — OpenCloud kann sofort starten.
> - Die Dateien liegen als **lesbarer Ordnerbaum** auf dem Volume. Backup und Notfall-Restore werden dadurch einfach; selbst eine Kopie ohne Metadaten ist noch ein vollständiger Dateibestand (OpenCloud nimmt neue Dateien beim Start per „Assimilation" auf).
> - Die Migrationsprüfung kann direkt gegen diesen Baum rechnen (Architekturentscheidung 6).
>
> **Konsequenzen:** RWO → genau eine Replica, Strategie `Recreate`. Beim Start durchläuft PosixFS den ganzen Baum, um Caches aufzuwärmen — bei 2 TB dauert ein Neustart deutlich länger als bei AFFiNE (großzügige `startupProbe`, Stolperstein 7). `fsGroupChangePolicy: OnRootMismatch` ist Pflicht, sonst läuft bei jedem Pod-Start ein rekursives `chown` über alle Dateien.
>
> **Verworfene Alternativen:**
> - *decomposedS3 + MinIO-on-QNAP:* MinIO-Community ist archiviert, ohne offizielle Images — widerspricht der Renovate-/Patch-Strategie.
> - *decomposedS3 + Garage/SeaweedFS/RustFS:* neue, selbst zu betreibende Komponente nur für diesen Workload — „kein spekulatives Tooling".
> - *Hetzner Object Storage als Blob-Speicher:* jeder Dateizugriff über das Internet, laufende Traffic-Abhängigkeit, Daten nicht mehr im Haus.
> - *decomposedFS auf dem PVC:* funktioniert, aber technischer Ordnerbaum ohne Bedeutung für Menschen — verliert den Backup- und Prüfvorteil.

## Architekturentscheidung 2: Öffentlich ohne Cloudflare Access — Absicherung in Keycloak

> **Problemstellung.** Bei Paperless und AFFiNE schützt Cloudflare Access (E-Mail-OTP) die App. Die OpenCloud-Apps (Desktop, iOS, Android) haben keine Browser-Session für das Access-Cookie und können keine Service-Token-Header senden — sie scheitern am Gate. Öffentliche Links für Bandkollegen müssen ohne jedes Konto erreichbar sein.
>
> **Entscheidung: Kein Access für die OpenCloud-Hostnamen. Die Sicherheit liegt im Identity Provider und in der Route.**
> 1. **Keycloak** als einziger Login-Weg: Registrierung aus, Brute-Force-Erkennung an, **TOTP** für Rico (funktioniert mit den Apps, weil deren Login im System-Browser läuft).
> 2. **Demo-Konten und Demo-Gruppen aus der Upstream-Realm-Datei entfernt**, bevor irgendetwas öffentlich wird; OpenCloud legt kein eigenes Admin-Konto an (Stolperstein 1).
> 3. **Admin-Konsole von Keycloak nicht öffentlich:** Die öffentliche Route lässt nur `/realms/openCloud` und `/resources` durch — der `master`-Realm (Admin-Login) ist von außen nicht erreichbar. Administration läuft über `keycloak-admin.rm-it.org`, das nur am **HTTPS-Listener** hängt; der Tunnel liefert ausschließlich an den HTTP-Listener.
> 4. **Öffentliche Links** behalten den OpenCloud-Default: Passwort ist Pflicht.
> 5. **App-Tokens** (für die rclone-Migration) immer mit Ablaufdatum — sie werden bei einer Sperre in Keycloak **nicht** ungültig (Stolperstein 14).
> 6. **Keine Passwörter über Dritte:** Gäste setzen ihr Passwort über einen Einladungslink per Mail selbst (Architekturentscheidung 8); Rico kennt Gast-Passwörter nie.
>
> **Verworfene Alternativen:**
> - *Access mit Bypass-Policies für App-Pfade* (`/remote.php`, `/dav`, `/ocs`, `/data`, `/.well-known`, …): genau die Endpunkte, die man schützen wollte, wären trotzdem offen — nur unübersichtlicher.
> - *Nur über Tailscale/VPN:* Bandkollegen und öffentliche Links scheiden aus.
> - *Access-Service-Token:* Die Apps können keine eigenen Header senden.

## Architekturentscheidung 3: Keycloak mit Autoprovisioning in das eingebaute Verzeichnis (seit 1.2)

> **Problemstellung.** OpenCloud bringt einen eingebauten IdP mit. Keycloak war im Juni bereits als Portfolio-Bestandteil gesetzt; jetzt kommt ein funktionaler Grund hinzu: Ohne Access ist der IdP die einzige Hürde. Version 1.1 sah Keycloak mit OpenLDAP als gemeinsamem Verzeichnis vor (Upstream `idm/ldap-keycloak.yml`). Teil 0 hat am 16.11.2026 ergeben: Upstream nutzt dafür `bitnamilegacy/openldap:2.6`, seit 19.08.2025 ohne Updates. Ein gepflegter Ersatz fehlt (`osixia/openldap` seit 2021 nur Vorab-Tags, `quay.io/389ds/dirsrv` seit Juni 2025 ohne Push). Auch Upstreams Autoprovisioning-Variante `idm/external-idp.yml` hängt an diesem Image.
>
> **Entscheidung (Rico, 16.11.2026): Keycloak hält die Konten; OpenCloud legt sie bei der ersten Anmeldung in seinem eingebauten Verzeichnis `idm` an (Autoprovisioning). Kein externes LDAP.**
> - Keycloak authentifiziert (Passwort, TOTP, Brute-Force-Schutz, Einladung, Passwort vergessen) und liefert `sub`, Name, E-Mail und die Realm-Rollen im Token.
> - OpenCloud übernimmt Name und E-Mail bei jeder Anmeldung und ordnet die Rolle aus dem Claim `roles` zu: `opencloudAdmin` → admin, `opencloudSpaceAdmin` → spaceadmin, `opencloudUser` → user, `opencloudGuest` → user-light.
> - Realm-Datei aus Upstream `config/keycloak/opencloud-realm-autoprovisioning.dist.json` (Clients für Web, Desktop, iOS, Android, Rollen, Mapper), bereinigt in C.3.2.
> - Keycloak-Datenbank in `pantheon-pg` (Barman-gesichert). Keycloak bleibt **im** Cluster, weil es nur Apps dient und nichts zum Booten oder Reparieren des Clusters braucht.
>
> **Belegt am 7.2.5-Quelltext** (`UPSTREAM.md`): Graph schreibt per Default in `idm` (`ldap://localhost:9236`, Schreiben erlaubt) — Voraussetzung für `PROXY_AUTOPROVISION_ACCOUNTS`; bei leerem `OC_ADMIN_USER_ID` legt `idm` kein Admin-Konto an; der Proxy aktualisiert Anzeigename und E-Mail beim Login. Upstream liefert diese Kombination nicht als fertige Compose-Datei → D.9/D.10 prüfen sie mit `rico` und `testgast` live, **bevor** migriert wird.
>
> **Konsequenzen:**
> - Ein Konto existiert in OpenCloud erst nach der ersten Anmeldung. Mit einer Person teilen geht erst danach (Stolperstein 27).
> - Entfernen in zwei Schritten: in Keycloak sperren/löschen **und** in OpenCloud löschen (Stolperstein 28).
> - `idm/idm.boltdb` ordnet Keycloak-`sub` den internen OpenCloud-IDs zu. Ginge sie verloren, entstünden beim nächsten Login neue Konten, die persönlichen Spaces wären verwaist. Sie liegt auf `opencloud-data` und ist von QNAP-Snapshots und Off-site-Kopie erfasst (Block H); Wiederherstellung immer zusammen mit dem Config-PVC.
>
> **Verworfene Alternativen:**
> - *Keycloak + OpenLDAP, Shared User Directory (Version 1.1):* einziges Upstream-Image `bitnamilegacy` ohne Updates — widerspricht der Renovate-Strategie (Stolperstein 6).
> - *Upstream `idm/external-idp.yml` wörtlich:* dasselbe Image.
> - *OpenLDAP-Image selbst bauen:* eigener Build und eigenes Patchen — kein spekulatives Tooling.
> - *Eingebauter IdP statt Keycloak:* weniger Komponenten — aber ein späterer Wechsel des IdP ändert die Benutzer-IDs. Diese Entscheidung muss **vor** der Migration von 2 TB fallen, nicht danach.

## Architekturentscheidung 4: Interne Secrets erzeugt OpenCloud selbst — einmaliges `opencloud init`

> **Problemstellung.** OpenCloud braucht rund zwei Dutzend interne Secrets und IDs (JWT-, Transfer-, Machine-Auth-Secrets, System-User-ID, Mount-IDs, seit 7.0 zusätzlich ein Service-Account für den Sharing-Dienst). `opencloud init` erzeugt sie in `/etc/opencloud/opencloud.yaml`.
>
> **Entscheidung: initContainer führt `opencloud init` genau einmal aus — nur wenn `opencloud.yaml` fehlt — und schreibt auf das Config-PVC.** Die Werte entstehen im Cluster, berühren weder Git noch eine Claude-Sitzung. Gesichert wird das Config-PVC über die verschlüsselte Off-site-Kopie und QNAP-Snapshots (Block H).
>
> **Verworfene Alternative — alle Secrets als SOPS-Env-Variablen** (Muster einiger Community-Charts): Die Liste ist versionsabhängig; ein Upgrade wie 7.0 (neuer Service-Account) bricht still, wenn ein Eintrag fehlt. AFFiNE hatte genau **einen** Schlüssel — dort war Git die bessere Wahl, hier nicht.

## Architekturentscheidung 5: Topologie — WOPI im OpenCloud-Prozess, HTTPS am Gateway, Server-zu-Server über `hostAliases`

> **Problemstellung.** (a) Der WOPI-Dienst `collaboration` braucht dieselbe `opencloud.yaml` und den NATS-Registry-Dienst von OpenCloud; das Config-PVC ist RWO. (b) OpenCloud, Collabora und WOPI rufen sich gegenseitig über ihre **öffentlichen** URLs auf (OIDC-Discovery, WOPI-Callbacks). (c) Der Desktop-Client lädt beim ersten Sync den ganzen Bestand — über den Tunnel wären das Tage und ein Konflikt mit den Cloudflare-Nutzungsbedingungen für große Dateien.
>
> **Entscheidung:**
> 1. `collaboration` läuft als **zusätzlicher Dienst im OpenCloud-Prozess** (`OC_ADD_RUN_SERVICES=notifications,collaboration`, wie Upstream `weboffice/collabora.yml` seit 2026). Der WOPI-Endpunkt ist `https://cloud.rm-it.org/wopi` (Proxy-Route in 7.2.5 vorhanden) — kein eigener Hostname, kein zweiter Container, keine eigene NATS-Adresse. *(Seit 1.2, Entscheidung Rico 16.11.2026.)*
> 2. **Wildcard-Zertifikat `*.rm-it.org`** per cert-manager (DNS-01 über Cloudflare) und ein **HTTPS-Listener** am `pantheon-gateway` (Block B). Im LAN löst AdGuard die OpenCloud-Hostnamen direkt auf die Gateway-IP auf.
> 3. Pods erreichen die öffentlichen Hostnamen über `hostAliases` → Gateway-IP, also ohne Umweg über das Internet.
>
> **Nebeneffekt:** Damit ist auch die seit Juni offene Lücke „Gateway-TLS im LAN" für alle `*.rm-it.org`-Routen geschlossen.
>
> **Verworfene Alternativen:** *collaboration als zweiter Container mit eigenem Hostnamen `wopi.rm-it.org`* (Version 1.1: ein Hostname, eine Route, ein Service und eine Startreihenfolge mehr; Upstream ist davon abgerückt); *collaboration als eigenes Deployment* (bräuchte `podAffinity` aufs RWO-Volume und eine eigene NATS-Adresse); *Server-zu-Server über Cloudflare* (Internet-Abhängigkeit für interne Aufrufe); *nur Tunnel* (siehe (c)).

## Architekturentscheidung 6: Migration im Cluster — rclone von der Dropbox-API direkt in OpenCloud

> **Problemstellung.** 1,5–3 TB sollen von Dropbox nach OpenCloud, vollständig und nachweisbar. Der Mac soll dafür nicht tagelang laufen müssen, und „Nur online"-Dateien liegen dort ohnehin nicht lokal.
>
> **Entscheidung:**
> - **rclone-Job im Cluster** liest über die Dropbox-API und schreibt per **WebDAV** (Vendor `owncloud`, Authentifizierung mit OpenCloud-App-Token) über den **internen Service** in den persönlichen Space. Der Weg über die API stellt sicher, dass OpenCloud jede Datei regulär verarbeitet.
> - Die Jobs sind **suspendierte CronJobs** in Git und werden per `kubectl create job --from=cronjob/…` ausgelöst (Paperless-Muster E.6.5) — deklarativ, ohne unveränderliche Job-Manifeste.
> - **Prüfung per Dropbox-Inhalts-Hash:** Dropbox und WebDAV haben keinen gemeinsamen Hash. rclone kann den Dropbox-Hash aber für lokale Dateien berechnen — ein Prüf-Job hängt das Daten-PVC **lesend** ein und vergleicht jede Datei gegen Dropbox, ohne den Bestand ein zweites Mal herunterzuladen.
>
> **Verworfene Alternativen:**
> - *Upload vom Mac über den Desktop-Client:* Mac muss tagelang laufen; „Nur online"-Dateien fehlen lokal.
> - *Direkt in den PosixFS-Baum kopieren + Assimilation:* schnell und laut Doku unterstützt, aber OpenCloud müsste zum Einhängen gestoppt werden und es ist ein Eingriff am Dateibaum vorbei. **Fallback**, falls der WebDAV-Weg zu langsam oder fehlerhaft ist.
> - *Vendor `infinitescale` (TUS-Chunking):* für den internen Weg unnötig; bei großen Dateien mit PosixFS gab es in 7.0 einen gemeldeten Fehler beim Abschluss von TUS-Uploads (Stolperstein 19). Einfaches PUT ist hier robuster.

## Architekturentscheidung 7: Backup in drei Schichten

> **Problemstellung.** Ohne Dropbox gibt es keine zweite Kopie mehr. Die OpenCloud-Doku empfiehlt Snapshots oder eine Backup-Software und — für strenge Konsistenz — das Stoppen der Instanz.
>
> **Entscheidung:**
>
> | Schicht | Was | Wiederherstellung |
> |---|---|---|
> | 1. QNAP-Snapshots (täglich, 14 Tage) | LUNs von `opencloud-data` (inkl. `idm`) und `opencloud-config` | Vollständig inkl. Extended Attributes, Freigaben, Versionen |
> | 2. Off-site, nächtlich, **rclone crypt** → Storage Box (eigener Sub-Account) | Dateibaum inkl. `idm/idm.boltdb`, Config-PVC; geänderte/gelöschte Dateien 30 Tage im Archiv (`--backup-dir`) | Dateien vollständig; Freigaben/Versionen gehen verloren (Restore = Assimilation in frische Instanz) |
> | 3. Barman (bestehend) | DB `keycloak` | PITR wie bei AFFiNE |
>
> **Bewusst akzeptiert:** Beide Kopien sind *crash-konsistent* (kein Stopp der Instanz) — RPO 24 h. Für eine Ein-Personen-Dateiablage vertretbar; eine nachts geänderte Datei ist im Zweifel in der nächsten Nacht konsistent.
>
> **Warum verschlüsselt?** Persönliche Daten (1,5–3 TB) bei einem Dritten, plus die internen OpenCloud-Secrets aus dem Config-PVC. Die beiden crypt-Passwörter liegen zusätzlich **außerhalb von Pantheon und außerhalb von OpenCloud** sicher verwahrt — ohne sie ist die Off-site-Kopie wertlos.

## Architekturentscheidung 8: Systemmails über das IONOS-Postfach `noreply@rm-it.org`

> **Problemstellung.** Ohne Mail kann Keycloak weder „Passwort vergessen" noch Einladungen verschicken; Rico müsste Gast-Passwörter selbst vergeben und auf einem zweiten Weg übermitteln. OpenCloud könnte nicht über neue Freigaben benachrichtigen. Für AFFiNE ist seit 13.11.2026 ein Absender live: IONOS-Postfach `noreply@rm-it.org` (Mail Basic, im Domainvertrag enthalten), `smtp.ionos.de:587` mit STARTTLS, SPF/DKIM (`s1-ionos`)/DMARC in der Cloudflare-Zone, Antworten per Weiterleitung an Ricos private Adresse.
>
> **Entscheidung: Alle Systemmails von Keycloak und OpenCloud gehen über dasselbe Postfach als `noreply@rm-it.org`.**
> 1. **Keycloak** (Realm `openCloud`): SMTP steht im **Realm-Import** (`smtpServer`), das Passwort als Platzhalter `${SMTP_PASSWORD}`, das Keycloak beim Import aus der Umgebungsvariablen ersetzt. Absendername `Pantheon Cloud`. „Passwort vergessen" an, Einladungslinks (Aktions-E-Mail) 72 h gültig.
> 2. **OpenCloud**: Dienst `notifications` zusätzlich starten, `NOTIFICATIONS_SMTP_*` mit Absender `Pantheon Cloud <noreply@rm-it.org>`.
> 3. **Ein Secret `opencloud-smtp`** im Namespace `opencloud` (Schlüssel `smtp-password`) für beide. Das Postfach-Passwort steht damit in zwei SOPS-Secrets (`affine-smtp`, `opencloud-smtp`) — bei einer Passwortänderung beide erneuern (Stolperstein 24).
> 4. **Kein neuer DNS-Eintrag:** SPF, DKIM, DMARC und MX sind seit AFFiNE Teil G gesetzt. Block C prüft sie nur.
>
> **Konsequenz:** Gastkonten brauchen eine echte E-Mail-Adresse. Wechselt die Mail-Domain später zu einem anderen Anbieter, ändern sich nur Host, Port und die Secrets — in Keycloak über die Admin-Konsole (die Realm-Datei wirkt nur beim ersten Import, Stolperstein 3), in OpenCloud über das Deployment.
>
> **Verworfene Alternativen:**
> - *Kein SMTP, Passwörter von Hand:* Rico vergibt und übermittelt jedes Gast-Passwort; jede vergessene Anmeldung landet bei ihm.
> - *Eigenes Postfach je App (z. B. `cloud@rm-it.org`):* zweites Postfach, zweites Passwort, kein Mehrwert — der Absender soll einheitlich `noreply@` sein.
> - *Versanddienst oder eigener Mailserver:* zusätzlicher Anbieter bzw. Betriebsaufwand; das IONOS-Postfach ist bezahlt und zustellbar.

---

## Repository-Struktur

```text
clusters/pantheon/
├── infrastructure-certificates.yaml        ← Flux-Kustomization (Block B)
└── apps-opencloud.yaml                     ← Flux-Kustomization (Block C)

infrastructure/controllers/networking/
├── pantheon-gateway.yaml                   ← + HTTPS-Listener (Block B)
└── certificates/
    ├── kustomization.yaml
    ├── cloudflare-api-token-secret.yaml    ← SOPS, von Rico (Block A)
    ├── clusterissuer-letsencrypt-dns.yaml
    └── certificate-wildcard-rm-it-org.yaml

infrastructure/controllers/databases/pantheon-pg/
├── keycloak-db-role-secret.yaml            ← SOPS, von Rico (Block A)
├── keycloak-role.yaml
├── keycloak-database.yaml
└── kustomization.yaml                      ← drei Einträge ergänzen

apps/pantheon/opencloud/
├── UPSTREAM.md                             ← Teil 0: Upstream-Commit, Versionen, Abweichungen
├── kustomization.yaml
├── namespace.yaml
├── opencloud-secret.yaml                   ← SOPS, von Rico (Block A)
├── opencloud-smtp-secret.yaml              ← SOPS, von Rico (Block A): IONOS-Postfach-Passwort
├── keycloak/        keycloak.yaml, opencloud-realm.json
├── opencloud/       pvc.yaml, deployment.yaml, service.yaml, config/*
├── collabora.yaml
├── tika.yaml                               ← Block K
├── httproutes.yaml
├── migration/       script.yaml, cronjobs.yaml  + opencloud-migration-secret.yaml (Rico, Block F)
└── backup/          script.yaml, cronjobs.yaml  + opencloud-offsite-secret.yaml (Rico, Block H)

docs/rezepte/rezept-opencloud-pantheon.md   ← dieses Rezept (Teil 0)
CLAUDE.md                                   ← „Laufendes Vorhaben" auf OpenCloud (Teil 0)
renovate.json                               ← packageRules (Block D, Block K)
```

---

# Teil 0 — Vorab-Checks und Upstream-Abgleich *(Claude Code)*

**Ziel:** Rezept ins Repo bringen, `CLAUDE.md` auf das neue Vorhaben umstellen, alle Werte, die das Rezept nicht sicher vorab kennen kann, aus Cluster und Upstream ermitteln und in `apps/pantheon/opencloud/UPSTREAM.md` festhalten. Keine Clusteränderung.

## 0.0 — Rezept ablegen und Eingaben *(Rico, 5 Min)*

**Rezept ins Repo** (Rico, eigenes Terminal — die Datei liegt nach dem Download in `~/Downloads`):

```bash
mkdir -p ~/k8s-cluster/docs/rezepte
mv ~/Downloads/rezept-opencloud-pantheon.md ~/k8s-cluster/docs/rezepte/
```

**Startprompt Teil 0** — in Claude Code einfügen und die Werte ausfüllen:

```text
Lies CLAUDE.md und docs/rezepte/rezept-opencloud-pantheon.md (Abschnitte
„Arbeitsweise für Claude Code" und „Teil 0"). Führe Teil 0 vollständig aus.
Meine Eingaben:
DROPBOX_GB=2200          (belegter Speicher laut dropbox.com → Einstellungen → Tarif)
QNAP_FREE_TB=6.0         (frei im Speicherpool laut QNAP → Speicher & Snapshots)
ACME_EMAIL=deine@adresse.example (Adresse für Ablaufwarnungen von Let's Encrypt)
DOWN_MBIT=250 UP_MBIT=40 (Anschluss laut Router oder Speedtest)
DROPBOX_APPS=keine       (Apps/Geräte, die Dropbox als Sync-Ziel nutzen, z. B.
                          Notiz-Apps, Scanner, Kamera-Upload; „keine", wenn unbekannt)
HOSTNAMEN=ok             (oder Abweichungen zur Tabelle in 0.0)
```

> Die Werte im Beispiel sind Platzhalter zum Überschreiben, nicht geprüft. `ACME_EMAIL` erhält nur Ablaufwarnungen von Let's Encrypt.

| Zweck | Hostname | Erreichbar |
|---|---|---|
| OpenCloud | `cloud.rm-it.org` | LAN + öffentlich |
| Keycloak (Login, Konto) | `keycloak.rm-it.org` | LAN + öffentlich, nur `/realms/openCloud`, `/resources` |
| Keycloak-Administration | `keycloak-admin.rm-it.org` | **nur LAN** (HTTPS-Listener, keine öffentliche DNS) |
| Collabora | `collabora.rm-it.org` | LAN + öffentlich |

> **⚠️ Stolperstein 18 — Hostnamen sind endgültig.** OIDC-Issuer, Client-Redirects und alle App-Konten hängen an diesen Namen. Später ändern heißt: Realm anpassen und jedes Gerät neu anmelden.

## 0.1 — Repo vorbereiten *(Claude Code)*

```bash
git status -sb && git pull --rebase
test -f docs/rezepte/rezept-opencloud-pantheon.md && echo REZEPT_OK
```

In `CLAUDE.md` den Abschnitt **„Laufendes Vorhaben"** ersetzen durch:

```markdown
## Laufendes Vorhaben

**OpenCloud** (Dateiablage statt Dropbox, Dropbox wird danach gekündigt): `docs/rezepte/rezept-opencloud-pantheon.md`. Der Stand steht im Blockplan des Rezepts. Blöcke laufen bis zum nächsten ⏸ HALT durch; Schritte für Rico mit kopierfertigem Block oder genauem Klickpfad übergeben. `cloudflared` führt nur Rico aus.

AFFiNE ist abgeschlossen (`docs/rezepte/rezept-affine-pantheon.md`); offen ist dort nur der erste Renovate-Pull-Request.
```

Dazu in der Repository-Karte die Zeile für `docs/rezepte/` unverändert lassen und unter „Harte Regeln" nichts ändern.

**Vorschlag an Rico (nicht selbst ändern):** Für die vielen lesenden Prüfungen dieses Rezepts würden folgende Einträge in `.claude/settings.json` unter `allow` Rückfragen sparen: `"Bash(kubectl wait *)"`, `"Bash(kubectl explain *)"`, `"Bash(dig *)"`, `"Bash(jq *)"`, `"Bash(git ls-remote *)"`, `"Bash(kubectl get --raw *)"`. Claude Code zeigt den Diff; Rico entscheidet. `curl` bleibt bewusst bei der Einzelfreigabe.

## 0.2 — Cluster-Zustand

Erwartungen aus dem Repo-Stand vom 16.11.2026 sind eingetragen; Claude Code bestätigt sie am lebenden Cluster.

```bash
# Gateway: IP und vorhandene Listener
kubectl get gateway -n default pantheon-gateway \
  -o jsonpath='{.status.addresses[*].value}{"\n"}{range .spec.listeners[*]}{.name} {.protocol} {.port} {.hostname}{"\n"}{end}'
# Erwartung: 192.168.178.224 und genau ein Listener "http HTTP 80" (ohne hostname). Kein HTTPS-Listener.

# Flux-Kustomizations (Namen, Pfade, SOPS, Abhängigkeiten)
kubectl get kustomizations -n flux-system \
  -o custom-columns=NAME:.metadata.name,PATH:.spec.path,SOPS:.spec.decryption.provider,DEPENDS:.spec.dependsOn[*].name
# Erwartung u. a.: infrastructure-networking (./infrastructure/controllers/networking, sops),
#                  infrastructure-cert-manager (./infrastructure/controllers/cert-manager),
#                  keine Kustomization liest ./infrastructure/controllers/networking/certificates

# cert-manager: Namespace, CRDs, vorhandene Issuer
kubectl get deploy -A -l app.kubernetes.io/name=cert-manager -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name
kubectl get crd clusterissuers.cert-manager.io certificates.cert-manager.io
kubectl get clusterissuer,issuer -A 2>/dev/null
# Erwartung: Namespace cert-manager; CRDs vorhanden; kein ACME-Issuer
#            (vorhandene Issuer gehören zum Barman-Plugin — nicht anfassen)

# Tunnel: Catch-all zeigt auf den HTTP-Listener
grep -A2 'ingress:' infrastructure/controllers/networking/cloudflared/configmap.yaml
# Erwartung: service: http://cilium-gateway-pantheon-gateway.default.svc.cluster.local:80

# SOPS-Regel
cat .sops.yaml
# Erwartung: path_regex .*\.ya?ml$, encrypted_regex ^(data|stringData)$ -> jede Secret-Datei wird verschlüsselt

# Mail: DNS für noreply@rm-it.org unverändert seit AFFiNE Teil G?
R=@1.1.1.1
dig +short MX rm-it.org $R
dig +short TXT rm-it.org $R | grep -i 'v=spf1'
dig +short TXT _dmarc.rm-it.org $R
dig +short TXT s1-ionos._domainkey.rm-it.org $R | head -c 40; echo
# Erwartung: 10 mx00.ionos.de. / 10 mx01.ionos.de.; genau ein SPF mit include:_spf-eu.ionos.com;
#            v=DMARC1; p=none; DKIM-Schlüssel nicht leer
grep -n 'MAILER_HOST\|MAILER_PORT\|MAILER_USER' -A1 apps/pantheon/affine/deployment.yaml
# Erwartung: smtp.ionos.de / "587" / noreply@rm-it.org (Referenz für Block C und D)

# StorageClass: Erweiterung möglich?
kubectl get storageclass qnap-iscsi -o jsonpath='{.allowVolumeExpansion}{"\n"}'

# Kapazität der Worker
kubectl top nodes
kubectl describe nodes | grep -A6 "Allocated resources" | grep -E "cpu|memory"

# HTTPRoute-Timeouts von der installierten CRD unterstützt?
kubectl explain httproute.spec.rules.timeouts.request >/dev/null && echo TIMEOUTS_OK
```

## 0.3 — Versionen ermitteln (konkrete Tags, nie wandernde)

```bash
# OpenCloud: höchste 7.2.x der Production-Linie (Release-Notes 7.2.3: 06.08.2026)
git ls-remote --tags --refs https://github.com/opencloud-eu/opencloud 'v7.2.*' \
  | awk -F/ '{print $3}' | sort -V | tail -3
# Gegenprobe: Existiert der Tag im Production-Image (nicht opencloud-rolling)?
V=7.2.3   # auf die höchste Zahl oben setzen, ohne "v"
TOKEN=$(curl -s "https://auth.docker.io/token?service=registry.docker.io&scope=repository:opencloudeu/opencloud:pull" | jq -r .token)
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.oci.image.index.v1+json" \
  "https://registry-1.docker.io/v2/opencloudeu/opencloud/manifests/$V"
# Erwartung: 200

# rclone: neuestes Release; zum Vergleich der Tag, den Paperless bereits nutzt
git ls-remote --tags --refs https://github.com/rclone/rclone 'v1.*' | awk -F/ '{print $3}' | sort -V | tail -1
grep -rn 'image: .*rclone' apps/pantheon/paperless/ | head -3
```

Keycloak-, Collabora-, Tika- und LDAP-Tags kommen aus 0.4 (Upstream-Stand), jeweils auf den neuesten **Patch derselben Linie** gehoben, wenn verfügbar. Für rclone den Tag nehmen, den Paperless nutzt, sofern er nicht älter als eine Minor-Version ist — dann hebt Renovate beide gemeinsam.

> **⚠️ Stolperstein 16 — `opencloud-rolling` ist nicht die Production-Linie.** Rolling-Releases sind die schnelle Linie mit Features vor der Stabilisierung. Für eine Dateiablage nur `opencloudeu/opencloud:<X.Y.Z>`.

## 0.4 — Upstream-Compose auslesen

```bash
TMP=$(mktemp -d) && git clone --depth 1 https://github.com/opencloud-eu/opencloud-compose "$TMP/oc"
git -C "$TMP/oc" rev-parse HEAD                     # Commit festhalten
ls "$TMP/oc" "$TMP/oc/idm" "$TMP/oc/config" "$TMP/oc/config/keycloak" "$TMP/oc/config/ldap" "$TMP/oc/config/opencloud"
```

Claude Code liest und notiert in `UPSTREAM.md`:

| # | Was | Quelle | Wofür |
|---|---|---|---|
| a | `image:` von Keycloak, OpenLDAP, Collabora, Tika | `idm/ldap-keycloak.yml`, `weboffice/collabora.yml`, `search/tika.yml` | `__KEYCLOAK_TAG__`, `__COLLABORA_TAG__`, `__TIKA_TAG__`, LDAP-Manifest |
| b | Komplette `environment`-Listen von `opencloud` und `collaboration` in diesen Dateien plus `docker-compose.yml`, `external-proxy/opencloud.yml`; **wie der Notifications-Dienst zusätzlich gestartet wird** (`START_ADDITIONAL_SERVICES` in `.env` → welche Variable im Container, vermutlich `OC_ADD_RUN_SERVICES`) und welche `SMTP_*`-Variablen auf `NOTIFICATIONS_SMTP_*` abgebildet werden | dto., `.env.example` | Abgleich gegen D.4 (Abweichungen begründen), `__ADD_SERVICES_VAR__` |
| c | `entrypoint`/`command` der OpenCloud-Container | `docker-compose.yml` | D.4 (`command`), Init-Logik |
| d | Realm-Datei: Name, Clients (`web`, `OpenCloudDesktop`, `OpenCloudIOS`, `OpenCloudAndroid`) mit Redirect-URIs, Realm-Rollen (`opencloudAdmin`, `opencloudSpaceAdmin`, `opencloudUser`, `opencloudGuest`), Default-Rolle, Mapper für `roles` und `uuid`, LDAP-Federation (`connectionUrl`, `bindDn`, **`editMode`**), enthaltene `users`, vorhandener `smtpServer`-Block, Platzhalter-Mechanismus für Domain/Passwort | `config/keycloak/*.json`, ggf. Entrypoint-Skript | C.3 |
| e | LDAP: Base-DN, Admin-DN, Port, Env-Variablen des Images, Seed-LDIFs und Schema, **welche Einträge Demo-Konten sind** | `idm/ldap-keycloak.yml`, `config/ldap/**` | C.3, Stolperstein 1 |
| f | `config/opencloud/*` (CSP, Proxy, Apps, Passwortliste) und wo sie gemountet werden | `docker-compose.yml` | D.3 |
| g | `cap_add`, `user`, Ports von Collabora; ob `home_mode` gesetzt ist | `weboffice/collabora.yml` | D.5 |

**Init-Flags prüfen** (Wegwerf-Pod, keine Secrets):

```bash
kubectl run oc-init-help --rm -i --quiet --restart=Never -n default \
  --image=docker.io/opencloudeu/opencloud:${V} -- init --help
# Notieren: Flags für "insecure" und Admin-Passwort, ob init ohne TTY interaktiv fragt.
# Daraus __INIT_FLAGS__ ableiten: nicht-interaktiv, Zertifikatsprüfung AN (gültige Zertifikate),
# bei Pflicht-Admin-Passwort einen Zufallswert (idm läuft mit Keycloak nicht, der Wert bleibt ungenutzt).
```

> Falls das Image einen anderen Entrypoint als `opencloud` hat, `--command -- opencloud init --help` verwenden und `command:` in D.4 entsprechend setzen.

## 0.5 — Abgeleitete Werte

| Platzhalter | Regel |
|---|---|
| `__DATA_SIZE__` | `DROPBOX_GB / 1024 × 1,5`, aufgerundet auf volle `Ti`, mindestens `1Ti` (bei 1,5–3 TB also `3Ti`–`5Ti`) |
| `__KEYCLOAK_TAG__`, `__COLLABORA_TAG__`, `__TIKA_TAG__`, `__RCLONE_TAG__` | aus 0.3/0.4 |
| `__INIT_FLAGS__` | aus 0.4 |
| `__ADD_SERVICES_VAR__` | aus 0.4 b (Variable, mit der der Container zusätzliche Dienste startet) |
| `__ACME_EMAIL__` | aus 0.0 |
| OpenCloud-Tag | `7.2.3` im Rezept überall durch die höchste 7.2.x ersetzen |

Feste Werte aus dem Repo (keine Platzhalter mehr): cert-manager-Namespace `cert-manager`, HTTP-Listener `http`, Gateway-Manifest `infrastructure/controllers/networking/pantheon-gateway.yaml`, Flux `infrastructure-networking` und `infrastructure-cert-manager`. Weicht 0.2 davon ab → STOPP.

**Laufzeiten hochrechnen** (für den Abschlussbericht): Vollkopie ≈ `DROPBOX_GB × 8000 / DOWN_MBIT / 3600 × 1,3` Stunden; Off-site-Erstlauf ≈ `DROPBOX_GB × 8000 / UP_MBIT / 3600 × 1,3` Stunden (GB → Mbit: × 8000) (Faktor 1,3 für Protokoll-Overhead und Drosselung). Tagsüber bremst `--bwlimit` den Off-site-Lauf zusätzlich (Block H).

**STOPP-Bedingungen Teil 0:**

| Befund | Warum STOPP |
|---|---|
| Gateway hat bereits einen HTTPS-Listener oder der Listener heißt nicht `http` | Block B müsste angepasst werden — Rico entscheidet |
| Eine Flux-Kustomization liest `networking/certificates` bereits mit | Doppelte Verwaltung in Block B |
| `QNAP_FREE_TB` < `__DATA_SIZE__` × 1,2 (Snapshot-Reserve) | Daten-PVC und Snapshots würden den Pool füllen — *eingetreten 16.11.2026 (2,5 < 3,6), Lösung: 0.6* |
| Mail-DNS weicht von AFFiNE Teil G ab (MX, SPF, DKIM) | Keycloak/OpenCloud-Mails würden abgewiesen — erst klären |
| OpenLDAP-Image aus Upstream stammt von `bitnami`/`bitnamilegacy` ohne laufende Updates | widerspricht Renovate-Strategie (Stolperstein 6) — Rico entscheidet über die Alternative — *eingetreten 16.11.2026, Lösung: Architekturentscheidung 3 (1.2)* |
| Realm `editMode` ist nicht `WRITABLE` | Konten ließen sich nicht in Keycloak anlegen — C.5 müsste auf LDAP-Anlage umgestellt werden |
| Freie Worker-Kapazität < 5 GiB RAM Requests | OpenCloud + Keycloak + Collabora + Tika passen nicht |
| `TIMEOUTS_OK` fehlt | Route-Timeouts in D.6 nicht möglich — Rico entscheidet |
| `DROPBOX_APPS` nennt Apps, die Dropbox als Sync-Ziel nutzen | kein STOPP — in `UPSTREAM.md` unter „Abhängigkeiten der Kündigung" aufnehmen; Block J prüft sie |

**Commit Teil 0** (zwei Commits: Rezept + Steuerung, dann Ergebnisse):

```bash
git add docs/rezepte/rezept-opencloud-pantheon.md CLAUDE.md
git commit -m "docs(opencloud): add recipe 1.1 and switch current project to opencloud"
git add apps/pantheon/opencloud/UPSTREAM.md docs/rezepte/rezept-opencloud-pantheon.md
git commit -m "docs(opencloud): record upstream baseline, versions and cluster facts"
git show --stat HEAD~1 HEAD            # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
```

### Ergebnisprotokoll Teil 0

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| Gateway-IP / Listener | `192.168.178.224`, nur `http` | `192.168.178.224`, nur `http HTTP 80` ohne hostname ✅ |
| cert-manager-Namespace | `cert-manager` | `cert-manager`; CRDs da; nur `cnpg-system/selfsigned-issuer`, kein ACME-Issuer; `networking/kustomization.yaml` listet `certificates` nicht ✅ |
| Mail-DNS | wie AFFiNE G.2 | MX `mx00`/`mx01.ionos.de`, ein SPF `include:_spf-eu.ionos.com ~all`, DMARC `p=none`, DKIM `s1-ionos` → CNAME `s1.dkim.ionos.com`, Schlüssel vorhanden; AFFiNE `smtp.ionos.de`/`587`/`noreply@rm-it.org` ✅ |
| Upstream-Commit `opencloud-compose` | SHA | `d4695d235639f7b14b63efef12d67cfbaab557a6` (13.11.2026) |
| OpenCloud-Tag | höchste 7.2.x | `7.2.5` (Manifest 200; 8.x/9.x nur `opencloud-rolling`) |
| Keycloak / Collabora / Tika / OpenLDAP / rclone | konkrete Tags | `26.8.2` / `26.04.6.1.1` / `4.2.0` / ⛔ `bitnamilegacy/openldap:2.6` (STOPP → entfällt, Architekturentscheidung 3) / `1.76.0` |
| `__ADD_SERVICES_VAR__` | Variablenname | `OC_ADD_RUN_SERVICES`; `__INIT_FLAGS__` = `--insecure false` |
| Realm `editMode` / Default-Rolle | `WRITABLE` / `opencloudGuest` | `WRITABLE` / `default-roles-opencloud` ⊃ `opencloudGuest` ✅ |
| Demo-Konten im LDAP-Seed | Liste | `uid=admin` (fester Hash, Standard-Seed!), `alan`, `lynn`, `mary`, `margaret`, `dennis`; 9 Demo-Gruppen; Realm-Demo-Gruppen (u. a. `unix-lovers`→`opencloudAdmin`) |
| `__DATA_SIZE__` | aus `DROPBOX_GB` | 1690 GB → `3Ti`; ⛔ QNAP frei 2,5 TB < 3,6 (STOPP → Freiräumen in 0.6) |
| `allowVolumeExpansion` | `true`/`false` | `true`; Worker ~41 GiB RAM-Requests frei; `TIMEOUTS_OK` ✅ |
| Hochrechnung Kopie / Off-site-Erstlauf | Stunden | ≈ 20 h / ≈ 122 h (≈ 5 Tage), bei 250/40 Mbit/s |
| Abhängigkeiten der Kündigung (`DROPBOX_APPS`) | Liste | SafeInCloud (Passwort-Datenbank), Obsidian (Vault) |
| Entscheidungen Rico (16.11.2026) | — | Identität: Autoprovisioning ins eingebaute `idm`; WOPI über `cloud.rm-it.org/wopi`, kein `wopi.rm-it.org`; Speicher freiräumen (0.6) |

## 0.6 — Speicher im QNAP-Pool freiräumen *(Rico, ~1 h aktiv, spätestens vor Block F)*

**Warum:** Teil 0 hat einen STOPP ergeben: frei sind 2,5 TB, nötig sind `3Ti` × 1,2 ≈ 3,6 TB (Daten-PVC plus Snapshot-Reserve). Die Trident-LUNs sind *Thin* — das PVC belegt nur, was geschrieben wird. Die Reserve muss aber da sein, bevor Block F 1,7 TB kopiert. Blöcke A–E dürfen parallel laufen; **Block F startet erst, wenn das Ergebnisprotokoll 0.6 ≥ 3,6 TB zeigt.**

**Ausgangslage** (QNAP → Speicher & Snapshots → Übersicht, 16.11.2026):

| Volume | Typ | Belegt / Größe | Maßnahme | Gewinn |
|---|---|---|---|---|
| Transfer | Thin | 186 GB / 341 GB | löschen | ≈ 0,19 TB |
| Abyss Of Hel | Thick | 0,86 GB / 1014 GB | auf 100 GB verkleinern | ≈ 0,9 TB |
| TimeMachine | Thick | 0,94 TB / 2,42 TB | auf 1,5 TB verkleinern (1,5 × 1 TB MacBook) | ≈ 0,9 TB |
| UrdaSot | Thick | 56 GB / 1014 GB | verschlüsselt auf die Storage Box archivieren, dann löschen | ≈ 1,0 TB |
| PrivateCloud | Thin | 1,34 TB / 2,93 TB | **bleibt** bis Block J (HBS-3-Spiegel der Dropbox) | später ≈ 1,34 TB |

Erwartet frei danach: **≈ 5,5 TB**. PrivateCloud kann als Thin-Volume bis zur Dropbox-Quote (2000 GB) noch ≈ 0,5 TB wachsen — auch dann bleibt genug.

> PrivateCloud (1,34 TB) ist kleiner als der Dropbox-Bestand (1690 GB) — der HBS-3-Spiegel ist vermutlich unvollständig und **kein** Ersatz für die Migration über die Dropbox-API (Block F) oder deren Hash-Prüfung (Block G).

> **⏸ [Rico] — Reihenfolge einhalten; alles in der QNAP-Oberfläche bzw. im Browser**
>
> **1. Transfer prüfen und löschen**
> 1. File Station → Freigabeordner von *Transfer* öffnen: Liegt dort etwas, das in die Migration oder ins Archiv gehört? Falls ja, vorher nach *Wolfstavar* verschieben.
> 2. Speicher & Snapshots → Speicher → Speicher/Snapshots → *Transfer* markieren → **Verwalten → Entfernen** → Volume löschen bestätigen.
>
> **2. Abyss Of Hel auf 100 GB verkleinern**
> 1. *Abyss Of Hel* markieren → **Verwalten → Größe ändern** (je nach QTS-Version unter *Aktionen*) → neue Größe **100 GB** → Übernehmen.
> 2. Lässt QNAP das Verkleinern nicht zu (Option fehlt oder Hinweis auf Snapshots): **nichts löschen**, Meldung an Claude Code notieren.
>
> **3. TimeMachine auf 1,5 TB verkleinern**
> 1. Mac: *Systemeinstellungen → Allgemein → Time Machine → Optionen → Backup-Häufigkeit: Manuell* (keine Sicherung während der Größenänderung).
> 2. QNAP: *TimeMachine* markieren → **Verwalten → Größe ändern** → **1,5 TB** → Übernehmen; warten, bis der Status wieder *Bereit* ist.
> 3. Mac: Backup-Häufigkeit zurück auf *Automatisch stündlich*, dann **Backup jetzt erstellen** — muss ohne Fehler durchlaufen.
> 4. Bietet QNAP das Verkleinern nicht an: **nicht** das Volume löschen. Meldung an Claude Code notieren; Ausweg wäre ein neues Thin-Volume mit 1,5 TB und eine frische Time-Machine-Sicherung (Versionsverlauf geht verloren) — das entscheidet Rico gesondert.
>
> **4. UrdaSot verschlüsselt archivieren, prüfen, dann löschen**
> 1. **Hetzner-Konsole → Storage Box `u620152` → Sub-Accounts → Sub-Account erstellen:** Basisverzeichnis `urdasot-archiv`, **WebDAV-Support an**, externe Erreichbarkeit an, Kommentar „UrdaSot-Archiv". Passwort im Passwortmanager ablegen als **„Hetzner Storage Box – Sub-Account urdasot-archiv"**. Hetzner vergibt die Namen fortlaufend; Paperless hat `u620152-sub1`, dieser wird also voraussichtlich **`u620152-sub2`**. Den tatsächlichen Namen ins Ergebnisprotokoll 0.6 eintragen — Block H rechnet mit `u620152-sub3` für das OpenCloud-Backup.
> 2. **QNAP → HBS 3 → Sichern → Erstellen → Neuer Sicherungsauftrag:** Quelle = Freigabeordner von *UrdaSot* (alles). Ziel = *Cloud-Speicher → WebDAV*, URL `https://` + Sub-Account-Name + `.your-storagebox.de`, Benutzer = Sub-Account-Name, Passwort aus Schritt 1, Zielordner `urdasot`. Auftragsname `UrdaSot-Archiv`.
> 3. In den **Richtlinien** des Auftrags: **Clientseitige Verschlüsselung an**. Passwort im Passwortmanager ablegen als **„HBS 3 – Verschlüsselung UrdaSot-Archiv"** — ohne dieses Passwort ist das Archiv wertlos. Zeitplan: *Keiner* (einmaliger Lauf). Versionsverwaltung: Standard lassen.
> 4. Auftrag **jetzt sichern** → warten bis *Abgeschlossen* (56 GB bei 40 Mbit/s Upload ≈ 3–4 h).
> 5. **Wiederherstellung prüfen:** HBS 3 → *Wiederherstellen* → Auftrag aus dem Ziel `UrdaSot-Archiv` → 3–5 Dateien unterschiedlichen Typs (eine große, ein Dokument, ein Unterordner) in einen neuen Ordner `_restore-test` auf *Wolfstavar* zurückholen → öffnen, Inhalt prüfen → `_restore-test` löschen.
> 6. Optional, für eine zweite Kopie: denselben Auftrag zusätzlich auf eine externe USB-Platte.
> 7. Erst jetzt: *UrdaSot* markieren → **Verwalten → Entfernen**. Die 5 Snapshots des Volumes verschwinden dabei mit.
>
> **Hinweis zur Langlebigkeit:** Das Archiv liegt im HBS-3-Format (QuDedup). Ohne QNAP lässt es sich mit dem *QuDedup Extract Tool* (macOS/Windows, von qnap.com) und dem Verschlüsselungspasswort entpacken.
>
> **5. Ergebnis ablesen:** Speicher & Snapshots → Übersicht → Speicherpool 1 → **Freier Speicher**.
>
> **Fortsetzungssatz an Claude Code:** „Speicher freigeräumt, frei: … TB" (Zahl eintragen) — oder die Meldung aus Schritt 2, 3 oder 4.

Claude Code trägt die Werte ins Ergebnisprotokoll 0.6 ein, setzt im Blockplan „0.6 offen" auf ✅ mit Datum und committet (`docs(opencloud): record storage cleanup on qnap`). Bei < 3,6 TB: STOPP, Rico entscheidet (z. B. `__DATA_SIZE__ = 2Ti` mit späterer Erweiterung, `allowVolumeExpansion: true`).

### Ergebnisprotokoll 0.6

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| Transfer gelöscht | ja | |
| Abyss Of Hel | 100 GB | |
| TimeMachine | 1,5 TB, Time-Machine-Sicherung danach ok | |
| UrdaSot-Archiv auf der Storage Box | Sub-Account `u620152-sub2`, Auftrag abgeschlossen | |
| Wiederherstellungsprobe UrdaSot | Dateien öffnen sich | |
| UrdaSot gelöscht | ja | |
| Freier Speicher nach 0.6 | ≥ 3,6 TB (erwartet ≈ 5,5 TB) | |

---

# Block A — Secrets *(Rico, ~15 Min)*

> **⏸ Dieser ganze Block ist Ricos Teil.** Claude Code führt ihn **nicht** aus. Er erzeugt alle Grund-Secrets in einem Durchgang und verschlüsselt sie, bevor etwas davon in einer Claude-Sitzung sichtbar wird.

## A.1 — Cloudflare-API-Token anlegen *(Weboberfläche)*

**Cloudflare Dashboard → My Profile → API Tokens → Create Token → Custom token:**
- Permissions: **Zone → DNS → Edit** und **Zone → Zone → Read**
- Zone Resources: **Include → Specific zone → `rm-it.org`**
- Token kopieren (wird nur einmal angezeigt).

> Der Token darf nur DNS der einen Zone ändern — cert-manager legt damit kurzlebige `_acme-challenge`-TXT-Einträge an.

## A.2 — Secrets erzeugen und verschlüsseln *(eigenes Terminal, vier Schritte)*

Muster wie AFFiNE G.4: `umask 077`, `kubectl create secret … --dry-run=client` maskiert Sonderzeichen (wichtig für das IONOS-Passwort) und spricht nicht mit dem Cluster. Bricht `sops` ab, wird die Klartextdatei gelöscht. **Eingaben stehen in eigenen Schritten** — nie zusammen mit anderen Zeilen einfügen. Ein **neues Terminal-Fenster** nur für diesen Abschnitt öffnen (⌘N).

**Schritt 1 — vorbereiten** *(ohne Eingabe, im Ganzen einfügen)*:

```bash
cd ~/k8s-cluster && umask 077 && mkdir -p apps/pantheon/opencloud infrastructure/controllers/networking/certificates && for f in infrastructure/controllers/databases/pantheon-pg/keycloak-db-role-secret.yaml apps/pantheon/opencloud/opencloud-secret.yaml apps/pantheon/opencloud/opencloud-smtp-secret.yaml infrastructure/controllers/networking/certificates/cloudflare-api-token-secret.yaml; do test -e "$f" && echo "ABBRUCH: $f existiert schon"; done; echo VORBEREITET
# Erwartung: nur VORBEREITET
```

**Schritt 2 — Cloudflare-Token** *(einzeln einfügen, dann Token einfügen + Enter)*:

```bash
printf 'Cloudflare-API-Token (cert-manager, DNS-01 rm-it.org): '; read -rs CF_TOKEN; echo; echo "Länge: ${#CF_TOKEN}"
```

**Schritt 3 — Postfachpasswort** *(einzeln einfügen, dann Passwort einfügen + Enter)*:

```bash
printf 'Postfachpasswort noreply@rm-it.org (IONOS, wie affine-smtp): '; read -rs SMTP_PW; echo; echo "Länge: ${#SMTP_PW}"
```

**Schritt 4 — erzeugen und verschlüsseln** *(ohne Eingabe, im Ganzen einfügen; Subshell übernimmt beide Variablen)*:

```bash
(
cd ~/k8s-cluster || exit 1
D=infrastructure/controllers/databases/pantheon-pg
O=apps/pantheon/opencloud
C=infrastructure/controllers/networking/certificates
test -n "$CF_TOKEN" && test -n "$SMTP_PW" || { echo "ABBRUCH: Token oder Postfachpasswort leer"; exit 1; }
KC_DBPW=$(openssl rand -hex 24)
KC_ADMINPW=$(openssl rand -hex 16)

kubectl create secret generic keycloak-db-role -n databases --type=kubernetes.io/basic-auth \
  --from-literal=username=keycloak --from-literal=password="$KC_DBPW" \
  --dry-run=client -o yaml > "$D/keycloak-db-role-secret.yaml"
kubectl create secret generic opencloud-secret -n opencloud \
  --from-literal=keycloak-db-password="$KC_DBPW" \
  --from-literal=keycloak-admin-password="$KC_ADMINPW" \
  --dry-run=client -o yaml > "$O/opencloud-secret.yaml"
kubectl create secret generic opencloud-smtp -n opencloud \
  --from-literal=smtp-password="$SMTP_PW" \
  --dry-run=client -o yaml > "$O/opencloud-smtp-secret.yaml"
kubectl create secret generic cloudflare-api-token -n cert-manager \
  --from-literal=api-token="$CF_TOKEN" \
  --dry-run=client -o yaml > "$C/cloudflare-api-token-secret.yaml"

for f in "$D/keycloak-db-role-secret.yaml" "$O/opencloud-secret.yaml" \
         "$O/opencloud-smtp-secret.yaml" "$C/cloudflare-api-token-secret.yaml"; do
  sops --encrypt --in-place "$f" || { rm -f "$f"; echo "ABBRUCH: sops bei $f, Datei entfernt"; }
done

echo
echo "Keycloak-Bootstrap-Admin (Realm master, temporär) – Benutzer: kcadmin  Passwort: $KC_ADMINPW"
echo
grep -c 'ENC\[' "$D/keycloak-db-role-secret.yaml" "$O/opencloud-secret.yaml" \
  "$O/opencloud-smtp-secret.yaml" "$C/cloudflare-api-token-secret.yaml"
)
# Erwartung: je Datei eine Zahl >= 2
```

Passwort im Passwortmanager ablegen als **„Keycloak-Bootstrap-Admin kcadmin (Realm master, temporär)"** (gebraucht in C.5, danach nur noch für einen Neuaufbau). Dann **einzeln** `unset CF_TOKEN SMTP_PW; clear; exit` und das Fenster schließen.

> **⚠️ Stolperstein 20 — `.sops.yaml` verschlüsselt nur `data`/`stringData`.** `kubectl create … -o yaml` schreibt die Werte unter `data` (Base64) — die Regel greift. Ein `grep -c 'ENC\['` von `0` heißt: Datei ist Klartext — nicht committen.

> Das Keycloak-DB-Passwort wird zweimal gebraucht (Rolle in `databases`, App in `opencloud`). Aus derselben Variable im selben Block erzeugt, können die beiden Stellen nicht auseinanderlaufen (AFFiNE A.1). Das IONOS-Passwort ist dasselbe wie in `affine-smtp` (Stolperstein 24).

**Fortsetzungssatz an Claude Code:** „Secrets für OpenCloud liegen bereit, starte Block B."

---

# Block B — HTTPS am Gateway, LAN-Direktweg *(Claude Code, ohne HALT)*

**Ziel:** Wildcard-Zertifikat `*.rm-it.org` und ein HTTPS-Listener am `pantheon-gateway`. Danach sind alle `*.rm-it.org`-Routen im LAN per HTTPS erreichbar, sobald ein Hostname auf `192.168.178.224` auflöst.

## B.1 — Eingangsprüfung

```bash
grep -c 'ENC\[' infrastructure/controllers/networking/certificates/cloudflare-api-token-secret.yaml
grep -E '^\s+api-token:' infrastructure/controllers/networking/certificates/cloudflare-api-token-secret.yaml
# Erwartung: Zahl >= 2; Wertzeile beginnt mit ENC[
```

## B.2 — Issuer, Zertifikat, Flux-Kustomization

`infrastructure/controllers/networking/certificates/clusterissuer-letsencrypt-dns.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-dns
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: __ACME_EMAIL__
    privateKeySecretRef:
      name: letsencrypt-dns-account-key
    solvers:
      - dns01:
          cloudflare:
            apiTokenSecretRef:
              name: cloudflare-api-token
              key: api-token
        selector:
          dnsZones:
            - rm-it.org
```

`infrastructure/controllers/networking/certificates/certificate-wildcard-rm-it-org.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-rm-it-org
  namespace: default            # Namespace des Gateways — der Listener liest das Secret von hier
spec:
  secretName: wildcard-rm-it-org-tls
  issuerRef:
    kind: ClusterIssuer
    name: letsencrypt-dns
  dnsNames:
    - "*.rm-it.org"
```

`infrastructure/controllers/networking/certificates/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - cloudflare-api-token-secret.yaml
  - clusterissuer-letsencrypt-dns.yaml
  - certificate-wildcard-rm-it-org.yaml
```

`clusters/pantheon/infrastructure-certificates.yaml` — eigener Schalter, nach cert-manager (Operator/CR-Split wie beim Barman-Plugin):

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure-certificates
  namespace: flux-system
spec:
  interval: 10m
  dependsOn:
    - name: infrastructure-cert-manager
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure/controllers/networking/certificates
  prune: true
  wait: false
  decryption:
    provider: sops
    secretRef:
      name: sops-age
```

> **Prüfen vor dem Commit:** `infrastructure/controllers/networking/kustomization.yaml` listet ihre Ressourcen explizit (`lb-ip-pool.yaml`, `l2-announcement-policy.yaml`, `pantheon-gateway.yaml`, `cloudflared`) und darf `certificates` **nicht** aufnehmen — sonst würde dasselbe Objekt von zwei Flux-Kustomizations verwaltet.

## B.3 — Committen, Zertifikat abwarten

```bash
kubectl kustomize infrastructure/controllers/networking/certificates/ > /dev/null && echo BUILD_OK
git add infrastructure/controllers/networking/certificates/ clusters/pantheon/infrastructure-certificates.yaml
git commit -m "feat(certs): add letsencrypt dns-01 issuer and wildcard certificate"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source
flux get kustomizations infrastructure-certificates
kubectl wait --for=condition=Ready clusterissuer/letsencrypt-dns --timeout=3m
kubectl wait --for=condition=Ready certificate/wildcard-rm-it-org -n default --timeout=10m
# Erwartung: beide "condition met"
```

> Läuft das Warten ins Zeitlimit: `kubectl describe challenge -A` lesen (lesend erlaubt). Typisch: Token ohne `Zone:Read` oder falsche Zone. Let's Encrypt erlaubt nur wenige fehlgeschlagene Validierungen pro Stunde — nicht wiederholt neu anstoßen, sondern STOPP und berichten.

## B.4 — HTTPS-Listener

In `infrastructure/controllers/networking/pantheon-gateway.yaml` unter `spec.listeners` **nach** dem Listener `http` ergänzen, `http` unverändert lassen:

```yaml
    - name: https
      protocol: HTTPS
      port: 443
      hostname: "*.rm-it.org"
      tls:
        mode: Terminate
        certificateRefs:
          - kind: Secret
            name: wildcard-rm-it-org-tls
      allowedRoutes:
        namespaces:
          from: All
```

```bash
kubectl kustomize infrastructure/controllers/networking/ > /dev/null && echo BUILD_OK
git add infrastructure/controllers/networking/pantheon-gateway.yaml
git commit -m "feat(networking): add https listener for *.rm-it.org to gateway"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source
flux reconcile kustomization infrastructure-networking
flux get kustomizations infrastructure-networking
# Erwartung: READY True (die Kustomization hat wait: true — ein nicht programmierbarer Listener fiele hier auf)
```

> **⚠️ Stolperstein 23 — Tunnel bleibt auf dem HTTP-Listener.** `cloudflared` liefert per `http://…:80` an den Listener `http`. Das ist gewollt: Routen, die nur am Listener `https` hängen (Keycloak-Administration), sind dadurch von außen unerreichbar. Den Tunnel nicht auf `https://` umstellen, ohne Architekturentscheidung 2, Punkt 3 neu zu bewerten.

## B.5 — Verifizieren

```bash
kubectl get gateway -n default pantheon-gateway \
  -o jsonpath='{range .status.listeners[*]}{.name} {.attachedRoutes} {.conditions[?(@.type=="Programmed")].status}{"\n"}{end}'
# Erwartung: Listener "https" mit Programmed=True; attachedRoutes = Zahl der *.rm-it.org-Routen

# Eine bestehende *.rm-it.org-Route per HTTPS über die LAN-IP ansprechen (DNS-unabhängig):
HOST=$(kubectl get httproute -A -o jsonpath='{range .items[*]}{.spec.hostnames[0]}{"\n"}{end}' | grep 'rm-it.org$' | head -1)
curl -sS -o /dev/null -w "%{http_code}\n" --resolve "$HOST:443:192.168.178.224" "https://$HOST/"
echo | openssl s_client -connect 192.168.178.224:443 -servername "$HOST" 2>/dev/null \
  | openssl x509 -noout -issuer -subject -enddate
# Erwartung: HTTP-Code der App (200/302); issuer Let's Encrypt; subject CN=*.rm-it.org
```

> Bestehende Routen (Homepage, AFFiNE …) hängen jetzt zusätzlich am HTTPS-Listener. Wirksam wird das im LAN erst, wenn AdGuard ihren Namen auf die Gateway-IP umschreibt — für sie ändert sich also nichts, bis Rico das ausdrücklich will.

### Ergebnisprotokoll Block B

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| ClusterIssuer Ready | True | True (condition met) |
| Certificate Ready, Ablaufdatum | True, +90 Tage | True; 16.11.2026 → 14.02.2027, Erneuerung ab 15.01.2027 |
| Listener `https` Programmed | True | True, ResolvedRefs True, attachedRoutes 3 (affine, homepage, paperless); `http` unverändert (4, True) |
| `curl --resolve` auf bestehende Route | 200/302, LE-Zertifikat | `affine.rm-it.org`: 200; issuer Let's Encrypt YR1, CN=*.rm-it.org; HTTP-Listener weiter 200 |

---

# Block C — Identität: Keycloak-Datenbank, Keycloak *(1 HALT)*

## C.1 — Eingangsprüfung

```bash
grep -c 'ENC\[' infrastructure/controllers/databases/pantheon-pg/keycloak-db-role-secret.yaml \
  apps/pantheon/opencloud/opencloud-secret.yaml apps/pantheon/opencloud/opencloud-smtp-secret.yaml
grep -E '^\s+smtp-password:' apps/pantheon/opencloud/opencloud-smtp-secret.yaml | grep -c 'ENC\['
kubectl get certificate -n default wildcard-rm-it-org -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
test -f apps/pantheon/opencloud/UPSTREAM.md && echo UPSTREAM_OK
# Erwartung: Zahlen >= 2; 1; True; UPSTREAM_OK
```

## C.2 — Datenbank-Rolle und Datenbank (sofort live, wie AFFiNE A.2)

`infrastructure/controllers/databases/pantheon-pg/keycloak-role.yaml`:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: DatabaseRole
metadata:
  name: keycloak
  namespace: databases
spec:
  cluster:
    name: pantheon-pg
  name: keycloak
  ensure: present
  login: true
  passwordSecret:
    name: keycloak-db-role
```

`infrastructure/controllers/databases/pantheon-pg/keycloak-database.yaml`:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: keycloak
  namespace: databases
spec:
  cluster:
    name: pantheon-pg
  name: keycloak
  owner: keycloak
```

In `infrastructure/controllers/databases/pantheon-pg/kustomization.yaml` am Ende anhängen — Secret und Role vor der Database:

```yaml
  - keycloak-db-role-secret.yaml
  - keycloak-role.yaml
  - keycloak-database.yaml
```

```bash
kubectl kustomize infrastructure/controllers/databases/pantheon-pg/ > /dev/null && echo BUILD_OK
D=infrastructure/controllers/databases/pantheon-pg
git add "$D/keycloak-db-role-secret.yaml" "$D/keycloak-role.yaml" "$D/keycloak-database.yaml" "$D/kustomization.yaml"
git commit -m "feat(databases): add keycloak role and database for opencloud"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source
flux reconcile kustomization infrastructure-databases-cluster
kubectl get database keycloak -n databases -o jsonpath='{.status.applied}{"\n"}'
# Erwartung: true
```

## C.3 — Namespace, Keycloak, Routen

`apps/pantheon/opencloud/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: opencloud
  labels:
    # Collabora braucht zusätzliche Capabilities (MKNOD o. ä., Teil 0.4 g) -> 'baseline'.
    # Alle übrigen Pods setzen trotzdem restricted-konforme securityContexts.
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/warn: baseline
```

### C.3.1 — entfällt seit 1.2

Kein OpenLDAP mehr (Architekturentscheidung 3). Die Nummer bleibt, damit Verweise stabil sind.

> **⚠️ Stolperstein 1 — Demo-Konten mit bekannten Passwörtern.** Upstreams Realm-Datei für den Autoprovisioning-Modus enthält sechs Konten (`admin`, `alan`, `dennis`, `lynn`, `margaret`, `mary`) und neun Demo-Gruppen, darunter `unix-lovers` mit der Rolle `opencloudAdmin`. Auf einer öffentlich erreichbaren Instanz sind das offene Türen. C.3.2 leert `users` und `groups` vollständig. OpenCloud selbst legt kein Admin-Konto an (`OC_ADMIN_USER_ID=""` in D.4; Gegenprobe D.9). Liste der entfernten Einträge in `UPSTREAM.md`.

> **⚠️ Stolperstein 6 — Bitnami-Images.** Bitnami hat seinen Katalog 2025 hinter ein Abonnement verschoben; `bitnamilegacy/*` bekommt keine Updates mehr. In 1.1 betraf das OpenLDAP — deshalb seit 1.2 kein LDAP (Architekturentscheidung 3). Taucht ein solches Image später in einer Upstream-Datei auf: nicht übernehmen, STOPP.

### C.3.2 — Realm-Datei (`apps/pantheon/opencloud/keycloak/opencloud-realm.json`)

Aus der Upstream-Realm-Datei **`config/keycloak/opencloud-realm-autoprovisioning.dist.json`**, mit diesen Änderungen (per `jq`, Diff in `UPSTREAM.md`):

1. Alle Upstream-Domains (`cloud.opencloud.test`, `keycloak.opencloud.test`, …) → Pantheon-Hostnamen.
2. `"registrationAllowed": false`, `"bruteForceProtected": true`, `"resetPasswordAllowed": true` (Passwort vergessen per Mail), `"verifyEmail": false`, `"loginWithEmailAllowed": true`, `"actionTokenGeneratedByAdminLifespan": 259200` (Einladungslinks 72 h gültig statt 12 h).
3. `users` **und** `groups` leeren (Stolperstein 1).
4. **Default-Rolle** `default-roles-opencloud` um die Realm-Rolle `opencloudGuest` ergänzen. In der Autoprovisioning-Datei enthält sie keine OpenCloud-Rolle — ein neues Konto hätte sonst keine Rolle. So ist jedes neue Konto zunächst Gast (Stolperstein 2). Keine Klartext-Passwörter in Git; Keycloak ersetzt `${…}` beim Import aus Umgebungsvariablen.
5. **`smtpServer`** setzen (vorhandenen Upstream-Block ersetzen) — Werte wie AFFiNE Teil G:
   ```json
   "smtpServer": {
     "host": "smtp.ionos.de",
     "port": "587",
     "from": "noreply@rm-it.org",
     "fromDisplayName": "Pantheon Cloud",
     "replyTo": "noreply@rm-it.org",
     "envelopeFrom": "noreply@rm-it.org",
     "starttls": "true",
     "ssl": "false",
     "auth": "true",
     "user": "noreply@rm-it.org",
     "password": "${SMTP_PASSWORD}"
   }
   ```
6. `"internationalizationEnabled": true`, `"supportedLocales": ["de", "en"]`, `"defaultLocale": "de"` — Login-Seite und Mails für Bandkollegen auf Deutsch.
7. Clients, Rollen und Mapper sonst unverändert. Keine LDAP-Federation (die Autoprovisioning-Datei enthält keine).
8. **`components["org.keycloak.keys.KeyProvider"]` löschen** — die Upstream-Datei enthält echte Schlüssel (RSA-`privateKey`, HMAC- und AES-`secret`), öffentlich auf GitHub. Ohne den Abschnitt erzeugt Keycloak beim Import eigene (Stolperstein 29).
9. `"loginTheme": ""` — das Upstream-Theme `opencloud` wird nicht eingebunden; Keycloak nutzt seine Standard-Anmeldeseite.

```bash
R=apps/pantheon/opencloud/keycloak/opencloud-realm.json
jq -e '.registrationAllowed == false and .bruteForceProtected == true and .resetPasswordAllowed == true
       and ((.users // []) | length == 0) and ((.groups // []) | length == 0)
       and ((.components["org.keycloak.storage.UserStorageProvider"] // []) | length == 0)
       and ([.roles.realm[] | select(.name == "default-roles-opencloud") | .composites.realm[]] | index("opencloudGuest") != null)
       and .smtpServer.host == "smtp.ionos.de" and .smtpServer.from == "noreply@rm-it.org"
       and .smtpServer.password == "${SMTP_PASSWORD}"' "$R" && echo REALM_OK
grep -c 'opencloud.test' "$R"
grep -cE '"password"\s*:\s*"[^$]' "$R"
jq -c '[(.components["org.keycloak.keys.KeyProvider"] // [] | length),
        ([paths as $p | select(($p[-1]|tostring)|test("^(privateKey|certificate)$"))] | length),
        ([.. | objects | .secret? // empty | select(test("^\\*+$")|not)] | length)]' "$R"
# Erwartung: REALM_OK; 0; 0; [0,0,0]  (kein Passwort im Klartext, nur ${…}-Platzhalter; kein Schlüsselmaterial)
```

> **⚠️ Stolperstein 29 — Schlüssel in der Upstream-Realm-Datei.** `opencloud-realm-autoprovisioning.dist.json` (Upstream `d4695d2`) enthält das Schlüsselmaterial des Exports: RSA-Signaturschlüssel, HMAC- und AES-Secrets. Importiert, signierte Keycloak Tokens mit einem öffentlich bekannten Schlüssel — jeder könnte sich ein Token mit `opencloudAdmin` ausstellen, OpenCloud prüft per Signatur (`jwt`). Deshalb Punkt 8 und die `[0,0,0]`-Prüfung. Gegenprobe nach dem Import: das `x5c`-Zertifikat aus `/realms/openCloud/protocol/openid-connect/certs` ist **nicht** das aus der Upstream-Datei (C.4).

> **⚠️ Stolperstein 30 — Dateiname = Realm-Name.** Keycloak 26.8 bricht `--import-realm` ab, wenn der Dateiname nicht zum Realm passt (`File name / realm name mismatch … should be openCloud-realm.json`), Groß-/Kleinschreibung zählt. Im `configMapGenerator` deshalb `openCloud-realm.json=keycloak/opencloud-realm.json`.

> **⚠️ Stolperstein 3 — Der Realm-Import läuft nur einmal.** `--import-realm` überspringt einen bereits existierenden Realm. Die Datei in Git ist der **Anfangszustand**; spätere Änderungen (Konten, OTP, Rollen, **SMTP**) leben in der Datenbank. Wer den Realm neu importieren will, muss ihn vorher löschen. Ein geändertes IONOS-Passwort trägt Rico deshalb zusätzlich in der Admin-Konsole ein (Stolperstein 24).

### C.3.3 — Keycloak (`apps/pantheon/opencloud/keycloak/keycloak.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: keycloak
  namespace: opencloud
spec:
  replicas: 1
  selector:
    matchLabels:
      app: keycloak
  template:
    metadata:
      labels:
        app: keycloak
    spec:
      enableServiceLinks: false
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: keycloak
          # renovate: datasource=docker depName=quay.io/keycloak/keycloak
          image: quay.io/keycloak/keycloak:__KEYCLOAK_TAG__
          imagePullPolicy: IfNotPresent
          args: ["start", "--import-realm"]
          env:
            - name: KC_DB
              value: postgres
            - name: KC_DB_URL
              value: jdbc:postgresql://pantheon-pg-rw.databases.svc.cluster.local:5432/keycloak
            - name: KC_DB_USERNAME
              value: keycloak
            - name: KC_DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: opencloud-secret
                  key: keycloak-db-password
            - name: KC_HOSTNAME
              value: https://keycloak.rm-it.org
            - name: KC_HOSTNAME_ADMIN
              value: https://keycloak-admin.rm-it.org
            - name: KC_HTTP_ENABLED
              value: "true"
            - name: KC_PROXY_HEADERS
              value: xforwarded
            - name: KC_HEALTH_ENABLED
              value: "true"
            - name: KC_BOOTSTRAP_ADMIN_USERNAME
              value: kcadmin
            - name: KC_BOOTSTRAP_ADMIN_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: opencloud-secret
                  key: keycloak-admin-password
            - name: SMTP_PASSWORD              # Platzhalter in der Realm-Datei (smtpServer.password)
              valueFrom:
                secretKeyRef:
                  name: opencloud-smtp
                  key: smtp-password
          ports:
            - name: http
              containerPort: 8080
            - name: management
              containerPort: 9000
          startupProbe:
            httpGet:
              path: /health/started
              port: management
            periodSeconds: 10
            failureThreshold: 60
          readinessProbe:
            httpGet:
              path: /health/ready
              port: management
            periodSeconds: 15
          livenessProbe:
            httpGet:
              path: /health/live
              port: management
            periodSeconds: 30
            failureThreshold: 5
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: realm
              mountPath: /opt/keycloak/data/import
              readOnly: true
          resources:
            requests:
              memory: 512Mi
              cpu: 250m
            limits:
              memory: 1536Mi
      volumes:
        - name: realm
          configMap:
            name: keycloak-realm
---
apiVersion: v1
kind: Service
metadata:
  name: keycloak
  namespace: opencloud
spec:
  selector:
    app: keycloak
  ports:
    - name: http
      port: 8080
      targetPort: 8080
```

> **Warum `KC_BOOTSTRAP_ADMIN_*`?** Seit Keycloak 26 ist das der Weg für den ersten Admin; `KEYCLOAK_ADMIN` aus älteren Compose-Dateien ist veraltet. Der Bootstrap-Admin ist ausdrücklich **temporär** — Rico ersetzt ihn in C.5 durch ein dauerhaftes Konto (Stolperstein 17).

### C.3.4 — Routen (`apps/pantheon/opencloud/httproutes.yaml`, erster Teil)

```yaml
# Öffentlich (HTTP- und HTTPS-Listener): nur der OpenCloud-Realm und statische Ressourcen.
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: keycloak
  namespace: opencloud
spec:
  parentRefs:
    - name: pantheon-gateway
      namespace: default
  hostnames:
    - keycloak.rm-it.org
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /realms/openCloud
        - path:
            type: PathPrefix
            value: /resources
      backendRefs:
        - name: keycloak
          port: 8080
---
# Administration: NUR am HTTPS-Listener. Der Tunnel liefert an den HTTP-Listener -> von außen nicht erreichbar.
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: keycloak-admin
  namespace: opencloud
spec:
  parentRefs:
    - name: pantheon-gateway
      namespace: default
      sectionName: https
  hostnames:
    - keycloak-admin.rm-it.org
  rules:
    - backendRefs:
        - name: keycloak
          port: 8080
```

Dritte Route — der `master`-Realm auf dem Haupt-Hostnamen, **nur am HTTPS-Listener** (Stolperstein 31):

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: keycloak-master-lan
  namespace: opencloud
spec:
  parentRefs:
    - name: pantheon-gateway
      namespace: default
      sectionName: https
  hostnames:
    - keycloak.rm-it.org
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /realms/master
      backendRefs:
        - name: keycloak
          port: 8080
```

> **⚠️ Stolperstein 31 — Admin-Konsole meldet über den Haupt-Hostnamen an.** Mit `KC_HOSTNAME_ADMIN` läuft die Konsole unter `keycloak-admin.rm-it.org`, ihr `authServerUrl` ist aber `KC_HOSTNAME` (`https://keycloak.rm-it.org`). Die Konsole prüft dort `/realms/master/protocol/openid-connect/3p-cookies/…` — ohne die Route oben 404 und die Meldung „Timeout when waiting for 3rd party check iframe message". Die Route hängt nur am Listener `https`: im LAN erreichbar, über den Tunnel (HTTP-Listener) bleibt `/realms/master` 404 (C.4/2).

> **⚠️ Stolperstein 4 — `/realms/` wäre zu breit.** Die Keycloak-Doku empfiehlt `/realms/` öffentlich freizugeben. Darunter liegt aber auch `/realms/master` — der Admin-Realm mit Token-Endpunkt. Hier wird bewusst nur `/realms/openCloud` freigegeben.

### C.3.5 — Kustomization und Flux-Schalter

`apps/pantheon/opencloud/kustomization.yaml` (Stand Block C):

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - opencloud-secret.yaml
  - opencloud-smtp-secret.yaml
  - keycloak/keycloak.yaml
  - httproutes.yaml
configMapGenerator:
  - name: keycloak-realm
    namespace: opencloud
    files:
      - openCloud-realm.json=keycloak/opencloud-realm.json   # Keycloak 26.8: Dateiname = Realm-Name (Stolperstein 30)
```

`clusters/pantheon/apps-opencloud.yaml` (Vorlage `apps-affine.yaml`):

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps-opencloud
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./apps/pantheon/opencloud
  prune: true
  wait: false
  decryption:
    provider: sops
    secretRef:
      name: sops-age
```

## C.4 — Ausrollen und prüfen

```bash
kubectl kustomize apps/pantheon/opencloud/ > /dev/null && echo BUILD_OK
grep -rn '__[A-Z_]*__' apps/pantheon/opencloud/ || echo NO_PLACEHOLDERS
O=apps/pantheon/opencloud
git add "$O/kustomization.yaml" "$O/namespace.yaml" "$O/opencloud-secret.yaml" "$O/opencloud-smtp-secret.yaml" \
  "$O/keycloak" "$O/httproutes.yaml" clusters/pantheon/apps-opencloud.yaml
git commit -m "feat(opencloud): add identity layer with keycloak"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source
flux get kustomizations apps-opencloud
kubectl rollout status deploy/keycloak -n opencloud --timeout=10m
kubectl logs -n opencloud deploy/keycloak --since=15m | grep -iE 'import|realm|error' | head -20
# Erwartung: Realm "openCloud" importiert; keine Fehlerzeilen zu SMTP
```

**Prüfungen (alle DNS-unabhängig über `--resolve`):**

```bash
GW=192.168.178.224
# 1. Realm erreichbar, Issuer korrekt (HTTPS-Listener)
curl -s --resolve keycloak.rm-it.org:443:$GW \
  https://keycloak.rm-it.org/realms/openCloud/.well-known/openid-configuration | jq -r .issuer
# Erwartung: https://keycloak.rm-it.org/realms/openCloud

# 2. Tunnel-Pfad simulieren (HTTP-Listener): master-Realm und Admin-Host gesperrt
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: keycloak.rm-it.org" http://$GW/realms/master/
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: keycloak-admin.rm-it.org" http://$GW/
# Erwartung: 404 und 404

# 2b. master-Realm im LAN (HTTPS-Listener) erreichbar — für die Admin-Konsole (Stolperstein 31)
curl -s -o /dev/null -w "%{http_code}\n" --resolve keycloak.rm-it.org:443:$GW \
  https://keycloak.rm-it.org/realms/master/protocol/openid-connect/3p-cookies/step1.html
# Erwartung: 200

# 3. Admin-Host über HTTPS (nur LAN)
curl -s -o /dev/null -w "%{http_code}\n" --resolve keycloak-admin.rm-it.org:443:$GW https://keycloak-admin.rm-it.org/admin/
# Erwartung: 200 oder 302

# 4. Keine Konten und Gruppen im importierten Anfangszustand (Demo-Einträge entfernt)
jq -c '[((.users // []) | length), ((.groups // []) | length)]' apps/pantheon/opencloud/keycloak/opencloud-realm.json
# Erwartung: [0,0]

# 5. Eigener Signaturschlüssel, nicht der aus Upstream (Stolperstein 29)
curl -s --resolve keycloak.rm-it.org:443:$GW https://keycloak.rm-it.org/realms/openCloud/protocol/openid-connect/certs \
  | jq -r '.keys[] | select(.use=="sig") | .x5c[0]' | head -c 40; echo
# Erwartung: anders als der Anfang von rsa-generated.certificate in der Upstream-Datei
```

## C.5 — ⏸ HALT: DNS im LAN und Keycloak-Konten *(Rico, ~15 Min)*

> **⏸ HALT [Rico]**
>
> **1. AdGuard Home** (`http://192.168.178.53` → Filter → DNS-Umschreibungen) — je ein Eintrag auf `192.168.178.224`:
> `cloud.rm-it.org`, `keycloak.rm-it.org`, `keycloak-admin.rm-it.org`, `collabora.rm-it.org`
>
> **2. FRITZ!Box** (Heimnetz → Netzwerk → Netzwerkeinstellungen → DNS-Rebind-Schutz): dieselben vier Namen als Ausnahmen eintragen — wie bei den Omni-Hostnamen, jeder Name einzeln.
>
> **3. Keycloak-Administration** — `https://keycloak-admin.rm-it.org/admin/` öffnen, mit `kcadmin` und dem Passwort aus Block A anmelden:
> 1. Realm **master** → Users → **eigenes dauerhaftes Admin-Konto** `rico-admin` anlegen (E-Mail gesetzt, *Email verified* an), Passwort setzen („Keycloak-Administrator rico-admin (Realm master)"), Rolle `admin` zuweisen. Abmelden, mit dem neuen Konto anmelden, **`kcadmin` löschen**.
> 2. Realm **openCloud** → *Realm settings → Email*: Werte prüfen (Host `smtp.ionos.de`, Port `587`, From `noreply@rm-it.org`, Anzeigename `Pantheon Cloud`, StartTLS an, Authentifizierung an) → **Test connection**. Keycloak schickt die Testmail an die E-Mail-Adresse des gerade angemeldeten Admin-Kontos — die muss also gesetzt sein (Schritt 1). *Bleibt der Knopf grau („…e-mail address for the current user ()"), kennt die Konsolensitzung die Adresse nicht; neu anmelden oder überspringen — Schritt 5 ist der echte Ende-zu-Ende-Test (17.11.2026 so verlaufen).*
> 3. Realm **openCloud** → *Users* → **Add user**: Username `rico`, E-Mail (private Adresse), Vor-/Nachname → Create.
> 4. *Role mapping* → **Assign role** → Realm-Rolle **`opencloudAdmin`**.
> 5. *Credentials* → **Credential reset** → Aktionen **Update Password** und **Configure OTP** → *Send email*. Die Mail von `Pantheon Cloud <noreply@rm-it.org>` öffnen, Link folgen, Passwort setzen, Authenticator-App koppeln. — Das ist zugleich der Ende-zu-Ende-Test für Einladungen an Gäste (I.4).
> 6. Realm settings → *Login*: User registration **aus**, Forgot password **an** (Gegenprobe zur Realm-Datei).
>
> **Fortsetzungssatz:** „Konten in Keycloak angelegt, Einladungsmail kam an, weiter mit C.6." — oder die Fehlermeldung aus *Test connection*.

> **⚠️ Stolperstein 24 — ein Postfach-Passwort an drei Stellen.** Das IONOS-Passwort von `noreply@rm-it.org` steht in `affine-smtp`, in `opencloud-smtp` (OpenCloud) und — nach dem ersten Import — in der Keycloak-Datenbank. Ändert Rico das Passwort bei IONOS: beide Secrets neu erzeugen (Muster A.2 bzw. AFFiNE G.4) **und** in Keycloak unter *Realm settings → Email* eintragen. Signatur eines vergessenen Ortes: `535 Authentication credentials invalid` in den Logs der betroffenen App.

> **⚠️ Stolperstein 25 — IONOS akzeptiert nur die Postfach-Adresse als Absender.** `from`, `envelopeFrom` und `replyTo` in Keycloak sowie `NOTIFICATIONS_SMTP_SENDER` in OpenCloud müssen `noreply@rm-it.org` sein (Anzeigename frei). Eine andere Adresse endet mit `550 Sender address rejected` (AFFiNE G.3).

> **⚠️ Stolperstein 2 — Default-Rolle `opencloudGuest`.** Im Upstream-Realm bekommt jedes neue Konto per Default die Gast-Rolle — ohne persönlichen Space. Ohne explizite Rolle `opencloudAdmin`/`opencloudUser` sieht man nach dem Login einen leeren OpenCloud ohne „Meine Dateien".

> **⚠️ Stolperstein 27 — Konto erst nach der ersten Anmeldung.** Im Autoprovisioning-Modus legt OpenCloud ein Konto erst an, wenn sich die Person zum ersten Mal anmeldet. Vorher findet der Teilen-Dialog sie nicht. Reihenfolge deshalb immer: in Keycloak anlegen → Einladung → Person meldet sich einmal an → teilen (D.9, I.4).

> **⚠️ Stolperstein 28 — Konten in zwei Systemen.** Sperren oder Löschen in Keycloak verhindert die Anmeldung, das OpenCloud-Konto (mit Freigaben, App-Tokens, ggf. Speicher) bleibt aber bestehen. Endgültig entfernen: Keycloak → Users → Delete **und** OpenCloud → Administration → Benutzer → Löschen. App-Tokens vorher in OpenCloud löschen (Stolperstein 14).

> **⚠️ Stolperstein 17 — temporärer Bootstrap-Admin.** Keycloak 26 kennzeichnet `kcadmin` als temporär und warnt in der Konsole. Das dauerhafte Konto mit eigenem Passwort ist der saubere Zustand; das Passwort aus Block A ist danach nur noch für einen Neuaufbau relevant.

## C.6 — Gegenprobe *(Claude Code)*

```bash
GW=192.168.178.224
dig +short cloud.rm-it.org @192.168.178.53
# Erwartung: 192.168.178.224
```

> Das OpenCloud-Konto von `rico` entsteht erst bei der ersten Anmeldung (D.9, Stolperstein 27) — die Gegenprobe dazu steht in D.10.

### Ergebnisprotokoll Block C

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| `database keycloak` applied | true | true (Rolle ebenfalls true) |
| Issuer über HTTPS | `https://keycloak.rm-it.org/realms/openCloud` | ✅ gleich; „Realm 'openCloud' imported" (nach Fix Stolperstein 30) |
| `/realms/master` und Admin-Host über HTTP-Listener | 404 / 404 | ✅ 404 / 404; Admin über HTTPS 302 |
| Realm-Datei: Konten / Gruppen | `[0,0]` | ✅ `[0,0]`; Schlüsselmaterial `[0,0,0]`; Live-Signaturzertifikat ≠ Upstream |
| Keycloak *Test connection* | Testmail angekommen | übersprungen (Knopf grau, Stolperstein in C.5 Schritt 2); Versand über Einladung an `rico` belegt |
| Einladungsmail an `rico` (Update Password, OTP) | angekommen, nicht im Spam | ✅ angekommen, Passwort und OTP eingerichtet; Keycloak-Log ohne SMTP-Fehler |
| AdGuard-Auflösung | `192.168.178.224` | ✅ cloud, keycloak, keycloak-admin, collabora → `192.168.178.224`; FRITZ!Box-Ausnahmen eingetragen; `kcadmin` gelöscht, `rico-admin` aktiv |

---

# Block D — OpenCloud-Kern und Web-Office *(1 HALT)*

## D.1 — Eingangsprüfung

```bash
kubectl get deploy -n opencloud keycloak -o custom-columns=NAME:.metadata.name,READY:.status.readyReplicas
dig +short keycloak.rm-it.org @192.168.178.53
grep -n 'Einladungsmail an `rico`' docs/rezepte/rezept-opencloud-pantheon.md
# Erwartung: 1; 192.168.178.224; Ergebnisprotokoll C zeigt „angekommen"
```

## D.2 — PVCs (`apps/pantheon/opencloud/opencloud/pvc.yaml`)

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: opencloud-config
  namespace: opencloud
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: qnap-iscsi
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: opencloud-data
  namespace: opencloud
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: qnap-iscsi
  resources:
    requests:
      storage: __DATA_SIZE__
```

## D.3 — Konfigurationsdateien (`apps/pantheon/opencloud/opencloud/config/`)

Aus Upstream `config/opencloud/` übernehmen, was `docker-compose.yml` mountet (Teil 0.4 f) — mindestens die **CSP-Datei**. Darin alle Upstream-Domains durch Pantheon-Hostnamen ersetzen; `connect-src` muss `https://keycloak.rm-it.org`, `frame-src` muss `https://collabora.rm-it.org` erlauben. Als `configMapGenerator` `opencloud-config-files` einbinden — der Hash-Suffix sorgt dafür, dass eine Änderung den Pod neu ausrollt.

> **⚠️ Stolperstein 21 — CSP mit falscher Domain.** Login-Weiterleitung oder Collabora-Fenster bleiben leer, die Browser-Konsole meldet „Content Security Policy". Ursache ist fast immer ein übrig gebliebener `*.opencloud.test`-Eintrag.

## D.4 — OpenCloud-Deployment (`apps/pantheon/opencloud/opencloud/deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opencloud
  namespace: opencloud
spec:
  replicas: 1
  strategy:
    type: Recreate                       # RWO-Volumes: alter Pod muss erst loslassen
  selector:
    matchLabels:
      app: opencloud
  template:
    metadata:
      labels:
        app: opencloud
    spec:
      enableServiceLinks: false          # AFFiNE-/Paperless-Lehre: keine OPENCLOUD_*-Service-Variablen
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        fsGroupChangePolicy: OnRootMismatch   # Pflicht bei 2 TB: kein rekursives chown je Start
        seccompProfile:
          type: RuntimeDefault
      hostAliases:                       # Server-zu-Server über das Gateway, nicht übers Internet
        - ip: 192.168.178.224
          hostnames:
            - cloud.rm-it.org
            - keycloak.rm-it.org
            - collabora.rm-it.org
      initContainers:
        - name: init
          # Gleicher Tag wie der Container unten — Renovate hebt beide in einem Pull Request.
          # renovate: datasource=docker depName=docker.io/opencloudeu/opencloud
          image: docker.io/opencloudeu/opencloud:7.2.5
          imagePullPolicy: IfNotPresent
          command: ["/bin/sh", "-c"]
          args:
            - |
              if [ -f /etc/opencloud/opencloud.yaml ]; then
                echo "opencloud.yaml vorhanden - init uebersprungen"
                exit 0
              fi
              exec opencloud init __INIT_FLAGS__
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: config
              mountPath: /etc/opencloud
      containers:
        - name: opencloud
          # renovate: datasource=docker depName=docker.io/opencloudeu/opencloud
          image: docker.io/opencloudeu/opencloud:7.2.5
          imagePullPolicy: IfNotPresent
          command: ["opencloud"]
          args: ["server"]
          env:
            # --- Grundlagen, hinter TLS-terminierendem Gateway ---
            - name: OC_URL
              value: https://cloud.rm-it.org
            - name: OC_LOG_LEVEL
              value: info
            - name: OC_INSECURE
              value: "false"             # gültige Zertifikate auf allen Hostnamen (Block B)
            - name: PROXY_TLS
              value: "false"
            - name: PROXY_HTTP_ADDR
              value: 0.0.0.0:9200
            - name: PROXY_ENABLE_BASIC_AUTH
              value: "false"
            - name: PROXY_ENABLE_APP_AUTH
              value: "true"              # App-Tokens (rclone-Migration)
            - name: PROXY_CSP_CONFIG_FILE_LOCATION
              value: /etc/opencloud/csp.yaml
            # --- Externer IdP: Keycloak, Autoprovisioning ins eingebaute idm (Architekturentscheidung 3) ---
            - name: OC_EXCLUDE_RUN_SERVICES
              value: idp                 # idm läuft (Kontenverzeichnis); nur der eingebaute IdP ist aus
            - name: OC_OIDC_ISSUER
              value: https://keycloak.rm-it.org/realms/openCloud
            - name: PROXY_OIDC_ACCESS_TOKEN_VERIFY_METHOD
              value: jwt
            - name: PROXY_OIDC_REWRITE_WELLKNOWN
              value: "true"
            - name: WEB_OPTION_ACCOUNT_EDIT_LINK_HREF
              value: https://keycloak.rm-it.org/realms/openCloud/account
            - name: PROXY_AUTOPROVISION_ACCOUNTS
              value: "true"
            - name: PROXY_USER_OIDC_CLAIM
              value: sub                 # Keycloak-ID: stabil, auch wenn ein Konto umbenannt wird
            - name: PROXY_AUTOPROVISION_CLAIM_USERNAME
              value: sub
            - name: PROXY_USER_CS3_CLAIM
              value: username
            - name: PROXY_ROLE_ASSIGNMENT_DRIVER
              value: oidc
            - name: PROXY_ROLE_ASSIGNMENT_OIDC_CLAIM
              value: roles               # Realm-Rollen aus dem Client-Scope "roles" der Realm-Datei
            - name: OC_ADMIN_USER_ID
              value: ""                  # idm legt KEIN Admin-Konto an (Stolperstein 1)
            - name: SETTINGS_SETUP_DEFAULT_ASSIGNMENTS
              value: "false"
            - name: GRAPH_ASSIGN_DEFAULT_USER_ROLE
              value: "false"
            - name: GRAPH_USERNAME_MATCH
              value: none
            - name: FRONTEND_READONLY_USER_ATTRIBUTES   # Profil und Rollen werden in Keycloak gepflegt
              value: user.onPremisesSamAccountName,user.displayName,user.mail,user.passwordProfile,user.accountEnabled,user.appRoleAssignments
            # --- WOPI-Dienst collaboration im selben Prozess (Architekturentscheidung 5, wie Upstream weboffice/collabora.yml) ---
            - name: COLLABORATION_WOPI_SRC
              value: https://cloud.rm-it.org   # Proxy-Route /wopi
            - name: COLLABORATION_APP_NAME
              value: CollaboraOnline
            - name: COLLABORATION_APP_PRODUCT
              value: Collabora
            - name: COLLABORATION_APP_ADDR
              value: https://collabora.rm-it.org
            - name: COLLABORATION_APP_ICON
              value: https://collabora.rm-it.org/favicon.ico
            - name: COLLABORATION_APP_INSECURE
              value: "false"
            - name: COLLABORATION_CS3API_DATAGATEWAY_INSECURE
              value: "false"
            # --- Speicher: PosixFS (Default seit 2.0, hier explizit) ---
            - name: STORAGE_USERS_DRIVER
              value: posix
            - name: STORAGE_USERS_ID_CACHE_STORE
              value: nats-js-kv
            # --- Uploads und Freigaben ---
            - name: FRONTEND_UPLOAD_MAX_CHUNK_SIZE
              value: "10000000"          # Default 10 MB, explizit: muss unter Cloudflares 100 MB bleiben
            - name: OC_SHARING_PUBLIC_SHARE_MUST_HAVE_PASSWORD
              value: "true"              # Default, explizit: öffentliche Links nur mit Passwort
            # --- Mail-Benachrichtigungen über IONOS (Architekturentscheidung 8) ---
            # Zusatzdienste: notifications (Mails) und collaboration (WOPI). Variablenname aus Teil 0.4 b.
            - name: OC_ADD_RUN_SERVICES
              value: notifications,collaboration
            - name: NOTIFICATIONS_SMTP_HOST
              value: smtp.ionos.de
            - name: NOTIFICATIONS_SMTP_PORT
              value: "587"
            - name: NOTIFICATIONS_SMTP_ENCRYPTION
              value: starttls
            - name: NOTIFICATIONS_SMTP_AUTHENTICATION
              value: auto
            - name: NOTIFICATIONS_SMTP_INSECURE
              value: "false"
            - name: NOTIFICATIONS_SMTP_USERNAME
              value: noreply@rm-it.org
            - name: NOTIFICATIONS_SMTP_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: opencloud-smtp
                  key: smtp-password
            # IONOS akzeptiert als Absender nur die Postfach-Adresse (Stolperstein 25).
            - name: NOTIFICATIONS_SMTP_SENDER
              value: "Pantheon Cloud <noreply@rm-it.org>"
          ports:
            - name: http
              containerPort: 9200
          startupProbe:
            httpGet:
              path: /status.php
              port: http
            periodSeconds: 10
            failureThreshold: 180        # bis 30 Min: PosixFS wärmt beim Start Caches über den ganzen Baum auf
          readinessProbe:
            httpGet:
              path: /status.php
              port: http
            periodSeconds: 15
          # Bewusst keine livenessProbe: ein Neustart mitten in einem großen Upload kostet mehr, als er hilft.
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: config
              mountPath: /etc/opencloud
            - name: data
              mountPath: /var/lib/opencloud
            - name: config-files
              mountPath: /etc/opencloud/csp.yaml
              subPath: csp.yaml
              readOnly: true
            # weitere Dateien aus D.3 analog per subPath
          resources:
            requests:
              memory: 768Mi
              cpu: 250m
            limits:
              memory: 3Gi
              cpu: "2"
      volumes:
        - name: config
          persistentVolumeClaim:
            claimName: opencloud-config
        - name: data
          persistentVolumeClaim:
            claimName: opencloud-data
        - name: config-files
          configMap:
            name: opencloud-config-files
```

> **Pflicht-Abgleich (Teil 0.4 b):** Claude Code vergleicht die `env`-Liste des Containers mit den Upstream-Compose-Dateien (`docker-compose.yml`, `weboffice/collabora.yml`; für die Identität `idm/external-idp.yml` ohne die `OC_LDAP_*`-Zeilen). Jede Variable, die Upstream setzt und hier fehlt (oder umgekehrt), wird entweder übernommen oder in `UPSTREAM.md` begründet. Erwartbare Unterschiede: Traefik-Labels, `INSECURE=true` (hier `false`), Service-Hostnamen.

`apps/pantheon/opencloud/opencloud/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: opencloud
  namespace: opencloud
spec:
  selector:
    app: opencloud
  ports:
    - name: http
      port: 9200
      targetPort: 9200
```

## D.5 — Collabora (`apps/pantheon/opencloud/collabora.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: collabora
  namespace: opencloud
spec:
  replicas: 1
  selector:
    matchLabels:
      app: collabora
  template:
    metadata:
      labels:
        app: collabora
    spec:
      enableServiceLinks: false
      securityContext:
        seccompProfile:
          type: RuntimeDefault
      hostAliases:
        - ip: 192.168.178.224
          hostnames:
            - cloud.rm-it.org
      containers:
        - name: collabora
          # renovate: datasource=docker depName=docker.io/collabora/code
          image: docker.io/collabora/code:__COLLABORA_TAG__
          imagePullPolicy: IfNotPresent
          env:
            - name: aliasgroup1
              value: https://cloud.rm-it.org:443   # WOPI-Host = OpenCloud selbst (Pfad /wopi)
            - name: DONT_GEN_SSL_CERT
              value: "YES"
            - name: extra_params
              value: >-
                --o:ssl.enable=false
                --o:ssl.termination=true
                --o:welcome.enable=false
                --o:admin_console.enable=false
                --o:net.frame_ancestors=cloud.rm-it.org
                --o:home_mode.enable=true
          ports:
            - name: http
              containerPort: 9980
          startupProbe:
            httpGet:
              path: /hosting/discovery
              port: http
            periodSeconds: 10
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /hosting/discovery
              port: http
            periodSeconds: 30
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              add: ["MKNOD"]           # Teil 0.4 g: exakt wie Upstream cap_add
          resources:
            requests:
              memory: 512Mi
              cpu: 250m
            limits:
              memory: 2Gi
              cpu: "2"
---
apiVersion: v1
kind: Service
metadata:
  name: collabora
  namespace: opencloud
spec:
  selector:
    app: collabora
  ports:
    - name: http
      port: 9980
      targetPort: 9980
```

| Parameter | Warum |
|---|---|
| `aliasgroup1` | Nur dieser WOPI-Host (OpenCloud selbst, Pfad `/wopi`) darf Dokumente öffnen. |
| `ssl.enable=false`, `ssl.termination=true` | TLS endet am Gateway bzw. bei Cloudflare; Collabora erzeugt trotzdem `https`-URLs. |
| `admin_console.enable=false` | Die Collabora-Admin-Konsole wäre öffentlich erreichbar — sie wird nicht gebraucht, also aus. Spart zugleich ein Admin-Passwort. |
| `net.frame_ancestors` | Collabora darf nur in OpenCloud eingebettet werden. |
| `home_mode.enable` | Für Heimnutzung vorgesehener Modus (begrenzte Verbindungen, keine Support-Hinweise). In Teil 0.4 g gegen Upstream prüfen; fehlt die Option in der Version, Zeile streichen. |

## D.6 — Routen (`apps/pantheon/opencloud/httproutes.yaml`, ergänzen)

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: opencloud
  namespace: opencloud
spec:
  parentRefs:
    - name: pantheon-gateway
      namespace: default
  hostnames:
    - cloud.rm-it.org
  rules:
    - timeouts:
        request: "0s"                  # Gateway API: 0s = kein Timeout (große Downloads, lange WebDAV-Transfers)
      backendRefs:
        - name: opencloud
          port: 9200
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: collabora
  namespace: opencloud
spec:
  parentRefs:
    - name: pantheon-gateway
      namespace: default
  hostnames:
    - collabora.rm-it.org
  rules:
    - timeouts:
        request: "0s"                  # Editier-Sitzungen laufen über langlebige WebSockets
      backendRefs:
        - name: collabora
          port: 9980
```

> **⚠️ Stolperstein 8 — Route-Timeout bei großen Dateien.** Envoy bricht eine Antwort ab, die länger dauert als das Route-Timeout — bei einem mehrere GB großen Download ist das der Normalfall, nicht die Ausnahme. Deshalb hier vorsorglich `0s` (anders als bei AFFiNE, wo es nur bei Symptomen eingebaut wird). Geprüft in D.9.

## D.7 — Renovate-Regeln

In `renovate.json` unter `packageRules` anhängen:

```json
{
  "description": "OpenCloud: nur Production-Image mit reinen X.Y.Z-Tags (nie opencloud-rolling, nie latest). init und opencloud stehen im selben Deployment und werden gemeinsam angehoben. Minor/Major nur nach Teil L.",
  "matchPackageNames": ["docker.io/opencloudeu/opencloud"],
  "allowedVersions": "/^\\d+\\.\\d+\\.\\d+$/"
},
{
  "description": "Keycloak: nur X.Y.Z. Minor/Major migrieren das DB-Schema -> On-Demand-Backup vorher (Teil L).",
  "matchPackageNames": ["quay.io/keycloak/keycloak"],
  "allowedVersions": "/^\\d+\\.\\d+\\.\\d+$/"
},
{
  "description": "Collabora CODE: mehrstellige numerische Tags, keine Varianten-Suffixe.",
  "matchPackageNames": ["docker.io/collabora/code"],
  "versioning": "loose",
  "allowedVersions": "/^\\d+(\\.\\d+)+$/"
}
```

> Stil wie die bestehenden Regeln in `renovate.json` (Umlaute in `description` als `ae`/`oe`/`ue` ausschreiben, wie bei der AFFiNE-Regel). Die Regel für Tika kommt in Block K dazu.

```bash
python3 -m json.tool renovate.json > /dev/null && echo JSON_OK
```

## D.8 — Ausrollen und prüfen

`apps/pantheon/opencloud/kustomization.yaml` um `opencloud/pvc.yaml`, `opencloud/deployment.yaml`, `opencloud/service.yaml`, `collabora.yaml` und den `configMapGenerator` `opencloud-config-files` ergänzen.

```bash
kubectl kustomize apps/pantheon/opencloud/ > /dev/null && echo BUILD_OK
grep -rn '__[A-Z_]*__' apps/pantheon/opencloud/ || echo NO_PLACEHOLDERS
O=apps/pantheon/opencloud
git add "$O/kustomization.yaml" "$O/opencloud" "$O/collabora.yaml" "$O/httproutes.yaml" renovate.json
git commit -m "feat(opencloud): deploy opencloud with collabora and mail notifications"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source
kubectl rollout status deploy/opencloud -n opencloud --timeout=15m
kubectl rollout status deploy/collabora -n opencloud --timeout=10m
kubectl logs -n opencloud deploy/opencloud -c init
# Erwartung (erster Start): Ausgabe von "opencloud init" ohne Fehler. Bei späteren Starts: "init uebersprungen".
kubectl logs -n opencloud deploy/opencloud -c opencloud --since=15m | grep -iE 'notification|collaboration' | head -10
# Erwartung: Dienste notifications und collaboration gestartet; keine Zeilen mit smtp/auth-Fehlern
```

**Prüfungen:**

```bash
GW=192.168.178.224
R="--resolve cloud.rm-it.org:443:$GW --resolve collabora.rm-it.org:443:$GW"

# 1. Server antwortet, Version stimmt
curl -s $R https://cloud.rm-it.org/status.php | jq -c '{installed, productversion, version}'
# Erwartung: installed true, Version 7.2.x

# 2. OIDC-Discovery über OpenCloud umgeschrieben auf Keycloak
curl -s $R https://cloud.rm-it.org/.well-known/openid-configuration | jq -r .issuer
# Erwartung: https://keycloak.rm-it.org/realms/openCloud

# 3. WebFinger liefert den Issuer an die Apps
curl -s $R "https://cloud.rm-it.org/.well-known/webfinger?resource=https%3A%2F%2Fcloud.rm-it.org" | jq -c .
# Erwartung: Link-Eintrag mit Issuer https://keycloak.rm-it.org/realms/openCloud

# 4. Server-zu-Server: OpenCloud-Pod erreicht Keycloak über hostAliases + Gateway
kubectl exec -n opencloud deploy/opencloud -c opencloud -- \
  wget -q -O - https://keycloak.rm-it.org/realms/openCloud/.well-known/openid-configuration | head -c 120; echo
# Erwartung: Beginn eines JSON mit "issuer". Fehlt wget im Image -> Prüfung über die Logs (keine OIDC-Fehler).

# 5. Collabora-Discovery und WOPI-Route
curl -s -o /dev/null -w "%{http_code}\n" $R https://collabora.rm-it.org/hosting/discovery
curl -s -o /dev/null -w "%{http_code}\n" $R https://cloud.rm-it.org/wopi/
# Erwartung: 200; ein HTTP-Code des WOPI-Dienstes (kein 502/503, kein Verbindungsfehler)

# 6. Routen akzeptiert
kubectl get httproute -n opencloud \
  -o custom-columns=NAME:.metadata.name,ACCEPTED:.status.parents[0].conditions[0].status
```

## D.9 — ⏸ HALT: Erster Login im LAN *(Rico, ~10 Min)*

> **⏸ HALT [Rico]** — am Mac im Heimnetz, Browser:
> 1. `https://cloud.rm-it.org` → Weiterleitung zu Keycloak → `rico` + Passwort + OTP (eingerichtet in C.5) → zurück in OpenCloud.
> 2. Kontrolle: **„Meine Dateien"** vorhanden (sonst Stolperstein 2: Rolle fehlt). Oben rechts Benutzermenü → Rolle *Admin*. **Administration → Benutzer:** genau ein Eintrag `rico` — kein `admin`, keine Demo-Konten (Stolperstein 1).
> 3. **Administration → Benutzer → rico:** Kontingent **unbegrenzt** (oder mindestens `__DATA_SIZE__`). Sonst hier setzen — die Migration würde sonst am Kontingent scheitern.
> 4. **Neu → Dokument (.docx)** → öffnet sich in Collabora, Text tippen, schließen, erneut öffnen.
> 5. **Großdatei-Test:** eine Datei > 1 GB hochladen (Browser), danach wieder herunterladen. Beides muss ohne Abbruch durchlaufen.
> 6. **Benachrichtigungs-Test** mit einem Testkonto, dessen Mail über die IONOS-Weiterleitung bei dir landet:
>    - Keycloak-Administration → Realm **openCloud** → *Users* → **Add user**: Username `testgast`, E-Mail `noreply@rm-it.org`, Rolle `opencloudGuest` (Default prüfen) → *Credentials* → Passwort setzen, Temporary aus.
>    - **`testgast` meldet sich einmal an** (privates Browserfenster, `https://cloud.rm-it.org`) und wieder ab — erst danach existiert das Konto in OpenCloud (Stolperstein 27). Dabei prüfen: kein „Meine Dateien" (Gast), Benutzerliste zeigt jetzt `rico` und `testgast`.
>    - In OpenCloud einen Ordner `_test-freigabe` anlegen → *Teilen* → `testgast` → „Kann ansehen".
>    - Erwartung: Mail „… hat … mit dir geteilt" von `Pantheon Cloud <noreply@rm-it.org>` kommt über die Weiterleitung an deiner privaten Adresse an.
>    - `testgast` bleibt bis Block I für weitere Tests bestehen (in Keycloak *Enabled* aus, wenn nicht gebraucht).
>
> **Fortsetzungssatz:** „Login, Collabora, Großdatei und Benachrichtigung funktionieren, weiter mit D.10." — oder die Beobachtung, falls etwas nicht klappt.

## D.10 — Gegenprobe *(Claude Code)*

```bash
kubectl logs -n opencloud deploy/opencloud -c opencloud --since=30m | grep -ciE '"level":"(error|fatal)"'
# Erwartung: 0 oder wenige erklärbare Einträge — Zeilen bei Bedarf zeigen

# Wo liegt Ricos persönlicher Space im PosixFS-Baum? (lesend; gebraucht in Block F/G)
kubectl exec -n opencloud deploy/opencloud -c opencloud -- sh -c 'ls -la /var/lib/opencloud/storage/users/ && ls -la /var/lib/opencloud/storage/users/* | head -40'
# Erwartung: ein Verzeichnis für den persönlichen Space von rico mit der Testdatei aus D.9.
# Ergebnis als SPACE_PATH (absoluter Pfad im Container) in UPSTREAM.md notieren.
```

> **⚠️ Stolperstein 7 — Lange Starts.** PosixFS liest beim Start den ganzen Baum. Bei leerem Volume dauert das Sekunden, nach der Migration Minuten. Darum `startupProbe` bis 30 Min und keine `livenessProbe`. Jedes Update bedeutet entsprechend längere Unterbrechung (Teil L).

### Ergebnisprotokoll Block D

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| `status.php` | installed true, 7.2.x | |
| Issuer über OpenCloud / WebFinger | Keycloak-Realm | |
| Server-zu-Server Keycloak | JSON | |
| Collabora-Discovery | 200 | |
| Login + OTP, „Meine Dateien" | ok | |
| Collabora .docx | ok | |
| Upload/Download > 1 GB | ok | |
| Freigabe-Mail an `testgast` (über Weiterleitung) | angekommen | |
| `SPACE_PATH` | Pfad | |
| Benutzerliste (Autoprovisioning) | `rico`, `testgast`; kein `admin` | |

---

# Block E — Öffentlicher Zugang und Apps *(2 HALTs)*

## E.1 — Sicherheits-Gate vor dem ersten DNS-Eintrag

Alle Punkte müssen grün sein, sonst STOPP:

```bash
GW=192.168.178.224
# 1. Keine Registrierung auf der Login-Seite
curl -s --resolve keycloak.rm-it.org:443:$GW \
  "https://keycloak.rm-it.org/realms/openCloud/protocol/openid-connect/auth?client_id=web&response_type=code&scope=openid&redirect_uri=https%3A%2F%2Fcloud.rm-it.org%2Foidc-callback.html" \
  | grep -ci 'registration'
# Erwartung: 0

# 2. Realm-Datei in Git: Registrierung aus, Brute-Force an
jq -r '[.registrationAllowed, .bruteForceProtected] | @tsv' apps/pantheon/opencloud/keycloak/opencloud-realm.json
# Erwartung: false  true

# 3. Konten = nur bewusst angelegte: Realm-Datei ohne Konten/Gruppen (C.4/4: [0,0]);
#    OpenCloud-Benutzerliste laut Ergebnisprotokoll D: rico, testgast, kein admin

# 4. Admin-Pfade über den Tunnel-Pfad gesperrt (wie C.4/2)
# 5. Öffentliche Links verlangen Passwort (Env in D.4)
kubectl get deploy opencloud -n opencloud -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="OC_SHARING_PUBLIC_SHARE_MUST_HAVE_PASSWORD")].value}{"\n"}'
# Erwartung: true
```

## E.2 — ⏸ HALT: DNS-Routen über den Tunnel *(Rico, 2 Min)*

`cloudflared` ist für Claude Code gesperrt. Claude Code meldet das grüne Sicherheits-Gate und übergibt diesen Block:

> **⏸ HALT [Rico]** — im eigenen Terminal:
> ```bash
> for h in keycloak cloud collabora; do
>   cloudflared tunnel route dns pantheon-apps "$h.rm-it.org"
> done
> # keycloak-admin bekommt bewusst KEINEN öffentlichen Eintrag.
> ```
> Fragt `cloudflared` nach einem Login (fehlende `~/.cloudflared/cert.pem`): zuerst `cloudflared tunnel login`.
>
> **Fortsetzungssatz:** „DNS-Routen angelegt, weiter mit E.3."

> **Keine Access-Application anlegen** (Architekturentscheidung 2). Existiert durch frühere Experimente eine Access-Application für einen dieser Hostnamen, blockiert sie die Apps — in der Ausgabe von E.3 an einer Weiterleitung zu `cloudflareaccess.com` erkennbar.

## E.3 — Externe Prüfungen über die Cloudflare-Kante

Im LAN lösen die Namen auf die Gateway-IP auf. Für den Außenweg die Cloudflare-Adresse erzwingen:

```bash
CF=$(dig +short cloud.rm-it.org @1.1.1.1 | head -1); echo "$CF"
X="--resolve cloud.rm-it.org:443:$CF --resolve keycloak.rm-it.org:443:$CF"

curl -s $X https://cloud.rm-it.org/status.php | jq -c '{installed, productversion}'
curl -s $X https://keycloak.rm-it.org/realms/openCloud/.well-known/openid-configuration | jq -r .issuer
# Erwartung: installed true; https://keycloak.rm-it.org/realms/openCloud  (mit https!)

curl -s -o /dev/null -w "%{http_code}\n" $X https://keycloak.rm-it.org/realms/master/
curl -s -o /dev/null -w "%{http_code}\n" $X https://keycloak.rm-it.org/admin/
dig +short keycloak-admin.rm-it.org @1.1.1.1
# Erwartung: 404; 404; leer
```

> **⚠️ Stolperstein 5 — `http` im Issuer über den Tunnel.** `cloudflared` spricht das Gateway per HTTP an; überschreibt Envoy `X-Forwarded-Proto` mit `http`, könnte Keycloak Cookies ohne `Secure` setzen oder in Weiterleitungen `http` verwenden. `KC_HOSTNAME` mit vollständiger `https`-URL fängt das für Issuer und Links ab. Zeigt die Prüfung oben trotzdem `http://` oder schlägt der App-Login in E.4 mit einer Cookie-Meldung fehl → STOPP. Mögliche Abhilfe (Rico entscheidet): `cloudflared` auf `https://`-Origin mit `originServerName` umstellen — dann muss aber die Admin-Route anders geschützt werden, weil der Tunnel dann am HTTPS-Listener ankommt.

## E.4 — ⏸ HALT: Geräte-Test *(Rico, ~15 Min)*

> **⏸ HALT [Rico]**
> 1. **iPhone im Mobilfunk** (WLAN aus): OpenCloud-App installieren → Server `https://cloud.rm-it.org` → Login in Keycloak (Passwort + OTP) → Dateien sichtbar. Ein **Video > 150 MB** hochladen (testet TUS-Chunking unter Cloudflares 100-MB-Grenze).
> 2. **Mac:** OpenCloud-Desktop installieren → Konto hinzufügen → **noch keinen Vollsync**: nur einen leeren Testordner synchronisieren, eine Datei hinein, im Browser kontrollieren.
> 3. **Öffentlicher Link:** im Browser einen Link auf eine Testdatei erzeugen (Passwort wird verlangt) → im Mobilfunk in einem privaten Fenster öffnen → Download klappt.
> 4. Optional: in Keycloak unter *Sessions* sehen, dass Desktop und iPhone als eigene Clients angemeldet sind.
>
> **Fortsetzungssatz:** „Apps und Link funktionieren von außen, Block E abgeschlossen." — oder die Fehlermeldung.

> **⚠️ Stolperstein 9 — Uploads über 100 MB.** Cloudflare (Free) verwirft Request-Bodies über 100 MB. OpenCloud teilt Uploads per TUS in 10-MB-Stücke (D.4). `FRONTEND_UPLOAD_MAX_CHUNK_SIZE` daher nie über ~95 MB setzen.

### Ergebnisprotokoll Block E

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| Sicherheits-Gate 1–5 | grün | |
| Issuer über Cloudflare | `https://…` | |
| `/realms/master`, `/admin` extern | 404 / 404 | |
| `keycloak-admin` öffentlich | keine DNS-Antwort | |
| iPhone-Login + 150-MB-Upload | ok | |
| Desktop-Testordner | ok | |
| Öffentlicher Link mit Passwort | ok | |

---

# Block F — Migration I: Vorbereitung und Kopie *(1 HALT)*

## F.0 — Was migriert wird — und was nicht

| Wird übernommen | Wird **nicht** übernommen | Ersatz |
|---|---|---|
| Alle Dateien und Ordner inkl. Änderungszeit | Dropbox-Freigaben und -Links | in OpenCloud neu anlegen (Block I) |
| Dateien aus in die eigene Dropbox eingebundenen geteilten Ordnern | Versionsverlauf, gelöschte Dateien, Kommentare | — (OpenCloud baut ab jetzt eigene Versionen auf) |
| Dropbox-Paper-Dokumente als Export (HTML/Markdown) | Paper als editierbare Dokumente | Export-Dateien |
| | Kamera-Upload-Einstellung am Telefon | in der OpenCloud-App prüfen (Block I) |
| | Geteilte Ordner, die **anderen** gehören, bleiben bei deren Besitzern | Inhalt wird kopiert; die Zusammenarbeit läuft künftig über eine OpenCloud-Freigabe (I.4) |

Ziel ist die **Wurzel von Ricos persönlichem Space** — die Ordnerstruktur sieht danach aus wie in Dropbox.

**Eingangsprüfung Speicher** (STOPP, wenn nicht erfüllt):

```bash
grep -n '| Freier Speicher nach 0.6 |' docs/rezepte/rezept-opencloud-pantheon.md
# Erwartung: Ist-Spalte gefüllt und >= 3,6 TB (Teil 0.6). Leer oder kleiner -> STOPP, Rico an 0.6 erinnern.
```

## F.1 — ⏸ HALT: Zugänge für die Migration *(Rico, ~20 Min)*

> **⏸ HALT [Rico]**
>
> **1. Dropbox-App** (`https://www.dropbox.com/developers/apps` → Create app): *Scoped access*, *Full Dropbox*, Name z. B. `pantheon-migration`. Unter **Settings → OAuth 2 → Redirect URIs** `http://localhost:53682/` eintragen (sonst scheitert `rclone authorize` mit eigener App). Unter **Permissions**: `files.metadata.read`, `files.content.read` → Submit. App key und App secret notieren.
>
> **2. OpenCloud-App-Token:** im Browser → Benutzermenü → Einstellungen → **App-Tokens** → Neu → Name `rclone-migration`, Ablauf **30 Tage** → Token kopieren.
>
> **3. Testordner in Dropbox** `_opencloud-migrationstest` mit: einer Datei mit Umlauten im Namen (`Übungsliste – März.txt`), einem sehr langen Dateinamen, einer Datei > 1 GB, einem Unterordner.
>
> **4. Token holen und Secret schreiben** (eigenes Terminal; `rclone authorize` öffnet den Browser zur Dropbox-Freigabe und gibt danach eine JSON-Zeile aus, die der Block direkt übernimmt):
> ```bash
> (
> cd ~/k8s-cluster || exit 1
> umask 077
> O=apps/pantheon/opencloud/migration; mkdir -p "$O"
> F="$O/opencloud-migration-secret.yaml"
> test -e "$F" && { echo "ABBRUCH: $F existiert schon"; exit 1; }
> printf "Dropbox App key: ";       read -r  DBX_KEY
> printf "Dropbox App secret: ";    read -rs DBX_SECRET; echo
> DBX_TOKEN=$(rclone authorize dropbox "$DBX_KEY" "$DBX_SECRET" 2>/dev/null | grep -o '{.*}' | tail -1)
> test -n "$DBX_TOKEN" || { echo "ABBRUCH: kein Token von rclone authorize"; exit 1; }
> printf "OpenCloud-App-Token: ";   read -rs OC_TOKEN; echo
> OC_PASS=$(printf '%s' "$OC_TOKEN" | rclone obscure -)
> CONF=$(mktemp)
> cat > "$CONF" <<EOF
> [dropbox]
> type = dropbox
> client_id = ${DBX_KEY}
> client_secret = ${DBX_SECRET}
> token = ${DBX_TOKEN}
>
> [opencloud]
> type = webdav
> url = http://opencloud.opencloud.svc.cluster.local:9200/remote.php/webdav
> vendor = owncloud
> user = rico
> pass = ${OC_PASS}
> EOF
> kubectl create secret generic opencloud-migration -n opencloud \
>   --from-file=rclone.conf="$CONF" --dry-run=client -o yaml > "$F"
> rm -f "$CONF"
> unset DBX_KEY DBX_SECRET DBX_TOKEN OC_TOKEN OC_PASS
> sops --encrypt --in-place "$F" || { rm -f "$F"; echo "ABBRUCH: sops fehlgeschlagen, Datei entfernt"; }
> grep -c 'ENC\[' "$F"
> )
> # Erwartung: >= 2
> ```
> Scheitert das Herausfiltern der Token-Zeile, `rclone authorize dropbox "$DBX_KEY" "$DBX_SECRET"` einmal ohne Filter ausführen und die Ausgabe ansehen — die JSON-Zeile steht zwischen den Markierungen `Paste the following into your remote machine`.
>
> **Fortsetzungssatz:** „Migrations-Secret liegt bereit, weiter mit F.2."

> **⚠️ Stolperstein 11 — Dropbox-Ratenlimits.** Mit der rclone-eigenen Client-ID teilt man sich das Limit mit allen rclone-Nutzern. Eine eigene App plus `--tpslimit 12` hält die Kopie stabil; `too_many_requests` im Log ist dann gelegentlich normal und wird von rclone wiederholt.

## F.2 — Skript und suspendierte CronJobs *(Claude Code)*

`apps/pantheon/opencloud/migration/script.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: opencloud-migration-script
  namespace: opencloud
data:
  migrate.sh: |
    #!/bin/sh
    set -eu
    # rclone schreibt beim Token-Refresh in die Config -> beschreibbare Kopie (Stolperstein 10)
    cp /secret/rclone.conf /work/rclone.conf
    export RCLONE_CONFIG=/work/rclone.conf HOME=/work
    L="--tpslimit 12 --retries 10 --low-level-retries 20 --stats 10m --stats-one-line --stats-log-level NOTICE"
    case "$MODE" in
      probe)
        rclone about dropbox: || true
        rclone size dropbox: --fast-list --tpslimit 12
        rclone lsd dropbox: --tpslimit 12
        rclone about opencloud: || true
        rclone lsd opencloud:
        ;;
      test)
        rclone copy "dropbox:$TEST_DIR" "opencloud:$TEST_DIR" $L --log-level INFO
        rclone lsl "opencloud:$TEST_DIR"
        ;;
      copy)
        rclone copy dropbox: opencloud: --fast-list --transfers 4 --checkers 8 $L --log-level NOTICE
        ;;
      check)
        # Dropbox-Hash gegen den lokalen PosixFS-Baum (lesend eingehängt), Stolperstein 12
        rclone check dropbox: "$SPACE_PATH" --one-way --fast-list --tpslimit 12 \
          --combined /work/combined.txt || true
        echo "== Zusammenfassung =="
        printf "gleich:      %s\n" "$(grep -c '^= ' /work/combined.txt || true)"
        printf "fehlt:       %s\n" "$(grep -c '^- ' /work/combined.txt || true)"
        printf "abweichend:  %s\n" "$(grep -c '^\* ' /work/combined.txt || true)"
        printf "Fehler:      %s\n" "$(grep -c '^! ' /work/combined.txt || true)"
        echo "== Abweichungen (max. 200) =="
        grep -v '^= ' /work/combined.txt | head -200 || true
        ;;
      *) echo "unbekannter MODE=$MODE"; exit 2 ;;
    esac
```

`apps/pantheon/opencloud/migration/cronjobs.yaml` — vier suspendierte CronJobs (`migration-probe`, `migration-test`, `migration-copy`, `migration-check`), identisch bis auf Name, `MODE` und die Zusätze für `check`. Vorlage `migration-copy`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: migration-copy
  namespace: opencloud
spec:
  schedule: "0 4 1 1 *"              # ohne Bedeutung: suspendiert, nur per --from ausgelöst
  suspend: true
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      backoffLimit: 1
      ttlSecondsAfterFinished: 1209600   # 14 Tage: Logs bleiben für die Auswertung lesbar
      template:
        spec:
          restartPolicy: Never
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            runAsGroup: 1000
            seccompProfile:
              type: RuntimeDefault
          containers:
            - name: rclone
              # renovate: datasource=docker depName=docker.io/rclone/rclone
              image: docker.io/rclone/rclone:__RCLONE_TAG__
              imagePullPolicy: IfNotPresent
              command: ["/bin/sh", "/script/migrate.sh"]
              env:
                - name: MODE
                  value: copy
                - name: TEST_DIR
                  value: _opencloud-migrationstest
              securityContext:
                allowPrivilegeEscalation: false
                capabilities:
                  drop: ["ALL"]
              volumeMounts:
                - name: secret
                  mountPath: /secret
                  readOnly: true
                - name: script
                  mountPath: /script
                  readOnly: true
                - name: work
                  mountPath: /work
              resources:
                requests:
                  memory: 256Mi
                  cpu: 100m
                limits:
                  memory: 2Gi
          volumes:
            - name: secret
              secret:
                secretName: opencloud-migration
            - name: script
              configMap:
                name: opencloud-migration-script
            - name: work
              emptyDir: {}
```

**Zusätze für `migration-check`:** `env` `SPACE_PATH=/data<Rest von SPACE_PATH aus D.10 ab /var/lib/opencloud>`; Volume `data` → PVC `opencloud-data`, **`readOnly: true`**, gemountet unter `/data`; Pod-Affinität zum OpenCloud-Pod (RWO, gleicher Node):

```yaml
          affinity:
            podAffinity:
              requiredDuringSchedulingIgnoredDuringExecution:
                - labelSelector:
                    matchLabels:
                      app: opencloud
                  topologyKey: kubernetes.io/hostname
```

> **⚠️ Stolperstein 10 — rclone braucht eine beschreibbare Config.** Der Dropbox-Zugang besteht aus einem kurzlebigen Access-Token und einem Refresh-Token. rclone erneuert das Access-Token während des Laufs und will es in die Config zurückschreiben. Ein schreibgeschützt gemountetes Secret führt dann zu Fehlermeldungen beim Speichern; darum kopiert das Skript die Config zuerst nach `/work`.

> **Warum vier CronJobs statt einem mit Parameter?** `kubectl create job --from=cronjob/…` übernimmt die Vorlage unverändert; Umgebungsvariablen lassen sich dabei nicht überschreiben. Vier kleine Vorlagen bleiben deklarativ und ohne Commit pro Lauf.

```bash
# kustomization.yaml: migration/script.yaml, migration/cronjobs.yaml, migration/opencloud-migration-secret.yaml
kubectl kustomize apps/pantheon/opencloud/ > /dev/null && echo BUILD_OK
grep -rn '__[A-Z_]*__' apps/pantheon/opencloud/ || echo NO_PLACEHOLDERS
O=apps/pantheon/opencloud
git add "$O/migration" "$O/kustomization.yaml"
git commit -m "feat(opencloud): add suspended rclone migration jobs from dropbox"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source
kubectl get cronjob -n opencloud
# Erwartung: vier migration-*-CronJobs, SUSPEND True
```

## F.3 — Bestandsaufnahme

```bash
kubectl create job -n opencloud --from=cronjob/migration-probe mig-probe-1
kubectl wait -n opencloud --for=condition=complete job/mig-probe-1 --timeout=60m
kubectl logs -n opencloud job/mig-probe-1
# Erwartung: Gesamtgröße und Dateizahl von Dropbox; Liste der Hauptordner;
#            "about opencloud:" ohne Kontingent-Grenze (oder Grenze > Dropbox-Größe)
```

**STOPP**, wenn die Dropbox-Größe > 80 % von `__DATA_SIZE__` ist (PVC zu klein → bei `allowVolumeExpansion: true` PVC-Erweiterung als eigener Commit vorschlagen, sonst Rico entscheidet) oder `opencloud:` nicht erreichbar ist (Stolperstein 22).

## F.4 — Testkopie

```bash
kubectl create job -n opencloud --from=cronjob/migration-test mig-test-1
kubectl wait -n opencloud --for=condition=complete job/mig-test-1 --timeout=60m
kubectl logs -n opencloud job/mig-test-1 | tail -30
# Erwartung: alle Testdateien übertragen; lsl zeigt Größen und Änderungszeiten wie in Dropbox

kubectl exec -n opencloud deploy/opencloud -c opencloud -- \
  ls -la --time-style=full-iso "<SPACE_PATH>/_opencloud-migrationstest"
# Erwartung: Umlaut-Name korrekt, langer Name vorhanden, 1-GB-Datei mit voller Größe,
#            Änderungszeiten = Dropbox (nicht "heute")
```

> **⚠️ Stolperstein 22 — Interner WebDAV-Weg verweigert.** Antwortet `opencloud:` mit 401: App-Auth nicht aktiv (`PROXY_ENABLE_APP_AUTH`) oder falscher Benutzername. Mit 404/Weiterleitung: `/remote.php/webdav` wird nicht wie erwartet bedient — dann in der Config `url = https://cloud.rm-it.org/remote.php/webdav` und im CronJob `hostAliases` (cloud.rm-it.org → Gateway-IP) verwenden. Die Änderung ist ein Commit (CronJob) plus Rico-Änderung am Secret → **STOPP**, Rico informieren.

## F.5 — Vollkopie starten

```bash
kubectl create job -n opencloud --from=cronjob/migration-copy mig-copy-1
sleep 60 2>/dev/null || true
kubectl get pods -n opencloud -l job-name=mig-copy-1
kubectl logs -n opencloud job/mig-copy-1 --tail=5
```

> `sleep` ist in manchen Claude-Code-Umgebungen gesperrt — dann stattdessen `kubectl wait --for=condition=Ready pod -l job-name=mig-copy-1 -n opencloud --timeout=5m`.

Claude Code beendet den Block mit einer **Hochrechnung** aus der ersten Statistikzeile (Übertragungsrate → voraussichtliche Dauer) und dem Hinweis, Block G nach Abschluss zu starten. Fortschritt jederzeit: `kubectl logs -n opencloud job/mig-copy-1 --tail=3`.

> **Wiederaufsetzbar:** Bricht der Job ab (Node-Neustart, Netz), einfach `mig-copy-2` aus derselben Vorlage starten. `rclone copy` überspringt Dateien mit gleicher Größe und Änderungszeit.

### Ergebnisprotokoll Block F

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| Dropbox gesamt (Größe / Dateien) | ≈ `DROPBOX_GB` | |
| Kontingent OpenCloud | unbegrenzt | |
| Testkopie: Umlaute, langer Name, 1 GB, mtime | ok | |
| Übertragungsrate / Hochrechnung | — | |

---

# Block G — Migration II: Abschluss und Inhaltsprüfung *(Claude Code, ohne HALT)*

## G.1 — Eingangsprüfung

```bash
kubectl get job -n opencloud -l 'job-name' -o custom-columns=NAME:.metadata.name,COMPLETE:.status.succeeded,FAILED:.status.failed | grep mig-copy
kubectl logs -n opencloud job/<letzter mig-copy> --tail=15
# Erwartung: succeeded=1; letzte Statistik mit "Errors: 0" (oder wenige, aufgelistete)
```

Läuft der Job noch → kein STOPP, sondern Bericht mit aktuellem Stand und Ende des Blocks.

## G.2 — Delta-Lauf

```bash
kubectl create job -n opencloud --from=cronjob/migration-copy mig-copy-delta
kubectl wait -n opencloud --for=condition=complete job/mig-copy-delta --timeout=12h
kubectl logs -n opencloud job/mig-copy-delta --tail=10
# Erwartung: (nahezu) 0 übertragen, Errors 0 — Dropbox und OpenCloud sind deckungsgleich
```

## G.3 — Inhaltsprüfung per Dropbox-Hash

```bash
kubectl create job -n opencloud --from=cronjob/migration-check mig-check-1
kubectl wait -n opencloud --for=condition=complete job/mig-check-1 --timeout=24h
kubectl logs -n opencloud job/mig-check-1 | sed -n '/== Zusammenfassung ==/,$p'
```

> **⚠️ Stolperstein 12 — kein gemeinsamer Hash.** `rclone check dropbox: opencloud:` würde nur Größen vergleichen — Dropbox hat einen eigenen Hash-Typ, WebDAV liefert SHA1/MD5. Deshalb vergleicht der Prüf-Job gegen den **lokalen** Baum: rclone berechnet dort den Dropbox-Hash selbst. Kosten: einmal den Bestand von der QNAP lesen (Stunden), aber kein zweiter Download aus Dropbox.

## G.4 — Bewertung

| Befund | Bewertung |
|---|---|
| `fehlt` = 0, `abweichend` = 0, `Fehler` = 0 | ✅ Migration inhaltlich vollständig |
| Abweichungen nur bei Paper-Exporten (`.paper`, `.html`, `.md` aus Paper) | ✅ erklärbar — Exporte haben keinen Dropbox-Hash; Stichprobe öffnen |
| `fehlt` > 0 | erneuten `migration-copy`-Lauf starten, danach G.3 wiederholen; bleibt es → STOPP mit Liste |
| `abweichend` > 0 außerhalb von Paper | STOPP mit Liste (mögliche Ursache: Datei in Dropbox während der Kopie geändert) |

### Ergebnisprotokoll Block G

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| Vollkopie: Dauer, Fehler | —, 0 | |
| Delta: übertragen | ≈ 0 | |
| Check: gleich / fehlt / abweichend / Fehler | n / 0 / 0 / 0 | |

---

# Block H — Backup *(1 HALT)*

## H.1 — Bestandsaufnahme *(Claude Code)*

```bash
# PVC -> PV -> QNAP-LUN-Name (für die Snapshot-Planung)
for p in opencloud-data opencloud-config; do
  pv=$(kubectl get pvc -n opencloud "$p" -o jsonpath='{.spec.volumeName}')
  printf "%-18s %s %s\n" "$p" "$pv" "$(kubectl get pv "$pv" -o jsonpath='{.spec.csi.volumeAttributes.internalName}')"
done

# Verzeichnisse auf dem Daten-PVC -> Ausschlüsse festlegen
kubectl exec -n opencloud deploy/opencloud -c opencloud -- sh -c 'du -sh /var/lib/opencloud/* 2>/dev/null'
# Erwartung: storage (groß), daneben z. B. idm, thumbnails, search, nats. idm NIE ausschließen (Konten, Architekturentscheidung 3).
# Ausschließen: Thumbnails (neu erzeugbar) und laufende Uploads (storage/users/uploads o. ä.) — tatsächliche Namen notieren.
```

Claude Code nennt Rico im HALT die zwei LUN-Namen.

## H.2 — ⏸ HALT: Off-site-Ziel und Snapshots *(Rico, ~20 Min)*

> **⏸ HALT [Rico]**
>
> **1. Hetzner Storage Box → Sub-Account anlegen** (`u620152-sub3`), Basisverzeichnis z. B. `opencloud-backup`, **SSH-Support und externe Erreichbarkeit an**. Freien Speicher der Box notieren (Bestand ≈ `DROPBOX_GB` + Archiv).
>
> **2. Schlüssel und Passwörter** (eigenes Terminal):
> ```bash
> ssh-keygen -t ed25519 -N "" -C "pantheon-opencloud-offsite" -f ~/.ssh/id_ed25519_hetzner_opencloud
> cat ~/.ssh/id_ed25519_hetzner_opencloud.pub | ssh -p 23 u620152-sub3@u620152.your-storagebox.de install-ssh-key
> ssh -p 23 -i ~/.ssh/id_ed25519_hetzner_opencloud -o PasswordAuthentication=no u620152-sub3@u620152.your-storagebox.de ls
> # Erwartung: Login OHNE Passwortabfrage (Paperless-Lehre: sonst ist die Key-Auth nicht wirklich aktiv)
>
> CRYPT1=$(openssl rand -hex 32); CRYPT2=$(openssl rand -hex 32)
> echo "crypt password:  $CRYPT1"; echo "crypt password2: $CRYPT2"
> # -> BEIDE jetzt sicher verwahren (außerhalb von Pantheon und OpenCloud). Ohne sie ist die Off-site-Kopie nicht lesbar.
> ```
>
> **3. Secret schreiben:**
> ```bash
> cd ~/k8s-cluster
> B=apps/pantheon/opencloud/backup; mkdir -p "$B"
> P1=$(printf '%s' "$CRYPT1" | rclone obscure -); P2=$(printf '%s' "$CRYPT2" | rclone obscure -)
> {
>   cat <<EOF
> apiVersion: v1
> kind: Secret
> metadata:
>   name: opencloud-offsite
>   namespace: opencloud
> type: Opaque
> stringData:
>   rclone.conf: |
>     [storagebox]
>     type = sftp
>     host = u620152.your-storagebox.de
>     user = u620152-sub3
>     port = 23
>     key_file = /work/id_ed25519
>     shell_type = none
>     md5sum_command = none
>     sha1sum_command = none
>
>     [offsite]
>     type = crypt
>     remote = storagebox:opencloud
>     password = ${P1}
>     password2 = ${P2}
>   id_ed25519: |
> EOF
>   sed 's/^/    /' ~/.ssh/id_ed25519_hetzner_opencloud
> } > "$B/opencloud-offsite-secret.yaml"
> sops --encrypt --in-place "$B/opencloud-offsite-secret.yaml"
> unset CRYPT1 CRYPT2 P1 P2
> grep -c 'ENC\[' "$B/opencloud-offsite-secret.yaml"
> # Erwartung: >= 2
> ```
>
> **4. QNAP → Speicher & Snapshots** → für die zwei von Claude Code genannten LUNs: **Snapshot-Zeitplan täglich, Aufbewahrung 14 Tage**. Snapshot-Reserve im Pool prüfen.
>
> **Fortsetzungssatz:** „Off-site-Secret und Snapshots eingerichtet, weiter mit H.3."

> **⚠️ Stolperstein 13 — Ziel nie die Wurzel des Sub-Accounts.** `remote = storagebox:opencloud` zeigt auf ein **Unterverzeichnis**. Ein `sync` auf die Wurzel löscht dort alles, was nicht in der Quelle liegt — inklusive `.ssh/authorized_keys` (Paperless, 33 Tage unbemerkt).

## H.3 — Off-site-CronJob *(Claude Code)*

`apps/pantheon/opencloud/backup/script.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: opencloud-offsite-script
  namespace: opencloud
data:
  offsite.sh: |
    #!/bin/sh
    set -eu
    cp /secret/rclone.conf /work/rclone.conf
    cp /secret/id_ed25519 /work/id_ed25519 && chmod 600 /work/id_ed25519
    export RCLONE_CONFIG=/work/rclone.conf HOME=/work
    DAY=$(date +%F)
    case "$MODE" in
      backup)
        rclone sync /data offsite:data \
          --exclude "/thumbnails/**" --exclude "/storage/users/uploads/**" \
          --backup-dir "offsite:archive/$DAY/data" \
          --transfers 4 --checkers 8 --retries 5 --low-level-retries 20 \
          --bwlimit "08:00,4M 23:30,off" \
          --stats 15m --stats-one-line --stats-log-level NOTICE
        rclone sync /config offsite:config --backup-dir "offsite:archive/$DAY/config"
        rclone delete offsite:archive --min-age 30d --rmdirs
        date -u +%FT%TZ > /work/last-success
        rclone copyto /work/last-success offsite:last-success
        ;;
      verify)
        echo "letzter Erfolg: $(rclone cat offsite:last-success 2>/dev/null || echo NIE)"
        rclone lsd offsite:
        # Restore-Probe ohne Inhalte auszugeben: nur Hashes vergleichen
        a=$(sha1sum /config/opencloud.yaml | cut -d' ' -f1)
        b=$(rclone cat offsite:config/opencloud.yaml | sha1sum | cut -d' ' -f1)
        [ "$a" = "$b" ] && echo "RESTORE_CONFIG_OK" || echo "RESTORE_CONFIG_MISMATCH"
        F=$(cd /data && find storage -type f -size +1M | head -1)
        a=$(sha1sum "/data/$F" | cut -d' ' -f1)
        b=$(rclone cat "offsite:data/$F" | sha1sum | cut -d' ' -f1)
        [ "$a" = "$b" ] && echo "RESTORE_DATA_OK" || echo "RESTORE_DATA_MISMATCH"
        ;;
    esac
```

> Ausschlusspfade an die tatsächlichen Namen aus H.1 anpassen. `/data` entspricht `/var/lib/opencloud`.

`apps/pantheon/opencloud/backup/cronjobs.yaml` — `opencloud-offsite` (aktiv, nachts) und `opencloud-offsite-verify` (suspendiert). Vorlage:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: opencloud-offsite
  namespace: opencloud
spec:
  schedule: "17 2 * * *"
  timeZone: Europe/Berlin
  concurrencyPolicy: Forbid            # der erste Lauf dauert Tage -> keine Überlappung
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        spec:
          restartPolicy: Never
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            runAsGroup: 1000
            fsGroup: 1000
            seccompProfile:
              type: RuntimeDefault
          affinity:
            podAffinity:                 # RWO-Volumes des OpenCloud-Pods -> gleicher Node
              requiredDuringSchedulingIgnoredDuringExecution:
                - labelSelector:
                    matchLabels:
                      app: opencloud
                  topologyKey: kubernetes.io/hostname
          containers:
            - name: rclone
              # renovate: datasource=docker depName=docker.io/rclone/rclone
              image: docker.io/rclone/rclone:__RCLONE_TAG__
              imagePullPolicy: IfNotPresent
              command: ["/bin/sh", "/script/offsite.sh"]
              env:
                - name: MODE
                  value: backup
              securityContext:
                allowPrivilegeEscalation: false
                capabilities:
                  drop: ["ALL"]
              volumeMounts:
                - name: data
                  mountPath: /data
                  readOnly: true
                - name: config
                  mountPath: /config
                  readOnly: true
                - name: secret
                  mountPath: /secret
                  readOnly: true
                - name: script
                  mountPath: /script
                  readOnly: true
                - name: work
                  mountPath: /work
              resources:
                requests:
                  memory: 256Mi
                  cpu: 100m
                limits:
                  memory: 1Gi
          volumes:
            - name: data
              persistentVolumeClaim:
                claimName: opencloud-data
                readOnly: true
            - name: config
              persistentVolumeClaim:
                claimName: opencloud-config
                readOnly: true
            - name: secret
              secret:
                secretName: opencloud-offsite
                defaultMode: 0440        # mit fsGroup 1000 lesbar; das Skript kopiert und setzt 600
            - name: script
              configMap:
                name: opencloud-offsite-script
            - name: work
              emptyDir: {}
```

`opencloud-offsite-verify`: gleiche Vorlage, `suspend: true`, `MODE=verify`.

```bash
kubectl kustomize apps/pantheon/opencloud/ > /dev/null && echo BUILD_OK
grep -rn '__[A-Z_]*__' apps/pantheon/opencloud/ || echo NO_PLACEHOLDERS
O=apps/pantheon/opencloud
git add "$O/backup" "$O/kustomization.yaml"
git commit -m "feat(opencloud): add nightly encrypted offsite backup"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source

# Erstlauf sofort anstoßen (dauert bei 1,5–3 TB Tage; Hochrechnung aus Teil 0.5; nachts ohne Bandbreitenlimit)
kubectl create job -n opencloud --from=cronjob/opencloud-offsite offsite-initial
kubectl wait -n opencloud --for=condition=Ready pod -l job-name=offsite-initial --timeout=10m
kubectl logs -n opencloud job/offsite-initial -c rclone --tail=5
# Erwartung: rclone überträgt
```

> Ein nächtlicher Lauf, der in den noch laufenden Erstlauf fällt, wird wegen `concurrencyPolicy: Forbid` übersprungen — gewollt.

**Nach Abschluss des Erstlaufs** (neue Claude-Code-Sitzung, Startprompt „Führe H.4 aus"):

## H.4 — Restore-Probe

```bash
kubectl create job -n opencloud --from=cronjob/opencloud-offsite-verify offsite-verify-1
kubectl wait -n opencloud --for=condition=complete job/offsite-verify-1 --timeout=30m
kubectl logs -n opencloud job/offsite-verify-1
# Erwartung: "letzter Erfolg: <Datum>", RESTORE_CONFIG_OK, RESTORE_DATA_OK
```

## H.5 — Wiederherstellungs-Stufen (beschrieben, im Ernstfall anwenden)

| Szenario | Weg |
|---|---|
| Einzelne Datei versehentlich gelöscht | OpenCloud-Papierkorb; sonst QNAP-Snapshot (LUN klonen, Datei herausholen) oder `offsite:archive/<Tag>/data/…` |
| Datei-Version gestern | OpenCloud-Versionen; sonst `offsite:archive/<Tag>` |
| Daten-LUN defekt, QNAP lebt | QNAP-Snapshot zurückrollen (OpenCloud vorher auf 0 skalieren) → vollständig inkl. Freigaben |
| QNAP verloren | Neue Instanz nach diesem Rezept; `offsite:config` nach `/etc/opencloud` und `offsite:data/idm` nach `/var/lib/opencloud/idm` (gleicher Stand wie die Config — Konten behalten ihre IDs), Keycloak-DB per Barman; Dateien aus `offsite:data` in den Space-Pfad kopieren, OpenCloud starten → **Assimilation**. Freigaben und Versionen sind verloren, Dateien vollständig. |

### Ergebnisprotokoll Block H

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| LUN-Namen (2) | — | |
| QNAP-Snapshot-Zeitpläne | täglich, 14 Tage | |
| Erstlauf Dauer | — | |
| Restore-Probe Config / Daten | OK / OK | |

---

# Block I — Umstieg *(2 HALTs)*

## I.1 — ⏸ HALT: Dropbox einfrieren *(Rico, ~10 Min)*

> **⏸ HALT [Rico]**
> 1. **Mac:** Dropbox-Client **pausieren und beenden** (Autostart aus). Ab jetzt nichts mehr in Dropbox ablegen.
> 2. **Telefon:** Dropbox-Kamera-Upload **aus**.
> 3. Bandkollegen kurz informieren, dass bestehende Dropbox-Links in den nächsten Tagen durch OpenCloud-Links ersetzt werden.
>
> **Fortsetzungssatz:** „Dropbox ist eingefroren, Schlusskopie starten."

## I.2 — Schlusskopie und Prüfung *(Claude Code)*

```bash
kubectl create job -n opencloud --from=cronjob/migration-copy mig-copy-final
kubectl wait -n opencloud --for=condition=complete job/mig-copy-final --timeout=12h
kubectl logs -n opencloud job/mig-copy-final --tail=5
kubectl create job -n opencloud --from=cronjob/migration-check mig-check-final
kubectl wait -n opencloud --for=condition=complete job/mig-check-final --timeout=24h
kubectl logs -n opencloud job/mig-check-final | sed -n '/== Zusammenfassung ==/,$p'
# Erwartung wie G.4: fehlt 0, abweichend 0 (außer erklärbaren Paper-Exporten)
```

## I.3 — ⏸ HALT: Geräte umstellen und Freigaben *(Rico, 30–60 Min)*

> **⏸ HALT [Rico]**
> 1. **Mac — OpenCloud-Desktop:** Sync-Ordner einrichten. Bei großem Bestand **selektiv** synchronisieren (nur die Arbeitsordner) oder, falls der Client auf macOS virtuelle Dateien anbietet, diese nutzen. Der Erstsync läuft im LAN direkt übers Gateway.
> 2. **Telefon — OpenCloud-App:** falls eine automatische Foto-Übertragung angeboten wird, einrichten; sonst als offenen Punkt notieren.
> 3. **Freigaben für Bandkollegen** neu anlegen — je nach Fall:
>    - *Öffentlicher Link* (mit Passwort, optional Ablaufdatum) auf den Ordner — für gelegentliches Teilen.
>    - *Gastkonto* — kein eigener Speicher, sieht nur, was geteilt wird, kann die Apps nutzen — für dauerhafte Zusammenarbeit. Anlage und Anleitung zum Weiterschicken: **I.4**.
> 4. Alte Dropbox-Links an den Stellen ersetzen, wo sie verwendet wurden.
> 5. **Apps mit Dropbox als Sync-Ziel** (Liste aus Teil 0, `DROPBOX_APPS`) auf OpenCloud (WebDAV) oder einen anderen Ort umstellen.
> 6. **App-Token `rclone-migration` noch nicht löschen** — er wird für einen eventuellen Nachlauf bis zum Entscheidungstor gebraucht.
> 7. `testgast` aus D.9 in Keycloak deaktivieren (*Enabled* aus) oder löschen, Ordner `_test-freigabe` entfernen.
>
> **Fortsetzungssatz:** „Umstieg erledigt."

> **⚠️ Stolperstein 26 — Dropbox-Ordner auf dem Mac sind nicht unbedingt lokal.** Die Dropbox-App auf macOS legt Dateien unter `~/Library/CloudStorage/Dropbox` ab; „Nur online"-Dateien sind dort nur Platzhalter. Hat Dropbox außerdem **Schreibtisch, Dokumente oder Downloads** gesichert („Dropbox Backup"), liegen diese Mac-Ordner faktisch in Dropbox. Wer die Dropbox-App deinstalliert, bevor diese Ordner zurück auf den Mac geholt sind, sieht sie leer. In Block J deshalb erst *Dropbox → Einstellungen → Backups* beenden (Dateien zurück auf den Mac), dann deinstallieren. Der Inhalt ist unabhängig davon über die Migration in OpenCloud.

## I.4 — Gäste: Konto anlegen, teilen, Anleitung weiterschicken *(Rico, je Gast ~5 Min)*

Kein Claude-Code-Schritt, sondern Ricos Vorgehen für jede Person, die dauerhaft mitarbeitet. Auch nach Block J jederzeit wiederholbar.

**Welcher Weg wann?**

| Fall | Weg | Gast braucht |
|---|---|---|
| Einmalig etwas schicken oder einsammeln (Mitschnitt an den Tontechniker, Fotos vom Gig) | Öffentlicher Link mit Passwort und Ablaufdatum; Berechtigung „nur ansehen", „nur hochladen" oder „bearbeiten" | nur einen Browser |
| Gemeinsamer Bandordner, Dateien sollen sich auf Handy/Rechner abgleichen | Gastkonto + Freigabe des Ordners | Konto, optional App |

**1. Konto anlegen und einladen** — `https://keycloak-admin.rm-it.org/admin/` (nur im Heimnetz), Realm **openCloud**:
1. *Users → Add user:* Username (z. B. Vorname, klein), **E-Mail (Pflicht)**, Vor- und Nachname → *Create*.
2. *Role mapping:* Rolle **`opencloudGuest`** (ist im Upstream-Realm Default — prüfen, dass keine andere OpenCloud-Rolle zugewiesen ist).
3. *Credentials* → **Credential reset** → Aktion **Update Password** → *Send email*. Der Gast bekommt eine Mail von `Pantheon Cloud <noreply@rm-it.org>` mit einem Link (72 h gültig), über den er sein Passwort selbst setzt. Rico kennt das Passwort nie.
4. Zwei-Faktor **nicht** erzwingen. Wer möchte, richtet es selbst im Konto ein (Anleitung unten, Schritt 5).

> **Erst anmelden, dann teilen (Stolperstein 27):** OpenCloud legt das Konto erst bei der ersten Anmeldung an. Vorher findet der Teilen-Dialog den Gast nicht. Also: Einladung schicken → Gast setzt sein Passwort und meldet sich einmal unter `https://cloud.rm-it.org` an → dann Schritt 2. Wer sofort etwas braucht, bekommt bis dahin einen öffentlichen Link.

> Ist der Link abgelaufen: Schritt 3 wiederholen. Kommt die Mail nicht an: Spam-Ordner des Gasts; Rico prüft in Keycloak *Realm settings → Email → Test connection*.

**2. Ordner teilen** — in OpenCloud am Ordner (z. B. `Band`) → *Teilen* → Namen des Gasts suchen → Berechtigung **„Kann bearbeiten"** (hoch- und herunterladen, umbenennen, löschen) oder **„Kann ansehen"** → *Teilen*. OpenCloud schickt dem Gast dazu eine Benachrichtigung von `noreply@rm-it.org`.

> Teilt man einen Ordner mit mehreren Gästen, lohnt eine Gruppe: *OpenCloud → Administration → Gruppen* (liegt im eingebauten Verzeichnis `idm`) → Gruppe `band` anlegen, Gäste hinzufügen, den Ordner einmal mit der Gruppe teilen. Neue Mitglieder sehen dann automatisch alles.

**3. Anleitung schicken** — Text zum Kopieren (per Messenger oder Mail):

```text
Hi! Unser Bandordner liegt ab jetzt auf meiner eigenen Cloud statt in Dropbox.
So kommst du ran:

1. Erste Anmeldung (am besten am Rechner)
   - Du bekommst eine Mail von "Pantheon Cloud" (noreply@rm-it.org).
     Falls nicht: bitte im Spam-Ordner nachsehen.
   - Link in der Mail öffnen (gilt 3 Tage) und ein eigenes Passwort setzen
     (am besten lang und zufällig).
   - Danach https://cloud.rm-it.org öffnen und einmal anmelden.
     Erst dann kann ich dir den Ordner freigeben - sag mir kurz Bescheid.

2. Im Browser
   - Links auf "Mit mir geteilt" (bzw. "Freigaben") klicken
   - Dort liegt der Bandordner
   - Herunterladen: Datei anklicken oder mehrere markieren -> "Herunterladen"
   - Hochladen: Dateien einfach ins Browserfenster ziehen
     (auch große Aufnahmen, die werden stückweise übertragen)

3. Am Handy (iPhone oder Android)
   - App "OpenCloud" aus dem App Store bzw. Play Store installieren
   - Server: cloud.rm-it.org
   - Anmelden mit Benutzername und deinem neuen Passwort
     (die Anmeldung öffnet sich kurz im Browser, danach bleibst du angemeldet)

4. Am Rechner mit automatischem Abgleich (wie früher Dropbox)
   - "OpenCloud Desktop" für Windows/macOS/Linux von https://opencloud.eu installieren
   - Server: https://cloud.rm-it.org, anmelden wie am Handy
   - Den Bandordner zum Synchronisieren auswählen
   - Danach liegt er wie ein normaler Ordner auf deinem Rechner

5. Optional: zweiter Faktor für mehr Sicherheit
   - https://keycloak.rm-it.org/realms/openCloud/account öffnen
   - "Kontosicherheit" -> "Anmeldung" -> Authenticator-App einrichten

Passwort vergessen? Auf der Anmeldeseite auf "Passwort vergessen?"
klicken - du bekommst eine Mail von noreply@rm-it.org.
Auf Mails von dieser Adresse bitte nicht antworten, sondern mir direkt schreiben.
Bitte die Zugangsdaten nicht weitergeben - wer dazukommen soll,
bekommt einen eigenen Zugang.
```

> **Antworten an `noreply@`:** Die IONOS-Weiterleitung schickt sie an Ricos private Adresse — es geht nichts verloren, aber der Hinweis im Text spart Umwege.

**Gast entfernen** (z. B. Bandwechsel): *Keycloak → Users → Gast → Enabled aus* (sofort keine Anmeldung mehr), danach in OpenCloud die Freigaben bzw. die Gruppenmitgliedschaft entfernen. Hat der Gast App-Tokens erzeugt, diese in OpenCloud löschen (Stolperstein 14). Konto erst löschen, wenn sicher ist, dass er nicht zurückkommt — **in beiden Systemen**: Keycloak → Users → Delete und OpenCloud → Administration → Benutzer → Löschen (Stolperstein 28).

### Ergebnisprotokoll Block I

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| Schlusskopie übertragen | wenige/0 Dateien | |
| Schluss-Check fehlt / abweichend | 0 / 0 | |
| Desktop, Telefon umgestellt | ok | |
| Apps mit Dropbox-Sync umgestellt | Liste aus Teil 0 abgearbeitet | |
| Freigaben neu angelegt | Liste | |
| Erster Gast: Einladungsmail, Passwort selbst gesetzt, Freigabe-Mail | ok | |

---

# Block J — Dropbox-Ablösung (Entscheidungstor) *(Rico entscheidet)*

**Erst wenn alle Punkte erfüllt sind:**

| # | Bedingung | Nachweis |
|---|---|---|
| 1 | ≥ 30 Tage Alltag nur mit OpenCloud, ohne Rückgriff auf Dropbox | Ricos Einschätzung |
| 2 | Off-site-Backup ≥ 7 Nächte in Folge erfolgreich | `kubectl get jobs -n opencloud -l job-name` / `last-success` |
| 3 | Restore-Probe grün (H.4), höchstens 7 Tage alt | `opencloud-offsite-verify` |
| 4 | QNAP-Snapshots für beide LUNs (`opencloud-data`, `opencloud-config`) vorhanden | QNAP-Oberfläche |
| 5 | Schluss-Check aus I.2 grün | Ergebnisprotokoll I |
| 6 | Alle Geräte, Apps mit Dropbox-Sync und Freigaben umgestellt | Ergebnisprotokoll I |
| 7 | Mindestens ein Gast hat sich per Einladungsmail selbst angemeldet | Ergebnisprotokoll I |

**Danach — Rico, in dieser Reihenfolge:**
1. **Dropbox Backup beenden**, falls aktiv (*Dropbox-App → Einstellungen → Backups*), damit Schreibtisch/Dokumente wieder lokal auf dem Mac liegen (Stolperstein 26).
2. **Dropbox-App auf dem Mac abmelden und deinstallieren** (Menüleiste → Profil → *Einstellungen → Konto → Abmelden*, dann App in den Papierkorb). Den lokalen Ordner `~/Library/CloudStorage/Dropbox` (bzw. `~/Dropbox`) erst löschen, wenn klar ist, dass nichts darin fehlt — er ist nach Block G/I ohnehin vollständig in OpenCloud.
3. Dropbox-App auf iPhone/iPad löschen (Kamera-Upload ist seit I.1 aus).
4. In Dropbox unter *Einstellungen → Verbundene Apps* die App `pantheon-migration` entfernen; in der Developer-Konsole löschen.
5. In OpenCloud den App-Token `rclone-migration` löschen.
6. **QNAP → HBS 3 → Synchronisieren:** den Auftrag Dropbox → *PrivateCloud* deaktivieren (nicht löschen), damit er nach der Herabstufung nicht mit Fehlern läuft.
7. **Dropbox-Abo kündigen** (Tarif auf Basic herabstufen). Das Konto bleibt mit dem Bestand lesbar, synchronisiert aber nicht mehr, sobald es über dem Basic-Kontingent liegt — als letzte Rückfallebene für einige Wochen.
8. **Konto löschen** ist unumkehrbar und ein eigener, späterer Schritt — frühestens nach dem nächsten Monats-Wartungsfenster mit grüner Restore-Probe. Im selben Schritt das QNAP-Volume *PrivateCloud* entfernen (gibt ≈ 1,34 TB frei) und den HBS-3-Auftrag löschen.

**Danach — Claude Code** (Startprompt „Führe J.1 aus"):

## J.1 — Migrationsreste entfernen

```bash
git rm -r apps/pantheon/opencloud/migration/
# kustomization.yaml: die drei migration/*-Einträge entfernen
kubectl kustomize apps/pantheon/opencloud/ > /dev/null && echo BUILD_OK
git add apps/pantheon/opencloud/kustomization.yaml
git commit -m "chore(opencloud): remove dropbox migration jobs after cutover"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source
kubectl get cronjob,secret -n opencloud | grep -i migration || echo MIGRATION_REMOVED
```

> `git rm` hat die Löschungen bereits vorgemerkt; `git add` nimmt nur die geänderte `kustomization.yaml` dazu. Das SOPS-verschlüsselte Secret bleibt in der Git-Historie. Weil Dropbox-App und App-Token widerrufen sind, ist es wertlos.

---

# Block K — Volltextsuche mit Tika *(Claude Code, ohne HALT; frühestens nach Block G)*

> **Warum erst jetzt?** Mit Tika extrahiert OpenCloud bei jeder neuen Datei den Text. Während der Migration hätte das 1,5–3 TB zusätzlich durch Tika geschickt — tagelange CPU-Last auf den Workern ohne Nutzen für die Kopie. Block K darf vor oder nach Block J laufen, aber nicht während einer Kopie (`kubectl get jobs -n opencloud` ohne laufenden `mig-*`-Job).

## K.1 — Eingangsprüfung

```bash
kubectl get jobs -n opencloud -o custom-columns=NAME:.metadata.name,ACTIVE:.status.active | grep -E 'mig-|offsite' || echo KEINE_JOBS
# Erwartung: kein Job mit ACTIVE=1 (der nächtliche Off-site-Lauf darf laufen, wenn sein Erstlauf abgeschlossen ist)
```

## K.2 — Tika und OpenCloud-Konfiguration

Claude Code übersetzt `search/tika.yml` nach `apps/pantheon/opencloud/tika.yaml`: Deployment + Service `tika` (Port 9998), Tag `__TIKA_TAG__`, `imagePullPolicy: IfNotPresent`, Renovate-Marker, `runAsNonRoot`, `drop: ALL`, requests 512Mi/250m, limits 2Gi, `readinessProbe` per HTTP auf `/tika`.

In D.4, Container `opencloud`, ergänzen (Abgleich gegen Upstream `search/tika.yml`):

```yaml
            - name: SEARCH_EXTRACTOR_TYPE
              value: tika
            - name: SEARCH_EXTRACTOR_TIKA_TIKA_URL
              value: http://tika:9998
            - name: FRONTEND_FULL_TEXT_SEARCH_ENABLED
              value: "true"
```

In `renovate.json` eine Regel für das Tika-Image ergänzen (nur reine Versionen wie `X.Y.Z` bzw. `X.Y.Z.W`, keine `-full`/`-slim`-Varianten wechseln — Variante aus Upstream beibehalten).

```bash
O=apps/pantheon/opencloud
kubectl kustomize "$O/" > /dev/null && echo BUILD_OK
python3 -m json.tool renovate.json > /dev/null && echo JSON_OK
git add "$O/tika.yaml" "$O/kustomization.yaml" "$O/opencloud/deployment.yaml" renovate.json
git commit -m "feat(opencloud): add apache tika for full-text search"
git show --stat HEAD                   # Rico zeigen, Freigabe abwarten
git pull --rebase && git push
flux reconcile kustomization flux-system --with-source
kubectl rollout status deploy/tika -n opencloud --timeout=5m
kubectl rollout status deploy/opencloud -n opencloud --timeout=30m
```

> Der OpenCloud-Neustart dauert nach der Migration länger (Stolperstein 7) — Block K abends starten, nicht während Gäste aktiv arbeiten.

## K.3 — Bestand nachindizieren

```bash
kubectl exec -n opencloud deploy/opencloud -c opencloud -- opencloud search --help
# Erwartung: ein Unterbefehl zum Indizieren aller Spaces (z. B. "index" mit --all-spaces)
```

Den ermittelten Befehl **einmal** per `kubectl exec` starten (Freigabe-Klick). Er läuft im OpenCloud-Prozess weiter; Fortschritt über `kubectl top pod -n opencloud` (CPU von `tika`) und die Suchfunktion im Browser: ein Wort aus einem migrierten PDF suchen → Treffer.

### Ergebnisprotokoll Block K

| Prüfpunkt | Erwartung | Ist |
|---|---|---|
| Tika-Rollout | ok | |
| Nachindizierung gestartet | Befehl, Uhrzeit | |
| Volltextsuche (Wort aus PDF) | Treffer | |

---

# Teil L — Betrieb: Updates und Rückweg

## L.1 — Was ist wo gesichert?

| Datenart | Ort | Sicherung |
|---|---|---|
| Dateien, Metadaten, Freigaben, Versionen | PVC `opencloud-data` | QNAP-Snapshot (voll) + Off-site crypt (Dateien) |
| Interne Secrets und IDs | PVC `opencloud-config` | QNAP-Snapshot + Off-site crypt |
| OpenCloud-Konten (`idm/idm.boltdb`) | PVC `opencloud-data` | QNAP-Snapshot + Off-site crypt (mit dem Dateibaum) |
| Keycloak (Konten, Passwörter, OTP-Geräte, Clients, Sessions) | DB `keycloak` | Barman (WAL + täglich) |
| Manifeste, Realm-Anfangszustand, CSP | Git | Git |
| Grund-Secrets, SMTP-Passwort | SOPS | Git (verschlüsselt) |
| SMTP-Einstellungen von Keycloak (nach Import) | DB `keycloak` | Barman |
| crypt-Passwörter, Bootstrap-Admin | — | sicher verwahrt außerhalb von Pantheon und OpenCloud |

## L.2 — Update-Regeln

| Komponente | Patch | Minor/Major |
|---|---|---|
| OpenCloud | Release-Notes lesen → Merge → `rollout status --timeout=30m` → `status.php`-Version → Login im Browser | **Upgrade-Guide Pflicht** (Beispiel 7.0: neuer Service-Account für Sharing). Direkt vorher QNAP-Snapshot von Daten- und Config-LUN (Rico). Downtime einplanen (Stolperstein 7). |
| Keycloak | Merge, Login testen | On-Demand-Barman-Backup direkt vor dem Merge (DB-Migration ohne Rückweg) |
| Collabora | Merge, `.docx` öffnen | dto. |
| Tika | Merge, Suche nach einem Wort aus einem PDF | dto. |
| rclone | Merge; nächsten Off-site-Lauf prüfen | dto. |

**Grundsätze** (wie AFFiNE F.2): Tags gepinnt, `IfNotPresent`, Renovate-Regeln aus D.7. `init` und `opencloud` tragen **immer denselben Tag** — Renovate hebt beide Zeilen im selben Pull Request; beim manuellen Editieren beide ändern.

## L.3 — Rückweg bei misslungenem OpenCloud-Upgrade

1. `kubectl scale deploy/opencloud -n opencloud --replicas=0`
2. QNAP: Snapshots von Daten- und Config-LUN von vor dem Upgrade zurückrollen.
3. Image-Tag per `git revert` zurück, reconcilen, hochskalieren.

> Ein reiner Image-Rollback ohne Snapshot reicht nicht, wenn das Upgrade Metadaten migriert hat (Beispiel 7.0: Space-Mitgliedschaften).

## L.4 — Regelmäßig

- Monatliches Wartungsfenster: Restore-Probe (`opencloud-offsite-verify`) mitlaufen lassen.
- App-Tokens mit abgelaufenem Zweck löschen (Stolperstein 14).
- Keycloak: Sessions und Konten der Gäste prüfen.
- Wird das Passwort von `noreply@rm-it.org` geändert: Stolperstein 24 (zwei Secrets + Keycloak-Admin-Konsole).

> **⚠️ Stolperstein 14 — App-Tokens überleben eine Sperre.** Wird ein Konto in Keycloak deaktiviert, bleiben seine App-Tokens in OpenCloud gültig. Darum immer mit Ablaufdatum anlegen und beim Entzug eines Zugangs zusätzlich in OpenCloud löschen.

> **⚠️ Stolperstein 19 — TUS-Abschluss bei großen Dateien.** Für OpenCloud 7.0 mit PosixFS wurde gemeldet, dass sehr große TUS-Uploads beim Abschluss hängen bleiben, während einfaches PUT funktioniert. Die Migration nutzt PUT; Clients nutzen TUS. Der Großdatei-Test in D.9/E.4 deckt das ab — nach Minor-Upgrades wiederholen.

---

## Definition of Done

**Sechs-Punkte-Checkliste (Pantheon-Standard):**

| # | Punkt | Umsetzung |
|---|---|---|
| 1 | Routing über Gateway API | Vier HTTPRoutes (keycloak, keycloak-admin, opencloud, collabora); Admin-Route nur am HTTPS-Listener; Timeouts `0s` für OpenCloud/Collabora |
| 2 | StorageClass `qnap-iscsi` | `opencloud-data`, `opencloud-config` |
| 3 | PostgreSQL-Connection | DB `keycloak` in `pantheon-pg`, Rolle + DB deklarativ |
| 4 | Frische SOPS-Secrets | `keycloak-db-role`, `opencloud-secret`, `opencloud-smtp`, `cloudflare-api-token`, `opencloud-migration` (temporär), `opencloud-offsite` |
| 5 | PodSecurity | Namespace `baseline` (Collabora-Capability, dokumentiert); alle übrigen Container `runAsNonRoot`, `drop: ALL`, `RuntimeDefault` |
| 6 | Renovate | Marker an allen Images; `packageRules` für OpenCloud, Keycloak, Collabora (D.7), Tika (K.2) |

**OpenCloud-spezifisch:**

| # | Punkt | Nachweis |
|---|---|---|
| 7 | HTTPS im LAN, gültiges Zertifikat | Block B |
| 8 | Login über Keycloak mit OTP, Registrierung aus, keine Demo-Konten, kein OpenCloud-Admin-Konto `admin` | C.4, C.5, D.9, E.1 |
| 9 | Keycloak-Admin nur im LAN, `master` nicht öffentlich | C.4, E.3 |
| 10 | Browser, Desktop, iOS von außen ohne Access-OTP | E.4 |
| 11 | Uploads > 100 MB über Cloudflare, Downloads > 1 GB im LAN | D.9, E.4 |
| 12 | Office im Browser, Volltextsuche | D.9, K.3 |
| 13 | Systemmails als `noreply@rm-it.org`: Keycloak (Einladung, Passwort vergessen), OpenCloud (Freigabe) | C.5, D.9, I.4 |
| 14 | Dropbox-Bestand vollständig, Hash-geprüft | G.4, I.2 |
| 15 | Backup dreischichtig, Restore-Probe grün | Block H |
| 16 | Dropbox-App deinstalliert, Abo gekündigt, Migrationsreste entfernt | Block J |

---

## Bewusst zurückgestellt

Reihenfolge = empfohlene Priorität, jeweils mit dem Risiko bis dahin.

1. **Cloudflare-Rate-Limit auf den Keycloak-Login** (eine Regel im Free-Plan). *Risiko:* Brute-Force-Versuche erreichen Keycloak; dessen Sperre greift, erzeugt aber Last und Log-Rauschen.
2. **Monitoring.** Sensor „Alter von `offsite:last-success` > 36 h" und Pod-Neustarts im Namespace `opencloud` für das Monitoring-Rezept (CT 110–112). *Risiko:* ein still scheiternder Off-site-Lauf fällt erst bei der monatlichen Probe auf (Paperless-Erfahrung: 33 Tage).
3. **DMARC verschärfen** (`p=none` → `p=quarantine`), sobald alle Absender der Domain (AFFiNE, Keycloak, OpenCloud) eine Woche lang `dkim=pass` zeigen. *Risiko bis dahin:* gefälschte Mails mit Absender `@rm-it.org` werden von Empfängern nicht aussortiert.
4. **Virenprüfung (ClamAV).** *Risiko:* hochgeladene Dateien von Gästen werden nicht geprüft.
5. **`restricted`-Härtung** durch Umzug von Collabora in einen eigenen Namespace.
6. **SSO für AFFiNE und Paperless über Keycloak** — jetzt möglich, eigener Schritt je App.
7. **Kalender/Kontakte (Radicale)** — bewusst nicht Teil dieses Vorhabens. *Risiko:* keins für die Dropbox-Ablösung.
8. **Hochverfügbarkeit.** Eine Replica auf RWO-Volumes; Node-Ausfall = Unterbrechung bis zum Neustart.
9. **Euro-Office statt Collabora** — Alternative, gegenseitig ausschließend.
10. **Homepage-Kachel.**

---

## Rezept-Changelog

**1.2 (16.11.2026)** — Ergebnisse aus Teil 0, Entscheidungen Rico vom selben Tag.
- **Identität (Architekturentscheidung 3 neu):** Autoprovisioning ins eingebaute OpenCloud-Verzeichnis `idm` statt Keycloak + OpenLDAP. Grund: einziges Upstream-LDAP-Image `bitnamilegacy/openldap:2.6` seit 19.08.2025 ohne Updates. C.3.1 (OpenLDAP), LDAP-Passwort in A.2, LDAP-Prüfungen in C.4/C.6/E.1, LDAP-Export in H und `ldap-data` entfallen. Realm-Datei aus `opencloud-realm-autoprovisioning.dist.json` (Konten und Gruppen geleert, `opencloudGuest` als Default-Rolle). D.4 mit `PROXY_AUTOPROVISION_ACCOUNTS=true`, `sub` als Benutzerkennung, Rollen aus Claim `roles`, `OC_EXCLUDE_RUN_SERVICES=idp`. Neue Stolpersteine 27 (Konto erst nach erster Anmeldung) und 28 (Konten in zwei Systemen); Stolperstein 1 auf die Realm-Datei umgeschrieben; D.9 prüft die Benutzerliste (kein `admin`).
- **WOPI (Architekturentscheidung 5):** `collaboration` als Dienst im OpenCloud-Prozess unter `https://cloud.rm-it.org/wopi` (wie Upstream). Hostname `wopi.rm-it.org`, WOPI-Container, Service und Route entfallen; Collabora `aliasgroup1` auf `cloud.rm-it.org`.
- **0.6 Verlauf (17.11.2026):** Transfer lag in einem eigenen SSD-Pool (kein Gewinn für Pool 1); nach Abyss Of Hel (100 GB) und TimeMachine (1,5 TB) 4,4 TB frei → Eingang Block F erfüllt. UrdaSot-Archiv mit **rclone crypt vom Mac** statt HBS 3 (HBS-3-WebDAV verbindet nicht mit Hetzner, Zugangsdaten per `curl` bestätigt); Upload über 2,4-GHz-WLAN langsam und anfangs mit SMB-Timeouts → `--transfers 2 --checkers 4 --bwlimit 3.5M`.
- **Neu 0.6 (Rico):** Speicher im QNAP-Pool freiräumen (Transfer löschen, Abyss Of Hel und TimeMachine verkleinern, UrdaSot verschlüsselt auf die Storage Box archivieren und löschen). Teil 0 hatte 2,5 TB frei gegen 3,6 TB Bedarf gemessen. Block F prüft das als Eingang; das Archiv belegt voraussichtlich den Storage-Box-Sub-Account `u620152-sub2`, Block H nutzt deshalb `u620152-sub3`; Block J deaktiviert den HBS-3-Spiegel PrivateCloud und entfernt das Volume mit dem Konto-Löschen.
- **Block C (17.11.2026):** Stolperstein 29 (Upstream-Realm enthält echte Schlüssel → `KeyProvider` löschen, Prüfung `[0,0,0]`, Gegenprobe C.4/5), Stolperstein 30 (Dateiname = Realm-Name, `configMapGenerator` mit Schlüssel `openCloud-realm.json`), Stolperstein 31 (Route `keycloak-master-lan` nur am HTTPS-Listener für die Admin-Konsole), `loginTheme` geleert; C.5 mit Konto `rico-admin` und Hinweis zu grauem *Test connection*.
- **Korrekturen:** OpenCloud-Tag 7.2.3 → 7.2.5; Laufzeitformel in 0.5 mit × 8000 statt × 8 (GB → Mbit).
- **A.2 in vier Schritte geteilt** (Eingaben einzeln, wie am 16.11.2026 ausgeführt): eine Passwortabfrage im selben Einfügeblock wie weitere Zeilen frisst sonst die Folgezeilen als Eingabe. Bootstrap-Admin-Passwort mit sprechendem Namen.

**1.1 (16.11.2026)** — Abgleich mit dem Cluster, Systemmails über IONOS, Fokus Dropbox-Ablösung.
- **Repo-Stand eingearbeitet** (Commit `1a72f8c`): Ablage unter `docs/rezepte/`, `CLAUDE.md` „Laufendes Vorhaben" wird in Teil 0.1 auf OpenCloud umgestellt; Regeln aus `CLAUDE.md` und `.claude/settings.json` übernommen (kein `sops`, kein `cloudflared` für Claude Code, Push nach Freigabe mit `git show --stat`, nur Dateien des Schritts stagen). Feste Werte statt Platzhalter: Listener `http`, Namespace `cert-manager`, Flux `infrastructure-networking`/`infrastructure-cert-manager`, Gateway-Manifest-Pfad, Tunnel-Catch-all.
- **Neu Architekturentscheidung 8:** Alle Systemmails über das IONOS-Postfach `noreply@rm-it.org` (wie AFFiNE ADR 5). Keycloak: `smtpServer` im Realm-Import mit `${SMTP_PASSWORD}`, „Passwort vergessen" an, Einladungslinks 72 h, Deutsch als Standardsprache. OpenCloud: Dienst `notifications` mit `NOTIFICATIONS_SMTP_*`. Secret `opencloud-smtp` in Block A. Neue Prüfungen in C.5 (*Test connection*, Einladungsmail an `rico`) und D.9 (Freigabe-Mail an `testgast` über die IONOS-Weiterleitung).
- **Gäste (I.4):** Einladung per Mail statt vorläufigem Passwort auf zwei Wegen; Gäste-Anleitung mit Selbstbedienungs-Reset.
- **Block A** nach Muster AFFiNE G.4 (Subshell, `kubectl create secret --dry-run=client`, Abbruch bei vorhandener Datei); F.1 ohne `<…>`-Platzhalter, Token aus `rclone authorize` direkt übernommen.
- **E.2** ist ein HALT für Rico (`cloudflared` gesperrt) → Block E hat zwei HALTs.
- **Block J** ergänzt um Dropbox-Backup beenden, Dropbox-App abmelden/deinstallieren, Abo kündigen, Konto später löschen; Teil 0 erfasst Apps mit Dropbox als Sync-Ziel.
- **Block K** nur noch Tika (mit Eingangsprüfung, Renovate-Regel, Nachindizierung); Radicale gestrichen (zurückgestellt, Punkt 7).
- Laufzeit-Hochrechnung für 1,5–3 TB aus Down-/Upload-Bandbreite (Teil 0.5).
- Proton- und Passwortmanager-Bezüge entfernt. Stolpersteine 23–26 neu (Tunnel am HTTP-Listener, Postfach-Passwort an drei Stellen, IONOS-Absender, Dropbox-Ordner auf dem Mac).
- Teil 0 neu nummeriert: 0.0 Ablage/Eingaben, 0.1 Repo, 0.2 Cluster, 0.3 Versionen, 0.4 Upstream, 0.5 abgeleitete Werte.

**1.0.2 (02.11.2026)** — Verweis auf das Proton-Rezept (in 1.1 wieder entfernt).

**1.0.1 (02.11.2026)** — Gäste.
- **Neu I.4:** Gastkonto anlegen (Rolle `opencloudGuest`, vorläufiges Passwort), Ordner teilen (optional über Gruppe), Zugangsdaten auf zwei Wegen übergeben, Anleitung für Gäste zum Weiterschicken (Browser, App, Desktop, optionaler zweiter Faktor), Passwort-Reset ohne SMTP, Gast entfernen. I.3 verweist darauf.

**1.0 (02.11.2026)** — Erstfassung. Ersetzt die Architekturnotiz vom Juni 2026.
- **Speicher (Architekturentscheidung 1):** PosixFS auf `qnap-iscsi` statt decomposedS3 auf MinIO-on-QNAP. MinIO-Community archiviert, PosixFS seit OpenCloud 2.0 Standard. Die Voraussetzung „MinIO zuerst" entfällt.
- **Zugang (Architekturentscheidung 2):** Kein Cloudflare Access, weil die Apps daran scheitern. Absicherung über Keycloak (OTP, Brute-Force, Registrierung aus), entfernte Demo-Konten, nicht öffentliche Admin-Konsole, eingeschränkte Realm-Pfade.
- **Identität (Architekturentscheidung 3):** Keycloak + OpenLDAP im Shared-User-Directory-Modus nach Upstream `idm/ldap-keycloak.yml`; Begründung jetzt funktional (einzige Hürde ohne Access) und zeitlich (IdP-Wahl vor der Migration).
- **Topologie (Architekturentscheidung 5):** WOPI als Container im OpenCloud-Pod; Wildcard-Zertifikat und HTTPS-Listener am Gateway als Voraussetzung (LAN-Direktweg, schließt zugleich die offene Gateway-TLS-Lücke).
- **Migration (Architekturentscheidung 6, Blöcke F, G, I, J):** rclone im Cluster von der Dropbox-API per WebDAV in OpenCloud; Prüfung per Dropbox-Hash gegen den lokalen PosixFS-Baum; Entscheidungstor vor der Kündigung.
- **Backup (Architekturentscheidung 7, Block H):** QNAP-Snapshots + nächtliches rclone crypt auf eigenen Storage-Box-Sub-Account mit 30-Tage-Archiv, LDAP-Export mit Betriebsattributen, Restore-Probe über Hash-Vergleich.
- **Agentische Struktur:** Blöcke mit Eingangsprüfung, ⏸ HALT-Kästen mit Fortsetzungssatz, STOPP-Bedingungen, Platzhalter-Prüfung vor jedem Commit, Ergebnisprotokoll je Block.
- Stolpersteine 1–22 vorab eingebettet.
- **Noch nicht live verifiziert** — Werte nach dem ersten Durchlauf abgleichen (→ 1.1).

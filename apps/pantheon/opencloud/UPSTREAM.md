# OpenCloud — Upstream-Abgleich (Rezept Teil 0)

Ermittelt am 16.11.2026 durch Claude Code. Grundlage für alle `__PLATZHALTER__` in `docs/rezepte/rezept-opencloud-pantheon.md`.

## Quellen

| Quelle | Stand |
|---|---|
| `github.com/opencloud-eu/opencloud-compose` | Commit `d4695d235639f7b14b63efef12d67cfbaab557a6` (13.11.2026) |
| `github.com/opencloud-eu/opencloud` | Tag `v7.2.5` (Quelltext für Env-Variablen, Proxy-Routen, CSP-Loader) |

> Die Compose-Dateien zielen inzwischen auf `opencloudeu/opencloud-rolling:9.1.0`. Pantheon nutzt die Production-Linie 7.2.x (Stolperstein 16). Env-Variablen aus Compose wurden gegen den 7.2.5-Quelltext geprüft (siehe unten).

## Versionen

| Komponente | Image | Tag | Herkunft |
|---|---|---|---|
| OpenCloud | `docker.io/opencloudeu/opencloud` | `7.2.5` | höchste `v7.2.*` (7.2.3 → 7.2.5); Manifest-Abfrage HTTP 200. `8.x`/`9.x` existieren nur in `opencloud-rolling` (404 im Production-Repository) |
| Keycloak | `quay.io/keycloak/keycloak` | `26.8.2` | Upstream `26.8.2` = neuester Patch der Linie und neueste Version überhaupt |
| Collabora | `docker.io/collabora/code` | `26.04.6.1.1` | Upstream = neuester Patch von `26.04` |
| Tika | `docker.io/apache/tika` | `4.2.0` | Upstream nutzt `latest` (wandernd). `latest` = `4.2.0` = `4.2.0-1` (gleicher Digest). `4.2.0` gewählt, weil die Renovate-Regel nur `X.Y.Z` zulässt; `-SNAPSHOT` ausgeschlossen |
| OpenLDAP | `bitnamilegacy/openldap` | `2.6` | **STOPP — siehe Befund 2** |
| rclone | `docker.io/rclone/rclone` | `1.76.0` | neuestes Release `v1.76.0`; identisch mit Paperless (`apps/pantheon/paperless/offsite-sync-cronjob.yaml`) |

## a — Images aus Upstream

| Datei | Image |
|---|---|
| `docker-compose.yml` | `opencloudeu/opencloud-rolling:9.1.0` (Default) |
| `idm/ldap-keycloak.yml` | `bitnamilegacy/openldap:2.6`, `postgres:17.12-alpine` (entfällt: CNPG), `quay.io/keycloak/keycloak:26.8.2` |
| `weboffice/collabora.yml` | `collabora/code:26.04.6.1.1`, `alpine/openssl:3.5.9` (Einmal-Dienst für WOPI-Proof-Key) |
| `search/tika.yml` | `apache/tika:latest` |

## b — Umgebung, Zusatzdienste, SMTP

- **`__ADD_SERVICES_VAR__` = `OC_ADD_RUN_SERVICES`.** `.env` `START_ADDITIONAL_SERVICES` → Container `OC_ADD_RUN_SERVICES` (kommagetrennt). `notifications` muss dort stehen (`.env.example` Z. 427). Mit Collabora hängt Upstream zusätzlich `collaboration` an (siehe Befund 3).
- **`idm`/`idp` aus:** `OC_EXCLUDE_RUN_SERVICES: idm,idp`.
- **SMTP-Abbildung:** `SMTP_HOST`→`NOTIFICATIONS_SMTP_HOST`, `SMTP_PORT`→`…_PORT`, `SMTP_SENDER`→`…_SENDER`, `SMTP_USERNAME`→`…_USERNAME`, `SMTP_PASSWORD`→`…_PASSWORD`, `SMTP_INSECURE`→`…_INSECURE`, `SMTP_AUTHENTICATION`→`…_AUTHENTICATION`, `SMTP_TRANSPORT_ENCRYPTION`→`…_ENCRYPTION` (`starttls`/`ssltls`/`none`).
- **Keycloak-Modus (`idm/ldap-keycloak.yml`):** `OC_LDAP_URI=ldaps://ldap-server:1636`, `OC_LDAP_INSECURE=true`, `OC_LDAP_BIND_DN=cn=admin,dc=opencloud,dc=eu`, Gruppen-/User-Base-DN unter `dc=opencloud,dc=eu`, Schema-ID `entryUUID`, `OC_LDAP_SERVER_WRITE_ENABLED=false`, `GRAPH_LDAP_GROUP_CREATE_BASE_DN=ou=custom,ou=groups,…`, `GRAPH_LDAP_REFINT_ENABLED=true`, `PROXY_AUTOPROVISION_ACCOUNTS=false`, `PROXY_ROLE_ASSIGNMENT_DRIVER=oidc`, `OC_OIDC_ISSUER=https://<keycloak>/realms/openCloud`, `PROXY_OIDC_REWRITE_WELLKNOWN=true`, `WEB_OIDC_CLIENT_ID=web`, `PROXY_USER_OIDC_CLAIM=uuid`, `PROXY_USER_CS3_CLAIM=userid`, `OC_ADMIN_USER_ID=""`, `SETTINGS_SETUP_DEFAULT_ASSIGNMENTS=false`, `GRAPH_ASSIGN_DEFAULT_USER_ROLE=false`, `GRAPH_USERNAME_MATCH=none`, `IDP_DOMAIN=<keycloak>` (nur für CSP), `FRONTEND_READONLY_USER_ATTRIBUTES=…` (Profilfelder nur in Keycloak änderbar).
- **Basis (`docker-compose.yml`):** `PROXY_TLS=false`, `OC_INSECURE=false`, `PROXY_ENABLE_BASIC_AUTH=false`, `IDM_CREATE_DEMO_USERS=false`, `FRONTEND_ARCHIVER_MAX_SIZE=10000000000`, `PROXY_CSP_CONFIG_FILE_LOCATION=/etc/opencloud/csp.yaml`, `OC_PASSWORD_POLICY_BANNED_PASSWORDS_LIST=banned-password-list.txt`, `OC_SHARING_PUBLIC_SHARE_MUST_HAVE_PASSWORD=true`, Passwortregeln 8/1/1/1/1, `OC_DEFAULT_LANGUAGE`, `OC_GRPC_MAX_RECEIVED_MESSAGE_SIZE` (leer; Hinweis auf viele Dateien je Ordner).
- **`external-proxy/opencloud.yml`:** `PROXY_HTTP_ADDR=0.0.0.0:9200`.
- **Tika (`search/tika.yml`):** `SEARCH_EXTRACTOR_TYPE=tika`, `SEARCH_EXTRACTOR_TIKA_TIKA_URL=http://tika:9998`, `FRONTEND_FULL_TEXT_SEARCH_ENABLED=true`.
- **Gegenprobe 7.2.5:** Von 77 Variablen der Compose-Dateien fehlen im 7.2.5-Quelltext nur `OC_ENABLE_GUEST_LINKS` (Funktion erst nach 7.2; im Rezept nicht verwendet) sowie `COLLABORA_DOMAIN`, `IDP_DOMAIN`, `TRAEFIK_PORT_HTTPS` — diese drei sind Vorlagenvariablen der `csp.yaml`, die 7.2.5 per `gofig.ParseEnv` auswertet (`services/proxy/pkg/middleware/security.go`).

## c — Entrypoint / Command

`entrypoint: /bin/sh`, `command: -c "opencloud init || true; opencloud server"`, `user: 1000:1000`.

**Init-Flags (7.2.5, `opencloud init --help`):** `--admin-password` (optional, sonst zufällig), `--config-path` (Default `/etc/opencloud`), `-d`, `-f`, `--insecure` (Default `ask` → fragt ohne TTY nach), `-q`. Kein Entrypoint-Wechsel nötig (`init --help` lief direkt).
**`__INIT_FLAGS__` = `--insecure false`** — nicht-interaktiv, Zertifikatsprüfung an. Admin-Passwort nicht Pflicht (idm läuft nicht), daher kein Zufallswert nötig.

## d — Realm (`config/keycloak/opencloud-realm.dist.json`)

- Realm `openCloud`; `registrationAllowed=false`, `resetPasswordAllowed=true`, `bruteForceProtected=true`, `loginWithEmailAllowed=true`, `smtpServer: {}` (leer, wird in C.3 gefüllt), `passwordPolicy` nicht gesetzt.
- Clients (alle `publicClient`): `web` (Redirects `https://cloud.opencloud.test/`, `…/oidc-silent-redirect.html`, `…/oidc-callback.html`), `OpenCloudDesktop` (`http://127.0.0.1`, `http://localhost`), `OpenCloudIOS` (`oc://ios.opencloud.eu`), `OpenCloudAndroid` (`oc://android.opencloud.eu`); zusätzlich `cyberduck` (nur als Einzeldatei in `clients/`). Default-Scopes je Client: `web-origins, profile, roles, groups, OpenCloudUnique_ID, basic, email`.
- Realm-Rollen: `opencloudAdmin`, `opencloudSpaceAdmin`, `opencloudUser`, `opencloudGuest`. **Default-Rolle** `default-roles-opencloud` = `opencloudGuest` + `offline_access` + `uma_authorization`.
- Mapper: Scope `roles` → Claim `roles` (Realm-Rollen); Scope `OpenCloudUnique_ID` → Claim `uuid`.
- LDAP-Federation `ldap`: `connectionUrl=ldap://ldap-server:1389`, `bindDn=cn=admin,dc=opencloud,dc=eu`, `bindCredential=ldap-admin-password` (Platzhalter), **`editMode=WRITABLE`**, `usersDn=ou=users,dc=opencloud,dc=eu`, `importEnabled=true`, `syncRegistrations=true`, `uuidLDAPAttribute=entryUUID`, `vendor=other`; Gruppen-Mapper `ldap-groups` mit `mode=LDAP_ONLY`, `groups.dn=ou=groups,dc=opencloud,dc=eu`.
- `users`: keine.
- **`groups` mit Rollen:** `administrators`→`opencloudAdmin`, `users`→`opencloudUser`, `apollos`→`opencloudSpaceAdmin`, **`unix-lovers`→`opencloudAdmin`**, ohne Rolle: `basic-haters`, `bible-readers`, `chess-lovers`, `machine-lovers`, `programmers`, `vlsi-lovers`. Alle außer `administrators` und `users` sind Demo-Gruppen → in C.3.2 entfernen (Stolperstein 1).
- Required Actions aktiv u. a. `CONFIGURE_TOTP`, `UPDATE_PASSWORD`, `VERIFY_EMAIL`; OTP-Typ `totp`.
- Platzhalter-Mechanismus (`config/keycloak/docker-entrypoint-override.sh`): `sed` ersetzt `cloud.opencloud.test` → `$OC_DOMAIN` und `ldap-admin-password` → `$LDAP_ADMIN_PASSWORD`, schreibt nach `/opt/keycloak/data/import/`, startet `kc.sh start --import-realm`.
- `opencloud-realm-autoprovisioning.dist.json`: Variante für den Autoprovisioning-Modus (nicht genutzt).

## e — LDAP (`idm/ldap-keycloak.yml`, `config/ldap/**`) — seit Rezept 1.2 nicht verwendet, nur Referenz

- Base-DN `dc=opencloud,dc=eu`; Admin-DN `cn=admin,dc=opencloud,dc=eu`; Ports `1389` (LDAP), `1636` (LDAPS, selbstsigniertes Zertifikat aus dem Entrypoint-Override).
- Image-Env: `LDAP_ROOT`, `LDAP_ADMIN_PASSWORD`, `LDAP_ENABLE_TLS=yes`, `LDAP_TLS_VERIFY_CLIENT=never`, `LDAP_TLS_CA_FILE/CERT_FILE/KEY_FILE`, `BITNAMI_DEBUG`.
- Seeds: `10_base.ldif` (Base, `ou=users`, `ou=groups`, `ou=custom,ou=groups`, Eintrag `cn=admin`), `20_admin.ldif`, `50_acls.ldif` (per `init-ldap-acls.sh` via `slapmodify`), Schema `schemas/10_opencloud_schema.ldif` (`openCloudUUID`, `openCloudExternalIdentity`, …).
- **Demo-/Personeneinträge (Stolperstein 1), werden nicht übernommen:**
  - `20_admin.ldif`: `uid=admin,ou=users,…` **mit festem Passwort-Hash** (wird in Upstream standardmäßig geladen, nicht nur im Demo-Modus) und Gruppe `cn=administrators` mit diesem Mitglied.
  - `30_demo_users.ldif`: `alan`, `lynn`, `mary`, `margaret`, `dennis` (Passwort `demo`).
  - `40_demo_groups.ldif`: `users`, `chess-lovers`, `machine-lovers`, `bible-readers`, `apollos`, `unix-lovers`, `basic-haters`, `vlsi-lovers`, `programmers`.
  - Übernommen werden nur `10_base.ldif`, Schema und ACLs.

## f — `config/opencloud/*`

| Datei | Mount | Bewertung |
|---|---|---|
| `csp.yaml` | `/etc/opencloud/csp.yaml` | übernehmen; Vorlagenvariablen `IDP_DOMAIN`, `COLLABORA_DOMAIN`, `COMPANION_DOMAIN`, `EURO_OFFICE_DOMAIN`, `TRAEFIK_PORT_HTTPS` (Default nach `|`) |
| `apps.yaml` | `/etc/opencloud/apps.yaml` | nur `maps.folderViewEnabled: false` |
| `banned-password-list.txt` | `/etc/opencloud/banned-password-list.txt` | 5 Zeilen |
| `proxy.yaml` | im Basis-Compose **nicht** gemountet | Routen nur für `yjs`/`radicale` — nicht benötigt |
| `apps/` | `/var/lib/opencloud/web/assets/apps` | Web-Erweiterung `maps` — nicht benötigt |

## g — Collabora (`weboffice/collabora.yml`)

- `cap_add: SYS_ADMIN`, `security_opt: seccomp=unconfined, apparmor:unconfined`; kein `user:` gesetzt; keine `ports` (nur hinter Proxy).
- `home_mode.enable=${COLLABORA_HOME_MODE:-false}`; `ssl.termination=true`, `welcome.enable=false`, `net.frame_ancestors=<OC-Domain>`, `net.lok_allow.host[14]=<OC-Domain>`.
- **Neu:** `aliasgroup1=https://<OC-Domain>` (nicht mehr WOPI-Domain); WOPI-Proof-Key (4096 Bit RSA) per Einmal-Dienst `alpine/openssl`, gemountet nach `/etc/coolwsd/proof_key`.
- Healthcheck `coolwsd --probe --use-env-vars`.

## d2 — Realm für Autoprovisioning (`config/keycloak/opencloud-realm-autoprovisioning.dist.json`) — Grundlage seit Rezept 1.2

- Keine `UserStorageProvider`-Komponente (keine LDAP-Federation).
- `users`: `admin`, `alan`, `dennis`, `lynn`, `margaret`, `mary` → **werden entfernt**.
- `groups`: `apollos`, `basic-haters`, `bible-readers`, `chess-lovers`, `machine-lovers`, `programmers`, `unix-lovers`, `users`, `vlsi-lovers` → **werden alle entfernt**.
- Default-Rolle `default-roles-opencloud` = `offline_access`, `uma_authorization` (+ Account-Client-Rollen) — **ohne OpenCloud-Rolle** → `opencloudGuest` wird ergänzt.
- Clients wie in d (`web`, `OpenCloudDesktop`, `OpenCloudIOS`, `OpenCloudAndroid`); Scope `roles` → Claim `roles` (Realm-Rollen), Scope `groups` → Claim `groups`. Kein Scope `OpenCloudUnique_ID` — nicht nötig, Benutzerkennung ist `sub`.
- `registrationAllowed=false`, `bruteForceProtected=true`, **`resetPasswordAllowed=false`** (anders als die LDAP-Variante; C.3.2 Punkt 2 setzt `true`), `smtpServer: {}`.

## d3 — Autoprovisioning im 7.2.5-Quelltext

| Aussage | Beleg |
|---|---|
| Graph nutzt per Default das eingebaute `idm`, schreibbar | `services/graph/pkg/config/defaults/defaultconfig.go`: `URI: ldap://localhost:9236`, `BindDN: uid=libregraph,ou=sysusers,o=libregraph-idm`, `WriteEnabled: true` |
| `idm`-Datenbank | `services/idm/pkg/config/defaults/defaultconfig.go`: `<BaseDataPath>/idm/idm.boltdb` → `/var/lib/opencloud/idm/idm.boltdb` |
| Kein Admin-Konto bei leerem `OC_ADMIN_USER_ID` | `services/idm/pkg/command/server.go`: Konto `admin` nur `if cfg.AdminUserID != ""` |
| Autoprovisioning braucht beschreibbares Verzeichnis | `services/proxy/pkg/config/config.go`: `PROXY_AUTOPROVISION_ACCOUNTS` („requires a write-enabled libregraph user backend") |
| Aktualisierung beim Login | `services/proxy/pkg/user/backend/cs3.go`: `UpdateUserIfNeeded` (nur Anzeigename und E-Mail, je Login eine Änderung), `SyncGroupMemberships` (nur mit `PROXY_AUTOPROVISION_CLAIM_GROUPS`) |
| Rollen-Mapping (Default) | `services/proxy/pkg/config/defaults/defaultconfig.go`: `opencloudAdmin`→`admin`, `opencloudSpaceAdmin`→`spaceadmin`, `opencloudUser`→`user`, `opencloudGuest`→`user-light` |
| WOPI auf der Hauptdomain | `services/proxy/pkg/config/defaults/defaultconfig.go`: Route `/wopi` → `eu.opencloud.web.collaboration`, `Unprotected: true` |

Nicht als Upstream-Compose erprobt (Upstream `idm/external-idp.yml` nutzt ein externes OpenLDAP) → Live-Prüfung in Rezept D.9/D.10.

## Befunde und Entscheidungen

| # | Befund (16.11.2026) | Entscheidung Rico (16.11.2026) |
|---|---|---|
| 1 | **Speicher (STOPP):** `__DATA_SIZE__` = 1690 / 1024 × 1,5 = 2,48 → `3Ti`; Schwelle 3,6 TB > 2,5 TB frei. Trident-LUNs sind *Thin* (QNAP-Übersicht). | Speicher freiräumen nach Rezept 0.6 (Transfer löschen, Abyss Of Hel → 100 GB, TimeMachine → 1,5 TB, UrdaSot archivieren und löschen); `__DATA_SIZE__` bleibt `3Ti` |
| 2 | **OpenLDAP-Image (STOPP, Stolperstein 6):** `bitnamilegacy/openldap:2.6`, letzter Push 19.08.2025. `osixia/openldap` seit 1.5.0 (2021) nur Vorab-Tags (`2.6.15-rc`, 27.10.2026); `quay.io/389ds/dirsrv` letzter Push 22.06.2025. | Kein LDAP: Autoprovisioning ins eingebaute `idm` (Architekturentscheidung 3, Rezept 1.2). Abschnitt e ist damit nur noch Referenz. |
| 3 | **WOPI-Topologie:** Upstream lässt `collaboration` im OpenCloud-Prozess laufen, `COLLABORATION_WOPI_SRC=https://<OC-Domain>`, keine WOPI-Domain; 7.2.5 hat die Route `/wopi`. | Wie Upstream: `cloud.rm-it.org/wopi`, kein `wopi.rm-it.org`, kein zweiter Container |
| 4 | **Formel Laufzeit (Rezept 0.5):** Faktor 1000 fehlte. | Korrigiert in Rezept 1.2 (`× 8000`) |
| 5 | **PrivateCloud (HBS-3-Spiegel) 1,34 TB < Dropbox 1690 GB** — Spiegel vermutlich unvollständig. | Kein Ersatz für Migration und Hash-Prüfung; Volume wird in Block J entfernt |

## Block D — Entscheidungen (Rico, 18.11.2026)

**Collabora-Capabilities** — wie Default des offiziellen Helm-Charts `CollaboraOnline/online` `kubernetes/helm/collabora-online` (`securityContext: {}`): Standard-Capabilities des Containers (u. a. `MKNOD`, `SYS_CHROOT`, `CHOWN`, `FOWNER`), **kein** `SYS_ADMIN`, `allowPrivilegeEscalation` nicht auf `false` (Datei-Capabilities von `coolforkit`), Seccomp `RuntimeDefault`. PodSecurity `baseline` bleibt erfüllt. Upstream-Compose (`SYS_ADMIN`, `seccomp=unconfined`, `apparmor:unconfined`) wäre nur mit `privileged` möglich. Folge: Collabora kopiert die Jail-Vorlage statt sie einzuhängen (langsamerer erster Dokumentstart) — Prüfung D.8/D.9.

**WOPI-Prüfschlüssel** — wird gebraucht. 7.2.5 prüft Proof-Keys per Default (`COLLABORATION_APP_PROOF_DISABLE=false`), cached den öffentlichen Schlüssel aus `/hosting/discovery` 12 h (`COLLABORATION_APP_PROOF_DURATION`) und lädt bei fehlgeschlagener Prüfung **nicht** neu (`services/collaboration/pkg/proofkeys/handler.go`, Verify) → nach einem Collabora-Neustart mit neuem Schlüssel bis zu 12 h HTTP 500 beim Öffnen. Umsetzung wie `proofKeysSecretRef` des Helm-Charts (für GitOps empfohlen): Secret `collabora-proof-key` (Rico, 4096 Bit, `-traditional`, SOPS) mit `proof_key` und `proof_key.pub`, per `subPath` nach `/etc/coolwsd/`, `defaultMode 0440`, Pod-`fsGroup 1001`.

**Pflicht-Abgleich D.4** (Upstream `docker-compose.yml`, `weboffice/collabora.yml`, `idm/external-idp.yml` gegen 7.2.5):

| Variable | Umsetzung |
|---|---|
| `IDM_CREATE_DEMO_USERS=false` | übernommen (Default, explizit; Stolperstein 1) |
| `FRONTEND_ARCHIVER_MAX_SIZE=10000000000` | übernommen (Default 1 GiB) |
| `OC_PASSWORD_POLICY_BANNED_PASSWORDS_LIST` + `banned-password-list.txt` | übernommen (ConfigMap `opencloud-config-files`) |
| `OC_DEFAULT_LANGUAGE` | `de` |
| `WEBFINGER_*_OIDC_CLIENT_ID/SCOPES` | nicht gesetzt — 7.2.5-Defaults = Client-IDs der Realm-Datei; Rollen-Claim kommt über den Default-Scope `roles` |
| `FRONTEND_APP_HANDLER_SECURE_VIEW_APP_ADDR`, `GRAPH_AVAILABLE_ROLES` | weggelassen — „Sicher ansehen" nicht benötigt; Upstream-Liste enthält die Rolle selbst nicht |
| `OC_GRPC_MAX_RECEIVED_MESSAGE_SIZE` | Default; erst bei `grpc: received message larger than max` (viele Dateien je Ordner, Migration) anheben |
| `OC_LOG_COLOR`, `OC_LOG_PRETTY`, `PROXY_ENABLE_BASIC_AUTH`, Passwortregeln, `CHECK_FOR_UPDATES` | Defaults (identisch) |
| `COLLABORA_DOMAIN`, `IDP_DOMAIN`, `TRAEFIK_PORT_HTTPS` | nicht nötig — `csp.yaml` enthält die Hostnamen direkt |

**Collabora zusätzlich wie Upstream:** `--o:net.lok_allow.host[14]=cloud.rm-it.org`, `--o:ssl.ssl_verification=true` (gültiges Let's-Encrypt-Zertifikat über `hostAliases`). `home_mode.enable=true` bleibt (Rezept).

**CSP** (`opencloud/config/csp.yaml`): aus Upstream, Vorlagenvariablen durch `keycloak.rm-it.org`/`collabora.rm-it.org` ersetzt, Companion- und Euro-Office-Einträge entfernt. `apps.yaml` (nur Karten-App) und `proxy.yaml` (yjs/Radicale) nicht übernommen.

## Abhängigkeiten der Kündigung (`DROPBOX_APPS`)

Block J prüft vor der Kündigung, dass jede App ein neues Synchronisationsziel hat:

| App | Nutzung | Hinweis |
|---|---|---|
| SafeInCloud Password Manager | Dropbox als Synchronisationsziel der Passwortdatenbank | Kritisch: vor Dropbox-Abschaltung auf ein anderes Ziel umstellen (SafeInCloud kann WebDAV) und Synchronisation auf allen Geräten prüfen |
| Obsidian | Dropbox als Synchronisationsziel des Vaults | Vault-Ordner in OpenCloud-Desktop-Sync aufnehmen bzw. mobile Synchronisation klären, bevor Dropbox entfällt |

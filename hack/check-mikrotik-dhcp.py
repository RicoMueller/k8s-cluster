#!/usr/bin/env python3
# Prueft die MikroTik-Switches (CRS310, RouterOS 7) lesend auf Einstellungen,
# die DHCP im Heimnetz blockieren koennen. Fragt dafuer die REST-Schnittstelle
# der Weboberflaeche ab (http://<switch>/rest/...). Aendert nichts.
#
# Anlass: 14.-18.11.2026 bekam das MacBook ueber den Switch "Switching" per LAN
# keine Adresse mehr (nur 169.254.x.x). tcpdump am Mac zeigte DHCP-Anfragen,
# aber keine Antwort der Fritzbox. Dock, Adapter und Mac waren unauffaellig;
# das Steam Deck hatte zeitgleich dasselbe Problem. Dieses Skript gehoert
# deshalb in jedes Wartungsfenster (Checkliste), damit der Fehler regelhaft
# mitgeprueft wird.
#
# Pruefungen je Switch:
#   S1  Erreichbarkeit, Identity, RouterOS-Version, Laufzeit
#   S2  DHCP-Snooping: aktiv ohne vertrauenswuerdigen Port (trusted) -> Antworten
#       der Fritzbox werden verworfen; Option 82
#   S3  VLAN: PVID der Ports und Mitgliedschaft als untagged (bei vlan-filtering)
#   S4  Bridge-Filter, Switch-Regeln, IP-Firewall auf der Bridge (DHCP Port 67/68)
#   S5  DHCP-Server auf dem Switch (zweiter DHCP-Server im Netz)
#   S6  Ports: horizon, Fehlerzaehler, Link-Abbrueche
#   S7  Log: Schleifen, STP, DHCP, Link down
#   S8  MAC-Tabelle: auf welchem Port die bekannten Geraete gelernt sind
#
# Voraussetzung (einmalig je Switch, macht Rico):
#   1. Gruppe nur lesend anlegen (Terminal in WinBox/WebFig):
#        /user group add name=pantheon-check policy=read,web,api,rest-api comment="hack/check-mikrotik-dhcp.py"
#      Fehlt "api" oder "rest-api", antwortet die REST-Schnittstelle mit HTTP 500
#      "not allowed (9)" (am 22.11.2026 so beobachtet). Ohne Terminal: WebFig ->
#      System -> Users -> Groups -> Add New, Policies read, web, api, rest-api.
#   2. Benutzer in WebFig anlegen: System -> Users -> "+", Name pantheon-check,
#      Group pantheon-check, Passwort vergeben.
#   3. Am Mac das Passwort in den Schluesselbund legen (fragt es ab):
#        security add-generic-password -s pantheon-mikrotik-check -a pantheon-check -w
#
# Aufruf:
#   Mac:     python3 hack/check-mikrotik-dhcp.py
#   Runner:  MIKROTIK_CHECK_PASSWORD=... python3 hack/check-mikrotik-dhcp.py
#   Nur ein Switch:  python3 hack/check-mikrotik-dhcp.py Switching
#
# Umgebungsvariablen (alle optional):
#   MIKROTIK_CHECK_USER      Benutzer (Standard: pantheon-check)
#   MIKROTIK_CHECK_PASSWORD  Passwort; sonst Schluesselbund, sonst Abfrage am Terminal
#   MIKROTIK_CHECK_SWITCHES  Ersetzt die Liste unten, Format "Name=host[:port],Name=host"
#
# Exit-Code: 0 = alles ok, 1 = Warnungen, 2 = Fehler (auch: Switch nicht erreichbar,
#            kein Passwort, unbekannter Switch)
#
# Nur Python-Standardbibliothek (laeuft auf dem Mac und auf dem Runner CT 101).
# HTTP ist unverschluesselt; der Benutzer darf deshalb nur lesen.

import base64
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

# Switches: Name -> Adresse. "Switching" haengt zwischen Arbeitsplatz und Fritzbox.
SWITCHES = {
    "Switching": "192.168.178.144",
    "Kubernetes": "192.168.178.171",
}

# Geraete, deren Port in der MAC-Tabelle gesucht wird (S8).
KNOWN_MACS = {
    "00:E0:4C:CC:21:34": "UGREEN-Dock U715 (MacBook)",
}

KEYCHAIN_SERVICE = "pantheon-mikrotik-check"
TIMEOUT_S = 10
LINK_DOWN_WARN = 5
LOG_PATTERN = re.compile(r"loop|stp|topology|dhcp|link down|flap|storm", re.IGNORECASE)
DHCP_PORTS = {"67", "68"}

OK, INFO, WARN, ERR = "OK", "INFO", "WARN", "FEHLER"
_RANK = {OK: 0, INFO: 0, WARN: 1, ERR: 2}


class Report:
    def __init__(self):
        self.lines = []
        self.worst = 0

    def add(self, level, check, text):
        self.lines.append((level, check, text))
        self.worst = max(self.worst, _RANK[level])
        print(f"  [{level:<6}] {check}  {text}")


def fail(text):
    print(text, file=sys.stderr)
    sys.exit(2)


def is_true(value):
    return str(value).lower() in ("true", "yes")


def split_list(value):
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


def vlan_ids(value):
    """'1,10-12' -> {1, 10, 11, 12}"""
    ids = set()
    for part in split_list(value):
        if "-" in part:
            lo, hi = part.split("-", 1)
            ids.update(range(int(lo), int(hi) + 1))
        elif part.isdigit():
            ids.add(int(part))
    return ids


def ports_hit_dhcp(value):
    """dst-port-Feld wie '67', '67-68', '53,67' auf DHCP-Ports pruefen."""
    for part in split_list(value):
        if "-" in part:
            lo, hi = part.split("-", 1)
            if lo.isdigit() and hi.isdigit() and int(lo) <= 68 and int(hi) >= 67:
                return True
        elif part in DHCP_PORTS:
            return True
    return False


def password_for(user):
    env = os.environ.get("MIKROTIK_CHECK_PASSWORD")
    if env:
        return env
    if shutil.which("security"):
        res = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", user, "-w"],
            capture_output=True, text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    if sys.stdin.isatty():
        return getpass.getpass(f"Passwort fuer {user} auf den MikroTik-Switches: ")
    fail("Kein Passwort: MIKROTIK_CHECK_PASSWORD setzen oder Schluesselbund-Eintrag "
         f"'{KEYCHAIN_SERVICE}' anlegen (siehe Kopf des Skripts).")


def switch_list():
    raw = os.environ.get("MIKROTIK_CHECK_SWITCHES")
    if not raw:
        return dict(SWITCHES)
    result = {}
    for item in split_list(raw):
        name, _, host = item.partition("=")
        result[name.strip()] = host.strip()
    return result


class RouterOS:
    def __init__(self, host, user, password):
        self.base = f"http://{host}/rest"
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

    def get(self, path):
        """Liefert JSON oder None, wenn der Pfad auf diesem Geraet nicht existiert."""
        req = urllib.request.Request(f"{self.base}/{path}", headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode() or "null")
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                return None
            raise

    def items(self, path):
        data = self.get(path)
        if data is None:
            return None
        return data if isinstance(data, list) else [data]


def check_switch(name, host, user, password, seen_macs):
    print(f"\n== {name} ({host}) ==")
    rep = Report()
    api = RouterOS(host, user, password)

    # S1 Erreichbarkeit
    try:
        res = api.get("system/resource") or {}
        ident = (api.get("system/identity") or {}).get("name", "?")
    except urllib.error.HTTPError as exc:
        hint = ""
        if exc.code in (401, 403):
            hint = " (Benutzer/Passwort pruefen)"
        elif exc.code == 500:
            hint = " (Gruppe pantheon-check braucht die Policies read, api, rest-api)"
        rep.add(ERR, "S1", f"REST-Abfrage abgelehnt: HTTP {exc.code}{hint}")
        return rep
    except (urllib.error.URLError, OSError) as exc:
        rep.add(ERR, "S1", f"nicht erreichbar: {exc}")
        return rep
    rep.add(OK, "S1", f"Identity {ident}, {res.get('board-name', '?')}, RouterOS {res.get('version', '?')}, "
                      f"Laufzeit {res.get('uptime', '?')}")

    bridges = api.items("interface/bridge") or []
    ports = api.items("interface/bridge/port") or []
    active_ports = [p for p in ports if not is_true(p.get("disabled"))]

    # S2 DHCP-Snooping
    for br in bridges:
        bname = br.get("name", "?")
        if not is_true(br.get("dhcp-snooping")):
            rep.add(OK, "S2", f"Bridge {bname}: DHCP-Snooping aus")
            continue
        trusted = [p.get("interface") for p in active_ports
                   if p.get("bridge") == bname and is_true(p.get("trusted"))]
        if not trusted:
            rep.add(ERR, "S2", f"Bridge {bname}: DHCP-Snooping AN, aber kein Port trusted -> "
                               "DHCP-Antworten der Fritzbox werden verworfen")
        else:
            rep.add(INFO, "S2", f"Bridge {bname}: DHCP-Snooping AN, trusted: {', '.join(trusted)} "
                                "-> pruefen, ob das der Weg zur Fritzbox ist")
        if is_true(br.get("add-dhcp-option82")):
            rep.add(WARN, "S2", f"Bridge {bname}: Option 82 wird an DHCP-Anfragen angehaengt")

    # S3 VLAN
    vlans = api.items("interface/bridge/vlan") or []
    for br in bridges:
        bname = br.get("name", "?")
        bports = [p for p in active_ports if p.get("bridge") == bname]
        if not is_true(br.get("vlan-filtering")):
            odd = [f"{p.get('interface')}={p.get('pvid')}" for p in bports if str(p.get("pvid", "1")) != "1"]
            note = f" (PVID abweichend, ohne Wirkung: {', '.join(odd)})" if odd else ""
            rep.add(OK, "S3", f"Bridge {bname}: vlan-filtering aus{note}")
            continue
        pvids = {}
        for p in bports:
            pvids.setdefault(str(p.get("pvid", "1")), []).append(p.get("interface"))
        level = WARN if len(pvids) > 1 else OK
        rep.add(level, "S3", f"Bridge {bname}: vlan-filtering AN, PVIDs: " +
                "; ".join(f"{v}: {', '.join(i)}" for v, i in sorted(pvids.items())))
        for p in bports:
            pvid = int(p.get("pvid", "1"))
            member = any(
                v.get("bridge") == bname and pvid in vlan_ids(v.get("vlan-ids"))
                and p.get("interface") in split_list(v.get("current-untagged") or v.get("untagged"))
                for v in vlans
            )
            if not member:
                rep.add(ERR, "S3", f"Port {p.get('interface')}: PVID {pvid} ist nicht als untagged "
                                   "Mitglied eingetragen -> Endgeraet ohne Netz")

    # S4 Filter
    drops = []
    for f in api.items("interface/bridge/filter") or []:
        if is_true(f.get("disabled")) or f.get("action") != "drop":
            continue
        hit = ports_hit_dhcp(f.get("dst-port")) or (f.get("ip-protocol") == "udp" and not f.get("dst-port"))
        drops.append((hit, f"Bridge-Filter {f.get('chain')} {f.get('mac-protocol', '')} "
                           f"{f.get('ip-protocol', '')} {f.get('dst-port', '')}".strip()))
    rules = api.items("interface/ethernet/switch/rule")
    for r in rules or []:
        if is_true(r.get("disabled")) or r.get("new-dst-ports", None) not in ("",):
            continue
        hit = ports_hit_dhcp(r.get("dst-port")) or (r.get("protocol") == "udp" and not r.get("dst-port"))
        drops.append((hit, f"Switch-Regel ports={r.get('ports')} protocol={r.get('protocol', '')} "
                           f"dst-port={r.get('dst-port', '')} verwirft"))
    settings = api.get("interface/bridge/settings") or {}
    if is_true(settings.get("use-ip-firewall")):
        for f in api.items("ip/firewall/filter") or []:
            if is_true(f.get("disabled")) or f.get("action") not in ("drop", "reject"):
                continue
            hit = ports_hit_dhcp(f.get("dst-port")) or (f.get("protocol") == "udp" and not f.get("dst-port"))
            drops.append((hit, f"IP-Firewall (use-ip-firewall) {f.get('chain')} {f.get('protocol', '')} "
                               f"{f.get('dst-port', '')}".strip()))
    if not drops:
        rep.add(OK, "S4", "keine verwerfenden Filter- oder Switch-Regeln")
    for hit, text in drops:
        rep.add(ERR if hit else WARN, "S4", text + (" -> trifft DHCP" if hit else ""))

    # S5 DHCP-Server auf dem Switch
    servers = [s for s in api.items("ip/dhcp-server") or [] if not is_true(s.get("disabled"))]
    if servers:
        rep.add(WARN, "S5", "DHCP-Server aktiv auf: " + ", ".join(s.get("interface", "?") for s in servers))
    else:
        rep.add(OK, "S5", "kein DHCP-Server auf dem Switch")

    # S6 Ports
    for p in active_ports:
        if p.get("horizon") not in (None, "", "none"):
            rep.add(WARN, "S6", f"Port {p.get('interface')}: horizon={p.get('horizon')} "
                                "(kein Verkehr zu Ports mit gleichem horizon)")
    problems = []
    for i in api.items("interface") or []:
        if i.get("type") not in ("ether", "sfp-sfpplus") and not str(i.get("name", "")).startswith(("ether", "sfp")):
            continue
        if not is_true(i.get("running")):
            continue
        errs = sum(int(i.get(k, 0) or 0) for k in ("rx-error", "tx-error"))
        downs = int(i.get("link-downs", 0) or 0)
        if errs or downs >= LINK_DOWN_WARN:
            problems.append(f"{i.get('name')}: Fehler {errs}, Link-Abbrueche {downs}")
    if problems:
        rep.add(WARN, "S6", "Ports mit Auffaelligkeiten seit Start: " + "; ".join(problems))
    else:
        rep.add(OK, "S6", "keine Port-Fehler, keine gehaeuften Link-Abbrueche")

    # S7 Log
    hits = [e for e in api.items("log") or []
            if LOG_PATTERN.search(f"{e.get('topics', '')} {e.get('message', '')}")]
    if any("loop" in f"{e.get('topics', '')} {e.get('message', '')}".lower() for e in hits):
        rep.add(WARN, "S7", "Log meldet eine Schleife (loop)")
    rep.add(INFO if hits else OK, "S7", f"{len(hits)} relevante Log-Eintraege" + (", die letzten:" if hits else ""))
    for e in hits[-10:]:
        print(f"           {e.get('time', '')}  {e.get('topics', '')}  {e.get('message', '')}")

    # S8 MAC-Tabelle
    for h in api.items("interface/bridge/host") or []:
        mac = str(h.get("mac-address", "")).upper()
        if mac in KNOWN_MACS:
            port = h.get("on-interface") or h.get("interface") or "?"
            seen_macs.setdefault(mac, []).append(f"{name}:{port}")
            rep.add(INFO, "S8", f"{KNOWN_MACS[mac]} ({mac}) gelernt an Port {port}")
    return rep


def main():
    user = os.environ.get("MIKROTIK_CHECK_USER", "pantheon-check")
    switches = switch_list()
    wanted = sys.argv[1:]
    if wanted:
        unknown = [w for w in wanted if w not in switches]
        if unknown:
            fail(f"Unbekannter Switch: {', '.join(unknown)} (bekannt: {', '.join(switches)})")
        switches = {n: switches[n] for n in wanted}

    password = password_for(user)
    seen_macs = {}
    worst = 0
    summary = []
    for name, host in switches.items():
        rep = check_switch(name, host, user, password, seen_macs)
        worst = max(worst, rep.worst)
        summary.append((name, {0: OK, 1: WARN, 2: ERR}[rep.worst]))

    print("\n== Bekannte Geraete in der MAC-Tabelle ==")
    for mac, label in KNOWN_MACS.items():
        where = ", ".join(seen_macs.get(mac, [])) or "nicht gesehen (Geraet aus oder nicht verbunden?)"
        print(f"  {label} ({mac}): {where}")

    print("\n== Ergebnis ==")
    for name, level in summary:
        print(f"  {name:<12} {level}")
    sys.exit(worst)


if __name__ == "__main__":
    main()

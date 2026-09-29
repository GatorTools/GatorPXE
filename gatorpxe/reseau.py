"""La carte réseau du service (§9 de l'analyse).

Sans réglage, c'est la carte principale : celle de la route par défaut. Une
carte réglée n'est jamais remplacée par une autre, même absente : le service
attend qu'elle revienne plutôt que de répondre sur un réseau qu'on n'a pas
choisi.
"""

from __future__ import annotations

import ipaddress
import json
import logging

from . import sysexec

_log = logging.getLogger("gatorpxe.reseau")


def carte_principale() -> str | None:
    """La carte de la route par défaut, celle de plus petite métrique."""
    table = sysexec.lire("/proc/net/route") or ""
    candidates = []
    for ligne in table.splitlines()[1:]:
        champs = ligne.split()
        if len(champs) >= 7 and champs[1] == "00000000":
            candidates.append((int(champs[6]), champs[0]))
    return min(candidates)[1] if candidates else None


def _lire(carte: str) -> dict | None:
    """La première adresse IPv4 de la carte, telle que la décrit `ip -j`."""
    resultat = sysexec.executer(["ip", "-j", "-4", "addr", "show", "dev", carte],
                                 echec_prevu=True, discret=True)
    if not resultat.ok:
        return None
    try:
        for interface in json.loads(resultat.sortie):
            for adr in interface.get("addr_info", []):
                if adr.get("family") == "inet":
                    return adr
    except (ValueError, TypeError) as erreur:
        _log.warning("adresse de %s illisible : %s", carte, erreur)
    return None


def adresse(carte: str) -> ipaddress.IPv4Interface | None:
    """L'adresse IPv4 de la carte, avec son réseau ; None si elle n'en a pas."""
    adr = _lire(carte)
    try:
        return ipaddress.IPv4Interface(f"{adr['local']}/{adr['prefixlen']}") if adr else None
    except (ValueError, KeyError) as erreur:
        _log.warning("adresse de %s illisible : %s", carte, erreur)
        return None


def adresse_dynamique(carte: str) -> bool:
    """L'adresse vient-elle du DHCP ? Une réservation DHCP ne se distingue pas
    d'un bail ordinaire : elle aussi est « dynamique » pour la machine."""
    adr = _lire(carte)
    return bool(adr and adr.get("dynamic"))

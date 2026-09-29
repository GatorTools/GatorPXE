"""Les derniers postes démarrés (§11 et §13 de l'analyse), lus dans le journal HTTP.

Un poste qui atteint le menu le demande avec son adresse matérielle et sa
plateforme (`menu.ipxe?mac=…&plateforme=…`). Ce qu'il demande ensuite dit ce
qu'il a choisi : CloneGator, une image, une ISO Windows extraite. Un poste qui
ne demande rien d'autre est reparti sur son disque, ou vers un autre serveur.
"""

from __future__ import annotations

import datetime
import os
import re
import urllib.parse
from dataclasses import dataclass

from . import journal

FICHIER = os.path.join(journal.RACINE, "http-acces.log")
LECTURE = 512 * 1024  # la fin du journal suffit

# Le format par défaut de lighttpd :
# 192.168.199.141 192.168.199.1:8069 - [28/Sep/2026:20:28:50 +0000] "GET /menu.ipxe HTTP/1.1" 200 269 …
_LIGNE = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "GET (\S+) [^"]*" (\d+)')

# Les mois du journal, toujours en anglais : strptime suivrait la langue du système.
_MOIS = {nom: rang for rang, nom in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}
_HEURE = re.compile(r"^(\d+)/(\w+)/(\d+):(\d+):(\d+):(\d+) ([+-])(\d\d)(\d\d)$")

CLONEGATOR = "clonegator"
IMAGE = "image"
AUCUN = ""


@dataclass
class Poste:
    heure: datetime.datetime
    adresse: str
    mac: str
    plateforme: str  # « efi » ou « pcbios »
    choix: str = AUCUN  # CLONEGATOR, IMAGE, ou AUCUN
    image: str = ""  # le chemin de l'image dans le dossier d'images


def lire(windows: dict[str, str] | None = None, nombre: int = 10) -> list[Poste]:
    """Les derniers postes, le plus récent en premier. `windows` : le boot.wim
    extrait → le chemin de son ISO (état du service)."""
    try:
        with open(FICHIER, "rb") as fichier:
            fichier.seek(0, os.SEEK_END)
            fichier.seek(max(0, fichier.tell() - LECTURE))
            texte = fichier.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return analyser(texte.splitlines(), windows or {})[:nombre]


def _heure(texte: str) -> datetime.datetime | None:
    """« 29/Sep/2026:13:06:34 +0000 », à l'heure locale."""
    morceaux = _HEURE.match(texte)
    if not morceaux or morceaux.group(2) not in _MOIS:
        return None
    jour, _, annee, h, m, s, signe, dh, dm = morceaux.groups()
    decalage = datetime.timedelta(hours=int(dh), minutes=int(dm)) * (-1 if signe == "-" else 1)
    try:
        heure = datetime.datetime(int(annee), _MOIS[morceaux.group(2)], int(jour), int(h), int(m), int(s),
                                  tzinfo=datetime.timezone(decalage))
    except ValueError:
        return None
    return heure.astimezone()


def analyser(lignes: list[str], windows: dict[str, str]) -> list[Poste]:
    postes: list[Poste] = []
    dernier: dict[str, Poste] = {}  # adresse IP → son dernier passage au menu
    for ligne in lignes:
        trouve = _LIGNE.match(ligne)
        if not trouve or trouve.group(4) not in ("200", "206"):
            continue
        adresse, quand, url = trouve.group(1), trouve.group(2), trouve.group(3)
        chemin, _, requete = url.partition("?")
        chemin = urllib.parse.unquote(chemin)
        if chemin == "/menu.ipxe":
            champs = urllib.parse.parse_qs(requete)
            if "mac" not in champs:
                continue  # un menu demandé à la main, pas par un poste
            heure = _heure(quand)
            if heure is None:
                continue
            # Chaque demande du menu est un passage : le retour au menu après
            # un échec se fait dans le script, sans rien redemander au serveur.
            poste = Poste(heure, adresse, champs["mac"][0].replace("-", ":"),
                          champs.get("plateforme", [""])[0])
            dernier[adresse] = poste
            postes.append(poste)
            continue
        poste = dernier.get(adresse)
        if poste is None or poste.choix != AUCUN:
            continue
        if chemin.startswith("/clonegator/"):
            poste.choix = CLONEGATOR
        elif chemin.startswith("/images/"):
            poste.choix, poste.image = IMAGE, chemin[len("/images/"):]
        elif chemin.startswith("/windows/") and chemin[1:] in windows:
            poste.choix, poste.image = IMAGE, windows[chemin[1:]]
    return list(reversed(postes))

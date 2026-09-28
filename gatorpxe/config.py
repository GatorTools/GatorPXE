"""Réglages (§11 et §12 de l'analyse), dans `/etc/gatorpxe/gatorpxe.json`.

Écrits par l'interface, relus par le service ; on n'a jamais à les ouvrir
(P5). Un fichier absent ou illisible donne les réglages par défaut : les
postes démarrent même quand personne n'a rien réglé (P4).

Les renvois (§8) viendront avec la phase 4.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields

_log = logging.getLogger("gatorpxe.config")

FICHIER = os.environ.get("GATORPXE_CONFIG", "/etc/gatorpxe/gatorpxe.json")

DISQUE_LOCAL = "disque"
CLONEGATOR = "clonegator"


@dataclass
class Reglages:
    proxy_dhcp: bool = True
    carte: str = ""  # vide : la carte réseau principale, détectée seule (§9)
    dossier_images: str = "/srv/gatorpxe/images"
    clonegator: bool = True
    delai: int = 10  # secondes avant l'entrée par défaut (§5)
    entree_defaut: str = DISQUE_LOCAL
    langue: str = "en"


def lire() -> Reglages:
    try:
        with open(FICHIER, encoding="utf-8") as fichier:
            brut = json.load(fichier)
    except FileNotFoundError:
        return Reglages()
    except (OSError, ValueError) as erreur:
        _log.warning("%s illisible, réglages par défaut : %s", FICHIER, erreur)
        return Reglages()
    if not isinstance(brut, dict):
        _log.warning("%s incohérent, réglages par défaut", FICHIER)
        return Reglages()

    # Chaque réglage est pris s'il a le bon type, sinon laissé à sa valeur par
    # défaut : un réglage abîmé ne fait pas perdre les autres.
    defaut = Reglages()
    valeurs = {}
    for champ in fields(Reglages):
        valeur = brut.get(champ.name)
        attendu = type(getattr(defaut, champ.name))
        if valeur is None:
            continue
        if type(valeur) is not attendu:
            _log.warning("%s : réglage %s ignoré (%r)", FICHIER, champ.name, valeur)
            continue
        valeurs[champ.name] = valeur
    return Reglages(**valeurs)


def ecrire(reglages: Reglages) -> None:
    """Écrit les réglages d'un seul coup : un fichier à moitié écrit ne doit
    jamais être relu par le service."""
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    temporaire = FICHIER + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as fichier:
        json.dump(asdict(reglages), fichier, ensure_ascii=False, indent=2)
        fichier.write("\n")
        fichier.flush()
        os.fsync(fichier.fileno())
    os.replace(temporaire, FICHIER)

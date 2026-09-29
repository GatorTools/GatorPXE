"""Ce que le service voit, pour l'interface (§11 de l'analyse).

Le service l'écrit à chaque tour dans `/var/lib/gatorpxe/etat.json` ;
l'interface le lit. Elle ne sonde ainsi ni le réseau ni le dossier d'images, et
reste indépendante du service : fermée ou plantée, elle ne change rien pour les
postes (P4).
"""

from __future__ import annotations

import json
import os

from . import chemins

FICHIER = os.path.join(chemins.ETAT, "etat.json")

# Pourquoi le service ne sert pas les postes.
SANS_CARTE = "sans_carte"
SANS_ADRESSE = "sans_adresse"
SANS_IPXE = "sans_ipxe"


def ecrire(etat: dict) -> None:
    chemins.ecrire_si_change(FICHIER, json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def lire() -> dict | None:
    try:
        with open(FICHIER, encoding="utf-8") as fichier:
            etat = json.load(fichier)
    except (OSError, ValueError):
        return None
    return etat if isinstance(etat, dict) else None

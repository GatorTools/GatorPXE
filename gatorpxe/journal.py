"""Journal du service (§13 de l'analyse), dans `/var/log/gatorpxe/`.

Un seul fichier, `gatorpxe.log`, qui reçoit tout ce que le logiciel
journalise — commandes système comprises, verbatim. La version est écrite à
chaque ouverture : on sait toujours quelle version a tourné.
"""

from __future__ import annotations

import logging
import os

from . import VERSION

RACINE = os.environ.get("GATORPXE_JOURNAUX", "/var/log/gatorpxe")
FICHIER = "gatorpxe.log"


def ouvrir(qui: str) -> logging.Logger:
    """Branche le journal sur le logger « gatorpxe » et y note le démarrage.

    `qui` nomme ce qui démarre : « service », « interface »…"""
    os.makedirs(RACINE, exist_ok=True)
    gestionnaire = logging.FileHandler(os.path.join(RACINE, FICHIER), encoding="utf-8")
    gestionnaire.setLevel(logging.DEBUG)
    gestionnaire.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s : %(message)s")
    )
    racine = logging.getLogger("gatorpxe")
    racine.addHandler(gestionnaire)
    racine.setLevel(logging.DEBUG)

    log = logging.getLogger("gatorpxe.journal")
    log.info("GatorPXE %s — %s démarré", VERSION, qui)
    return log

"""Les ISO Windows (§6 de l'analyse) : leur `boot.wim`, extrait une fois.

wimboot n'a besoin que de lui : il y trouve de lui-même le gestionnaire de
démarrage et ses fichiers. Chaque extraction porte un nom tiré du chemin de
l'ISO et de son empreinte : une ISO remplacée est extraite de nouveau, et les
extractions qui ne servent plus sont effacées.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile

from . import chemins, sysexec

_log = logging.getLogger("gatorpxe.windows")

DELAI = 1800.0  # un boot.wim de 2 Go sur un disque lent


def nom(chemin: str, empreinte: tuple[int, int]) -> str:
    return hashlib.sha1(f"{chemin}\0{empreinte}".encode()).hexdigest()[:16] + ".wim"


def extrait(nom_wim: str) -> bool:
    return os.path.isfile(os.path.join(chemins.WINDOWS, nom_wim))


def extraire(iso: str, chemin_wim: str, nom_wim: str) -> None:
    """Extrait le boot.wim de l'ISO ; il n'apparaît sous son nom qu'une fois
    complet."""
    os.makedirs(chemins.WINDOWS, mode=0o755, exist_ok=True)
    _log.info("extraction de %s depuis %s", chemin_wim, iso)
    with tempfile.TemporaryDirectory(dir=chemins.WINDOWS, prefix=".extraction-") as dossier:
        resultat = sysexec.executer(["7z", "e", "-y", f"-o{dossier}", iso, chemin_wim], delai=DELAI)
        fichier = os.path.join(dossier, os.path.basename(chemin_wim))
        if not resultat.ok or not os.path.isfile(fichier):
            _log.warning("extraction impossible : %s", iso)
            return
        os.chmod(fichier, 0o644)
        os.replace(fichier, os.path.join(chemins.WINDOWS, nom_wim))
    _log.info("%s prêt : %s", iso, nom_wim)


def menage(gardes: set[str]) -> None:
    """Efface les extractions qui ne correspondent plus à aucune ISO."""
    for fichier in sysexec.lister(chemins.WINDOWS):
        if fichier not in gardes:
            chemin = os.path.join(chemins.WINDOWS, fichier)
            shutil.rmtree(chemin, ignore_errors=True) if os.path.isdir(chemin) else os.remove(chemin)
            _log.info("extraction effacée : %s", fichier)

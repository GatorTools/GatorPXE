"""Ce qu'une ISO laisse prévoir de son démarrage par le réseau (§6 de l'analyse).

Sans la démarrer : `7z` liste son contenu (il ne lit que le répertoire, même
pour une ISO de plusieurs gigaoctets) et en extrait au besoin le chargeur UEFI.

  - Un dossier propre à une famille Linux trahit un système à relire sur le
    support après le démarrage : en sanboot, il ne le retrouve pas.
  - Un chargeur UEFI qui n'est pas signé par l'autorité UEFI de Microsoft sera
    refusé par Secure Boot.
  - Une ISO Windows porte `sources/boot.wim` : c'est lui qu'on démarre, par
    wimboot, une fois extrait (module windows).

La détection repère des familles connues ; elle ne garantit rien. Faute
d'indice, une ISO est présentée sans marque.
"""

from __future__ import annotations

import logging
import os
import struct
import tempfile
from dataclasses import dataclass

from . import sysexec

_log = logging.getLogger("gatorpxe.examen")

DELAI = 60.0

# Dossier ou fichier révélateur → famille. Comparaison sans casse.
FAMILLES = {
    "casper": "Ubuntu",
    "live": "Debian live",
    "liveos": "Fedora",
    "images/install.img": "Fedora",
    "install.amd": "installeur Debian",
    "arch": "Arch",
    "apks": "Alpine",
}
CHARGEUR_UEFI = "efi/boot/bootx64.efi"
WINDOWS = "sources/boot.wim"
AUTORITES_MICROSOFT = (b"Microsoft Corporation UEFI CA 2011", b"Microsoft UEFI CA 2023")


@dataclass
class Examen:
    famille: str | None = None  # famille Linux qui ne démarrera pas en sanboot
    signe: bool | None = None  # chargeur UEFI signé par Microsoft ; None : inconnu
    wim: str | None = None  # ISO Windows : le chemin de sources/boot.wim dans l'ISO


def famille(chemins: list[str]) -> str | None:
    """La famille Linux que trahissent les chemins de l'ISO, None sinon."""
    presents = set()
    for chemin in chemins:
        morceaux = chemin.replace("\\", "/").strip("/").lower().split("/")
        presents.add(morceaux[0])
        presents.add("/".join(morceaux[:2]))
    for indice, nom in FAMILLES.items():
        if indice in presents:
            return nom
    return None


def signe_par_microsoft(contenu: bytes) -> bool:
    """Le programme EFI porte-t-il une signature de l'autorité UEFI de Microsoft ?"""
    try:
        pe = struct.unpack_from("<I", contenu, 0x3C)[0]
        if contenu[pe:pe + 4] != b"PE\0\0":
            return False
        options = pe + 24
        magique = struct.unpack_from("<H", contenu, options)[0]
        repertoires = options + (112 if magique == 0x20B else 96)
        debut, taille = struct.unpack_from("<II", contenu, repertoires + 4 * 8)
    except struct.error:
        return False
    signature = contenu[debut:debut + taille]
    return bool(taille) and any(autorite in signature for autorite in AUTORITES_MICROSOFT)


def examiner(iso: str) -> Examen:
    liste = sysexec.executer(["7z", "l", "-slt", "-ba", iso], delai=DELAI)
    if not liste.ok:
        return Examen()
    chemins = [ligne[7:] for ligne in liste.sortie.splitlines() if ligne.startswith("Path = ")]
    examen = Examen(famille=famille(chemins),
                    wim=next((c for c in chemins if c.replace("\\", "/").lower() == WINDOWS), None))

    chargeur = next((c for c in chemins if c.replace("\\", "/").lower() == CHARGEUR_UEFI), None)
    if chargeur:
        with tempfile.TemporaryDirectory() as dossier:
            extrait = sysexec.executer(["7z", "e", "-y", f"-o{dossier}", iso, chargeur], delai=DELAI)
            fichier = os.path.join(dossier, os.path.basename(chargeur))
            if extrait.ok and os.path.isfile(fichier):
                with open(fichier, "rb") as programme:
                    examen.signe = signe_par_microsoft(programme.read())
    _log.info("ISO examinée : %s — %s", iso, examen)
    return examen

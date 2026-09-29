"""Réglages (§11 et §12 de l'analyse), dans `/etc/gatorpxe/gatorpxe.json`.

Écrits par l'interface, relus par le service ; on n'a jamais à les ouvrir
(P5). Un fichier absent ou illisible donne les réglages par défaut : les
postes démarrent même quand personne n'a rien réglé (P4).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields

_log = logging.getLogger("gatorpxe.config")

FICHIER = os.environ.get("GATORPXE_CONFIG", "/etc/gatorpxe/gatorpxe.json")

DISQUE_LOCAL = "disque"
CLONEGATOR = "clonegator"

# Les types de renvoi (§8).
WDS = "wds"
IPXE = "ipxe"
PXE = "pxe"
TYPES_RENVOI = (WDS, IPXE, PXE)

# Ce que demande un WDS, et MECM/SCCM qui démarre de même.
WDS_BIOS = "boot\\x64\\wdsnbp.com"
WDS_UEFI = "boot\\x64\\wdsmgfw.efi"


@dataclass
class Renvoi:
    """Une entrée du menu qui envoie le poste vers un autre serveur (§8)."""

    nom: str
    type: str
    adresse: str  # le serveur ; pour iPXE/HTTP, l'adresse du script (http://…)
    fichier_bios: str = ""  # PXE générique : vide, l'entrée ne paraît pas en BIOS
    fichier_uefi: str = ""  # PXE générique : vide, l'entrée ne paraît pas en UEFI

    def fichiers(self) -> tuple[str, str]:
        """Les fichiers à charger en BIOS et en UEFI : WDS les a d'office."""
        if self.type == WDS:
            return WDS_BIOS, WDS_UEFI
        return self.fichier_bios, self.fichier_uefi


@dataclass
class Reglages:
    proxy_dhcp: bool = True
    carte: str = ""  # vide : la carte réseau principale, détectée seule (§9)
    dossier_images: str = "/srv/gatorpxe/images"
    clonegator: bool = True
    delai: int = 10  # secondes avant l'entrée par défaut (§5)
    entree_defaut: str = DISQUE_LOCAL
    langue: str = "en"
    renvois: list[Renvoi] = field(default_factory=list)  # dans l'ordre du menu


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
        if champ.name == "renvois":
            valeurs["renvois"] = _renvois(valeur)
            continue
        attendu = type(getattr(defaut, champ.name))
        if valeur is None:
            continue
        if type(valeur) is not attendu:
            _log.warning("%s : réglage %s ignoré (%r)", FICHIER, champ.name, valeur)
            continue
        valeurs[champ.name] = valeur
    return Reglages(**valeurs)


def _renvois(brut) -> list[Renvoi]:
    """Les renvois lisibles ; un renvoi abîmé est écarté seul."""
    renvois = []
    for element in brut if isinstance(brut, list) else []:
        try:
            renvoi = Renvoi(**{cle: element[cle] for cle in element
                               if cle in {f.name for f in fields(Renvoi)}})
        except (TypeError, KeyError):
            renvoi = None
        if (renvoi is None or renvoi.type not in TYPES_RENVOI
                or not all(isinstance(getattr(renvoi, f.name), str) for f in fields(Renvoi))
                or not renvoi.nom or not renvoi.adresse):
            _log.warning("%s : renvoi ignoré (%r)", FICHIER, element)
            continue
        renvois.append(renvoi)
    return renvois


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

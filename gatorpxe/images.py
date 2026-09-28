"""Le dossier d'images (§6 de l'analyse).

Déposer un fichier suffit : il paraît au menu au balayage suivant. Un
sous-dossier devient un sous-menu. Les fichiers non reconnus sont écartés, avec
leur raison, pour que l'interface puisse la dire.

Un fichier en cours de copie ne doit pas paraître au menu : une image n'est
retenue que si sa taille et sa date n'ont pas changé depuis le balayage
précédent — au premier balayage, faute de précédent, que si elle n'a pas bougé
depuis `REPOS` secondes.

Ne lance rien : l'inventaire se teste avec un dossier de faux fichiers.
"""

from __future__ import annotations

import os
import re
import stat
import time
from dataclasses import dataclass, field

ISO = "ISO"
WIM = "WIM"
EFI = "EFI"
TYPES = {".iso": ISO, ".wim": WIM, ".efi": EFI}

# Raisons d'écarter un fichier : des phrases pour l'interface (§11).
REPOS = 10

NON_RECONNU = "format non reconnu"
ILLISIBLE = "illisible par le serveur web : droits de lecture manquants"
EN_COPIE = "en cours de copie"


@dataclass
class Image:
    chemin: str  # relatif au dossier d'images, séparé par des /
    nom: str  # nom affiché, sans son type
    type: str
    # Ce que l'examen d'une ISO laisse prévoir (module examen), rempli par le service.
    reseau: bool = True  # False : ne démarrera pas par le réseau
    secure_boot: bool = True  # False : refusée par Secure Boot


@dataclass
class Dossier:
    nom: str
    chemin: str  # relatif au dossier d'images ; vide pour la racine
    images: list[Image] = field(default_factory=list)
    dossiers: list[Dossier] = field(default_factory=list)

    @property
    def vide(self) -> bool:
        return not self.images and all(d.vide for d in self.dossiers)


@dataclass
class Ecarte:
    chemin: str
    raison: str


@dataclass
class Inventaire:
    racine: Dossier | None  # None : dossier d'images introuvable
    ecartes: list[Ecarte] = field(default_factory=list)
    empreintes: dict[str, tuple[int, int]] = field(default_factory=dict)


def nom_affiche(nom: str, extension: bool = True) -> str:
    """`ubuntu-24.04-desktop.iso` → `ubuntu 24.04 desktop`. Un nom de
    dossier n'a pas d'extension : `ubuntu-24.04` garde son `.04`."""
    base = os.path.splitext(nom)[0] if extension else nom
    return re.sub(r"[\s_-]+", " ", base).strip() or base


def _cle(nom: str) -> str:
    return nom.casefold()


def inventaire(racine: str, precedentes: dict[str, tuple[int, int]] | None = None) -> Inventaire:
    """Parcourt le dossier d'images.

    `precedentes` : les empreintes du balayage précédent ; None au premier."""
    if not os.path.isdir(racine):
        return Inventaire(None)
    resultat = Inventaire(Dossier("", ""))
    _parcourir(racine, resultat.racine, precedentes, resultat)
    return resultat


def _parcourir(racine: str, dossier: Dossier, precedentes, resultat: Inventaire) -> None:
    try:
        entrees = sorted(os.scandir(os.path.join(racine, dossier.chemin)), key=lambda e: _cle(e.name))
    except OSError:
        return
    for entree in entrees:
        if entree.name.startswith("."):
            continue
        chemin = f"{dossier.chemin}/{entree.name}" if dossier.chemin else entree.name
        try:
            infos = entree.stat()
        except OSError:
            continue
        if stat.S_ISDIR(infos.st_mode):
            if not infos.st_mode & stat.S_IXOTH:
                resultat.ecartes.append(Ecarte(chemin + "/", ILLISIBLE))
                continue
            sous = Dossier(nom_affiche(entree.name, extension=False), chemin)
            _parcourir(racine, sous, precedentes, resultat)
            if not sous.vide:
                dossier.dossiers.append(sous)
            continue
        if not stat.S_ISREG(infos.st_mode):
            continue
        type_ = TYPES.get(os.path.splitext(entree.name)[1].lower())
        if not type_:
            resultat.ecartes.append(Ecarte(chemin, NON_RECONNU))
            continue
        if not infos.st_mode & stat.S_IROTH:
            resultat.ecartes.append(Ecarte(chemin, ILLISIBLE))
            continue
        empreinte = (infos.st_size, infos.st_mtime_ns)
        resultat.empreintes[chemin] = empreinte
        if precedentes is None:
            stable = time.time() - infos.st_mtime >= REPOS
        else:
            stable = precedentes.get(chemin) == empreinte
        if not stable:
            resultat.ecartes.append(Ecarte(chemin, EN_COPIE))
            continue
        dossier.images.append(Image(chemin, nom_affiche(entree.name), type_))

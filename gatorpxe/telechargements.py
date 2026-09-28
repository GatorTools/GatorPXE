"""Ce que le service va chercher sur Internet (§7 et §10 de l'analyse).

Deux paquets, pris dans la dernière release de leur dépôt GitHub :

  - iPXE, `ipxeboot.tar.gz` : le shim et l'iPXE signés pour l'UEFI,
    `undionly.kpxe` pour le BIOS ;
  - CloneGator, `clonegator-live-pxe.tar` : les fichiers du démarrage réseau de
    son live.

Chaque version est rangée dans son propre dossier, et un lien `actuel` désigne
celle en service : la bascule se fait d'un seul coup. Sans Internet, la
dernière version obtenue reste en service.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass

from . import VERSION, chemins

_log = logging.getLogger("gatorpxe.telechargements")

DELAI = 60.0


@dataclass(frozen=True)
class Paquet:
    nom: str
    depot: str  # « propriétaire/dépôt » sur GitHub
    archive: str  # le fichier joint à la release
    fichiers: dict[str, str]  # chemin dans l'archive → nom rangé
    dossier: str  # où ranger les versions

    def version(self) -> str | None:
        """La version en service, None si aucune n'a encore été obtenue."""
        try:
            return os.path.basename(os.readlink(os.path.join(self.dossier, "actuel")))
        except OSError:
            return None

    def actuel(self) -> str | None:
        """Le dossier des fichiers en service."""
        return os.path.join(self.dossier, "actuel") if self.version() else None


IPXE = Paquet(
    nom="iPXE",
    depot="ipxe/ipxe",
    archive="ipxeboot.tar.gz",
    fichiers={
        "ipxeboot/x86_64-sb/shimx64.efi": "shimx64.efi",
        "ipxeboot/x86_64-sb/ipxe.efi": "ipxe.efi",
        "ipxeboot/x86_64/undionly.kpxe": "undionly.kpxe",
    },
    dossier=chemins.IPXE,
)

CLONEGATOR = Paquet(
    nom="CloneGator",
    depot="GatorTools/CloneGator",
    archive="clonegator-live-pxe.tar",
    fichiers={nom: nom for nom in ("shimx64.efi", "vmlinuz", "initrd.img", "filesystem.squashfs")},
    dossier=chemins.CLONEGATOR,
)


def _ouvrir(url: str):
    requete = urllib.request.Request(url, headers={"User-Agent": f"GatorPXE/{VERSION}"})
    return urllib.request.urlopen(requete, timeout=DELAI)


def mettre_a_jour(paquet: Paquet) -> str | None:
    """Obtient la dernière release du paquet si elle n'est pas déjà là.

    Rend la version en service, nouvelle ou non. Un échec (pas d'Internet,
    archive incomplète) est journalisé et laisse la version précédente."""
    try:
        with _ouvrir(f"https://api.github.com/repos/{paquet.depot}/releases/latest") as reponse:
            release = json.load(reponse)
        version = release["tag_name"]
        url = next(a["browser_download_url"] for a in release["assets"] if a["name"] == paquet.archive)
    except (OSError, ValueError, KeyError, StopIteration) as erreur:
        _log.warning("%s : dernière release introuvable : %s", paquet.nom, erreur)
        return paquet.version()

    if version == paquet.version():
        return version

    _log.info("%s %s : téléchargement de %s", paquet.nom, version, url)
    os.makedirs(paquet.dossier, mode=0o755, exist_ok=True)
    provisoire = tempfile.mkdtemp(prefix=".nouveau-", dir=paquet.dossier)
    try:
        # L'archive est d'abord téléchargée en entier, à côté de sa destination :
        # celle de CloneGator fait 250 Mo, trop pour la mémoire ou /tmp.
        with tempfile.TemporaryFile(dir=paquet.dossier) as archive:
            with _ouvrir(url) as reponse:
                shutil.copyfileobj(reponse, archive)
            archive.seek(0)
            with tarfile.open(fileobj=archive, mode="r:*") as tar:
                for membre, nom in paquet.fichiers.items():
                    source = tar.extractfile(tar.getmember(membre))
                    with open(os.path.join(provisoire, nom), "wb") as destination:
                        shutil.copyfileobj(source, destination)
                    os.chmod(os.path.join(provisoire, nom), 0o644)
        os.chmod(provisoire, 0o755)
        dossier = os.path.join(paquet.dossier, version)
        shutil.rmtree(dossier, ignore_errors=True)
        os.rename(provisoire, dossier)
    except (OSError, KeyError, tarfile.TarError) as erreur:
        _log.warning("%s %s non obtenu : %s", paquet.nom, version, erreur)
        shutil.rmtree(provisoire, ignore_errors=True)
        return paquet.version()

    # Bascule d'un seul coup, puis ménage des anciennes versions. Un fichier
    # en cours d'envoi reste lisible jusqu'à la fin de l'envoi.
    lien = os.path.join(paquet.dossier, ".actuel")
    if os.path.lexists(lien):
        os.remove(lien)
    os.symlink(version, lien)
    os.replace(lien, os.path.join(paquet.dossier, "actuel"))
    for nom in os.listdir(paquet.dossier):
        if nom not in (version, "actuel"):
            shutil.rmtree(os.path.join(paquet.dossier, nom), ignore_errors=True)
    _log.info("%s %s en service", paquet.nom, version)
    return version

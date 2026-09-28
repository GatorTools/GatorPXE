"""Ce que le service va chercher sur Internet (§7 et §10 de l'analyse).

Pour l'instant, iPXE : le paquet `ipxeboot.tar.gz` de sa dernière release porte
le shim et l'iPXE signés pour l'UEFI, et `undionly.kpxe` pour le BIOS. Chaque
version est rangée dans son propre dossier ; sans Internet, la dernière obtenue
reste en service.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tarfile
import tempfile
import urllib.request

from . import VERSION, chemins

_log = logging.getLogger("gatorpxe.telechargements")

DELAI = 60.0
IPXE_RELEASE = "https://api.github.com/repos/ipxe/ipxe/releases/latest"
IPXE_PAQUET = "ipxeboot.tar.gz"

# Ce qu'on garde du paquet d'iPXE : chemin dans l'archive → nom servi.
IPXE_FICHIERS = {
    "ipxeboot/x86_64-sb/shimx64.efi": "shimx64.efi",
    "ipxeboot/x86_64-sb/ipxe.efi": "ipxe.efi",
    "ipxeboot/x86_64/undionly.kpxe": "undionly.kpxe",
}


def _ouvrir(url: str):
    requete = urllib.request.Request(url, headers={"User-Agent": f"GatorPXE/{VERSION}"})
    return urllib.request.urlopen(requete, timeout=DELAI)


def ipxe_version() -> str | None:
    """La version d'iPXE en service, None si aucune n'a encore été obtenue."""
    try:
        return os.path.basename(os.readlink(os.path.join(chemins.IPXE, "actuel")))
    except OSError:
        return None


def ipxe_dossier() -> str | None:
    return os.path.join(chemins.IPXE, "actuel") if ipxe_version() else None


def ipxe_mettre_a_jour() -> str | None:
    """Obtient la dernière release d'iPXE si elle n'est pas déjà là.

    Rend la version en service, nouvelle ou non. Un échec (pas d'Internet,
    archive incomplète) est journalisé et laisse la version précédente."""
    try:
        with _ouvrir(IPXE_RELEASE) as reponse:
            release = json.load(reponse)
        version = release["tag_name"]
        url = next(a["browser_download_url"] for a in release["assets"] if a["name"] == IPXE_PAQUET)
    except (OSError, ValueError, KeyError, StopIteration) as erreur:
        _log.warning("dernière release d'iPXE introuvable : %s", erreur)
        return ipxe_version()

    if version == ipxe_version():
        return version

    _log.info("iPXE %s : téléchargement de %s", version, url)
    os.makedirs(chemins.IPXE, mode=0o755, exist_ok=True)
    provisoire = tempfile.mkdtemp(prefix=".nouveau-", dir=chemins.IPXE)
    try:
        with tempfile.TemporaryFile() as archive:
            with _ouvrir(url) as reponse:
                shutil.copyfileobj(reponse, archive)
            archive.seek(0)
            with tarfile.open(fileobj=archive, mode="r:gz") as tar:
                for membre, nom in IPXE_FICHIERS.items():
                    source = tar.extractfile(tar.getmember(membre))
                    with open(os.path.join(provisoire, nom), "wb") as destination:
                        shutil.copyfileobj(source, destination)
                    os.chmod(os.path.join(provisoire, nom), 0o644)
        os.chmod(provisoire, 0o755)
        dossier = os.path.join(chemins.IPXE, version)
        shutil.rmtree(dossier, ignore_errors=True)
        os.rename(provisoire, dossier)
    except (OSError, KeyError, tarfile.TarError) as erreur:
        _log.warning("iPXE %s non obtenu : %s", version, erreur)
        shutil.rmtree(provisoire, ignore_errors=True)
        return ipxe_version()

    # Bascule d'un seul coup, puis ménage des anciennes versions.
    lien = os.path.join(chemins.IPXE, ".actuel")
    if os.path.lexists(lien):
        os.remove(lien)
    os.symlink(version, lien)
    os.replace(lien, os.path.join(chemins.IPXE, "actuel"))
    for nom in os.listdir(chemins.IPXE):
        if nom not in (version, "actuel"):
            shutil.rmtree(os.path.join(chemins.IPXE, nom), ignore_errors=True)
    _log.info("iPXE %s en service", version)
    return version

"""Les emplacements du service (§12 de l'analyse).

Tout ce que le service télécharge, prépare ou génère vit sous `/var/lib/gatorpxe`.
dnsmasq et lighttpd abandonnent root : ce qu'ils servent doit rester lisible
par tous.
"""

from __future__ import annotations

import os

ETAT = os.environ.get("GATORPXE_ETAT", "/var/lib/gatorpxe")
TFTP = os.path.join(ETAT, "tftp")  # le petit chargeur iPXE, et rien d'autre
HTTP = os.path.join(ETAT, "http")  # le menu ; les images viendront en phase 3
IPXE = os.path.join(ETAT, "ipxe")  # les releases d'iPXE téléchargées
CLONEGATOR = os.path.join(ETAT, "clonegator")  # le démarrage réseau de CloneGator (§7)
WIMBOOT = os.path.join(ETAT, "wimboot")  # pour les images Windows (§6)
WINDOWS = os.path.join(ETAT, "windows")  # boot.wim extraits des ISO Windows (§6)
REGLAGES = os.path.join(ETAT, "reglages")  # réglages générés de dnsmasq et lighttpd

PORT_HTTP = 8069


def ecrire_si_change(chemin: str, contenu: str | bytes) -> bool:
    """Écrit un fichier d'un seul coup, lisible par tous, s'il a changé.

    Rend True s'il a été écrit : un réglage régénéré à l'identique ne doit pas
    faire relancer dnsmasq ni lighttpd."""
    brut = contenu.encode("utf-8") if isinstance(contenu, str) else contenu
    try:
        with open(chemin, "rb") as fichier:
            if fichier.read() == brut:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(chemin), mode=0o755, exist_ok=True)
    temporaire = chemin + ".tmp"
    with open(temporaire, "wb") as fichier:
        fichier.write(brut)
    os.chmod(temporaire, 0o644)
    os.replace(temporaire, chemin)
    return True

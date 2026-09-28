"""Le menu de démarrage (§5 de l'analyse), en script iPXE.

Ne lance rien et ne lit rien : il reçoit les réglages et rend un texte, ce qui
le rend testable seul.

iPXE n'affiche que l'ASCII : les accents sont retirés des textes du menu.
"""

from __future__ import annotations

import unicodedata

from . import config
from .langue import t


def ascii(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if ord(c) < 128)


def script_menu(reglages: config.Reglages, adresse_http: str, clonegator: bool = False) -> str:
    """`adresse_http` : le serveur, `http://…:8069` ; `clonegator` : les
    fichiers de démarrage réseau de CloneGator sont là.

    Les adresses sont écrites en entier : l'iPXE de certaines cartes réseau
    ignore `${cwduri}`."""
    lignes = [
        "#!ipxe",
        "# Généré par GatorPXE : ne pas modifier, il sera réécrit.",
        "",
        "menu GatorPXE",
    ]
    avec_clonegator = clonegator and reglages.clonegator
    if avec_clonegator:
        lignes.append(f"item {config.CLONEGATOR} CloneGator")
    lignes.append(f"item {config.DISQUE_LOCAL} {ascii(t('Démarrer sur le disque local'))}")
    choix = f"choose --default {config.DISQUE_LOCAL}"
    if reglages.delai > 0:
        choix += f" --timeout {reglages.delai * 1000}"
    lignes += [
        f"{choix} cible || goto {config.DISQUE_LOCAL}",
        "goto ${cible}",
        "",
        # En UEFI, rendre la main au micrologiciel, qui passe à l'option de
        # démarrage suivante — avec un code d'échec : sur une réussite, EDK2
        # s'arrête et ouvre son menu. En BIOS, démarrer le premier disque.
        f":{config.DISQUE_LOCAL}",
        "iseq ${platform} efi && exit 1 ||",
        "sanboot --no-describe --drive 0x80",
        "",
    ]
    if avec_clonegator:
        # Le live de CloneGator charge son système compressé par HTTP (`fetch=`).
        lignes += [
            f":{config.CLONEGATOR}",
            # Le noyau de Debian n'est accepté par Secure Boot qu'à travers le
            # shim de Debian : iPXE le charge d'abord, et lui confie le noyau.
            "iseq ${platform} efi && shim clonegator/shimx64.efi ||",
            "kernel clonegator/vmlinuz initrd=initrd.img boot=live quiet"
            f" fetch={adresse_http}/clonegator/filesystem.squashfs",
            "initrd clonegator/initrd.img",
            "boot",
            "",
        ]
    return "\n".join(lignes)


def script_relais(adresse_http: str) -> str:
    """Le script que reçoit un iPXE par TFTP : il passe au menu en HTTP.

    Servi sous deux noms : `gatorpxe.ipxe`, que le proxy DHCP désigne, et
    `autoexec.ipxe`, que l'iPXE signé cherche de lui-même — ce qui évite la
    boucle quand le DHCP est réglé à la main (§9)."""
    return f"#!ipxe\nchain {adresse_http}/menu.ipxe\n"

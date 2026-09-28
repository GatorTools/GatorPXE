"""Le menu de démarrage (§5 de l'analyse), en script iPXE.

Ne lance rien et ne lit rien : il reçoit les réglages et l'inventaire des
images, et rend un texte, ce qui le rend testable seul.

Ordre : CloneGator, les images (un sous-dossier devient un sous-menu), puis le
disque local. iPXE n'affiche que l'ASCII : les accents sont retirés des textes.
Les adresses sont écrites en entier : l'iPXE de certaines cartes réseau ignore
`${cwduri}`.
"""

from __future__ import annotations

import unicodedata
import urllib.parse

from . import config, images
from .langue import t

PRINCIPAL = "gatorpxe"
ECHEC = "echec"


def ascii(texte: str) -> str:
    """Le texte sans accents, et sans `$`, que iPXE prendrait pour un réglage."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if ord(c) < 128 and c != "$")


class _Script:
    def __init__(self, adresse_http: str):
        self.http = adresse_http
        self.menus: list[list[str]] = []  # un bloc par menu
        self.actions: list[list[str]] = []  # un bloc par entrée à démarrer
        self.numero = 0

    def identifiant(self, prefixe: str) -> str:
        self.numero += 1
        return f"{prefixe}{self.numero}"

    def url(self, chemin: str) -> str:
        return f"{self.http}/images/{urllib.parse.quote(chemin)}"

    def items_images(self, dossier: images.Dossier, parent: str) -> list[str]:
        """Les lignes `item` d'un dossier ; ses sous-menus et ses actions sont
        ajoutés au script."""
        items = []
        for sous in dossier.dossiers:
            etiquette = self.identifiant("m")
            items.append(f"item {etiquette} {ascii(sous.nom)} >")
            self.sous_menu(sous, etiquette, parent)
        for image in dossier.images:
            etiquette = self.identifiant("i")
            texte = f"{ascii(image.nom)} ({image.type})"
            marques = [] if image.reseau else [t("incompatible réseau")]
            en_uefi = marques + ([] if image.secure_boot else [t("sans Secure Boot")])
            if image.type == images.EFI:
                # Un programme EFI ne démarre pas en BIOS : l'entrée n'y paraît pas.
                items.append(f"iseq ${{platform}} efi && item {etiquette} {_marque(texte, en_uefi)} ||")
            elif en_uefi != marques:
                # « sans Secure Boot » ne concerne que l'UEFI.
                items.append(f"iseq ${{platform}} efi && item {etiquette} {_marque(texte, en_uefi)} || "
                             f"item {etiquette} {_marque(texte, marques)}")
            else:
                items.append(f"item {etiquette} {_marque(texte, marques)}")
            self.actions.append([f":{etiquette}", *_ou_echec(self.demarrer(image))])
        return items

    def sous_menu(self, dossier: images.Dossier, etiquette: str, parent: str) -> None:
        bloc = [f":{etiquette}", f"menu {ascii(dossier.nom)}"]
        bloc += self.items_images(dossier, etiquette)
        bloc += [
            "item --gap",
            f"item {parent} < {ascii(t('Retour'))}",
            f"choose cible || goto {parent}",
            "goto ${cible}",
        ]
        self.menus.append(bloc)

    def demarrer(self, image: images.Image) -> list[str]:
        url = self.url(image.chemin)
        if image.type == images.WIM:
            return [f"kernel {self.http}/wimboot/wimboot", f"initrd {url} boot.wim", "boot"]
        if image.type == images.EFI:
            return [f"chain {url}"]
        return [f"sanboot --no-describe {url}"]


def script_menu(reglages: config.Reglages, adresse_http: str, clonegator: bool = False,
                inventaire: images.Dossier | None = None) -> str:
    """`adresse_http` : le serveur, `http://…:8069` ; `clonegator` : les
    fichiers de démarrage réseau de CloneGator sont là ; `inventaire` : le
    dossier d'images, None s'il est introuvable."""
    script = _Script(adresse_http)
    avec_clonegator = clonegator and reglages.clonegator

    principal = [f":{PRINCIPAL}", "menu GatorPXE"]
    if avec_clonegator:
        principal.append(f"item {config.CLONEGATOR} CloneGator")
    if inventaire:
        principal += script.items_images(inventaire, PRINCIPAL)
    principal.append(f"item {config.DISQUE_LOCAL} {ascii(t('Démarrer sur le disque local'))}")
    choix = f"choose --default {config.DISQUE_LOCAL}"
    if reglages.delai > 0:
        choix += f" --timeout {reglages.delai * 1000}"
    principal += [f"{choix} cible || goto {config.DISQUE_LOCAL}", "goto ${cible}"]

    lignes = ["#!ipxe", "# Généré par GatorPXE : ne pas modifier, il sera réécrit.", ""]
    for bloc in [principal, *script.menus]:
        lignes += bloc + [""]
    lignes += [
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
        # Le noyau de Debian n'est accepté par Secure Boot qu'à travers le shim
        # de Debian : iPXE le charge d'abord, et lui confie le noyau. En BIOS,
        # la commande n'existe pas.
        lignes += [
            f":{config.CLONEGATOR}",
            f"iseq ${{platform}} efi && shim clonegator/shimx64.efi || iseq ${{platform}} pcbios || goto {ECHEC}",
            *_ou_echec([
                "kernel clonegator/vmlinuz initrd=initrd.img boot=live quiet"
                f" fetch={adresse_http}/clonegator/filesystem.squashfs",
                "initrd clonegator/initrd.img",
                "boot",
            ]),
            "",
        ]
    for bloc in script.actions:
        lignes += bloc + [""]
    lignes += [
        f":{ECHEC}",
        f"echo {ascii(t('Le démarrage a échoué.'))}",
        f"prompt {ascii(t('Appuyez sur une touche pour revenir au menu.'))}",
        f"goto {PRINCIPAL}",
        "",
    ]
    return "\n".join(lignes)


def _marque(texte: str, marques: list[str]) -> str:
    return f"{texte} - {ascii(', '.join(marques))}" if marques else texte


def _ou_echec(commandes: list[str]) -> list[str]:
    """Une commande qui échoue interrompt le script iPXE : chacune renvoie
    plutôt au message d'échec, qui ramène au menu."""
    return [f"{commande} || goto {ECHEC}" for commande in commandes]


def script_relais(adresse_http: str) -> str:
    """Le script que reçoit un iPXE par TFTP : il passe au menu en HTTP.

    Servi sous deux noms : `gatorpxe.ipxe`, que le proxy DHCP désigne, et
    `autoexec.ipxe`, que l'iPXE signé cherche de lui-même — ce qui évite la
    boucle quand le DHCP est réglé à la main (§9)."""
    return f"#!ipxe\nchain {adresse_http}/menu.ipxe\n"

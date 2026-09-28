"""L'instance dnsmasq de GatorPXE (§9 de l'analyse) : proxy DHCP et TFTP.

Proxy actif, dnsmasq ne répond qu'aux demandes de démarrage réseau et ne
distribue aucune adresse (P1). Il donne au poste le bon chargeur, BIOS ou UEFI,
puis reconnaît iPXE une fois chargé pour l'envoyer au menu. Proxy coupé, il ne
sert que le TFTP ; le DHCP existant désigne les fichiers.
"""

from __future__ import annotations

import ipaddress

from . import chemins

FICHIER_BIOS = "undionly.kpxe"
FICHIER_UEFI = "shimx64.efi"
RELAIS = "gatorpxe.ipxe"


def reglages(carte: str, adresse: ipaddress.IPv4Interface, proxy: bool, journal: str) -> str:
    lignes = [
        "# Généré par GatorPXE : ne pas modifier, il sera réécrit.",
        "port=0",  # pas de DNS
        f"interface={carte}",
        "bind-interfaces",
        "enable-tftp",
        f"tftp-root={chemins.TFTP}",
        f"log-facility={journal}",
    ]
    if proxy:
        lignes += [
            f"dhcp-range={adresse.network.network_address},proxy",
            "leasefile-ro",
            "log-dhcp",
            "dhcp-userclass=set:ipxe,iPXE",
            f'pxe-service=tag:!ipxe,x86PC,"GatorPXE",{FICHIER_BIOS}',
            f'pxe-service=tag:!ipxe,X86-64_EFI,"GatorPXE",{FICHIER_UEFI}',
            f'pxe-service=tag:!ipxe,BC_EFI,"GatorPXE",{FICHIER_UEFI}',
            f'pxe-service=tag:ipxe,x86PC,"GatorPXE",{RELAIS}',
            f'pxe-service=tag:ipxe,X86-64_EFI,"GatorPXE",{RELAIS}',
            f'pxe-service=tag:ipxe,BC_EFI,"GatorPXE",{RELAIS}',
        ]
    return "\n".join(lignes) + "\n"


def commande(fichier_reglages: str) -> list[str]:
    return ["dnsmasq", "--keep-in-foreground", f"--conf-file={fichier_reglages}",
            "--pid-file="]

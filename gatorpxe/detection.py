"""Ce que le service DHCP déjà en place dit du démarrage réseau (§9 de l'analyse).

Un DHCPINFORM, en se présentant comme un poste PXE, demande au service DHCP
les options 66 et 67 (serveur et fichier de démarrage). Il ne prend aucun bail.
Selon les serveurs, la réponse revient au port d'origine de la demande ou au
port 68, que le client DHCP de la machine occupe déjà : elle est donc lue
directement sur la carte, quel que soit son port. Celle de GatorPXE lui-même
est ignorée.

La détection n'est sûre que dans un sens : une réponse sans ces options ne
prouve rien, certains serveurs ne les donnant qu'à certains postes.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
import struct
import time
from dataclasses import dataclass

_log = logging.getLogger("gatorpxe.detection")

DELAI = 3.0
ETH_P_IP = 0x0800
COOKIE = b"\x63\x82\x53\x63"
CLASSE = b"PXEClient:Arch:00007:UNDI:003016"


@dataclass
class Demarrage:
    """Le serveur de démarrage que désigne le service DHCP déjà en place."""

    serveur: str  # option 66, ou à défaut le champ « next-server »
    fichier: str  # option 67, ou à défaut le champ « file »


def paquet_inform(adresse: str, mac: bytes, xid: bytes) -> bytes:
    entete = struct.pack("!BBBB4sHH4s4s4s4s16s64s128s", 1, 1, 6, 0, xid, 0, 0,
                         socket.inet_aton(adresse), bytes(4), bytes(4), bytes(4),
                         mac.ljust(16, b"\0"), bytes(64), bytes(128))
    options = (COOKIE + bytes([53, 1, 8]) + bytes([55, 4, 1, 3, 66, 67])
               + bytes([60, len(CLASSE)]) + CLASSE + bytes([93, 2, 0, 7]) + b"\xff")
    return entete + options


def analyser(reponse: bytes) -> tuple[str, Demarrage | None]:
    """Rend (xid, démarrage désigné) d'une réponse DHCP, ou (xid, None)."""
    if len(reponse) < 240 or reponse[236:240] != COOKIE:
        return "", None
    xid = reponse[4:8].hex()
    siaddr = socket.inet_ntoa(reponse[20:24])
    fichier_bootp = reponse[108:236].split(b"\0")[0].decode(errors="replace")
    options: dict[int, bytes] = {}
    i = 240
    while i < len(reponse) and reponse[i] != 255:
        if reponse[i] == 0:
            i += 1
            continue
        if i + 1 >= len(reponse):
            break
        longueur = reponse[i + 1]
        options[reponse[i]] = reponse[i + 2:i + 2 + longueur]
        i += 2 + longueur
    serveur = options.get(66, b"").split(b"\0")[0].decode(errors="replace") or (
        siaddr if siaddr != "0.0.0.0" else "")
    fichier = options.get(67, b"").split(b"\0")[0].decode(errors="replace") or fichier_bootp
    if not serveur and not fichier:
        return xid, None
    return xid, Demarrage(serveur, fichier)


def interroger(carte: str, adresse: ipaddress.IPv4Interface, mac: bytes) -> Demarrage | None:
    """Demande au service DHCP de la carte ce qu'il annonce aux postes PXE."""
    xid = os.urandom(4)
    propre = str(adresse.ip)
    try:
        # Sans liaison à la carte : liée à un pont, la socket ne reçoit rien.
        # Les trames sont filtrées par carte ci-dessous.
        ecoute = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ETH_P_IP))
        envoi = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        envoi.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        envoi.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, carte.encode())
        envoi.bind((propre, 0))
    except OSError as erreur:
        _log.warning("DHCPINFORM impossible sur %s : %s", carte, erreur)
        return None
    with ecoute, envoi:
        envoi.sendto(paquet_inform(propre, mac, xid), ("255.255.255.255", 67))
        fin = time.monotonic() + DELAI
        while (reste := fin - time.monotonic()) > 0:
            ecoute.settimeout(reste)
            try:
                trame, origine = ecoute.recvfrom(4096)
            except socket.timeout:
                break
            if origine[0] != carte:
                continue
            # En-tête IP puis UDP : réponses d'un serveur DHCP (port 67).
            longueur_ip = (trame[0] & 0x0F) * 4
            if len(trame) < longueur_ip + 8 or trame[9] != 17:
                continue
            source = socket.inet_ntoa(trame[12:16])
            port_source = struct.unpack("!H", trame[longueur_ip:longueur_ip + 2])[0]
            if port_source != 67 or source == propre:
                continue
            recu, demarrage = analyser(trame[longueur_ip + 8:])
            if recu == xid.hex():
                _log.info("service DHCP %s : démarrage réseau %s", source, demarrage or "non annoncé")
                return demarrage
    _log.info("service DHCP : pas de réponse au DHCPINFORM sur %s", carte)
    return None

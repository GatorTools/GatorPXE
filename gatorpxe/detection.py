"""Ce que le service DHCP du réseau annonce aux postes PXE (§9 de l'analyse).

GatorPXE envoie un DHCPINFORM, en se présentant comme un poste PXE, pour
demander au service DHCP du réseau ses options 66 et 67 (serveur et fichier de
démarrage). Un DHCPINFORM ne prend aucun bail.

La réponse ne peut pas être lue sur une socket UDP ordinaire : selon le
serveur, elle revient au port d'origine de la demande ou au port 68, que le
client DHCP de la machine occupe déjà. Elle est donc lue directement sur la
carte, par une socket brute. Un filtre posé dans le noyau n'y laisse passer que
les réponses de serveurs DHCP : même sur un serveur très chargé, Python n'a que
quelques paquets à examiner.

La détection n'est sûre que dans un sens : une réponse sans ces options ne
prouve rien, certains serveurs ne les donnant qu'à certains postes.
"""

from __future__ import annotations

import ctypes
import ipaddress
import logging
import os
import socket
import struct
import time
from dataclasses import dataclass

_log = logging.getLogger("gatorpxe.detection")

DELAI = 3.0  # secondes d'attente de la réponse
PORT_SERVEUR = 67
COOKIE = b"\x63\x82\x53\x63"
CLASSE = b"PXEClient:Arch:00007:UNDI:003016"  # un poste PXE UEFI x64

ETH_P_IP = 0x0800
SO_ATTACH_FILTER = 26  # absent du module socket

# Le filtre du noyau : « UDP, port source 67, paquet non fragmenté ». C'est le
# programme BPF de `tcpdump -d 'udp src port 67'`, décalé de 14 octets : une
# socket SOCK_DGRAM voit les paquets sans leur en-tête Ethernet.
# Chaque instruction : (code, saut si vrai, saut si faux, valeur).
_FILTRE = [
    (0x30, 0, 0, 9),       # octet 9 de l'en-tête IP : le protocole
    (0x15, 0, 6, 17),      # UDP ? sinon, refuser
    (0x28, 0, 0, 6),       # champ des fragments
    (0x45, 4, 0, 0x1FFF),  # fragment non initial ? refuser
    (0xB1, 0, 0, 0),       # X = longueur de l'en-tête IP
    (0x48, 0, 0, 0),       # port source UDP
    (0x15, 0, 1, PORT_SERVEUR),
    (0x06, 0, 0, 0xFFFF),  # accepter
    (0x06, 0, 0, 0),       # refuser
]


@dataclass
class Demarrage:
    """Le serveur de démarrage que désigne le service DHCP du réseau."""

    serveur: str  # option 66, ou à défaut le champ « next-server »
    fichier: str  # option 67, ou à défaut le champ « file »


# --------------------------------------------------------------- paquets ---

def paquet_inform(adresse: str, mac: bytes, xid: bytes) -> bytes:
    """Un DHCPINFORM de poste PXE qui demande les options 66 et 67."""
    entete = struct.pack("!BBBB4sHH4s4s4s4s16s64s128s",
                         1, 1, 6, 0,  # requête, Ethernet, adresse de 6 octets
                         xid, 0, 0,
                         socket.inet_aton(adresse), bytes(4), bytes(4), bytes(4),
                         mac.ljust(16, b"\0"), bytes(64), bytes(128))
    options = (bytes([53, 1, 8])                              # DHCPINFORM
               + bytes([55, 4, 1, 3, 66, 67])                 # options demandées
               + bytes([60, len(CLASSE)]) + CLASSE            # classe : poste PXE
               + bytes([93, 2, 0, 7])                         # architecture UEFI x64
               + b"\xff")
    return entete + COOKIE + options


def lire_options(options: bytes) -> dict[int, bytes]:
    """Les options DHCP d'un paquet, après le « cookie »."""
    lues: dict[int, bytes] = {}
    i = 0
    while i + 1 < len(options) and options[i] != 255:
        if options[i] == 0:  # bourrage
            i += 1
            continue
        code, longueur = options[i], options[i + 1]
        lues[code] = options[i + 2:i + 2 + longueur]
        i += 2 + longueur
    return lues


def _texte(brut: bytes) -> str:
    return brut.split(b"\0")[0].decode(errors="replace")


def analyser(reponse: bytes) -> tuple[bytes, Demarrage | None]:
    """Le numéro de transaction d'une réponse DHCP, et le démarrage qu'elle
    annonce (None si elle n'en annonce aucun, ou si ce n'est pas du DHCP)."""
    if len(reponse) < 240 or reponse[236:240] != COOKIE:
        return b"", None
    xid, siaddr, fichier_bootp = reponse[4:8], reponse[20:24], reponse[108:236]
    options = lire_options(reponse[240:])
    # Sans fichier de démarrage, rien n'est annoncé : beaucoup de serveurs DHCP
    # mettent de toute façon leur propre adresse dans « next-server ».
    fichier = _texte(options.get(67, b"")) or _texte(fichier_bootp)
    if not fichier:
        return xid, None
    serveur = _texte(options.get(66, b""))
    if not serveur and siaddr != bytes(4):
        serveur = socket.inet_ntoa(siaddr)
    return xid, Demarrage(serveur, fichier)


# --------------------------------------------------------------- réseau ---

def _ecoute() -> socket.socket:
    """Une socket brute qui ne reçoit que les réponses de serveurs DHCP.

    Elle n'est pas liée à la carte : liée à un pont (bridge), elle ne reçoit
    rien. Les paquets sont filtrés par carte à la réception."""
    ecoute = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ETH_P_IP))
    programme = b"".join(struct.pack("HBBI", *instruction) for instruction in _FILTRE)
    tampon = ctypes.create_string_buffer(programme)
    # struct sock_fprog { unsigned short len; struct sock_filter *filter; }
    fprog = struct.pack("HL", len(_FILTRE), ctypes.addressof(tampon))
    ecoute.setsockopt(socket.SOL_SOCKET, SO_ATTACH_FILTER, fprog)
    return ecoute


def _reponse_dhcp(paquet: bytes) -> tuple[str, bytes]:
    """L'adresse source et le contenu DHCP d'un paquet IP/UDP."""
    longueur_ip = (paquet[0] & 0x0F) * 4
    return socket.inet_ntoa(paquet[12:16]), paquet[longueur_ip + 8:]


def interroger(carte: str, adresse: ipaddress.IPv4Interface, mac: bytes) -> Demarrage | None:
    """Demande au service DHCP du réseau ce qu'il annonce aux postes PXE.

    Rend None s'il ne répond pas, s'il n'annonce rien, ou en cas d'erreur."""
    xid = os.urandom(4)
    propre = str(adresse.ip)
    try:
        with _ecoute() as ecoute, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as envoi:
            envoi.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            envoi.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, carte.encode())
            envoi.bind((propre, 0))
            envoi.sendto(paquet_inform(propre, mac, xid), ("255.255.255.255", PORT_SERVEUR))
            fin = time.monotonic() + DELAI
            while (reste := fin - time.monotonic()) > 0:
                ecoute.settimeout(reste)
                try:
                    paquet, origine = ecoute.recvfrom(4096)
                except socket.timeout:
                    break
                source, dhcp = _reponse_dhcp(paquet)
                # La réponse de GatorPXE lui-même (proxy DHCP) ne compte pas.
                if origine[0] != carte or source == propre:
                    continue
                recu, demarrage = analyser(dhcp)
                if recu == xid:
                    _log.info("service DHCP %s : démarrage réseau %s", source, demarrage or "non annoncé")
                    return demarrage
    except OSError as erreur:
        _log.warning("DHCPINFORM impossible sur %s : %s", carte, erreur)
        return None
    _log.info("service DHCP : pas de réponse au DHCPINFORM sur %s", carte)
    return None

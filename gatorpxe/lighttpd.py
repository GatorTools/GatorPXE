"""L'instance lighttpd de GatorPXE (§3 de l'analyse) : tout ce qui passe par HTTP.

Elle n'écoute que sur l'adresse de la carte du service, port 8069, et ne
touche pas à un lighttpd déjà installé (P3).
"""

from __future__ import annotations

import ipaddress
import os
import pwd

from . import chemins

UTILISATEUR = "www-data"


def reglages(adresse: ipaddress.IPv4Interface, journal_acces: str, journal_erreurs: str) -> str:
    return "\n".join([
        "# Généré par GatorPXE : ne pas modifier, il sera réécrit.",
        'server.modules = ("mod_accesslog")',
        f'server.document-root = "{chemins.HTTP}"',
        f'server.bind = "{adresse.ip}"',
        f"server.port = {chemins.PORT_HTTP}",
        f'server.username = "{UTILISATEUR}"',
        f'server.groupname = "{UTILISATEUR}"',
        f'server.errorlog = "{journal_erreurs}"',
        f'accesslog.filename = "{journal_acces}"',
        'mimetype.assign = (".ipxe" => "text/plain", "" => "application/octet-stream")',
        "",
    ])


def preparer_journaux(*journaux: str) -> None:
    """lighttpd abandonne root avant d'ouvrir ses journaux : ils sont créés
    d'avance, à son nom."""
    compte = pwd.getpwnam(UTILISATEUR)
    for chemin in journaux:
        with open(chemin, "a", encoding="utf-8"):
            pass
        os.chown(chemin, compte.pw_uid, compte.pw_gid)


def commande(fichier_reglages: str) -> list[str]:
    return ["lighttpd", "-D", "-f", fichier_reglages]

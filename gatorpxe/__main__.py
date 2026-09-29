"""Point d'entrée : `gatorpxe` ouvre l'interface (§11 de l'analyse),
`gatorpxe service` fait tourner le service (§3).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from . import VERSION, config, journal, langue, service
from .langue import t


def cmd_version(_args) -> int:
    print(f"GatorPXE {VERSION}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="gatorpxe")
    sous = parseur.add_subparsers(dest="commande")
    sous.add_parser("version", help="afficher la version").set_defaults(fonction=cmd_version)
    sous.add_parser("service", help="faire tourner le service (systemd)").set_defaults(
        fonction=lambda _args: service.lancer())
    args = parseur.parse_args(argv)

    if args.commande == "version":
        return args.fonction(args)

    langue.choisir(config.lire().langue)
    if os.geteuid() != 0:
        print(t("GatorPXE doit être lancé en root :  sudo gatorpxe"), file=sys.stderr)
        return 1
    if args.commande:
        return args.fonction(args)
    # Rien sur l'écran de curses : les avertissements de l'interface vont dans un fichier.
    os.makedirs(journal.RACINE, exist_ok=True)
    fichier = logging.FileHandler(os.path.join(journal.RACINE, "interface.log"), encoding="utf-8")
    fichier.setLevel(logging.WARNING)
    fichier.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    logging.getLogger().addHandler(fichier)
    from .ui import app
    return app.demarrer()


if __name__ == "__main__":
    sys.exit(main())

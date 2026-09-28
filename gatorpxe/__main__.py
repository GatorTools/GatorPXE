"""Point d'entrée : `gatorpxe` ouvrira l'interface (§11 de l'analyse),
`gatorpxe service` fera tourner le service (§3).

L'interface viendra en phase 5 ; d'ici là, `gatorpxe` affiche la version.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import VERSION, config, langue, service
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
    return cmd_version(args)


if __name__ == "__main__":
    sys.exit(main())

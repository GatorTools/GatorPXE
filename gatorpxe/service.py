"""Le service GatorPXE (§3 de l'analyse).

Il ne sert rien lui-même (§15) : il prépare les fichiers, génère les réglages
de dnsmasq et lighttpd, les lance et les relance s'ils s'arrêtent. Toutes les
quelques secondes, il refait le tour ; un réglage changé ne relance que
l'instance concernée. SIGHUP lui fait relire les réglages, SIGTERM l'arrête.
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import threading
import time
from typing import Callable

from . import chemins, config, dnsmasq, journal, langue, lighttpd, menu, reseau, sysexec, telechargements

_log = logging.getLogger("gatorpxe.service")

TOUR = 5.0  # secondes entre deux tours
MISE_A_JOUR = 24 * 3600  # une recherche de nouvelle version par jour


class Instance:
    """dnsmasq ou lighttpd : ses réglages générés, et le programme qui tourne."""

    def __init__(self, nom: str):
        self.nom = nom
        self.fichier = os.path.join(chemins.REGLAGES, f"{nom}.conf")
        self.programme: sysexec.Programme | None = None

    def appliquer(self, contenu: str, commande: Callable[[str], list[str]]) -> None:
        """Lance l'instance, ou la relance si ses réglages ont changé ou si
        elle s'est arrêtée."""
        change = chemins.ecrire_si_change(self.fichier, contenu)
        if self.programme and self.programme.vivant() and not change:
            return
        if self.programme and not self.programme.vivant():
            _log.warning("%s s'est arrêté (code %s) : relancé", self.nom, self.programme.code)
        elif change and self.programme:
            _log.info("%s : réglages changés, relancé", self.nom)
        self.arreter()
        self.programme = sysexec.Programme(commande(self.fichier),
                                           os.path.join(journal.RACINE, f"{self.nom}-sorties.log"))

    def arreter(self) -> None:
        if self.programme:
            self.programme.arreter()
            self.programme = None


class Service:
    def __init__(self):
        self.dnsmasq = Instance("dnsmasq")
        self.lighttpd = Instance("lighttpd")
        self.a_relire = True
        self.en_marche = True
        self.reglages = config.Reglages()
        self.derniere_recherche = 0.0
        self.derniere_recherche_clonegator = 0.0
        self.telechargement: threading.Thread | None = None
        self.attente_signalee = ""

    def tourner(self) -> None:
        signal.signal(signal.SIGHUP, lambda *_: setattr(self, "a_relire", True))
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "en_marche", False))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "en_marche", False))
        for dossier in (chemins.ETAT, chemins.TFTP, chemins.HTTP, chemins.REGLAGES):
            os.makedirs(dossier, mode=0o755, exist_ok=True)
            os.chmod(dossier, 0o755)
        try:
            while self.en_marche:
                self.tour()
                fin = time.monotonic() + TOUR
                while self.en_marche and not self.a_relire and time.monotonic() < fin:
                    time.sleep(0.2)
        finally:
            self.dnsmasq.arreter()
            self.lighttpd.arreter()
            _log.info("service arrêté")

    def tour(self) -> None:
        if self.a_relire:
            self.a_relire = False
            self.reglages = config.lire()
            langue.choisir(self.reglages.langue)
            _log.info("réglages lus : %s", self.reglages)

        ipxe = telechargements.IPXE
        if time.monotonic() - self.derniere_recherche > MISE_A_JOUR or not ipxe.version():
            self.derniere_recherche = time.monotonic()
            telechargements.mettre_a_jour(ipxe)
        chargeurs = ipxe.actuel()
        self.suivre_clonegator()

        carte = self.reglages.carte or reseau.carte_principale()
        adresse = reseau.adresse(carte) if carte else None
        attente = ""
        if not carte:
            attente = "aucune carte réseau principale"
        elif not adresse:
            attente = f"la carte {carte} n'a pas d'adresse IPv4"
        elif not chargeurs:
            attente = "iPXE pas encore obtenu"
        if attente:
            if attente != self.attente_signalee:
                _log.warning("en attente : %s ; les postes ne sont pas servis", attente)
                self.attente_signalee = attente
            self.dnsmasq.arreter()
            self.lighttpd.arreter()
            return
        if self.attente_signalee:
            _log.info("fin de l'attente : carte %s, adresse %s", carte, adresse)
            self.attente_signalee = ""

        self.preparer(chargeurs, f"http://{adresse.ip}:{chemins.PORT_HTTP}")
        acces = os.path.join(journal.RACINE, "http-acces.log")
        erreurs = os.path.join(journal.RACINE, "http-erreurs.log")
        lighttpd.preparer_journaux(acces, erreurs)
        self.lighttpd.appliquer(lighttpd.reglages(adresse, acces, erreurs), lighttpd.commande)
        self.dnsmasq.appliquer(
            dnsmasq.reglages(carte, adresse, self.reglages.proxy_dhcp,
                             os.path.join(journal.RACINE, "dnsmasq.log")),
            dnsmasq.commande,
        )

    def suivre_clonegator(self) -> None:
        """CloneGator, une fois par jour, en arrière-plan : ses 250 Mo
        n'empêchent pas le service de servir les postes. Retiré du menu, il
        n'est plus téléchargé."""
        if not self.reglages.clonegator or (self.telechargement and self.telechargement.is_alive()):
            return
        premiere_fois = not telechargements.CLONEGATOR.version()
        # Sans Internet, une nouvelle tentative toutes les heures tant qu'aucune version n'est là.
        delai = 3600 if premiere_fois else MISE_A_JOUR
        if self.derniere_recherche_clonegator and time.monotonic() - self.derniere_recherche_clonegator < delai:
            return
        self.derniere_recherche_clonegator = time.monotonic()
        self.telechargement = threading.Thread(
            target=telechargements.mettre_a_jour, args=(telechargements.CLONEGATOR,),
            name="clonegator", daemon=True)
        self.telechargement.start()

    def preparer(self, chargeurs: str, adresse_http: str) -> None:
        """Les fichiers servis : chargeurs iPXE et relais en TFTP ; menu et
        CloneGator en HTTP."""
        for nom in telechargements.IPXE.fichiers.values():
            with open(os.path.join(chargeurs, nom), "rb") as fichier:
                if chemins.ecrire_si_change(os.path.join(chemins.TFTP, nom), fichier.read()):
                    _log.info("chargeur %s mis en place", nom)
        relais = menu.script_relais(adresse_http)
        chemins.ecrire_si_change(os.path.join(chemins.TFTP, dnsmasq.RELAIS), relais)
        chemins.ecrire_si_change(os.path.join(chemins.TFTP, "autoexec.ipxe"), relais)

        # CloneGator est servi par un lien vers sa version en service.
        lien = os.path.join(chemins.HTTP, "clonegator")
        present = bool(telechargements.CLONEGATOR.version())
        if present and not os.path.islink(lien):
            if os.path.lexists(lien):
                shutil.rmtree(lien)
            os.symlink(os.path.join(chemins.CLONEGATOR, "actuel"), lien)
        elif not present and os.path.lexists(lien):
            os.remove(lien) if os.path.islink(lien) else shutil.rmtree(lien)
        if chemins.ecrire_si_change(os.path.join(chemins.HTTP, "menu.ipxe"),
                                    menu.script_menu(self.reglages, adresse_http, present)):
            _log.info("menu reconstruit")


def lancer() -> int:
    journal.ouvrir("service")
    for programme in ("dnsmasq", "lighttpd"):
        if not sysexec.disponible(programme):
            _log.error("%s introuvable : le service ne peut pas démarrer", programme)
            return 1
    Service().tourner()
    return 0


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
import socket
import threading
import time
from typing import Callable

from . import (VERSION, chemins, config, detection, dnsmasq, etat, examen, images, journal, langue, lighttpd, menu, reseau,
               sysexec, telechargements, windows)

_log = logging.getLogger("gatorpxe.service")

TOUR = 5.0  # secondes entre deux tours
DETECTION = 3600  # une interrogation du service DHCP déjà en place par heure
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
        self.inventaire = images.Inventaire(None)
        self.empreintes: dict[str, tuple[int, int]] | None = None
        self.examens: dict[str, tuple[tuple[int, int], examen.Examen]] = {}
        self.extraction: threading.Thread | None = None
        # Ce que le service DHCP déjà en place annonce aux postes PXE (module detection).
        self.detection: threading.Thread | None = None
        self.derniere_detection = 0.0
        self.demarrage_dhcp: tuple[detection.Demarrage, str] | None = None  # et l'adresse du serveur

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
            self.derniere_detection = 0.0  # réglages changés : on réinterroge
            self.reglages = config.lire()
            langue.choisir(self.reglages.langue)
            _log.info("réglages lus : %s", self.reglages)

        ipxe = telechargements.IPXE
        if (time.monotonic() - self.derniere_recherche > MISE_A_JOUR
                or not ipxe.version() or not telechargements.WIMBOOT.version()):
            self.derniere_recherche = time.monotonic()
            telechargements.mettre_a_jour(ipxe)
            telechargements.mettre_a_jour(telechargements.WIMBOOT)
        chargeurs = ipxe.actuel()
        self.suivre_clonegator()

        carte = self.reglages.carte or reseau.carte_principale()
        adresse = reseau.adresse(carte) if carte else None
        attente = ""
        if not carte:
            attente = etat.SANS_CARTE
        elif not adresse:
            attente = etat.SANS_ADRESSE
        elif not chargeurs:
            attente = etat.SANS_IPXE
        if attente:
            if attente != self.attente_signalee:
                _log.warning("en attente (%s, carte %s) : les postes ne sont pas servis", attente, carte)
                self.attente_signalee = attente
            self.dnsmasq.arreter()
            self.lighttpd.arreter()
            self.publier(carte, adresse, attente)
            return
        if self.attente_signalee:
            _log.info("fin de l'attente : carte %s, adresse %s", carte, adresse)
            self.attente_signalee = ""

        self.balayer()
        self.preparer(chargeurs, f"http://{adresse.ip}:{chemins.PORT_HTTP}")
        acces = os.path.join(journal.RACINE, "http-acces.log")
        erreurs = os.path.join(journal.RACINE, "http-erreurs.log")
        lighttpd.preparer_journaux(acces, erreurs)
        self.lighttpd.appliquer(
            lighttpd.reglages(adresse, self.reglages.dossier_images, acces, erreurs), lighttpd.commande)
        self.dnsmasq.appliquer(
            dnsmasq.reglages(carte, adresse, self.reglages.proxy_dhcp,
                             os.path.join(journal.RACINE, "dnsmasq.log")),
            dnsmasq.commande,
        )
        self.detecter(carte, adresse)
        self.publier(carte, adresse, "")

    def publier(self, carte, adresse, attente: str) -> None:
        """L'état pour l'interface (module etat)."""
        def vivant(instance: Instance) -> bool:
            return bool(instance.programme and instance.programme.vivant())

        def liste(dossier: images.Dossier | None) -> list[dict]:
            if dossier is None:
                return []
            return [{"chemin": i.chemin, "nom": i.nom, "type": i.type, "reseau": i.reseau,
                     "secure_boot": i.secure_boot} for i in dossier.images] + [
                x for d in dossier.dossiers for x in liste(d)]

        etat.ecrire({
            "version": VERSION,
            "carte": carte or "",
            "adresse": str(adresse.ip) if adresse else "",
            "adresse_dynamique": reseau.adresse_dynamique(carte) if adresse else False,
            "dhcp_demarrage": _demarrage(self.demarrage_dhcp, adresse),
            "attente": attente,
            "proxy_dhcp": self.reglages.proxy_dhcp,
            "dnsmasq": vivant(self.dnsmasq),
            "lighttpd": vivant(self.lighttpd),
            "ipxe": telechargements.IPXE.version() or "",
            "clonegator": telechargements.CLONEGATOR.version() or "",
            "dossier_images": self.reglages.dossier_images,
            "dossier_introuvable": self.inventaire.racine is None,
            "images": liste(self.inventaire.racine),
            "ecartes": [{"chemin": e.chemin, "raison": e.raison} for e in self.inventaire.ecartes],
            "windows": {f"windows/{windows.nom(c, m[0])}": c for c, m in self.examens.items() if m[1].wim},
        })

    def detecter(self, carte: str, adresse) -> None:
        """Interroge le service DHCP déjà en place, en arrière-plan : au
        démarrage, à chaque changement de réglages, puis une fois par heure."""
        if self.detection and self.detection.is_alive():
            return
        if self.derniere_detection and time.monotonic() - self.derniere_detection < DETECTION:
            return
        self.derniere_detection = time.monotonic()
        mac = reseau.mac(carte)
        if not mac:
            return

        def interroger():
            demarrage = detection.interroger(carte, adresse, mac)
            if demarrage is None:
                self.demarrage_dhcp = None
                return
            try:  # l'option 66 peut être un nom
                ip = socket.gethostbyname(demarrage.serveur) if demarrage.serveur else ""
            except OSError:
                ip = demarrage.serveur
            self.demarrage_dhcp = (demarrage, ip)

        self.detection = threading.Thread(target=interroger, name="detection", daemon=True)
        self.detection.start()

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

    def balayer(self) -> None:
        """Le dossier d'images, à chaque tour. Le dossier par défaut est créé ;
        un dossier choisi ne l'est jamais : ce peut être un disque débranché,
        et le service attend qu'il revienne (§12)."""
        dossier = self.reglages.dossier_images
        if dossier == config.Reglages().dossier_images and not os.path.exists(dossier):
            os.makedirs(dossier, mode=0o755)
        avant = self.inventaire
        self.inventaire = images.inventaire(dossier, self.empreintes)
        self.empreintes = self.inventaire.empreintes
        gardes: set[str] = set()
        self.examiner(dossier, self.inventaire.racine, gardes)
        if not (self.extraction and self.extraction.is_alive()) and self.inventaire.racine is not None:
            windows.menage(gardes)
        if self.inventaire.racine is None and avant.racine is not None:
            _log.warning("dossier d'images introuvable : %s", dossier)
        elif self.inventaire.racine is not None and avant.racine is None:
            _log.info("dossier d'images : %s", dossier)
        presentes = _images(self.inventaire.racine)
        for chemin in sorted(presentes - _images(avant.racine)):
            _log.info("image ajoutée : %s", chemin)
        for chemin in sorted(_images(avant.racine) - presentes):
            _log.info("image retirée : %s", chemin)
        ecartes = {(e.chemin, e.raison) for e in self.inventaire.ecartes if e.raison != images.EN_COPIE}
        for chemin, raison in sorted(ecartes - {(e.chemin, e.raison) for e in avant.ecartes}):
            _log.info("fichier écarté : %s (%s)", chemin, raison)

    def examiner(self, racine: str, dossier: images.Dossier | None, gardes: set[str]) -> None:
        """Les marques des ISO : un examen par fichier, gardé tant que le
        fichier ne change pas. Une ISO Windows ne paraît au menu qu'une fois
        son boot.wim extrait, en arrière-plan, une ISO à la fois."""
        if dossier is None:
            return
        for sous in dossier.dossiers:
            self.examiner(racine, sous, gardes)
        prets = []
        for image in dossier.images:
            prets.append(image)
            if image.type != images.ISO:
                continue
            empreinte = self.empreintes[image.chemin]
            memoire = self.examens.get(image.chemin)
            if not memoire or memoire[0] != empreinte:
                memoire = (empreinte, examen.examiner(os.path.join(racine, image.chemin)))
                self.examens[image.chemin] = memoire
            resultat = memoire[1]
            image.reseau = resultat.famille is None
            # Une ISO Windows démarre par wimboot, signé : son propre chargeur ne sert pas.
            image.secure_boot = resultat.signe is not False or bool(resultat.wim)
            if resultat.wim:
                nom_wim = windows.nom(image.chemin, empreinte)
                gardes.add(nom_wim)
                if windows.extrait(nom_wim):
                    image.wim = f"windows/{nom_wim}"
                    continue
                prets.pop()
                self.inventaire.ecartes.append(images.Ecarte(image.chemin, images.EN_PREPARATION))
                if not (self.extraction and self.extraction.is_alive()):
                    self.extraction = threading.Thread(
                        target=windows.extraire, name="windows", daemon=True,
                        args=(os.path.join(racine, image.chemin), resultat.wim, nom_wim))
                    self.extraction.start()
        dossier.images = prets

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

        # CloneGator et wimboot sont servis par un lien vers leur version en service.
        present = _lier("clonegator", telechargements.CLONEGATOR)
        _lier("wimboot", telechargements.WIMBOOT)
        lien = os.path.join(chemins.HTTP, "windows")
        if not os.path.islink(lien):
            os.makedirs(chemins.WINDOWS, mode=0o755, exist_ok=True)
            os.symlink(chemins.WINDOWS, lien)
        if chemins.ecrire_si_change(os.path.join(chemins.HTTP, "menu.ipxe"),
                                    menu.script_menu(self.reglages, adresse_http, present,
                                                     self.inventaire.racine,
                                                     telechargements.IPXE.version() or "")):
            _log.info("menu reconstruit")


def _demarrage(trouve: tuple[detection.Demarrage, str] | None, adresse) -> dict | None:
    """Le serveur de démarrage annoncé par le service DHCP déjà en place, et
    s'il s'agit de ce serveur-ci."""
    if trouve is None or adresse is None:
        return None
    demarrage, ip = trouve
    return {"serveur": demarrage.serveur, "fichier": demarrage.fichier,
            "ce_serveur": ip == str(adresse.ip)}


def _images(dossier: images.Dossier | None) -> set[str]:
    if dossier is None:
        return set()
    return {i.chemin for i in dossier.images} | set().union(*(_images(d) for d in dossier.dossiers))


def _lier(nom: str, paquet: telechargements.Paquet) -> bool:
    """Le lien `http/<nom>` vers la version en service du paquet ; rend True
    si elle existe."""
    lien = os.path.join(chemins.HTTP, nom)
    present = bool(paquet.version())
    if present and not os.path.islink(lien):
        if os.path.lexists(lien):
            shutil.rmtree(lien)
        os.symlink(os.path.join(paquet.dossier, "actuel"), lien)
    elif not present and os.path.lexists(lien):
        os.remove(lien) if os.path.islink(lien) else shutil.rmtree(lien)
    return present


def lancer() -> int:
    journal.ouvrir("service")
    for programme in ("dnsmasq", "lighttpd"):
        if not sysexec.disponible(programme):
            _log.error("%s introuvable : le service ne peut pas démarrer", programme)
            return 1
    Service().tourner()
    return 0


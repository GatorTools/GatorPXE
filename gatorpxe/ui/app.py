"""L'interface de réglage (§11 de l'analyse) : `sudo gatorpxe`.

L'accueil montre l'état d'un coup d'œil — le service, le réseau, le menu tel
que les postes le voient, les derniers postes — et se met à jour seul. Chaque
réglage a son écran ; l'interface écrit les réglages, puis demande au service
de les relire. Elle ne touche jamais à dnsmasq ni à lighttpd : fermée ou
plantée, elle ne change rien pour les postes (P4).

Ce que voit le service vient de son état (module etat) ; les derniers postes,
du journal HTTP (module postes).
"""

from __future__ import annotations

import logging
import os

from .. import VERSION, config, dnsmasq, etat, images, langue, postes, reseau, sysexec
from ..chemins import PORT_HTTP
from ..langue import t
from .model import (
    AVERTISSEMENT, DETAIL, ECHEC, FORT, GRISE, NORMAL, OK,
    Champ, Element, Formulaire, Ligne, Liste, Page,
)

_log = logging.getLogger("gatorpxe.ui")

COLONNE = 18  # largeur des libellés de l'état
RAFRAICHIR = 2.0  # secondes entre deux mises à jour de l'accueil
PORTS = ("67", "69", "4011", str(PORT_HTTP))


# ----------------------------------------------------------- barres du bas ---

def _touches_liste():
    return [("↑↓", t("Choisir")), (t("Entrée"), t("Valider")), (t("Échap"), t("Retour"))]


def _touches_accueil():
    return [("↑↓", t("Choisir")), (t("Entrée"), t("Valider")), (t("Échap"), t("Quitter"))]


def _touches_formulaire():
    return [(t("Entrée"), t("Champ suivant, puis valider")), (t("Échap"), t("Retour"))]


def _touches_lire():
    return [("↑↓", t("Faire défiler")), (t("Entrée"), t("Revenir"))]


# ------------------------------------------------------------------ textes ---

def raison(code: str) -> str:
    """La raison d'un fichier écarté, dans la langue de l'interface."""
    if code == images.NON_RECONNU:
        return t("format non reconnu")
    if code == images.ILLISIBLE:
        return t("illisible par le serveur web : droits de lecture manquants")
    if code == images.EN_COPIE:
        return t("en cours de copie")
    if code == images.EN_PREPARATION:
        return t("ISO Windows en préparation")
    return code


def type_renvoi(code: str) -> str:
    if code == config.WDS:
        return "WDS"
    if code == config.IPXE:
        return "iPXE / HTTP"
    return t("PXE générique")


def plateforme(code: str) -> str:
    return "UEFI" if code == "efi" else "BIOS" if code == "pcbios" else "?"


def _etat_ligne(libelle: str, texte: str, style: str = NORMAL) -> Ligne:
    return Ligne([(f"{libelle:<{COLONNE}}", DETAIL), (texte, style)])


# ------------------------------------------------------------- application ---

class Application:
    def __init__(self, ecran):
        self.ecran = ecran
        self.reglages = config.lire()
        langue.choisir(self.reglages.langue)
        ecran.changer_langue = self.changer_langue

    def changer_langue(self, code: str) -> None:
        """F2 : l'interface, et le menu des postes, changent de langue."""
        langue.choisir(code)
        self.reglages.langue = code
        self._enregistrer()

    def _enregistrer(self) -> str:
        """Écrit les réglages et demande au service de les relire ; rend un
        message à afficher, vide si tout va bien."""
        try:
            config.ecrire(self.reglages)
        except OSError as erreur:
            _log.warning("réglages non enregistrés : %s", erreur)
            return t("Réglages non enregistrés : {erreur}", erreur=erreur)
        if not service_actif():
            return t("Réglages enregistrés. Le service est arrêté : ils serviront à son démarrage.")
        resultat = sysexec.executer(["systemctl", "reload", "gatorpxe"])
        if not resultat.ok:
            return t("Réglages enregistrés, mais le service ne les a pas relus.")
        return ""

    def _page(self, titre: str, entete=None, touches=None, operation: str = "", etapes=None,
              etape: int = -1) -> Page:
        mode = t("Service actif") if service_actif() else t("Service arrêté")
        return Page(titre, entete or [], touches or _touches_liste(), operation, etapes or [], etape, mode)

    def _message(self, titre: str, lignes: list[Ligne]) -> None:
        self.ecran.afficher(lambda: (self._page(titre, touches=_touches_lire()), lignes))

    # -------------------------------------------------------------- accueil ---

    def lancer(self) -> None:
        self.ecran.presenter([
            (f"GatorPXE  {VERSION}", FORT),
            (t("Serveur de démarrage réseau"), NORMAL),
            (t("Un projet GatorTools"), OK),
        ])
        self.accueil()

    def accueil(self) -> None:
        def construire():
            entete = self._lignes_etat()
            liste = Liste("", [
                Element(t("Menu de démarrage"), "menu", detail=t("Ce que voient les postes, et les fichiers écartés")),
                Element(t("Derniers postes"), "postes", detail=t("Qui a démarré, quand, sur quoi")),
                Element(t("Réseau et DHCP"), "reseau", detail=t("Proxy DHCP, carte réseau")),
                Element(t("Dossier des images"), "dossier", detail=self.reglages.dossier_images),
                Element("CloneGator", "clonegator",
                        detail=t("Au menu") if self.reglages.clonegator else t("Retiré du menu")),
                Element(t("Renvois"), "renvois", detail=t("Vers d'autres serveurs de démarrage")),
                Element(t("Délai et entrée par défaut"), "delai",
                        detail=t("{n} s, puis {entree}", n=self.reglages.delai,
                                 entree=self._nom_entree(self.reglages.entree_defaut))),
                Element(t("Quitter"), "quitter"),
            ])
            return self._page("", entete, _touches_accueil()), liste

        actions = {
            "menu": self.voir_menu, "postes": self.voir_postes, "reseau": self.regler_reseau,
            "dossier": self.regler_dossier, "clonegator": self.regler_clonegator,
            "renvois": self.regler_renvois, "delai": self.regler_delai,
        }
        while True:
            choix = self.ecran.choisir(construire, intervalle=RAFRAICHIR, attente=t("Lecture de l'état…"))
            if choix in (None, "quitter"):
                return
            actions[choix]()

    def _lignes_etat(self) -> list[Ligne]:
        vu = etat.lire()
        lignes = []
        if not service_actif():
            lignes.append(_etat_ligne(t("Service"), t("arrêté : les postes ne sont pas servis"), ECHEC))
        elif vu is None:
            lignes.append(_etat_ligne(t("Service"), t("démarrage en cours…"), AVERTISSEMENT))
        else:
            lignes.append(_etat_ligne(t("Service"), t("actif"), OK))
        if vu:
            lignes.append(self._ligne_reseau(vu))
            lignes.append(self._ligne_menu(vu))
            if vu.get("ecartes"):
                lignes.append(_etat_ligne("", t("{n} fichier(s) écarté(s) : voir le menu de démarrage",
                                                 n=len(vu["ecartes"])), AVERTISSEMENT))
        pare_feu = verifier_pare_feu()
        if pare_feu:
            lignes.append(_etat_ligne(t("Pare-feu"), pare_feu, AVERTISSEMENT))
        derniers = postes.lire((vu or {}).get("windows"), nombre=3)
        lignes.append(_etat_ligne(t("Derniers postes"), "" if derniers else t("aucun pour l'instant"), GRISE))
        for poste in derniers:
            lignes.append(Ligne([(" " * COLONNE, NORMAL), (self._texte_poste(poste), NORMAL)]))
        return lignes

    def _ligne_reseau(self, vu: dict) -> Ligne:
        attente, carte = vu.get("attente"), vu.get("carte") or "?"
        if attente == etat.SANS_CARTE:
            return _etat_ligne(t("Réseau"), t("aucune carte réseau : choisissez-en une"), ECHEC)
        if attente == etat.SANS_ADRESSE:
            return _etat_ligne(t("Réseau"), t("la carte {carte} n'a pas d'adresse IPv4", carte=carte), ECHEC)
        if attente == etat.SANS_IPXE:
            return _etat_ligne(t("Réseau"), t("iPXE pas encore téléchargé : accès à Internet ?"), ECHEC)
        if not (vu.get("dnsmasq") and vu.get("lighttpd")):
            return _etat_ligne(t("Réseau"), t("dnsmasq ou lighttpd arrêté : relance en cours"), AVERTISSEMENT)
        if vu.get("proxy_dhcp"):
            return _etat_ligne(t("Réseau"), t("{carte}, {adresse} ; proxy DHCP actif",
                                              carte=carte, adresse=vu.get("adresse")), OK)
        return _etat_ligne(t("Réseau"), t("{carte}, {adresse} ; proxy DHCP coupé : votre DHCP désigne le serveur",
                                          carte=carte, adresse=vu.get("adresse")), NORMAL)

    def _ligne_menu(self, vu: dict) -> Ligne:
        morceaux = []
        if self.reglages.clonegator:
            version = vu.get("clonegator")
            morceaux.append(f"CloneGator {version}" if version else t("CloneGator (téléchargement…)"))
        morceaux.append(t("{n} image(s)", n=len(vu.get("images", []))))
        morceaux.append(t("{n} renvoi(s)", n=len(self.reglages.renvois)))
        if vu.get("dossier_introuvable"):
            return _etat_ligne(t("Menu"), t("dossier d'images introuvable : {dossier}",
                                            dossier=vu.get("dossier_images")), AVERTISSEMENT)
        return _etat_ligne(t("Menu"), ", ".join(morceaux), NORMAL)

    def _texte_poste(self, poste: postes.Poste) -> str:
        if poste.choix == postes.CLONEGATOR:
            choix = "CloneGator"
        elif poste.choix == postes.IMAGE:
            choix = poste.image
        else:
            choix = t("disque local, ou un renvoi")
        return f"{poste.heure:%Y-%m-%d %H:%M}  {poste.mac}  {poste.adresse:<15}  {plateforme(poste.plateforme):<4}  {choix}"

    def _nom_entree(self, code: str) -> str:
        return "CloneGator" if code == config.CLONEGATOR else t("disque local")

    # ------------------------------------------------------ vues détaillées ---

    def voir_menu(self) -> None:
        def construire():
            vu = etat.lire() or {}
            lignes = []
            if self.reglages.clonegator:
                lignes.append(Ligne([("  CloneGator", FORT), (f"   {vu.get('clonegator') or t('pas encore téléchargé')}",
                                                            DETAIL)]))
            for image in vu.get("images", []):
                marques = [] if image.get("reseau", True) else [t("incompatible réseau")]
                if not image.get("secure_boot", True):
                    marques.append(t("sans Secure Boot"))
                # Les marques avant le chemin : sur un écran étroit, c'est le chemin qui est coupé.
                ligne = Ligne([(f"  {image['nom']} ({image['type']})", FORT)])
                if marques:
                    ligne.morceaux.append((f"   {', '.join(marques)}", AVERTISSEMENT))
                ligne.morceaux.append((f"   {image['chemin']}", DETAIL))
                lignes.append(ligne)
            for renvoi in self.reglages.renvois:
                ligne = Ligne([(f"  {renvoi.nom}", FORT)])
                if renvoi.type == config.WDS and vu.get("ipxe") in config.IPXE_SANS_WDS_UEFI:
                    ligne.morceaux.append(("   " + t("pas en UEFI pour l'instant"), AVERTISSEMENT))
                ligne.morceaux.append((f"   {type_renvoi(renvoi.type)}, {renvoi.adresse}", DETAIL))
                lignes.append(ligne)
            lignes.append(Ligne.de(f"  {t('Démarrer sur le disque local')}", FORT))
            if vu.get("dossier_introuvable"):
                lignes += [Ligne.de(""), Ligne.de(t("Dossier d'images introuvable : {dossier}",
                                                    dossier=vu.get("dossier_images")), AVERTISSEMENT)]
            if vu.get("ecartes"):
                lignes += [Ligne.de(""), Ligne.de(t("Fichiers écartés"), FORT)]
                for ecarte in vu["ecartes"]:
                    lignes.append(Ligne([(f"  {ecarte['chemin']}", NORMAL),
                                         (f"   {raison(ecarte['raison'])}", AVERTISSEMENT)]))
            entete = [Ligne.de(t("Dans l'ordre où les postes le voient. Au bout de {n} s : {entree}.",
                                 n=self.reglages.delai, entree=self._nom_entree(self.reglages.entree_defaut)),
                               DETAIL)]
            return self._page(t("Menu de démarrage"), entete, _touches_lire()), lignes

        self.ecran.afficher(construire)

    def voir_postes(self) -> None:
        def construire():
            vu = etat.lire() or {}
            derniers = postes.lire(vu.get("windows"), nombre=50)
            lignes = [Ligne.de("  " + self._texte_poste(p)) for p in derniers] or [
                Ligne.de(t("Aucun poste n'a encore démarré sur ce serveur."), GRISE)]
            entete = [Ligne.de(t("Heure, adresse matérielle, adresse IP, BIOS ou UEFI, entrée choisie."), DETAIL)]
            return self._page(t("Derniers postes"), entete, _touches_lire()), lignes

        self.ecran.afficher(construire)

    # --------------------------------------------------------------- réglages ---

    def _choisir(self, titre: str, elements, explication: str = "", placer=None, etapes=None, etape=-1):
        def construire():
            liste = Liste("", elements(), explication=explication)
            if placer is not None:
                liste.placer(placer)
            operation, noms = etapes() if etapes else ("", [])
            return self._page(titre, operation=operation, etapes=noms, etape=etape), liste
        return self.ecran.choisir(construire)

    def _appliquer(self) -> None:
        message = self._enregistrer()
        if message:
            self._message(t("Réglages"), [Ligne.de(message, AVERTISSEMENT)])

    def regler_reseau(self) -> None:
        while True:
            def elements():
                carte = self.reglages.carte or t("automatique ({carte})", carte=reseau.carte_principale() or "?")
                return [
                    Element(t("Proxy DHCP"), "proxy",
                            detail=t("actif") if self.reglages.proxy_dhcp else t("coupé")),
                    Element(t("Carte réseau"), "carte", detail=carte),
                    Element(t("Réglages pour votre DHCP"), "dhcp",
                            detail=t("À saisir quand le proxy DHCP est coupé")),
                ]
            choix = self._choisir(t("Réseau et DHCP"), elements, t(
                "Le proxy DHCP ne répond qu'aux postes qui démarrent par le réseau."))
            if choix is None:
                return
            if choix == "proxy":
                self.regler_proxy()
            elif choix == "carte":
                self.regler_carte()
            else:
                self.voir_reglages_dhcp()

    def regler_proxy(self) -> None:
        def elements():
            return [Element(t("Actif"), True, detail=t("Rien à régler sur votre DHCP")),
                    Element(t("Coupé"), False, detail=t("Votre DHCP désigne le serveur et ses fichiers"))]
        choix = self._choisir(t("Proxy DHCP"), elements, placer=self.reglages.proxy_dhcp)
        if choix is None or choix == self.reglages.proxy_dhcp:
            return
        self.reglages.proxy_dhcp = choix
        self._appliquer()
        if not choix:
            self.voir_reglages_dhcp()

    def regler_carte(self) -> None:
        def elements():
            principale = reseau.carte_principale()
            liste = [Element(t("Automatique"), "", detail=t("la carte principale ({carte})", carte=principale or "?"))]
            for nom in cartes():
                adresse = reseau.adresse(nom)
                liste.append(Element(nom, nom, detail=str(adresse) if adresse else t("sans adresse IPv4")))
            return liste
        choix = self._choisir(t("Carte réseau"), elements, t(
            "Le proxy DHCP et le TFTP ne répondent que sur cette carte."), placer=self.reglages.carte)
        if choix is None or choix == self.reglages.carte:
            return
        self.reglages.carte = choix
        self._appliquer()

    def voir_reglages_dhcp(self) -> None:
        def construire():
            vu = etat.lire() or {}
            serveur = vu.get("adresse") or t("(adresse du serveur)")
            lignes = [
                _etat_ligne(t("Serveur"), serveur, FORT),
                _etat_ligne("", t("option 66, ou « next-server »"), DETAIL),
                _etat_ligne(t("Fichier UEFI"), dnsmasq.FICHIER_UEFI, FORT),
                _etat_ligne(t("Fichier BIOS"), dnsmasq.FICHIER_BIOS, FORT),
                _etat_ligne("", t("option 67, selon l'architecture du poste (option 93 : 7 ou 9 en UEFI, 0 en BIOS)"),
                            DETAIL),
                Ligne.de(""),
                Ligne.de(t("En BIOS seulement, pour éviter une boucle :"), FORT),
                Ligne.de(t("si la classe utilisateur (option 77) vaut « iPXE », le fichier devient"), NORMAL),
                Ligne.de(f"  http://{serveur}:{PORT_HTTP}/menu.ipxe", FORT),
                Ligne.de(t("En UEFI, rien de plus : iPXE trouve le menu de lui-même."), DETAIL),
            ]
            if self.reglages.proxy_dhcp:
                entete = [Ligne.de(t("Le proxy DHCP est actif : rien à régler dans votre service DHCP."), NORMAL),
                          Ligne.de(t("Si vous le désactivez, configurez-le ainsi (options 66 et 67) :"), NORMAL)]
            else:
                entete = [Ligne.de(t("Le proxy DHCP est désactivé. Si ce n'est pas déjà fait, configurez votre "
                                     "service DHCP (options 66 et 67) :"), FORT)]
                if vu.get("adresse_dynamique"):
                    # Une réservation DHCP ne se voit pas d'ici : « si ce n'est pas déjà fait ».
                    lignes += [
                        Ligne.de(""),
                        Ligne.de(t("Cette machine reçoit son adresse de votre service DHCP, et le proxy DHCP est "
                                   "désactivé :"), AVERTISSEMENT),
                        Ligne.de(t("si ce n'est pas déjà fait, réservez cette adresse dans votre service DHCP, "
                                   "ou donnez-lui une adresse fixe."), AVERTISSEMENT),
                    ]
            return self._page(t("Réglages pour votre DHCP"), entete, _touches_lire()), lignes
        self.ecran.afficher(construire)

    def regler_dossier(self) -> None:
        precedent = self.reglages.dossier_images
        while True:
            def construire(valeur=precedent):
                formulaire = Formulaire("", [Champ("dossier", t("Dossier"), valeur)], explication=t(
                    "Déposer une image ici suffit : elle paraît au menu. Un sous-dossier donne un sous-menu."))
                return self._page(t("Dossier des images"), touches=_touches_formulaire()), formulaire
            valeurs = self.ecran.saisir(construire)
            if valeurs is None:
                return
            dossier = valeurs["dossier"].strip().rstrip("/") or "/"
            if not os.path.isabs(dossier) or not os.path.isdir(dossier):
                self._message(t("Dossier des images"), [Ligne.de(t("Dossier introuvable : {dossier}",
                                                                   dossier=dossier), ECHEC)])
                precedent = dossier
                continue
            if dossier != self.reglages.dossier_images:
                self.reglages.dossier_images = dossier
                self._appliquer()
            return

    def regler_clonegator(self) -> None:
        def elements():
            version = (etat.lire() or {}).get("clonegator") or t("pas encore téléchargé")
            return [Element(t("Au menu"), True, detail=t("Tenu à jour chaque jour ; version {v}", v=version)),
                    Element(t("Retiré du menu"), False, detail=t("Plus téléchargé"))]
        choix = self._choisir("CloneGator", elements, placer=self.reglages.clonegator)
        if choix is None or choix == self.reglages.clonegator:
            return
        self.reglages.clonegator = choix
        if not choix and self.reglages.entree_defaut == config.CLONEGATOR:
            self.reglages.entree_defaut = config.DISQUE_LOCAL
        self._appliquer()

    def regler_delai(self) -> None:
        while True:
            def elements():
                return [Element(t("Délai"), "delai", detail=t("{n} s", n=self.reglages.delai)),
                        Element(t("Entrée par défaut"), "entree",
                                detail=self._nom_entree(self.reglages.entree_defaut))]
            choix = self._choisir(t("Délai et entrée par défaut"), elements, t(
                "Sans choix de l'opérateur, le menu démarre l'entrée par défaut au bout du délai."))
            if choix is None:
                return
            if choix == "delai":
                self._saisir_delai()
            else:
                self._choisir_entree()

    def _saisir_delai(self) -> None:
        def construire():
            formulaire = Formulaire("", [Champ("delai", t("Secondes"), str(self.reglages.delai))],
                                    explication=t("0 : le menu attend un choix."))
            return self._page(t("Délai"), touches=_touches_formulaire()), formulaire
        while True:
            valeurs = self.ecran.saisir(construire)
            if valeurs is None:
                return
            texte = valeurs["delai"].strip()
            if texte.isdigit() and int(texte) <= 3600:
                if int(texte) != self.reglages.delai:
                    self.reglages.delai = int(texte)
                    self._appliquer()
                return
            self._message(t("Délai"), [Ligne.de(t("Un nombre de secondes, de 0 à 3600."), ECHEC)])

    def _choisir_entree(self) -> None:
        def elements():
            return [Element(t("Disque local"), config.DISQUE_LOCAL, detail=t("Recommandé")),
                    Element("CloneGator", config.CLONEGATOR, actif=self.reglages.clonegator,
                            motif="" if self.reglages.clonegator else t("retiré du menu"))]
        choix = self._choisir(t("Entrée par défaut"), elements, placer=self.reglages.entree_defaut)
        if choix is None or choix == self.reglages.entree_defaut:
            return
        self.reglages.entree_defaut = choix
        self._appliquer()

    # ---------------------------------------------------------------- renvois ---

    def regler_renvois(self) -> None:
        while True:
            def elements():
                liste = [Element(r.nom, i, detail=f"{type_renvoi(r.type)}, {r.adresse}")
                         for i, r in enumerate(self.reglages.renvois)]
                return liste + [Element(t("Ajouter un renvoi"), "ajouter")]
            choix = self._choisir(t("Renvois"), elements, t(
                "Des entrées du menu vers d'autres serveurs de démarrage, dans cet ordre."))
            if choix is None:
                return
            if choix == "ajouter":
                self.editer_renvoi(None)
            else:
                self.agir_sur_renvoi(choix)

    def agir_sur_renvoi(self, rang: int) -> None:
        renvoi = self.reglages.renvois[rang]
        derniers = len(self.reglages.renvois) - 1

        def elements():
            return [Element(t("Modifier"), "modifier"),
                    Element(t("Monter"), "monter", actif=rang > 0),
                    Element(t("Descendre"), "descendre", actif=rang < derniers),
                    Element(t("Retirer"), "retirer")]
        choix = self._choisir(renvoi.nom, elements, f"{type_renvoi(renvoi.type)}, {renvoi.adresse}")
        renvois = self.reglages.renvois
        if choix == "modifier":
            self.editer_renvoi(rang)
            return
        if choix == "monter":
            renvois[rang - 1], renvois[rang] = renvois[rang], renvois[rang - 1]
        elif choix == "descendre":
            renvois[rang + 1], renvois[rang] = renvois[rang], renvois[rang + 1]
        elif choix == "retirer":
            reponse = self.ecran.confirmer(lambda: (
                self._page(t("Retirer « {nom} » du menu ?", nom=renvoi.nom)),
                [("annuler", t("Annuler")), ("retirer", t("Retirer"))]))
            if reponse != "retirer":
                return
            del renvois[rang]
        else:
            return
        self._appliquer()

    def editer_renvoi(self, rang: int | None) -> None:
        ancien = self.reglages.renvois[rang] if rang is not None else None

        def etapes():
            return t("Renvoi"), [t("Type"), t("Adresse")]

        def elements():
            return [Element("WDS", config.WDS, detail=t("Windows Deployment Services, ou MECM/SCCM")),
                    Element("iPXE / HTTP", config.IPXE, detail=t("Un autre serveur iPXE, FOG, netboot.xyz…")),
                    Element(t("PXE générique"), config.PXE, detail=t("Tout autre serveur : pxelinux, GRUB…"))]
        type_ = self._choisir(t("Quel type de serveur ?"), elements, placer=ancien.type if ancien else None,
                              etapes=etapes, etape=0)
        if type_ is None:
            return

        def champs(valeurs):
            liste = [Champ("nom", t("Nom au menu"), valeurs.get("nom", "")),
                     Champ("adresse", t("Adresse du script") if type_ == config.IPXE else t("Serveur"),
                           valeurs.get("adresse", ""))]
            if type_ == config.PXE:
                liste += [Champ("fichier_bios", t("Fichier BIOS"), valeurs.get("fichier_bios", "")),
                          Champ("fichier_uefi", t("Fichier UEFI"), valeurs.get("fichier_uefi", ""))]
            return liste

        explications = {
            config.WDS: t("L'adresse du serveur WDS : GatorPXE connaît les fichiers à demander."),
            config.IPXE: t("L'adresse du script de démarrage, en http:// ou https://."),
            config.PXE: t("Le serveur, et le fichier à charger en BIOS et en UEFI ; un seul suffit."),
        }
        valeurs = {} if ancien is None or ancien.type != type_ else {
            "nom": ancien.nom, "adresse": ancien.adresse,
            "fichier_bios": ancien.fichier_bios, "fichier_uefi": ancien.fichier_uefi}
        while True:
            def construire(valeurs=valeurs):
                operation, noms = etapes()
                formulaire = Formulaire("", champs(valeurs), explication=explications[type_])
                return (self._page(type_renvoi(type_), touches=_touches_formulaire(), operation=operation,
                                   etapes=noms, etape=1), formulaire)
            saisies = self.ecran.saisir(construire)
            if saisies is None:
                return
            valeurs = {cle: valeur.strip() for cle, valeur in saisies.items()}
            erreur = verifier_renvoi(type_, valeurs)
            if erreur:
                self._message(type_renvoi(type_), [Ligne.de(erreur, ECHEC)])
                continue
            renvoi = config.Renvoi(valeurs["nom"], type_, valeurs["adresse"],
                                   valeurs.get("fichier_bios", ""), valeurs.get("fichier_uefi", ""))
            if rang is None:
                self.reglages.renvois.append(renvoi)
            else:
                self.reglages.renvois[rang] = renvoi
            self._appliquer()
            return


# ------------------------------------------------------------ vérifications ---

def verifier_renvoi(type_: str, valeurs: dict[str, str]) -> str:
    """Rend l'erreur à montrer, ou une chaîne vide si le renvoi est complet."""
    if not valeurs.get("nom"):
        return t("Donnez un nom : c'est lui qui paraît au menu.")
    adresse = valeurs.get("adresse", "")
    if not adresse or " " in adresse:
        return t("L'adresse est vide ou contient une espace.")
    if type_ == config.IPXE and not adresse.startswith(("http://", "https://")):
        return t("L'adresse du script commence par http:// ou https://.")
    if type_ == config.PXE and not (valeurs.get("fichier_bios") or valeurs.get("fichier_uefi")):
        return t("Donnez au moins un fichier, BIOS ou UEFI.")
    return ""


def service_actif() -> bool:
    return sysexec.executer(["systemctl", "is-active", "--quiet", "gatorpxe"],
                            echec_prevu=True, discret=True).ok


def cartes() -> list[str]:
    """Les cartes réseau de la machine, sans la boucle locale."""
    return [nom for nom in sysexec.lister("/sys/class/net") if nom != "lo"]


def verifier_pare_feu() -> str:
    """Un avertissement si ufw est actif sans laisser passer les ports de
    GatorPXE (§9) ; vide sinon."""
    if not sysexec.disponible("ufw"):
        return ""
    resultat = sysexec.executer(["ufw", "status"], echec_prevu=True, discret=True)
    if not resultat.ok or "Status: active" not in resultat.sortie:
        return ""
    manquants = [port for port in PORTS if port not in resultat.sortie]
    if not manquants:
        return ""
    return t("ufw actif : ouvrez les ports {ports} (67, 69 et 4011 en UDP, {http} en TCP)",
             ports=", ".join(manquants), http=PORT_HTTP)


def demarrer() -> int:
    """Ouvre l'interface sur le terminal courant."""
    import curses
    import locale

    from .ecran import Ecran

    locale.setlocale(locale.LC_ALL, "")
    os.environ.setdefault("ESCDELAY", "25")  # Échap répond tout de suite
    console = sysexec.sur_console_virtuelle()

    def principal(fenetre):
        Application(Ecran(fenetre, console_physique=console)).lancer()

    try:
        curses.wrapper(principal)
    except KeyboardInterrupt:
        pass
    return 0


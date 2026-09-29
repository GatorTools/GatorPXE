"""Unique point de passage vers le système (§15 de l'analyse).

Aucun autre module du projet n'appelle `subprocess` ni ne lit `/sys` ou
`/proc` directement. Tout passe par ici, ce qui donne trois choses :

  - un délai d'attente sur *chaque* commande : rien ne fige le service ;
  - le journal verbatim des commandes réellement lancées ;
  - un point unique à remplacer pour faire tourner le reste du logiciel
    ailleurs que sur un vrai serveur.

Repris de CloneGator (`clonegator/sysexec.py`), sans ce qui touche aux disques.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass

_log = logging.getLogger("gatorpxe.sysexec")

DELAI_DEFAUT = 30.0


@dataclass
class Resultat:
    """Ce qu'une commande externe a produit. N'est jamais une exception."""

    argv: list[str]
    code: int
    sortie: str
    erreur: str
    duree: float
    expire: bool = False

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.expire

    @property
    def commande(self) -> str:
        return " ".join(self.argv)

    def __str__(self) -> str:
        if self.expire:
            etat = f"EXPIRE apres {self.duree:.1f}s"
        else:
            etat = f"code={self.code} en {self.duree:.2f}s"
        return f"{self.commande} -> {etat}"


class Programme:
    """Un programme qui tourne en permanence : dnsmasq, lighttpd.

    Le service le lance, vérifie qu'il vit encore, et l'arrête. Ses sorties vont
    dans un fichier du journal : un tube non lu finirait par le figer.
    """

    def __init__(self, argv: list[str], sorties: str):
        self.argv = list(argv)
        self.sorties = sorties
        with open(sorties, "ab") as fichier:
            self._popen = subprocess.Popen(
                self.argv, stdin=subprocess.DEVNULL, stdout=fichier, stderr=fichier,
            )
        _log.info("lancé (pid %d) : %s", self._popen.pid, self.commande)

    @property
    def commande(self) -> str:
        return " ".join(self.argv)

    def vivant(self) -> bool:
        return self._popen.poll() is None

    @property
    def code(self) -> int | None:
        return self._popen.poll()

    def arreter(self, delai: float = 5.0) -> None:
        """SIGTERM, puis SIGKILL s'il ne s'arrête pas dans le délai."""
        if self._popen.poll() is not None:
            return
        self._popen.terminate()
        try:
            self._popen.wait(timeout=delai)
        except subprocess.TimeoutExpired:
            _log.warning("tué : %s", self.commande)
            self._popen.kill()
            self._popen.wait(timeout=delai)
        _log.info("arrêté : %s", self.commande)


def disponible(programme: str) -> bool:
    """Le programme est-il installé ?"""
    return shutil.which(programme) is not None


def executer(
    argv: list[str],
    delai: float = DELAI_DEFAUT,
    entree: str | None = None,
    dossier: str | None = None,
    echec_prevu: bool = False,
    discret: bool = False,
) -> Resultat:
    """Lance une commande et rapporte ce qu'elle a fait.

    Ne lève jamais d'exception sur un code de retour non nul : c'est à
    l'appelant de décider si l'échec est grave. Un dépassement de délai tue le
    processus et revient avec `expire=True`.

    `discret` : une commande relancée à chaque tour du service n'est journalisée
    que si elle échoue.
    """
    debut = time.monotonic()
    try:
        fin = subprocess.run(
            argv,
            input=entree,
            cwd=dossier,
            capture_output=True,
            text=True,
            timeout=delai,
            check=False,
        )
    except subprocess.TimeoutExpired as expiration:
        resultat = Resultat(
            argv=list(argv),
            code=-1,
            sortie=_texte(expiration.stdout),
            erreur=_texte(expiration.stderr),
            duree=time.monotonic() - debut,
            expire=True,
        )
        _log.warning("%s", resultat)
        return resultat
    except FileNotFoundError:
        resultat = Resultat(
            argv=list(argv),
            code=127,
            sortie="",
            erreur=f"{argv[0]} : introuvable",
            duree=time.monotonic() - debut,
        )
        _log.warning("%s", resultat)
        return resultat

    resultat = Resultat(
        argv=list(argv),
        code=fin.returncode,
        sortie=fin.stdout or "",
        erreur=fin.stderr or "",
        duree=time.monotonic() - debut,
    )

    if resultat.ok:
        if not discret:
            _log.debug("%s", resultat)
    elif echec_prevu:
        # Un échec qui fait partie du fonctionnement normal : au journal, sans alerte.
        _log.info("%s | %s", resultat, resultat.erreur.strip()[:200])
    else:
        _log.warning("%s | %s", resultat, resultat.erreur.strip()[:200])

    return resultat


def lister(repertoire: str) -> list[str]:
    """Noms des entrées d'un répertoire système, triés ; vide s'il n'existe pas."""
    try:
        return sorted(os.listdir(repertoire))
    except OSError as erreur:
        _log.debug("%s illisible (%s)", repertoire, erreur)
        return []


def lire(chemin: str) -> str | None:
    """Le contenu d'un petit fichier système (un attribut de /sys), sans le
    saut de ligne final ; None s'il est illisible."""
    try:
        with open(chemin, encoding="utf-8") as fichier:
            return fichier.read().strip()
    except OSError:
        return None


def sur_console_virtuelle() -> bool:
    """Le programme tourne-t-il sur une console texte de la machine (tty1…),
    et pas dans une session SSH ?

    On ne peut pas se fier au seul terminal du programme : `sudo`, réglé avec
    `use_pty` (le défaut d'Ubuntu 24.04), intercale un pseudo-terminal. On
    remonte donc les processus parents : si l'un d'eux tient une console
    virtuelle (majeur 4, mineur 1 à 63), on est sur l'écran de la machine."""
    pid = os.getpid()
    for _ in range(8):
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as fichier:
                champs = fichier.read().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            return False
        # Après la commande entre parenthèses : état, parent, groupe, session, terminal.
        parent, terminal = int(champs[1]), int(champs[4])
        majeur = (terminal >> 8) & 0xFFF
        mineur = (terminal & 0xFF) | ((terminal >> 12) & 0xFFF00)
        if majeur == 4 and 1 <= mineur <= 63:
            return True
        if parent <= 1:
            return False
        pid = parent
    return False


def _texte(brut: bytes | str | None) -> str:
    if brut is None:
        return ""
    if isinstance(brut, bytes):
        return brut.decode("utf-8", errors="replace")
    return brut

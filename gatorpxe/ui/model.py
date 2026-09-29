"""Ce que l'interface affiche et comment elle réagit aux touches, sans curses.

Repris de CloneGator. Tout ce qui se décide ici — où va le curseur, ce qu'on a
tapé dans un champ — est une structure de données ordinaire : on peut la
tester, et l'imprimer en texte brut, sans jamais ouvrir un écran. `ecran.py`
ne fait que dessiner ces structures et traduire les touches.

Les touches arrivent déjà traduites : « haut », « bas », « entree », « espace »,
« echap », « effacer », « tab », un chiffre « 1 » à « 9 », ou un caractère.

Un écran peut être reconstruit à tout moment, dans une autre langue (F2) :
`reprendre` recopie dans la nouvelle structure ce que l'opérateur avait fait
dans l'ancienne — curseur, texte saisi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..langue import t

# Styles d'un morceau de ligne ; ecran.py leur donne couleur et graisse. Une
# couleur n'a qu'un sens : vert, le choix et la réussite ; rouge, l'échec et
# l'effacement ; gris, ce qui n'est pas disponible.
NORMAL = "normal"
FORT = "fort"
GRISE = "grise"
OK = "ok"
ECHEC = "echec"
AVERTISSEMENT = "avertissement"
DETAIL = "detail"  # le second plan : détails, explications
AIDE = DETAIL

# Ce qu'une touche provoque dans une liste ou un formulaire.
VALIDER = "valider"
RETOUR = "retour"

# Symboles, tous présents dans la police de la console (Uni2-Fixed16).
CURSEUR = "▶"
CROIX = "✗"
POINT = "●"


@dataclass
class Ligne:
    """Une ligne d'écran : des morceaux de texte, chacun avec son style."""

    morceaux: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def de(cls, texte: str = "", style: str = NORMAL) -> "Ligne":
        return cls([(texte, style)])

    def texte(self) -> str:
        return "".join(t for t, _ in self.morceaux)


def replier(ligne: Ligne, largeur: int) -> list[Ligne]:
    """Replie une ligne trop longue en plusieurs, mot à mot, styles gardés. Les
    lignes suivantes sont alignées sur le premier mot de la première (après un
    « ! » ou un retrait)."""
    if largeur <= 0 or len(ligne.texte()) <= largeur:
        return [ligne]
    texte = ligne.texte()
    retrait = next((i for i, c in enumerate(texte) if c.isalnum()), 0)
    # Mots avec leur style ; les espaces restent attachés au mot qui les précède.
    mots: list[tuple[str, str]] = []
    for morceau, style in ligne.morceaux:
        courant = ""
        for car in morceau:
            courant += car
            if car == " ":
                mots.append((courant, style))
                courant = ""
        if courant:
            mots.append((courant, style))
    lignes = [Ligne()]
    longueur = 0
    for mot, style in mots:
        if longueur + len(mot.rstrip()) > largeur and longueur > retrait:
            lignes.append(Ligne([(" " * retrait, NORMAL)]))
            longueur = retrait
        lignes[-1].morceaux.append((mot, style))
        longueur += len(mot)
    return lignes


@dataclass
class Element:
    """Un choix d'une liste. Un élément inactif reste visible, grisé, avec son
    motif : on comprend ainsi pourquoi il manque."""

    libelle: str
    valeur: object = None
    actif: bool = True
    motif: str = ""
    detail: str = ""  # ajouté en second plan, après le libellé
    alerte: bool = False  # un « ! » devant le libellé : il y a quelque chose à voir


@dataclass
class Liste:
    titre: str
    elements: list[Element]
    explication: str = ""
    curseur: int = 0
    message: str = ""  # une remarque passagère

    def __post_init__(self):
        actifs = self._actifs()
        if actifs and self.curseur not in actifs:
            self.curseur = actifs[0]

    def _actifs(self) -> list[int]:
        return [i for i, e in enumerate(self.elements) if e.actif]

    def placer(self, valeur) -> None:
        """Présélectionne l'élément qui porte cette valeur, s'il est actif."""
        for i, element in enumerate(self.elements):
            if element.valeur == valeur and element.actif:
                self.curseur = i
                return

    def reprendre(self, ancienne: "Liste") -> None:
        """Garde le curseur de la version précédente de cette liste : l'écran
        vient d'être reconstruit."""
        if len(ancienne.elements) == len(self.elements) and ancienne.curseur in self._actifs():
            self.curseur = ancienne.curseur
        self.message = ancienne.message

    def touche(self, touche: str) -> str | None:
        """Applique une touche ; rend VALIDER, RETOUR ou None."""
        self.message = ""
        actifs = self._actifs()
        if touche == "echap":
            return RETOUR
        if not actifs:
            return None
        if touche in ("haut", "bas"):
            rang = actifs.index(self.curseur) if self.curseur in actifs else 0
            rang = (rang - 1) % len(actifs) if touche == "haut" else (rang + 1) % len(actifs)
            self.curseur = actifs[rang]
        elif touche.isdigit() and touche != "0":
            numero = int(touche) - 1
            if numero < len(self.elements) and self.elements[numero].actif:
                self.curseur = numero
                return VALIDER
        elif touche == "entree":
            return VALIDER
        return None

    @property
    def choix(self):
        return self.elements[self.curseur].valeur if self.elements else None

    def lignes(self) -> list[Ligne]:
        """Une ligne par élément : curseur, numéro, libellé aligné, puis le
        motif d'un refus ou le détail, en second plan."""
        lignes = []
        largeur = max((len(e.libelle) for e in self.elements), default=0)
        for i, element in enumerate(self.elements):
            marque = CURSEUR if i == self.curseur else " "
            numero = str(i + 1) if i < 9 else " "
            style = FORT if element.actif else GRISE
            libelle = element.libelle.ljust(largeur) if element.detail or element.motif else element.libelle
            ligne = Ligne([(f" {marque} {numero}  ", style), ("! " if element.alerte else "  ", AVERTISSEMENT),
                           (f"{libelle}", style)])
            if element.motif:
                ligne.morceaux.append((f"   {CROIX} {element.motif}",
                                       AVERTISSEMENT if element.actif else GRISE))
            if element.detail:
                ligne.morceaux.append((f"   {element.detail}", DETAIL if element.actif else GRISE))
            lignes.append(ligne)
        return lignes

    @property
    def rang_affiche(self) -> int:
        """La ligne de `lignes()` qui porte le curseur."""
        return self.curseur


@dataclass
class Champ:
    cle: str  # nom stable, pour relire la valeur, quelle que soit la langue
    libelle: str
    valeur: str = ""
    masque: bool = False  # un mot de passe : affiché en points, jamais conservé


@dataclass
class Formulaire:
    titre: str
    champs: list[Champ]
    explication: str = ""
    curseur: int = 0
    message: str = ""

    def reprendre(self, ancien: "Formulaire") -> None:
        valeurs = {champ.cle: champ.valeur for champ in ancien.champs}
        for champ in self.champs:
            champ.valeur = valeurs.get(champ.cle, champ.valeur)
        self.curseur = ancien.curseur
        self.message = ancien.message

    def touche(self, touche: str) -> str | None:
        self.message = ""
        champ = self.champs[self.curseur]
        if touche == "echap":
            return RETOUR
        if touche in ("haut",):
            self.curseur = (self.curseur - 1) % len(self.champs)
        elif touche in ("bas", "tab"):
            self.curseur = (self.curseur + 1) % len(self.champs)
        elif touche == "entree":
            if self.curseur < len(self.champs) - 1:
                self.curseur += 1
            else:
                return VALIDER
        elif touche == "effacer":
            champ.valeur = champ.valeur[:-1]
        elif touche == "espace":
            champ.valeur += " "
        elif len(touche) == 1 and touche.isprintable():
            champ.valeur += touche
        return None

    @property
    def valeurs(self) -> dict[str, str]:
        return {champ.cle: champ.valeur for champ in self.champs}

    def lignes(self) -> list[Ligne]:
        lignes = []
        largeur = max(len(c.libelle) for c in self.champs)
        for i, champ in enumerate(self.champs):
            valeur = "•" * len(champ.valeur) if champ.masque else champ.valeur
            actif = i == self.curseur
            marque = CURSEUR if actif else " "
            lignes.append(Ligne([(f" {marque} {champ.libelle:<{largeur}}  ", FORT if actif else NORMAL),
                                 (f" {valeur}{'_' if actif else ''} ", "saisie" if actif else DETAIL)]))
            lignes.append(Ligne.de(""))
        return lignes


@dataclass
class Page:
    """Ce qu'un écran montre : la question posée, des lignes d'en-tête, et en bas
    les touches utiles. Une liste ou un formulaire s'insère entre les deux.

    `operation` et `etapes` dessinent le fil des étapes (Renvoi : Type ›
    Adresse) ; `etape` est l'étape en cours. `mode` s'écrit à droite de la
    bande du haut."""

    titre: str
    entete: list[Ligne] = field(default_factory=list)
    touches: list[tuple[str, str]] = field(default_factory=list)
    operation: str = ""
    etapes: list[str] = field(default_factory=list)
    etape: int = -1
    mode: str = ""

"""Le catalogue anglais de l'interface : texte français → texte anglais.

Les champs entre accolades ({n}…) se retrouvent tels quels dans la traduction.
Le test `tests.test_traductions` vérifie que chaque `t()` du code a son entrée
ici, avec les mêmes champs.
"""

ANGLAIS: dict[str, str] = {
    # ------------------------------------------------------------- lancement
    "GatorPXE doit être lancé en root :  sudo gatorpxe": "GatorPXE must be run as root:  sudo gatorpxe",
}

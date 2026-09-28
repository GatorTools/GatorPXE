"""Les réglages (§11) : défauts, aller-retour, fichier abîmé."""

import json
import os
import tempfile
import unittest
from unittest import mock

from gatorpxe import config


class Reglages(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.fichier = os.path.join(self.dossier.name, "gatorpxe", "gatorpxe.json")
        patch = mock.patch.object(config, "FICHIER", self.fichier)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.dossier.cleanup)

    def ecrire_brut(self, texte):
        os.makedirs(os.path.dirname(self.fichier), exist_ok=True)
        with open(self.fichier, "w", encoding="utf-8") as fichier:
            fichier.write(texte)

    def test_sans_fichier_les_defauts(self):
        reglages = config.lire()
        self.assertTrue(reglages.proxy_dhcp)
        self.assertTrue(reglages.clonegator)
        self.assertEqual(reglages.delai, 10)
        self.assertEqual(reglages.entree_defaut, config.DISQUE_LOCAL)

    def test_aller_retour(self):
        config.ecrire(config.Reglages(proxy_dhcp=False, carte="eno1", delai=5))
        self.assertEqual(config.lire(), config.Reglages(proxy_dhcp=False, carte="eno1", delai=5))

    def test_fichier_illisible_donne_les_defauts(self):
        self.ecrire_brut("{pas du json")
        self.assertEqual(config.lire(), config.Reglages())
        self.ecrire_brut("[1, 2]")
        self.assertEqual(config.lire(), config.Reglages())

    def test_un_reglage_abime_ne_fait_pas_perdre_les_autres(self):
        self.ecrire_brut(json.dumps({"proxy_dhcp": "non", "delai": 3, "inconnu": 1}))
        reglages = config.lire()
        self.assertTrue(reglages.proxy_dhcp)
        self.assertEqual(reglages.delai, 3)


if __name__ == "__main__":
    unittest.main()

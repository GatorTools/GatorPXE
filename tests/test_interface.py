"""Le repli des lignes trop longues à la largeur de l'écran."""

import unittest

from gatorpxe.ui.model import AVERTISSEMENT, Ligne, replier


class Repli(unittest.TestCase):
    def test_ligne_courte_intacte(self):
        ligne = Ligne.de("court")
        self.assertEqual(replier(ligne, 40), [ligne])

    def test_repli_aligne_apres_le_point_d_exclamation(self):
        ligne = Ligne([("! ", AVERTISSEMENT), ("un deux trois quatre cinq six sept", AVERTISSEMENT)])
        lignes = [l.texte() for l in replier(ligne, 16)]
        self.assertEqual(lignes[0].rstrip(), "! un deux trois")
        self.assertTrue(all(l.startswith("  ") for l in lignes[1:]))
        self.assertTrue(all(len(l.rstrip()) <= 16 for l in lignes))
        self.assertEqual(" ".join(l.strip() for l in lignes).replace("! ", ""),
                         "un deux trois quatre cinq six sept")


if __name__ == "__main__":
    unittest.main()

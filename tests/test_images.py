"""Le dossier d'images (§6) et sa place au menu (§5)."""

import os
import tempfile
import time
import unittest

from gatorpxe import config, images, menu

HTTP = "http://192.168.199.1:8069"


class Inventaire(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.racine = self.dossier.name

    def deposer(self, chemin, contenu=b"x", mode=0o644, age=60):
        """Un fichier déposé il y a `age` secondes."""
        complet = os.path.join(self.racine, chemin)
        os.makedirs(os.path.dirname(complet), exist_ok=True)
        with open(complet, "wb") as fichier:
            fichier.write(contenu)
        os.chmod(complet, mode)
        quand = time.time() - age
        os.utime(complet, (quand, quand))

    def test_noms_types_et_ordre(self):
        self.deposer("ubuntu-24.04-desktop.iso")
        self.deposer("Boot_WinPE.WIM")
        self.deposer("memtest.efi")
        racine = images.inventaire(self.racine).racine
        self.assertEqual([(i.nom, i.type) for i in racine.images],
                         [("Boot WinPE", "WIM"), ("memtest", "EFI"), ("ubuntu 24.04 desktop", "ISO")])

    def test_sous_dossier_et_dossier_vide(self):
        self.deposer("linux-2024/debian.iso")
        os.makedirs(os.path.join(self.racine, "vide"))
        racine = images.inventaire(self.racine).racine
        self.assertEqual([(d.nom, d.chemin) for d in racine.dossiers], [("linux 2024", "linux-2024")])
        self.assertEqual(racine.dossiers[0].images[0].chemin, "linux-2024/debian.iso")

    def test_fichiers_ecartes(self):
        self.deposer("notes.txt")
        self.deposer("prive.iso", mode=0o600)
        self.deposer(".cache.iso")
        inventaire = images.inventaire(self.racine)
        self.assertEqual(inventaire.racine.images, [])
        self.assertEqual({(e.chemin, e.raison) for e in inventaire.ecartes},
                         {("notes.txt", images.NON_RECONNU), ("prive.iso", images.ILLISIBLE)})

    def test_image_en_cours_de_copie(self):
        self.deposer("grosse.iso", b"debut", age=0)
        premier = images.inventaire(self.racine)
        self.assertEqual(premier.racine.images, [])  # premier balayage : trop récente
        self.deposer("grosse.iso", b"debut et suite", age=0)
        pendant = images.inventaire(self.racine, premier.empreintes)
        self.assertEqual(pendant.racine.images, [])
        self.assertEqual(pendant.ecartes[0].raison, images.EN_COPIE)
        apres = images.inventaire(self.racine, pendant.empreintes)
        self.assertEqual(len(apres.racine.images), 1)

    def test_premier_balayage_retient_une_image_au_repos(self):
        self.deposer("ancienne.iso", age=60)
        self.assertEqual(len(images.inventaire(self.racine).racine.images), 1)

    def test_dossier_introuvable(self):
        self.assertIsNone(images.inventaire(os.path.join(self.racine, "absent")).racine)


class MenuImages(unittest.TestCase):
    def inventaire(self):
        return images.Dossier("", "", images=[
            images.Image("mon outil.iso", "mon outil", images.ISO),
            images.Image("winpe.wim", "winpe", images.WIM),
            images.Image("shell.efi", "shell", images.EFI),
        ], dossiers=[images.Dossier("Linux", "Linux", images=[
            images.Image("Linux/debian.iso", "debian", images.ISO)])])

    def test_entrees_et_ordre(self):
        script = menu.script_menu(config.Reglages(), HTTP, True, self.inventaire())
        ordre = [script.index(x) for x in
                 ("item clonegator", "Linux >", "mon outil (ISO)", "item disque")]
        self.assertEqual(ordre, sorted(ordre))

    def test_commandes_de_demarrage(self):
        script = menu.script_menu(config.Reglages(), HTTP, inventaire=self.inventaire())
        self.assertIn(f"sanboot --no-describe {HTTP}/images/mon%20outil.iso || goto echec", script)
        self.assertIn(f"kernel {HTTP}/wimboot/wimboot || goto echec\n"
                      f"initrd {HTTP}/images/winpe.wim boot.wim || goto echec\n"
                      "boot || goto echec", script)
        self.assertIn(f"chain {HTTP}/images/shell.efi", script)
        self.assertIn("iseq ${platform} efi && item", script)

    def test_sous_menu_revient_au_menu_principal(self):
        script = menu.script_menu(config.Reglages(), HTTP, inventaire=self.inventaire())
        bloc = script[script.index("menu Linux"):]
        self.assertIn("debian (ISO)", bloc)
        self.assertIn(f"item {menu.PRINCIPAL} < Back", bloc)

    def test_sans_dossier_d_images(self):
        script = menu.script_menu(config.Reglages(), HTTP, inventaire=None)
        self.assertNotIn("/images/", script)


if __name__ == "__main__":
    unittest.main()

"""Le menu de démarrage (§5) et les réglages générés de dnsmasq (§9)."""

import ipaddress
import unittest

from gatorpxe import config, dnsmasq, langue, menu

ADRESSE = ipaddress.IPv4Interface("192.168.199.1/24")
HTTP = "http://192.168.199.1:8069"


class Menu(unittest.TestCase):
    def tearDown(self):
        langue.choisir(langue.ANGLAIS)

    def test_disque_local_par_defaut_apres_le_delai(self):
        script = menu.script_menu(config.Reglages(delai=10), HTTP)
        self.assertTrue(script.startswith("#!ipxe\n"))
        self.assertIn("choose --default disque --timeout 10000 cible", script)
        self.assertIn("Boot from local disk", script)

    def test_sans_delai_le_menu_attend(self):
        self.assertNotIn("--timeout", menu.script_menu(config.Reglages(delai=0), HTTP))

    def test_uefi_rend_la_main_sur_un_echec(self):
        # Sur une réussite, EDK2 ouvre son menu au lieu de passer au disque.
        self.assertIn("iseq ${platform} efi && exit 1 ||", menu.script_menu(config.Reglages(), HTTP))

    def test_francais_sans_accents(self):
        langue.choisir(langue.FRANCAIS)
        script = menu.script_menu(config.Reglages(), HTTP)
        self.assertIn("Demarrer sur le disque local", script)
        self.assertTrue(all(ord(c) < 128 for c in script.split("\n", 2)[2]))

    def test_clonegator_en_tete_quand_il_est_la(self):
        script = menu.script_menu(config.Reglages(), HTTP, clonegator=True)
        self.assertLess(script.index("item clonegator"), script.index("item disque"))
        # Le shim de Debian en UEFI seulement : la commande n'existe pas en BIOS.
        self.assertIn("iseq ${platform} efi && shim clonegator/shimx64.efi ||", script)
        self.assertIn(f"fetch={HTTP}/clonegator/filesystem.squashfs", script)

    def test_clonegator_absent_ou_retire(self):
        self.assertNotIn("clonegator", menu.script_menu(config.Reglages(), HTTP, clonegator=False))
        retire = config.Reglages(clonegator=False)
        self.assertNotIn("clonegator", menu.script_menu(retire, HTTP, clonegator=True))

    def test_relais(self):
        self.assertEqual(menu.script_relais("http://192.168.199.1:8069"),
                         "#!ipxe\nchain http://192.168.199.1:8069/menu.ipxe"
                         "?mac=${mac:hexhyp}&plateforme=${platform}\n")


class Dnsmasq(unittest.TestCase):
    def test_proxy_actif(self):
        texte = dnsmasq.reglages("eno1", ADRESSE, True, "/tmp/j")
        self.assertIn("interface=eno1\nbind-interfaces", texte)
        self.assertIn("dhcp-range=192.168.199.0,proxy", texte)
        self.assertIn('pxe-service=tag:!ipxe,x86PC,"GatorPXE",undionly.kpxe', texte)
        self.assertIn('pxe-service=tag:!ipxe,X86-64_EFI,"GatorPXE",shimx64.efi', texte)
        self.assertIn('pxe-service=tag:ipxe,X86-64_EFI,"GatorPXE",gatorpxe.ipxe', texte)

    def test_proxy_coupe_ne_sert_que_le_tftp(self):
        texte = dnsmasq.reglages("eno1", ADRESSE, False, "/tmp/j")
        self.assertIn("enable-tftp", texte)
        self.assertNotIn("dhcp", texte)
        self.assertNotIn("pxe-service", texte)


if __name__ == "__main__":
    unittest.main()


class Renvois(unittest.TestCase):
    def script(self, *renvois):
        return menu.script_menu(config.Reglages(renvois=list(renvois)), HTTP)

    def test_wds_connait_ses_fichiers(self):
        script = self.script(config.Renvoi("WDS de l'ecole", config.WDS, "10.0.0.5"))
        self.assertIn("item r1 WDS de l'ecole", script)
        self.assertIn("set netX/next-server 10.0.0.5", script)
        self.assertIn("chain tftp://10.0.0.5/boot\\x64\\wdsnbp.com || goto echec", script)
        self.assertIn(":r1u\nset netX/filename boot\\x64\\wdsmgfw.efi\n"
                      "chain tftp://10.0.0.5/boot\\x64\\wdsmgfw.efi || goto echec", script)

    def test_ipxe(self):
        script = self.script(config.Renvoi("netboot.xyz", config.IPXE, "https://boot.netboot.xyz"))
        self.assertIn("chain https://boot.netboot.xyz || goto echec", script)

    def test_pxe_generique_uefi_seulement(self):
        script = self.script(config.Renvoi("GRUB", config.PXE, "10.0.0.7", fichier_uefi="grubx64.efi"))
        self.assertIn("iseq ${platform} efi && item r1 GRUB ||", script)
        self.assertNotIn("goto r1u", script)

    def test_renvois_apres_les_images_avant_le_disque(self):
        script = self.script(config.Renvoi("A", config.IPXE, "http://a"))
        self.assertLess(script.index("item r1 A"), script.index("item disque"))

    def test_lecture_des_renvois(self):
        import json, os, tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as dossier:
            fichier = os.path.join(dossier, "g.json")
            with open(fichier, "w") as f:
                json.dump({"renvois": [
                    {"nom": "W", "type": "wds", "adresse": "10.0.0.5"},
                    {"nom": "sans adresse", "type": "wds", "adresse": ""},
                    {"nom": "X", "type": "inconnu", "adresse": "1.2.3.4"},
                    "pas un renvoi",
                ]}, f)
            with mock.patch.object(config, "FICHIER", fichier):
                self.assertEqual([r.nom for r in config.lire().renvois], ["W"])


class EntreeParDefaut(unittest.TestCase):
    def test_clonegator_par_defaut_s_il_est_au_menu(self):
        reglages = config.Reglages(entree_defaut=config.CLONEGATOR)
        self.assertIn("choose --default clonegator", menu.script_menu(reglages, HTTP, clonegator=True))
        # Pas encore téléchargé : le disque local.
        self.assertIn("choose --default disque", menu.script_menu(reglages, HTTP, clonegator=False))


class WdsEnUefi(unittest.TestCase):
    def script(self, ipxe):
        reglages = config.Reglages(renvois=[config.Renvoi("WDS", config.WDS, "10.0.0.5")])
        return menu.script_menu(reglages, HTTP, ipxe=ipxe)

    def test_marque_en_uefi_avec_ipxe_2_0_0(self):
        self.assertIn("iseq ${platform} efi && item r1 WDS - not in UEFI for now || item r1 WDS\n",
                      self.script("v2.0.0"))

    def test_sans_marque_avec_une_autre_version(self):
        script = self.script("v2.0.1")
        self.assertIn("item r1 WDS\n", script)
        self.assertNotIn("UEFI for now", script)

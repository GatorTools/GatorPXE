"""Le menu de démarrage (§5) et les réglages générés de dnsmasq (§9)."""

import ipaddress
import unittest

from gatorpxe import config, dnsmasq, langue, menu

ADRESSE = ipaddress.IPv4Interface("192.168.199.1/24")


class Menu(unittest.TestCase):
    def tearDown(self):
        langue.choisir(langue.ANGLAIS)

    def test_disque_local_par_defaut_apres_le_delai(self):
        script = menu.script_menu(config.Reglages(delai=10))
        self.assertTrue(script.startswith("#!ipxe\n"))
        self.assertIn("choose --default disque --timeout 10000 cible", script)
        self.assertIn("Boot from local disk", script)

    def test_sans_delai_le_menu_attend(self):
        self.assertNotIn("--timeout", menu.script_menu(config.Reglages(delai=0)))

    def test_uefi_rend_la_main_sur_un_echec(self):
        # Sur une réussite, EDK2 ouvre son menu au lieu de passer au disque.
        self.assertIn("iseq ${platform} efi && exit 1 ||", menu.script_menu(config.Reglages()))

    def test_francais_sans_accents(self):
        langue.choisir(langue.FRANCAIS)
        script = menu.script_menu(config.Reglages())
        self.assertIn("Demarrer sur le disque local", script)
        self.assertTrue(all(ord(c) < 128 for c in script.split("\n", 2)[2]))

    def test_relais(self):
        self.assertEqual(menu.script_relais("http://192.168.199.1:8069"),
                         "#!ipxe\nchain http://192.168.199.1:8069/menu.ipxe\n")


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

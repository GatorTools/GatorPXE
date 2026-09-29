"""Les derniers postes, lus dans le journal HTTP (§11)."""

import unittest

from gatorpxe import postes

JOURNAL = [
    '10.0.0.5 10.0.0.1:8069 - [29/Sep/2026:08:00:00 +0000] "GET /menu.ipxe HTTP/1.1" 200 10 "-" "curl"',
    '10.0.0.7 10.0.0.1:8069 - [29/Sep/2026:08:01:00 +0000] "GET /menu.ipxe?mac=52-54-00-aa-bb-cc&plateforme=efi HTTP/1.1" 200 10 "-" "iPXE/2.0.0"',
    '10.0.0.7 10.0.0.1:8069 - [29/Sep/2026:08:01:20 +0000] "GET /clonegator/shimx64.efi HTTP/1.1" 200 10 "-" "iPXE/2.0.0"',
    '10.0.0.8 10.0.0.1:8069 - [29/Sep/2026:08:02:00 +0000] "GET /menu.ipxe?mac=52-54-00-11-22-33&plateforme=pcbios HTTP/1.1" 200 10 "-" "iPXE"',
    '10.0.0.8 10.0.0.1:8069 - [29/Sep/2026:08:02:15 +0000] "GET /windows/abc.wim HTTP/1.1" 200 10 "-" "iPXE"',
    '10.0.0.9 10.0.0.1:8069 - [29/Sep/2026:08:03:00 +0000] "GET /menu.ipxe?mac=52-54-00-44-55-66&plateforme=efi HTTP/1.1" 200 10 "-" "iPXE"',
    '10.0.0.9 10.0.0.1:8069 - [29/Sep/2026:08:03:12 +0000] "GET /images/Linux/mon%20outil.iso HTTP/1.1" 200 10 "-" "iPXE"',
    '10.0.0.10 10.0.0.1:8069 - [29/Sep/2026:08:04:00 +0000] "GET /menu.ipxe?mac=52-54-00-77-88-99&plateforme=efi HTTP/1.1" 200 10 "-" "iPXE"',
]


class Postes(unittest.TestCase):
    def test_choix_de_chaque_poste(self):
        resultat = postes.analyser(JOURNAL, {"windows/abc.wim": "W/hbcd.iso"})
        self.assertEqual([(p.adresse, p.mac, p.plateforme, p.choix, p.image) for p in resultat], [
            ("10.0.0.10", "52:54:00:77:88:99", "efi", postes.AUCUN, ""),
            ("10.0.0.9", "52:54:00:44:55:66", "efi", postes.IMAGE, "Linux/mon outil.iso"),
            ("10.0.0.8", "52:54:00:11:22:33", "pcbios", postes.IMAGE, "W/hbcd.iso"),
            ("10.0.0.7", "52:54:00:aa:bb:cc", "efi", postes.CLONEGATOR, ""),
        ])

    def test_independant_de_la_langue_du_systeme(self):
        import locale
        ancienne = locale.setlocale(locale.LC_TIME)
        for nom in ("fr_CA.UTF-8", "fr_FR.UTF-8", "fr_CA.utf8", "fr_FR.utf8"):
            try:
                locale.setlocale(locale.LC_TIME, nom)
                break
            except locale.Error:
                continue
        else:
            self.skipTest("aucune locale française")
        try:
            self.assertEqual(len(postes.analyser(JOURNAL, {})), 4)
        finally:
            locale.setlocale(locale.LC_TIME, ancienne)

    def test_deux_demarrages_du_meme_poste(self):
        lignes = [JOURNAL[5], JOURNAL[5].replace("08:03:00", "08:05:00"), JOURNAL[6].replace("08:03:12", "08:05:10")]
        resultat = postes.analyser(lignes, {})
        self.assertEqual([(p.heure.minute, p.choix) for p in resultat], [(5, postes.IMAGE), (3, postes.AUCUN)])


if __name__ == "__main__":
    unittest.main()

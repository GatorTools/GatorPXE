"""Ce que le service DHCP déjà en place annonce aux postes PXE (§9)."""

import socket
import struct
import unittest

from gatorpxe import detection


def reponse(xid=b"\x01\x02\x03\x04", siaddr="0.0.0.0", fichier=b"", options=b""):
    entete = struct.pack("!BBBB4sHH4s4s4s4s16s64s128s", 2, 1, 6, 0, xid, 0, 0, bytes(4), bytes(4),
                         socket.inet_aton(siaddr), bytes(4), bytes(16), bytes(64), fichier.ljust(128, b"\0"))
    return entete + detection.COOKIE + bytes([53, 1, 5]) + options + b"\xff"


class Analyse(unittest.TestCase):
    def test_options_66_et_67(self):
        options = bytes([66, 14]) + b"192.168.89.130" + bytes([67, 20]) + b"boot\\x64\\wdsmgfw.efi"
        xid, demarrage = detection.analyser(reponse(options=options))
        self.assertEqual(xid, b"\x01\x02\x03\x04")
        self.assertEqual(demarrage, detection.Demarrage("192.168.89.130", "boot\\x64\\wdsmgfw.efi"))

    def test_champs_bootp_a_defaut(self):
        _, demarrage = detection.analyser(reponse(siaddr="10.0.0.1", fichier=b"shimx64.efi"))
        self.assertEqual(demarrage, detection.Demarrage("10.0.0.1", "shimx64.efi"))

    def test_rien_d_annonce(self):
        self.assertIsNone(detection.analyser(reponse())[1])

    def test_next_server_seul_n_annonce_rien(self):
        # dnsmasq, entre autres, met toujours sa propre adresse dans « next-server ».
        self.assertIsNone(detection.analyser(reponse(siaddr="10.0.0.2"))[1])

    def test_lecture_des_options_avec_bourrage(self):
        options = bytes([0, 0, 66, 3]) + b"abc" + bytes([0, 67, 1]) + b"x" + b"\xff" + bytes([66, 1]) + b"z"
        self.assertEqual(detection.lire_options(options), {66: b"abc", 67: b"x"})

    def test_paquet_inform(self):
        paquet = detection.paquet_inform("10.0.0.9", bytes.fromhex("525400aabbcc"), b"\x09\x09\x09\x09")
        self.assertEqual(paquet[12:16], socket.inet_aton("10.0.0.9"))  # ciaddr
        self.assertIn(bytes([53, 1, 8]), paquet)  # DHCPINFORM
        self.assertIn(detection.CLASSE, paquet)


if __name__ == "__main__":
    unittest.main()

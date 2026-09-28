# GatorPXE

Un serveur de démarrage réseau (PXE) simple, de la famille
[GatorTools](https://gatortools.github.io/) : on l'installe sur un serveur
Debian ou Ubuntu, et les postes du réseau démarrent sur un menu construit tout
seul :

- **CloneGator**, pour cloner, sauvegarder et restaurer ;
- **les images** déposées dans un dossier : WIM, ISO, EFI ;
- **des renvois** vers d'autres serveurs de démarrage, comme WDS.

Aucune adresse IP distribuée, rien à régler sur le DHCP existant.

**État : en préparation, rien n'est codé.** Le détail est dans
l'[analyse fonctionnelle](ANALYSE-FONCTIONNELLE.md), qui fait foi.

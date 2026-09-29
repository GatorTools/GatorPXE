# GatorPXE

Un serveur de démarrage réseau (PXE) simple, de la famille
[GatorTools](https://gatortools.github.io/) : on l'installe sur un serveur
Debian ou Ubuntu, et les postes du réseau démarrent sur un menu construit tout
seul :

- **CloneGator**, pour cloner, sauvegarder et restaurer ;
- **les images** déposées dans un dossier : WIM, ISO, EFI ;
- **des renvois** vers d'autres serveurs de démarrage, comme WDS.

Aucune adresse IP distribuée, rien à régler sur le DHCP existant, et pas même
besoin d'une adresse fixe : on peut l'essayer sur n'importe quel ordinateur du
réseau.

**État : version d'essai.** Sur Ubuntu 24.04 ou Debian 13 :

```bash
wget -qO- gatortools.github.io/apt/install.sh | sudo sh
sudo apt install gatorpxe
sudo gatorpxe
```

Le détail est dans l'[analyse fonctionnelle](ANALYSE-FONCTIONNELLE.md), qui fait
foi, et l'avancement dans le [plan de développement](PLAN-DE-DEVELOPPEMENT.md).

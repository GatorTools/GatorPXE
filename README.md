# GatorPXE

Un serveur de démarrage réseau (PXE) simple, de la famille
[GatorTools](https://gatortools.github.io/) : on l'installe sur un serveur
Debian ou Ubuntu, on le démarre, et les ordinateurs du réseau peuvent démarrer
dessus.

**État : description du projet, rien n'est codé.** Ce document rassemble
l'idée telle que Kevin l'a exposée le 2026-09-28. Les choix techniques sont des
pistes, à trancher un point à la fois avant d'écrire une analyse et un plan.

## L'idée

- **Installer et démarrer, c'est tout.** Un paquet pour Debian et Ubuntu, par
  le [dépôt APT de GatorTools](https://gatortools.github.io/apt/). Le minimum
  de configuration, et jamais de fichier texte à modifier à la main.
- **Une interface qui propose les options**, au lancement du logiciel, dans
  l'esprit de CloneGator. La principale : activer ou non le **proxy DHCP**,
  pour que les postes trouvent le serveur sans toucher au DHCP existant.
- **Un menu de démarrage construit tout seul.** Un poste qui démarre sur le
  serveur voit un menu, alimenté par trois sources.

## Les trois sources du menu

### 1. Des images démarrables

Un dossier prévu pour ça. Y déposer une image démarrable suffit à l'ajouter au
menu, sans rien régler : les postes la voient au démarrage suivant. Formats
visés : ISO, WIM, et d'autres images démarrables.

### 2. Des renvois vers d'autres serveurs de démarrage

Des entrées de menu qui redirigent le poste vers un autre serveur : par
exemple le serveur WDS d'une entreprise, ou un autre serveur PXE. Ajouter une
entrée doit être simple : choisir le type de serveur, donner son adresse.

### 3. Des sauvegardes CloneGator

Un dossier qui contient des sauvegardes au format CloneGator. Le poste choisit
une sauvegarde dans le menu, puis, sur l'écran suivant, le disque local où la
restaurer ; la restauration se fait ensuite toute seule. GatorPXE devient ainsi
un serveur de restauration d'images CloneGator.

## Questions ouvertes

À trancher une à une, le moment venu :

- **Formats d'images** pris en charge, et comment chacun démarre par le réseau.
  Un WIM (Windows PE) démarre bien avec wimboot ; les ISO sont le cas délicat,
  beaucoup ne démarrent pas telles quelles par le réseau et devront être
  essayées famille par famille.
- **Types de serveurs** vers lesquels renvoyer (WDS, iPXE, PXE générique), et
  les particularités de chacun.
- **La restauration des sauvegardes CloneGator** : le poste démarre le
  CloneGator live par le réseau, qui doit alors ouvrir directement la
  sauvegarde choisie et ne demander que le disque cible. Où vit ce choix, et
  comment le live lit la sauvegarde (HTTP, partage réseau) ? Il faudra ajouter
  ce mode à CloneGator.
- **L'interface** : en mode texte, comme CloneGator, ou autre.
- **BIOS et UEFI** demandent deux chargeurs réseau différents ; **Secure Boot**
  refuse iPXE sans disposition particulière.
- **Le proxy DHCP** : son comportement à côté des DHCP courants (Windows
  Server, routeurs), et le cas où l'on préfère régler soi-même son DHCP.

## Pistes techniques

- **iPXE** comme chargeur réseau : il affiche le menu, démarre un WIM avec
  wimboot, renvoie vers un autre serveur, et télécharge en HTTP, bien plus vite
  qu'en TFTP.
- **dnsmasq** pour le TFTP et le proxy DHCP.
- Le **CloneGator live** démarre par le réseau : sa construction produit déjà
  le noyau, l'initrd et le système compressé nécessaires ; il restera à les
  joindre aux releases de CloneGator.
- Comme pour CloneGator : rien à installer hors des dépôts de Debian et
  d'Ubuntu.

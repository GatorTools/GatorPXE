# GatorPXE

Un serveur de démarrage réseau (PXE) simple, de la famille
[GatorTools](https://gatortools.github.io/) : on l'installe sur un serveur
Debian ou Ubuntu, on le démarre, et les ordinateurs du réseau peuvent démarrer
dessus.

**État : rien n'est codé.** L'[analyse fonctionnelle](ANALYSE-FONCTIONNELLE.md) décrit
le projet en détail et fait foi ; ce qui suit en est le résumé d'origine. Ce document rassemble
l'idée telle que Kevin l'a exposée le 2026-09-28, et ce qui en a été décidé
depuis. Les choix techniques sont des
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

### 3. CloneGator

CloneGator, le logiciel de clonage et de sauvegarde de GatorTools, figure au
menu par défaut ; on peut l'en retirer dans les réglages. Il ne passe pas par
son ISO : GatorPXE sert directement les fichiers de démarrage réseau de son
live (noyau, initrd, système compressé), plus légers et plus sûrs à démarrer
qu'une ISO, et les tient à jour avec les releases de CloneGator.

Restaurer une sauvegarde passe par CloneGator lui-même : le poste démarre
CloneGator, puis Restaurer, le partage réseau où sont les sauvegardes, la
sauvegarde, le disque. GatorPXE ne lit pas les sauvegardes et n'a pas à
connaître leur format.

**Plus tard, en option** : GatorPXE transmettrait à CloneGator l'adresse du
partage de sauvegardes, pour qu'elle soit déjà remplie au démarrage ; seul le
mot de passe resterait à taper.

## Questions ouvertes

À trancher une à une, le moment venu :

- **Formats d'images** pris en charge, et comment chacun démarre par le réseau.
  Un WIM (Windows PE) démarre bien avec wimboot ; les ISO sont le cas délicat,
  beaucoup ne démarrent pas telles quelles par le réseau et devront être
  essayées famille par famille.
- **Types de serveurs** vers lesquels renvoyer (WDS, iPXE, PXE générique), et
  les particularités de chacun.
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
  joindre aux releases de CloneGator, où GatorPXE ira les chercher.
- Comme pour CloneGator : rien à installer hors des dépôts de Debian et
  d'Ubuntu.

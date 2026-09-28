# GatorPXE — Plan de développement

Compagnon de [ANALYSE-FONCTIONNELLE.md](ANALYSE-FONCTIONNELLE.md), révision 0.2.
Les renvois `§n` pointent vers l'analyse.

| Rév. | Date | Auteur | Changement |
|------|------|--------|------------|
| 0.1 | 2026-09-28 | Kevin + Claude | Découpage initial en modules et en phases |
| 0.2 | 2026-09-28 | Kevin + Claude | Le réseau de la station porte un WDS de production : tous les essais se font dans un réseau de VM isolé, sortie par NAT seulement ; recette sur un réseau physique séparé |

---

## 1. Les idées qui structurent le plan

### 1.1 La chaîne de démarrage d'abord

Ce qui est risqué dans GatorPXE, ce n'est pas l'interface — celle de CloneGator existe — mais
la chaîne qui mène un poste jusqu'au menu : proxy DHCP, chargeur BIOS ou UEFI, shim et iPXE
signés, passage de TFTP à HTTP, boucle d'iPXE évitée. Elle passe en premier, avec un menu réduit
à « Démarrer sur le disque local ». Tout le reste ajoute des entrées à un menu qui s'affiche déjà.

### 1.2 Un réseau d'essai isolé, sur la station

Le réseau où se trouve la station porte **un serveur WDS de production** : il répond lui-même aux
démarrages réseau. Un proxy DHCP essayé là entrerait en concurrence avec lui, et des postes de
l'école pourraient démarrer sur GatorPXE. **Aucun essai ne se fait sur ce réseau.** GatorPXE n'y
est jamais lancé sur une carte physique ; seul le pont d'essai lui est donné.

Tous les essais se font sur un **réseau de VM isolé**, fabriqué sur la station :

- un pont (`ip link add … type bridge`), **sans carte physique** ;
- un **DHCP « existant »** : un dnsmasq ordinaire, dans son propre espace de noms réseau, qui
  distribue les adresses comme le ferait le DHCP d'une école ;
- GatorPXE sur le pont, comme sur un serveur ;
- des **postes QEMU** branchés au pont : BIOS, UEFI, UEFI avec Secure Boot (OVMF et les clés
  Microsoft, comme pour le live de CloneGator).

QEMU tourne en émulation : lent, mais un démarrage réseau jusqu'au menu prend peu de temps. Les
démarrages lourds (Windows PE, CloneGator) se mesurent en minutes ; on les réserve aux essais de
fin de phase.

Le pont **sort par NAT** vers le réseau de l'école, dans ce sens seulement : les postes QEMU
atteignent Internet et le partage d'essai, mais aucune diffusion — DHCP, démarrage réseau — ne
franchit la station, dans un sens comme dans l'autre.

Les essais sur de **vrais postes** se font sur un réseau physique séparé : un commutateur relié
à une carte libre de la station (`enp5s0` ou `eno1`), qui ne touche pas au réseau de l'école.

### 1.3 Une seule couche touche le système

Comme dans CloneGator (§15) : `sysexec` est le seul module qui lance une commande ou lit `/sys`
et `/proc`, avec un délai sur chaque commande et un journal verbatim. Il est repris de
`clonegator/sysexec.py`.

### 1.4 Ce qui est repris de CloneGator

`sysexec`, la traduction (`t()`, `F2`), le clavier et la présentation de l'interface texte sont
**copiés** depuis CloneGator, puis adaptés. Une bibliothèque commune aux deux dépôts serait
possible plus tard ; elle n'est pas justifiée pour deux logiciels.

---

## 2. Modules

```
gatorpxe/
  __main__.py      `gatorpxe` : l'interface ; `gatorpxe service` : le service (systemd) ;
                   sous-commandes de développement
  sysexec.py       commandes externes, /sys et /proc : délai, capture, journal
  config.py        /etc/gatorpxe/gatorpxe.json : lecture, écriture, valeurs par défaut
  journal.py       journaux dans /var/log/gatorpxe (§13)
  service.py       la boucle du service : relit les réglages, lance et surveille les
                   instances, balaie les dossiers, déclenche les mises à jour
  reseau.py        carte réseau principale, adresse, ports et pare-feu (§9)
  dnsmasq.py       réglages de l'instance dnsmasq : proxy DHCP, TFTP, BIOS/UEFI, iPXE
  lighttpd.py      réglages de l'instance lighttpd (port 8069)
  telechargements.py  iPXE signé, wimboot, CloneGator : téléchargement, vérification,
                   dernière version gardée hors ligne
  images.py        inventaire du dossier : type, nom affiché, sous-dossiers, fichiers ignorés
  windows.py       extraction des ISO Windows par 7zip, une fois, dans /var/lib/gatorpxe
  renvois.py       WDS, iPXE/HTTP, PXE générique (§8)
  menu.py          le script iPXE du menu, à partir de l'inventaire et des réglages
  postes.py        derniers postes démarrés, lus dans les journaux de dnsmasq et lighttpd
  ui/
    model.py       état affiché, sans curses — testable seul
    screens.py     rendu curses (§11)
outils/
  reseau-essai.sh  le réseau d'essai (§1.2) : pont, DHCP « existant », postes QEMU
  construire-paquet.sh
paquet/            control, unité systemd, scripts d'installation
tests/             unittest, bibliothèque standard
```

Deux séparations à tenir :

- **`menu` et `images` ne lancent rien.** Ils reçoivent un inventaire et rendent un texte. Ils se
  testent avec un dossier de faux fichiers.
- **L'interface ne touche pas aux instances.** Elle écrit les réglages et demande au service de
  les relire ; les postes n'en dépendent jamais (P4).

---

## 3. Phases

Chaque phase se met au point sur le réseau d'essai (§1.2). Elle se termine par la revue de
Kevin ; une release n'est publiée qu'à ce moment-là.

### Phase 0 — Socle et réseau d'essai · taille S

- squelette du dépôt, version affichée et journalisée dès le premier jour (datée à la minute du
  commit, comme CloneGator)
- `sysexec`, `journal`, `config`, traduction : repris de CloneGator
- `outils/reseau-essai.sh` : le pont, le DHCP « existant », un poste QEMU en BIOS, en UEFI, en
  UEFI Secure Boot

**Fini quand** : les trois postes QEMU reçoivent une adresse du DHCP « existant » et échouent
proprement faute de serveur de démarrage.

### Phase 1 — La chaîne de démarrage · taille L

- `telechargements` : l'iPXE signé (shim et iPXE) et wimboot, depuis les releases d'iPXE ;
  l'iPXE BIOS du paquet `ipxe`
- `dnsmasq` : proxy DHCP et TFTP sur la carte choisie, bon chargeur pour BIOS et UEFI, iPXE
  reconnu et renvoyé vers le menu en HTTP
- `lighttpd` : l'instance sur le port 8069
- `service` : lance, surveille et relance les deux instances ; unité systemd de développement
- `menu` : un menu réduit à « Démarrer sur le disque local », délai de 10 s (§5)
- chaque démarrage de poste journalisé (§13)
- proxy coupé : les réglages à saisir dans le DHCP, essayés sur le DHCP « existant » réglé à la
  main (§16)

**Fini quand** : les trois postes QEMU, Secure Boot compris, affichent le menu et repartent sur
leur disque local ; aucune boucle d'iPXE, proxy actif comme DHCP réglé à la main.

### Phase 2 — CloneGator au menu · taille M

**Côté CloneGator d'abord** (son §17) : joindre aux releases le noyau, l'initrd et le système
compressé du live, que `outils/construire-live.sh` produit déjà dans `dist/`. Le live charge
son système par HTTP (`fetch=` de `live-boot`).

- `telechargements` : les trois fichiers de la dernière release, mise à jour quotidienne,
  dernière version gardée sans Internet
- l'entrée CloneGator en tête du menu, retirable dans les réglages

**Fini quand** : CloneGator démarre par le réseau en BIOS et en UEFI Secure Boot, et y mène une
sauvegarde vers le partage d'essai, atteint par le NAT.

### Phase 3 — Les images · taille L

- `images` : balayage du dossier toutes les quelques secondes, noms nettoyés, sous-menus,
  fichiers ignorés et pourquoi ; dossier introuvable sans arrêt du service (§12)
- WIM par wimboot ; ISO Windows extraite par 7zip, une fois, puis wimboot ; ISO quelconque en
  sanboot ; EFI chargé directement (§6)

**Essais** : une ISO Windows 11 et un WIM en UEFI Secure Boot ; les ISO Linux courantes en
sanboot, avec la liste de celles qui démarrent (§16). Les images d'essai viennent des sites
officiels ou du partage d'essai.

**Fini quand** : déposer une ISO Windows 11 fait paraître l'entrée au menu, et le poste
Secure Boot démarre dessus ; le résultat des ISO Linux est consigné ici.

### Phase 4 — Les renvois · taille M

- `renvois` : WDS (fichiers connus, BIOS et UEFI), iPXE/HTTP, PXE générique
- dans l'ordre choisi, après les images

**Essais** : iPXE/HTTP vers netboot.xyz ; PXE générique vers un second serveur monté sur le
réseau d'essai. **WDS demande un vrai serveur WDS** : la manière de l'essayer sans toucher au WDS
de production reste à décider avec Kevin, en BIOS et en UEFI Secure Boot (§16).

**Fini quand** : chaque type de renvoi mène un poste au menu de l'autre serveur.

### Phase 5 — L'interface · taille L

- reprise de la présentation, des touches et de `F2` de CloneGator
- l'accueil (§11) : service, proxy, menu tel que les postes le voient, fichiers ignorés, derniers
  postes
- les écrans de réglage, un par sujet ; relecture des réglages par le service sans couper les
  postes
- vérification du pare-feu et des ports (§9)

**Fini quand** : tout se règle depuis l'interface sans ouvrir un fichier (P5), revue de Kevin sur
la console de la station.

### Phase 6 — Paquet et recette · taille M

- `.deb` (`dnsmasq-base`, `lighttpd`, `ipxe`, `7zip`, `python3`) : unité systemd, service démarré
  à l'installation, serveur web par défaut de lighttpd désactivé seulement s'il vient d'être
  installé (§14, P3)
- release GitHub ; ligne `GatorTools/GatorPXE` dans `logiciels.txt` du dépôt APT ; page
  `gatorpxe/` du site mise à jour

**Recette** : sur un Ubuntu 24.04 et un Debian 13 neufs, installation par apt, puis démarrage de
vrais postes sur le réseau physique séparé (§1.2), à côté d'un DHCP ordinaire (§16).

**Fini quand** : un serveur neuf, installé par `apt install gatorpxe` sans rien régler, fait
démarrer de vrais postes sur CloneGator et sur une image déposée.

---

## 4. Chemin critique

```
Phase 0 ── Phase 1 ──┬── Phase 2 ──┐
                     ├── Phase 3 ──┼── Phase 5 ── Phase 6
                     └── Phase 4 ──┘
```

Le jalon qui compte est la **fin de la phase 1** : un poste Secure Boot affiche le menu. Les
phases 2 à 4 ne font qu'y ajouter des entrées.

## 5. Premier pas concret

1. Installer sur la station `dnsmasq-base`, `lighttpd`, `ipxe` et `7zip`.
2. `outils/reseau-essai.sh` : le pont isolé, sa sortie par NAT, et un poste QEMU UEFI
   Secure Boot qui prend son adresse sur le pont.
3. Le shim et l'iPXE signés, servis à la main par un dnsmasq en proxy : voir le poste
   Secure Boot atteindre une invite iPXE. C'est le point le plus incertain de toute la chaîne ;
   il passe avant le reste du socle.

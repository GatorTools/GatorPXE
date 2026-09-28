# GatorPXE — Plan de développement

Compagnon de [ANALYSE-FONCTIONNELLE.md](ANALYSE-FONCTIONNELLE.md), révision 0.6.
Les renvois `§n` pointent vers l'analyse.

| Rév. | Date | Auteur | Changement |
|------|------|--------|------------|
| 0.1 | 2026-09-28 | Kevin + Claude | Découpage initial en modules et en phases |
| 0.2 | 2026-09-28 | Kevin + Claude | Le réseau de la station porte un WDS de production : tous les essais se font dans un réseau de VM isolé, sortie par NAT seulement ; recette sur un réseau physique séparé |
| 0.3 | 2026-09-28 | Claude | Phase 0 faite, en attente de la revue de Kevin : réseau d'essai, socle, et la chaîne Secure Boot essayée à la main jusqu'au menu |
| 0.4 | 2026-09-28 | Kevin + Claude | Analyse 0.3 : iPXE BIOS pris dans les releases d'iPXE ; wimboot passe en phase 3, où il sert. Phase 1 commencée |
| 0.5 | 2026-09-28 | Claude | Phase 1 faite, en attente de la revue de Kevin. Analyse 0.4 |
| 0.6 | 2026-09-28 | Kevin + Claude | Phase 2 faite, en attente de revue : CloneGator publie `clonegator-live-pxe.tar` (sa révision 1.6), GatorPXE le sert. Analyse 0.5 |
| 0.7 | 2026-09-28 | Claude | Phase 3 commencée sans les images Windows, qui viendront de Kevin. Analyse 0.6 |

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
  telechargements.py  iPXE, wimboot, CloneGator : téléchargement, vérification,
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

### Phase 0 — Socle et réseau d'essai · taille S · **faite, en attente de revue**

- squelette du dépôt, version affichée et journalisée dès le premier jour (datée à la minute du
  commit, comme CloneGator)
- `sysexec`, `journal`, `config`, traduction : repris de CloneGator
- `outils/reseau-essai.sh` : le pont, le DHCP « existant », un poste QEMU en BIOS, en UEFI, en
  UEFI Secure Boot

**Fini quand** : les trois postes QEMU reçoivent une adresse du DHCP « existant » et échouent
proprement faute de serveur de démarrage.

**Où on en est (2026-09-28).** `outils/reseau-essai.sh` monte et démonte le réseau d'essai
(pont, DHCP « existant », sortie par NAT dans une table nftables à part), démarre des postes
QEMU en BIOS, UEFI et UEFI Secure Boot, capture leur écran et leur envoie des touches. Un poste
du pont atteint Internet et le partage d'essai. Le socle — `sysexec`, `journal`, `config`,
`langue` — est repris de CloneGator ; `gatorpxe version` fonctionne, et `gatorpxe` sans root le
dit en une phrase.

**Le point le plus incertain de la phase 1 est levé**, par un dnsmasq en proxy monté à la main :
le poste UEFI Secure Boot charge le shim signé, qui charge l'iPXE 2.0.0 signé depuis le même
dossier TFTP ; l'iPXE reconnaît le proxy et atteint le script de menu. Les postes BIOS et UEFI
aussi.

Enseignements :

- Les releases d'iPXE publient `ipxeboot.tar.gz` : shim et iPXE signés (`x86_64-sb/`), mais aussi
  les chargeurs BIOS (`undionly.kpxe`). Le paquet `ipxe` des dépôts est donc abandonné
  (analyse 0.3).
- L'iPXE signé cherche `autoexec.ipxe` sur le serveur TFTP avant tout : c'est sans doute la
  réponse à la boucle quand le DHCP est réglé à la main (§16).
- En BIOS, la carte réseau de QEMU contient elle-même un iPXE : le poste saute l'étape TFTP.
  Le chemin d'une vraie carte BIOS vers `undionly.kpxe` s'essaiera autrement en phase 1.
- dnsmasq abandonne root : ses fichiers ne peuvent pas vivre sous `/root` ni dans un dossier
  temporaire privé.

### Phase 1 — La chaîne de démarrage · taille L · **faite, en attente de revue**

- `telechargements` : iPXE depuis ses releases — shim et iPXE signés pour l'UEFI, `undionly.kpxe`
  pour le BIOS
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

**Où on en est (2026-09-28).** `gatorpxe service`, lancé par l'unité systemd (surcharge de
développement sur la station, jamais activée au démarrage), obtient iPXE v2.0.0, prépare les
chargeurs et le menu, lance dnsmasq et lighttpd sur la seule carte réglée, et les relance s'ils
s'arrêtent. Sur le réseau d'essai :

- proxy actif : les postes BIOS, UEFI et UEFI Secure Boot affichent le menu, puis démarrent au
  bout de 10 s sur leur disque local — le live de CloneGator, branché comme disque ;
- proxy coupé, DHCP « existant » réglé à la main : même résultat, sans boucle (analyse §9) ;
- carte réglée disparue : les instances s'arrêtent, le service attend et ne se rabat sur aucune
  autre carte ; la carte revenue, il repart seul.

Chaque démarrage de poste est au journal, brut : `dnsmasq.log` (adresse MAC, BIOS ou UEFI,
fichiers envoyés) et `http-acces.log` (adresse, fichiers demandés). La vue « derniers postes »
de l'accueil les rassemblera en phase 5.

Enseignements :

- En UEFI, « Démarrer sur le disque local » sort d'iPXE par `exit 1` : sur une sortie réussie,
  le micrologiciel EDK2 s'arrête et ouvre son menu au lieu de passer au disque.
- L'iPXE signé trouve `autoexec.ipxe` avant tout échange DHCP : en UEFI, le DHCP réglé à la main
  n'a besoin d'aucune condition. `undionly.kpxe` ne le cherche pas : en BIOS, sans la condition
  « classe utilisateur iPXE », il boucle.
- Reste à voir sur une vraie carte BIOS (recette) : le passage de sa ROM PXE à
  `undionly.kpxe`. Dans QEMU, la ROM de la carte est déjà un iPXE ; `undionly.kpxe` s'y charge
  et s'exécute, mais le premier maillon n'est pas celui d'un vrai poste.
- dnsmasq et lighttpd abandonnent root : lighttpd avant d'ouvrir ses journaux, que le service
  crée donc d'avance à son nom.

### Phase 2 — CloneGator au menu · taille M · **faite, en attente de revue**

**Côté CloneGator d'abord** (son §15) : publier avec chaque release le démarrage réseau du live,
comme pour n'importe quel serveur PXE. Le live charge son système par HTTP (`fetch=` de
`live-boot`).

- `telechargements` : l'archive de la dernière release, mise à jour quotidienne en
  arrière-plan, dernière version gardée sans Internet
- l'entrée CloneGator en tête du menu, retirable dans les réglages

**Fini quand** : CloneGator démarre par le réseau en BIOS et en UEFI Secure Boot, et y mène une
sauvegarde vers le partage d'essai, atteint par le NAT.

**Où on en est (2026-09-28).** Côté CloneGator : `construire-live.sh` produit
`clonegator-live-pxe_<version>.tar` (shim signé de Debian, noyau, initrd, système compressé) ;
l'archive est jointe à la release en cours, avec sa copie `clonegator-live-pxe.tar`, et la page
Télécharger la présente. Côté GatorPXE : le service la télécharge (250 Mo, 5 s), la range dans
`/var/lib/gatorpxe/clonegator/<version>`, et le menu propose CloneGator en tête. Sur le réseau
d'essai, CloneGator démarre par le réseau en BIOS et en UEFI Secure Boot, sans disque ; depuis
le poste Secure Boot, une sauvegarde de 253 Mo vers le partage d'essai réussit en 14 s.

Enseignements :

- Secure Boot refuse le noyau de Debian chargé par l'iPXE signé : seul le shim de Debian sait le
  vérifier. La commande `shim` d'iPXE le charge d'abord ; CloneGator publie donc son shim avec
  les trois autres fichiers. En BIOS, la commande n'existe pas : elle est réservée à l'UEFI.
- L'iPXE de certaines cartes réseau (1.21, celui de QEMU) ignore `${cwduri}` : le menu écrit les
  adresses en entier.

### Phase 3 — Les images · taille L · **en cours**

- `images` : balayage du dossier toutes les quelques secondes, noms nettoyés, sous-menus,
  fichiers ignorés et pourquoi ; dossier introuvable sans arrêt du service (§12)
- wimboot, téléchargé depuis ses releases ; WIM par wimboot ; ISO Windows extraite par 7zip, une fois, puis wimboot ; ISO quelconque en
  sanboot ; EFI chargé directement (§6)

**Essais** : une ISO Windows 11 et un WIM en UEFI Secure Boot ; les ISO Linux courantes en
sanboot, avec la liste de celles qui démarrent (§16). Les images d'essai viennent des sites
officiels ou du partage d'essai.

**Fini quand** : déposer une ISO Windows 11 fait paraître l'entrée au menu, et le poste
Secure Boot démarre dessus ; le résultat des ISO Linux est consigné ici.

**Où on en est (2026-09-28).** Fait, sans les images Windows : balayage du dossier à chaque tour,
noms nettoyés, sous-menus avec retour, fichiers écartés et leur raison, image en cours de copie
retenue seulement une fois stable ; wimboot 2.9.0 téléchargé (signé par l'autorité UEFI de
Microsoft) ; menu des ISO (sanboot), WIM (wimboot) et EFI (entrée masquée en BIOS) ; un
démarrage qui échoue ramène au menu. Résultat des ISO Linux : analyse §6. Restent l'ISO
Windows 11 et le WIM, que Kevin fournit.

Enseignements :

- Une commande qui échoue interrompt un script iPXE : chaque commande de démarrage renvoie au
  message d'échec.
- Au premier balayage, faute de balayage précédent, une image n'est retenue que si elle n'a pas
  bougé depuis 10 s : sinon, une ISO en cours de copie entrait au menu puis en sortait.
- sanboot ne charge pas l'ISO en mémoire : il la lit à la demande, et le disque disparaît quand
  le système démarré prend la main.

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

- `.deb` (`dnsmasq-base`, `lighttpd`, `7zip`, `python3`) : unité systemd, service démarré
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

1. Installer sur la station `dnsmasq-base`, `lighttpd` et `7zip`.
2. `outils/reseau-essai.sh` : le pont isolé, sa sortie par NAT, et un poste QEMU UEFI
   Secure Boot qui prend son adresse sur le pont.
3. Le shim et l'iPXE signés, servis à la main par un dnsmasq en proxy : voir le poste
   Secure Boot atteindre une invite iPXE. C'est le point le plus incertain de toute la chaîne ;
   il passe avant le reste du socle.

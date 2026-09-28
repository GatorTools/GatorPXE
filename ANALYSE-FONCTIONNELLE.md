# GatorPXE — Analyse fonctionnelle

Un serveur de démarrage réseau (PXE) de la famille GatorTools : on l'installe sur un serveur
Debian ou Ubuntu, on le démarre, et les postes du réseau démarrent sur un menu construit tout
seul.

## Tableau de révisions

| Rév. | Date | Auteur | Changement |
|------|------|--------|------------|
| 0.1 | 2026-09-28 | Kevin + Claude | Première rédaction, à partir de la description du projet et des choix validés un à un : Python, service et outil de réglage séparés, interface texte, lighttpd, iPXE signé, proxy DHCP, formats d'images, renvois, emplacements |
| 0.2 | 2026-09-28 | Kevin + Claude | Relecture : délai de 10 s sur le disque local confirmé (§5), 7zip retenu pour les ISO Windows (§14), §16 expliqué |
| 0.3 | 2026-09-28 | Kevin + Claude | iPXE BIOS pris dans les releases d'iPXE comme l'UEFI : le paquet `ipxe` n'est plus une dépendance (§10, §14, §15) |
| 0.4 | 2026-09-28 | Claude | Essais de la phase 1 : réglages exacts du DHCP réglé à la main, condition nécessaire en BIOS seulement (§9, §16) |
| 0.5 | 2026-09-28 | Kevin + Claude | CloneGator publie son démarrage réseau avec chaque release, shim de Debian compris ; GatorPXE le prend là (§7) |
| 0.6 | 2026-09-28 | Claude | Essais des ISO en sanboot : l'ISO n'est pas chargée en mémoire, et les ISO Linux courantes ne retrouvent pas leur support (§6, §16) |
| 0.7 | 2026-09-28 | Kevin + Claude | Sanboot gardé en première version ; les ISO sont examinées et marquées au menu, « incompatible réseau » et « sans Secure Boot » (§6) |

---

## 1. Contexte et objectif

Dans une école ou un service informatique, on démarre régulièrement des postes sur des outils :
CloneGator pour cloner ou restaurer, un Windows PE pour dépanner, un installeur Linux. Avec une
clé USB par outil et par technicien, on perd du temps et des clés. GatorPXE les met à disposition
de tout le réseau : le poste démarre sur la carte réseau, et choisit dans un menu.

L'objectif tient en une phrase : **installer, démarrer, déposer ses images — et rien d'autre à
régler**, ni sur le serveur ni sur le DHCP du réseau.

## 2. Principes directeurs

**P1 — GatorPXE ne dérange pas le réseau.** Il ne distribue aucune adresse IP : son proxy DHCP ne
répond qu'aux demandes de démarrage réseau, à côté du DHCP existant, qui reste seul maître des
adresses. On peut le couper (§9).

**P2 — GatorPXE n'écrit jamais sur un poste.** Il ne fait que servir des fichiers. Ce qui s'écrit
sur un disque, c'est l'outil démarré qui l'écrit — CloneGator, par exemple, avec ses propres
protections.

**P3 — GatorPXE ne touche pas aux services existants du serveur.** Ses outils (dnsmasq, lighttpd)
tournent en instances à lui, avec leurs propres réglages. Un dnsmasq ou un serveur web déjà en
place n'est jamais modifié.

**P4 — Les postes démarrent même quand personne ne règle rien.** Le service tourne seul ;
l'interface de réglage peut être ouverte, fermée, plantée, sans conséquence pour les postes.

**P5 — Aucun fichier texte à modifier à la main.** Tout se règle dans l'interface. Les fichiers
de réglage existent, mais on n'a jamais à les ouvrir.

---

## 3. Architecture

```
            ┌───────────────────────── serveur GatorPXE ─────────────────────────┐
            │                                                                    │
  sudo gatorpxe ──► interface de réglage ──► /etc/gatorpxe/gatorpxe.json         │
            │                                        │ relu par                  │
            │                                        ▼                           │
            │                             service gatorpxe (Python)              │
            │                  lance et surveille │  construit le menu          │
            │                                     │  tient CloneGator à jour     │
            │                        ┌────────────┴────────────┐                 │
            │                        ▼                         ▼                 │
            │           dnsmasq (proxy DHCP, TFTP)    lighttpd (HTTP, port 8069) │
            └────────────────────────┬─────────────────────────┬─────────────────┘
                                     │                         │
                 1. « où démarrer ? »                 3. menu, images, CloneGator
                 2. chargeur iPXE (TFTP)
                                     ▼                         ▼
                                        poste qui démarre
```

- **Le service `gatorpxe`** (unité systemd, démarrée avec le serveur) : un programme Python qui ne
  sert rien lui-même (§15). Il lance et surveille dnsmasq et lighttpd avec des réglages qu'il
  génère ; relit les dossiers toutes les quelques secondes et reconstruit le menu dès qu'une image
  apparaît ou disparaît ; télécharge et tient à jour les fichiers de CloneGator et les chargeurs
  iPXE.
- **L'outil de réglage `gatorpxe`** (commande, en root) : l'interface texte (§11). Il écrit les
  réglages, puis demande au service de les relire.
- **dnsmasq** : le proxy DHCP (§9) et le TFTP, qui ne sert que le petit chargeur iPXE.
- **lighttpd** : tout le reste, en HTTP — le menu, les images, CloneGator —, beaucoup plus rapide
  que TFTP. Il gère les téléchargements par morceaux dont iPXE a besoin pour une ISO.
- **iPXE** : le chargeur réseau que reçoit le poste. Il affiche le menu et démarre l'entrée
  choisie (§10 pour Secure Boot).

## 4. Périmètre

### Dans la première version

1. Service, outil de réglage, paquet `.deb` publié par le dépôt APT de GatorTools
2. Proxy DHCP actif par défaut, qu'on peut couper
3. Menu construit tout seul : CloneGator, images du dossier, renvois vers d'autres serveurs
4. Formats WIM, ISO Windows, ISO quelconque, EFI (§6)
5. Renvois WDS, iPXE/HTTP, PXE générique (§8)
6. BIOS et UEFI, Secure Boot actif compris (§10)
7. Interface en anglais et en français

### Plus tard, envisagé

- Reconnaître les familles d'ISO Linux courantes (Ubuntu, Debian, Fedora…) et les démarrer par
  leur noyau et leur initrd, plus fiable que l'ISO entière
- Pré-remplir dans CloneGator l'adresse du partage de sauvegardes
- Publier le dossier d'images comme partage réseau Windows
- Une interface web
- Une entrée de secours pour les postes où l'autorité tierce de Microsoft est refusée (§10)

### Hors périmètre

- Distribuer des adresses IP : GatorPXE n'est jamais un serveur DHCP complet (P1)
- Déployer ou installer des systèmes à la place de l'outil démarré : GatorPXE sert, il n'agit pas
  sur les postes (P2)

---

## 5. Le menu de démarrage

Un poste qui démarre sur GatorPXE voit un menu, dans cet ordre :

1. **CloneGator**, s'il n'a pas été retiré (§7)
2. **Les images** du dossier (§6), par ordre alphabétique ; un sous-dossier devient un sous-menu
3. **Les renvois** vers d'autres serveurs (§8), dans l'ordre choisi dans l'interface
4. **Démarrer sur le disque local**

Chaque image porte son nom de fichier nettoyé, suivi de son type entre parenthèses :
`ubuntu-24.04-desktop.iso` devient « ubuntu 24.04 desktop (ISO) ».

Sans choix de l'opérateur, le menu démarre au bout de 10 secondes sur **le disque local**. Un poste qui démarre par le réseau par erreur, ou dont on a
oublié de changer l'ordre de démarrage, retrouve ainsi son système au lieu de lancer un outil.
Délai et entrée par défaut se changent dans l'interface.

## 6. Les images

Un dossier (§12) où l'on dépose des images, par SSH ou en branchant un disque qui les contient.
**Déposer un fichier suffit** : il paraît au menu dans les secondes qui suivent. En retirer un
le retire du menu. Les fichiers non reconnus sont ignorés, et signalés dans l'interface.

| Format | Démarrage | Fiabilité |
|--------|-----------|-----------|
| **WIM** (Windows PE, outils Windows) | par wimboot | très bonne, Secure Boot compris |
| **ISO Windows** (installation, WinPE) | GatorPXE en extrait `boot.wim` et les fichiers de démarrage, une fois, puis wimboot | très bonne |
| **ISO quelconque** (Linux, outils divers) | iPXE présente l'ISO au poste comme un disque, lu par morceaux à la demande (sanboot) | faible pour les Linux : le chargeur et le noyau démarrent, puis le système cherche son ISO et ne la trouve plus ; bonne pour les outils autonomes (netboot.xyz…) |
| **EFI** (`.efi`) | chargé directement | bonne, s'il est signé quand Secure Boot est actif |

Le disque que présente iPXE n'existe que pour le micrologiciel : il disparaît dès que le système
démarré prend la main. Une ISO dont le système se charge tout entier au démarrage marche ; une ISO
qui relit ensuite son support échoue. Essais sur le réseau d'essai, BIOS et UEFI Secure Boot :

| ISO | Résultat |
|-----|----------|
| netboot.xyz | démarre (BIOS ; en UEFI, son `.efi`) |
| Debian 13 netinst | l'installeur démarre, puis ne trouve pas son support |
| Ubuntu 24.04 Server | le noyau démarre, puis ne trouve pas son support |
| Alpine 3.24 | le noyau démarre, puis ne trouve pas son support ; refusée par Secure Boot (chargeur non signé) |

Un démarrage qui échoue ramène au menu, après un message.

**Les ISO sont examinées** une fois, sans être démarrées : `7z` liste leur contenu et en extrait
le chargeur UEFI. Le menu marque :

- « incompatible réseau » : l'ISO porte le dossier d'une famille Linux qui relit son support
  après le démarrage (`casper/` d'Ubuntu, `live/` de Debian live, `LiveOS/` de Fedora,
  `install.amd/` de l'installeur Debian, `arch/`, `apks/` d'Alpine) ;
- « sans Secure Boot », en UEFI seulement : son chargeur UEFI n'est pas signé par l'autorité UEFI
  de Microsoft.

Les ISO marquées restent au menu : la détection repère des familles connues, elle ne garantit
rien. Une ISO sans indice est présentée sans marque.

## 7. CloneGator

CloneGator figure au menu par défaut ; on peut l'en retirer dans l'interface. Il ne passe pas par
son ISO : GatorPXE sert les fichiers de démarrage réseau de son live — noyau, initrd, système
compressé, et le shim signé de Debian — et le live charge son système par HTTP. C'est plus léger
et plus sûr qu'une ISO. Secure Boot l'accepte : en UEFI, iPXE confie le noyau signé de Debian au
shim de Debian, seul à pouvoir le vérifier.

Le service télécharge ces fichiers depuis les releases de CloneGator (`clonegator-live-pxe.tar`,
publiée avec chaque release comme pour n'importe quel serveur PXE) et les tient à jour, une fois
par jour, en arrière-plan. Retiré du menu, CloneGator n'est plus téléchargé. Sans accès à Internet, il garde la dernière version obtenue ; l'interface dit laquelle.

Restaurer une sauvegarde passe par CloneGator lui-même : Restaurer, le partage réseau où sont les
sauvegardes, la sauvegarde, le disque. GatorPXE ne lit pas les sauvegardes.

## 8. Les renvois vers d'autres serveurs

Une entrée de menu qui envoie le poste vers un autre serveur de démarrage. On la crée dans
l'interface : **nom** affiché au menu, **type**, **adresse**.

| Type | Pour | Ce qu'on saisit |
|------|------|-----------------|
| **WDS** | Windows Deployment Services, et MECM/SCCM qui démarre de même | l'adresse du serveur ; GatorPXE connaît les fichiers à demander, en BIOS et en UEFI |
| **iPXE / HTTP** | un autre serveur iPXE, FOG, netboot.xyz… | l'adresse du script de démarrage (`http://…`) |
| **PXE générique** | tout autre serveur (pxelinux, GRUB…) | l'adresse du serveur, et le fichier à charger en BIOS et en UEFI |

Avec Secure Boot actif, un renvoi ne marche que si l'autre serveur fournit, lui aussi, des
fichiers signés.

---

## 9. Réseau et DHCP

**Proxy DHCP, actif par défaut.** dnsmasq répond aux seules demandes de démarrage réseau, sur la
carte réseau principale du serveur, détectée seule ; on peut en choisir une autre. Il donne à
chaque poste le bon chargeur, BIOS ou UEFI, et reconnaît iPXE une fois chargé pour lui envoyer le
menu plutôt que de le recharger en boucle. Rien à régler sur le DHCP existant.

**Proxy DHCP coupé.** Pour un réseau où un proxy DHCP est interdit : l'interface affiche exactement
les réglages à saisir dans le DHCP existant (Windows Server, pfSense, routeur…) :

- l'adresse du serveur GatorPXE, et le fichier à charger : `shimx64.efi` en UEFI,
  `undionly.kpxe` en BIOS ;
- en BIOS seulement, la condition qui évite la boucle d'iPXE : si la classe utilisateur est
  « iPXE », le fichier est l'adresse du menu (`http://…:8069/menu.ipxe`). En UEFI, l'iPXE signé
  trouve le menu de lui-même.

**Ports** : DHCP proxy (67 et 4011, UDP), TFTP (69, UDP), HTTP (8069, TCP). Le pare-feu du
serveur, s'il y en a un, doit les laisser passer ; l'interface le vérifie et le dit.

## 10. BIOS, UEFI et Secure Boot

- **UEFI** : l'iPXE officiel signé (iPXE 2.0.0 et suivants). Un shim signé par l'autorité tierce de
  Microsoft charge un iPXE signé par iPXE : un PC standard démarre avec Secure Boot actif, sans
  clé à installer. Avec Secure Boot actif, il démarre CloneGator et les Linux signés, les WIM
  (wimboot est signé), les ISO dont le chargeur est signé ; il refuse le reste, ce qui est le rôle
  de Secure Boot.
- **BIOS** : l'iPXE des mêmes releases officielles (Secure Boot n'existe pas en BIOS).
- Certains PC récents refusent par défaut l'autorité tierce de Microsoft (« Allow Microsoft 3rd
  Party UEFI CA ») : il faut l'autoriser dans leur BIOS, comme pour tout Linux.

iPXE 2.0 et wimboot ne sont pas dans les dépôts Debian et Ubuntu : le service les télécharge
depuis les releases officielles d'iPXE, comme il le fait pour CloneGator. C'est la seule exception
à la règle « rien hors des dépôts » (§15).

---

## 11. L'interface

Une interface texte, comme CloneGator : `sudo gatorpxe`, par SSH ou sur l'écran du serveur. Même
présentation, mêmes touches, `F2` pour la langue (anglais par défaut, français).

**L'accueil montre l'état d'un coup d'œil** :

- le service : actif ou non ; le proxy DHCP : actif, sur quelle carte réseau ;
- le menu tel que les postes le voient : CloneGator (et sa version), les images trouvées, les
  renvois ; les fichiers ignorés et pourquoi ; un dossier d'images introuvable ;
- les derniers postes qui ont démarré : heure, adresse, BIOS ou UEFI, entrée choisie.

**Les réglages**, un écran chacun :

- proxy DHCP actif ou coupé (et, coupé, les réglages à faire dans son DHCP), carte réseau ;
- dossier des images ;
- CloneGator au menu ou non ;
- renvois : ajouter, modifier, retirer, ordonner ;
- délai du menu et entrée par défaut.

## 12. Emplacements

| Quoi | Où |
|------|-----|
| Réglages | `/etc/gatorpxe/gatorpxe.json`, écrit par l'interface |
| Images | `/srv/gatorpxe/images` par défaut, ou tout autre dossier choisi dans l'interface |
| Téléchargé et préparé par le service | `/var/lib/gatorpxe` : CloneGator, chargeurs iPXE, wimboot, fichiers extraits des ISO Windows, menu généré |
| Journaux | `/var/log/gatorpxe` |

Si le dossier d'images devient introuvable (disque externe débranché), les postes voient quand
même le menu, avec CloneGator et les renvois ; l'interface le signale. Le service ne s'arrête
jamais pour ça.

## 13. Journalisation

Le service consigne dans `/var/log/gatorpxe` : ses démarrages, les réglages relus, les images
ajoutées ou retirées, les mises à jour de CloneGator et d'iPXE, et **chaque démarrage de poste**
(heure, adresse MAC et IP, BIOS ou UEFI, fichiers demandés). C'est ce qui permet de répondre à « ce
poste a-t-il bien démarré sur le serveur ? ».

## 14. Livraison

Un paquet `.deb` pour Debian 13 et Ubuntu 24.04, publié par le dépôt APT de GatorTools :

```bash
wget -qO- gatortools.github.io/apt/install.sh | sudo sh
sudo apt install gatorpxe
```

- dépendances : `python3`, `dnsmasq-base` (le programme seul, sans le service système),
  `lighttpd`, `7zip` (pour extraire les fichiers d'une ISO Windows : elles sont au format
  UDF, que 7zip lit sans monter l'image) ;
- à l'installation : le service démarre, proxy DHCP actif ; si lighttpd n'était pas installé avant,
  son serveur web par défaut (port 80) est désactivé, jamais s'il l'était déjà (P3) ;
- à la désinstallation : le service s'arrête ; les images et les réglages restent.

## 15. Langage et règles

Les mêmes que CloneGator :

- **Python 3, bibliothèque standard seule.** Aucune dépendance hors des dépôts Debian et Ubuntu,
  sauf iPXE et wimboot, téléchargés depuis les releases d'iPXE (§10).
- **Python orchestre, il ne sert pas.** Les fichiers passent par dnsmasq et lighttpd.
- **Un seul point de passage vers le système**, pour tous les appels de commandes et lectures de
  `/sys` et `/proc`, avec un délai sur chaque commande et un journal verbatim.
- Tout ce que voit l'opérateur passe par la traduction (anglais par défaut, français) ; le code, les
  commentaires, les commits et les documents sont en français.

## 16. À vérifier par des essais

Ce que l'analyse promet mais que seul un essai sur de vrais postes et de vrais réseaux peut
confirmer. Chaque point deviendra une étape d'essai du plan de développement ; un essai qui échoue
fait revoir la section concernée.

- Le renvoi vers WDS, en BIOS et en UEFI, avec Secure Boot actif.
- ~~Le DHCP réglé à la main avec l'iPXE signé~~ : fait sur le réseau d'essai (§9).
- ~~Les ISO Linux courantes en sanboot~~ : faites, résultats au §6.
- L'extraction des ISO Windows récentes (Windows 11) et leur démarrage par wimboot.
- Le proxy DHCP à côté des DHCP courants : Windows Server, pfSense, routeurs grand public.

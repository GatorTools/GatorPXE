# GatorPXE — consignes de travail

Serveur de démarrage réseau (PXE) de la famille GatorTools : installé sur un
serveur Debian ou Ubuntu, il propose aux postes du réseau un menu construit
tout seul — CloneGator, des images démarrables déposées dans un dossier, des
renvois vers d'autres serveurs (WDS…).

**État : version d'essai publiée (apt install gatorpxe).** Analyse fonctionnelle (révision 0.13) et plan de
développement (révision 0.15) ; recette en cours chez Kevin ; phases 1, 2 et 5 faites, en attente de la revue de Kevin ; phases 3 et 4 en cours (ISO d'installation de Windows 11 et WDS restent).

## Les documents font foi

- [ANALYSE-FONCTIONNELLE.md](ANALYSE-FONCTIONNELLE.md) — ce que le logiciel doit faire
- [PLAN-DE-DEVELOPPEMENT.md](PLAN-DE-DEVELOPPEMENT.md) — dans quel ordre on le construit

Ce sont des **documents vivants**. Quand une décision les contredit, les mettre
à jour — signaler la contradiction en une phrase, livrer, puis réécrire la
section concernée et ajouter une ligne au tableau de révisions. Ne jamais
laisser le code s'écarter d'une spec figée en silence.

## Comment travailler avec Kevin

- **Un point à la fois.** Les décisions de conception se discutent une question
  à la fois, en partant de la vision de Kevin : une recommandation claire, puis
  « d'accord ? ». Jamais une liste de questions d'un coup.
- **Le minimum en première version.** Ne pas prévoir de mécanisme pour un
  besoin qui n'est pas confirmé ; une amélioration possible se mentionne en
  une ligne, sans la détailler.
- **Des textes courts et clairs** pour tout ce qui s'affiche (interface, site) :
  l'information d'abord, une phrase d'accroche au plus.
- **Autonomie** : commits et poussées sans demander ; s'arrêter en fin de phase
  ou pour une question. Ne publier une release (et reconstruire ce qui est
  long) qu'en fin de phase, après la revue de Kevin.

## Les règles, héritées de CloneGator (§15 de l'analyse)

- **Python 3, bibliothèque standard seule.** Aucune dépendance hors des dépôts
  Debian et Ubuntu, sauf iPXE et wimboot, téléchargés depuis les
  releases d'iPXE. Si un besoin semble réclamer autre chose, le signaler.
- **Python orchestre, il ne sert pas.** Les fichiers passent par dnsmasq et
  lighttpd, en instances propres à GatorPXE.
- **Un seul point de passage vers le système** pour toute commande externe et
  toute lecture de `/sys` ou `/proc`, avec un délai sur chaque commande et un
  journal verbatim (comme `clonegator/sysexec.py`).
- **Langue** : tout ce que voit l'opérateur passe par `t()` (anglais par défaut,
  français), le texte français servant de clé. Le reste — code, commentaires,
  commits, documents — est en français.
- **Interface texte**, avec la présentation, les touches et `F2` de CloneGator.

## L'organisation GatorTools

Organisation GitHub `GatorTools`, compte `kevin-belanger` (administrateur),
`gh` connecté sur la station.

| Dépôt | Rôle | Copie locale |
|-------|------|--------------|
| `GatorTools/CloneGator` | clonage, sauvegarde, restauration ; releases `.deb` et ISO live | `/root/clonegator` |
| `GatorTools/GatorPXE` | ce projet | `/root/GatorPXE` |
| `GatorTools/GatorTools.github.io` | le site, `gatortools.github.io` | `/root/GatorTools.github.io` |
| `GatorTools/apt` | le dépôt APT signé, `gatortools.github.io/apt` | `/root/GatorTools-apt` |

- **Dépôt APT** : un workflow reprend chaque heure les `.deb` des trois
  dernières releases des dépôts listés dans `logiciels.txt`. Pour publier
  GatorPXE par apt, ajouter une ligne `GatorTools/GatorPXE` ; ses releases
  doivent porter des paquets nommés `nom_version_architecture.deb`. La clé de
  signature est le secret `CLE_SIGNATURE` du dépôt `apt` (copie hors ligne
  chez Kevin).
- **CloneGator** : chaque release porte `clonegator-live-pxe.tar` (shim signé de
  Debian, noyau, initrd, système compressé), le démarrage réseau de son live,
  publié pour n'importe quel serveur PXE (§15 de son analyse). GatorPXE le prend
  là ; CloneGator ne sait rien de GatorPXE, et doit le rester.
- **Site** : la page `gatorpxe/` présente le projet « en préparation » ; la
  mettre à jour quand il deviendra disponible.

## Environnement

Station de test sous Ubuntu 24.04, **root comme seul utilisateur**, commandes
sans `sudo`. Cinq SSD d'essai dans les baies, sacrifiables. **Le réseau de
la station porte un WDS de production** : jamais de proxy DHCP ni de serveur de
démarrage sur une carte physique ; tous les essais se font dans le réseau de VM
isolé du plan (§1.2), qui ne sort que par NAT. Sur la station, le service tourne
depuis le paquet installé, réglé sur le pont d'essai (`/etc/gatorpxe/gatorpxe.json`) :
pour essayer du code, construire le paquet et l'installer
(`./outils/construire-paquet.sh`, puis `apt install ./dist/…`). Pas de
virtualisation matérielle : QEMU tourne en émulation (lent, mais utilisable
pour démarrer un poste virtuel en PXE). Partage réseau d'essai de Kevin :
`//10.150.19.15/kevin`, identifiants dans
`/root/.config/clonegator-essais/partage-essai.cred` — ne jamais écrire le mot
de passe dans un dépôt, un commit ou un journal.

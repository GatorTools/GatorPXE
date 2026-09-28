# GatorPXE — consignes de travail

Serveur de démarrage réseau (PXE) de la famille GatorTools : installé sur un
serveur Debian ou Ubuntu, il propose aux postes du réseau un menu construit
tout seul — CloneGator, des images démarrables déposées dans un dossier, des
renvois vers d'autres serveurs (WDS…).

**État : rien n'est codé.** L'analyse fonctionnelle est écrite (révision 0.2) ;
Kevin doit la relire, puis viendra le plan de développement.

## Les documents font foi

- [ANALYSE-FONCTIONNELLE.md](ANALYSE-FONCTIONNELLE.md) — ce que le logiciel doit faire
- `PLAN-DE-DEVELOPPEMENT.md` — dans quel ordre on le construit (à écrire)

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
  Debian et Ubuntu, sauf l'iPXE signé et wimboot, téléchargés depuis les
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
- **CloneGator** : ce dont GatorPXE a besoin de lui est au §17 de son analyse —
  joindre aux releases les fichiers de démarrage réseau du live (noyau, initrd,
  système compressé), que `outils/construire-live.sh` produit déjà.
- **Site** : la page `gatorpxe/` présente le projet « en préparation » ; la
  mettre à jour quand il deviendra disponible.

## Environnement

Station de test sous Ubuntu 24.04, **root comme seul utilisateur**, commandes
sans `sudo`. Cinq SSD d'essai dans les baies, sacrifiables. Pas de
virtualisation matérielle : QEMU tourne en émulation (lent, mais utilisable
pour démarrer un poste virtuel en PXE). Partage réseau d'essai de Kevin :
`//10.150.19.15/kevin`, identifiants dans
`/root/.config/clonegator-essais/partage-essai.cred` — ne jamais écrire le mot
de passe dans un dépôt, un commit ou un journal.

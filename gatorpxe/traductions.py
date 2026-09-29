"""Le catalogue anglais de l'interface : texte français → texte anglais.

Les champs entre accolades ({n}…) se retrouvent tels quels dans la traduction.
Le test `tests.test_traductions` vérifie que chaque `t()` du code a son entrée
ici, avec les mêmes champs.
"""

ANGLAIS: dict[str, str] = {
    # ------------------------------------------------------------- lancement
    "GatorPXE doit être lancé en root :  sudo gatorpxe": "GatorPXE must be run as root:  sudo gatorpxe",

    # -------------------------------------------------- menu de démarrage (§5)
    "Démarrer sur le disque local": "Boot from local disk",
    "Retour": "Back",
    "Le démarrage a échoué.": "Boot failed.",
    "Appuyez sur une touche pour revenir au menu.": "Press a key to return to the menu.",
    "incompatible réseau": "no network boot",
    "sans Secure Boot": "no Secure Boot",
    "pas en UEFI pour l'instant": "not in UEFI for now",

    # ---------------------------------------------------------------- touches
    "Choisir": "Select",
    "Entrée": "Enter",
    "Valider": "Confirm",
    "Échap": "Esc",
    "Quitter": "Quit",
    "Champ suivant, puis valider": "Next field, then confirm",
    "Faire défiler": "Scroll",
    "Revenir": "Back",
    "Annuler": "Cancel",
    "Langue": "Language",
    "Changer de langue": "Change language",

    # ---------------------------------------------------------------- accueil
    "Serveur de démarrage réseau": "Network boot server",
    "Un projet GatorTools": "A GatorTools project",
    "Lecture de l'état…": "Reading the status…",
    "Service actif": "Service running",
    "Service arrêté": "Service stopped",
    "Service": "Service",
    "actif": "running",
    "arrêté : les postes ne sont pas servis": "stopped: computers are not served",
    "démarrage en cours…": "starting…",
    "Réseau": "Network",
    "aucune carte réseau : choisissez-en une": "no network card: choose one",
    "la carte {carte} n'a pas d'adresse IPv4": "card {carte} has no IPv4 address",
    "iPXE pas encore téléchargé : accès à Internet ?": "iPXE not downloaded yet: Internet access?",
    "dnsmasq ou lighttpd arrêté : relance en cours": "dnsmasq or lighttpd stopped: restarting",
    "{carte}, {adresse} ; proxy DHCP actif": "{carte}, {adresse}; proxy DHCP on",
    "{carte}, {adresse} ; proxy DHCP coupé : votre DHCP désigne le serveur":
        "{carte}, {adresse}; proxy DHCP off: your DHCP points to the server",
    "Menu": "Menu",
    "CloneGator (téléchargement…)": "CloneGator (downloading…)",
    "{n} image(s)": "{n} image(s)",
    "{n} renvoi(s)": "{n} redirect(s)",
    "dossier d'images introuvable : {dossier}": "image folder not found: {dossier}",
    "{n} fichier(s) écarté(s) : voir le menu de démarrage": "{n} file(s) left out: see the boot menu",
    "Pare-feu": "Firewall",
    "ufw actif : ouvrez les ports {ports} (67, 69 et 4011 en UDP, {http} en TCP)":
        "ufw is on: open ports {ports} (67, 69 and 4011 UDP, {http} TCP)",
    "Derniers postes": "Recent computers",
    "aucun pour l'instant": "none yet",
    "disque local, ou un renvoi": "local disk, or a redirect",
    "Menu de démarrage": "Boot menu",
    "Ce que voient les postes, et les fichiers écartés": "What computers see, and files left out",
    "Qui a démarré, quand, sur quoi": "Who booted, when, into what",
    "Réseau et DHCP": "Network and DHCP",
    "Proxy DHCP, carte réseau": "Proxy DHCP, network card",
    "Dossier des images": "Image folder",
    "Au menu": "In the menu",
    "Retiré du menu": "Removed from the menu",
    "Renvois": "Redirects",
    "Vers d'autres serveurs de démarrage": "To other boot servers",
    "Délai et entrée par défaut": "Timeout and default entry",
    "{n} s, puis {entree}": "{n} s, then {entree}",
    "disque local": "local disk",

    # ------------------------------------------------------------------ menu
    "Dans l'ordre où les postes le voient. Au bout de {n} s : {entree}.":
        "In the order computers see it. After {n} s: {entree}.",
    "pas encore téléchargé": "not downloaded yet",
    "Dossier d'images introuvable : {dossier}": "Image folder not found: {dossier}",
    "Fichiers écartés": "Files left out",
    "format non reconnu": "unknown format",
    "illisible par le serveur web : droits de lecture manquants": "unreadable by the web server: missing read permission",
    "en cours de copie": "being copied",
    "ISO Windows en préparation": "Windows ISO being prepared",
    "Heure, adresse matérielle, adresse IP, BIOS ou UEFI, entrée choisie.":
        "Time, MAC address, IP address, BIOS or UEFI, chosen entry.",
    "Aucun poste n'a encore démarré sur ce serveur.": "No computer has booted from this server yet.",

    # -------------------------------------------------------------- réglages
    "Réglages": "Settings",
    "Réglages non enregistrés : {erreur}": "Settings not saved: {erreur}",
    "Réglages enregistrés. Le service est arrêté : ils serviront à son démarrage.":
        "Settings saved. The service is stopped: they will apply when it starts.",
    "Réglages enregistrés, mais le service ne les a pas relus.": "Settings saved, but the service did not reload them.",
    "Le proxy DHCP ne répond qu'aux postes qui démarrent par le réseau.":
        "The proxy DHCP only answers computers booting from the network.",
    "Proxy DHCP": "Proxy DHCP",
    "coupé": "off",
    "Carte réseau": "Network card",
    "automatique ({carte})": "automatic ({carte})",
    "Réglages pour votre DHCP": "Settings for your DHCP",
    "À saisir quand le proxy DHCP est coupé": "To enter when the proxy DHCP is off",
    "Actif": "On",
    "Coupé": "Off",
    "Rien à régler sur votre DHCP": "Nothing to set on your DHCP",
    "Votre DHCP désigne le serveur et ses fichiers": "Your DHCP points to the server and its files",
    "Automatique": "Automatic",
    "la carte principale ({carte})": "the main card ({carte})",
    "sans adresse IPv4": "no IPv4 address",
    "Le proxy DHCP et le TFTP ne répondent que sur cette carte.": "The proxy DHCP and TFTP only answer on this card.",
    "(adresse du serveur)": "(server address)",
    "Serveur": "Server",
    "option 66, ou « next-server »": "option 66, or \"next-server\"",
    "Fichier UEFI": "UEFI file",
    "Fichier BIOS": "BIOS file",
    "option 67, selon l'architecture du poste (option 93 : 7 ou 9 en UEFI, 0 en BIOS)":
        "option 67, by client architecture (option 93: 7 or 9 for UEFI, 0 for BIOS)",
    "En BIOS seulement, pour éviter une boucle :": "For BIOS only, to avoid a loop:",
    "si la classe utilisateur (option 77) vaut « iPXE », le fichier devient":
        "when the user class (option 77) is \"iPXE\", the file becomes",
    "En UEFI, rien de plus : iPXE trouve le menu de lui-même.": "For UEFI, nothing more: iPXE finds the menu by itself.",
    "À saisir dans votre DHCP (Windows Server, routeur…) si le proxy DHCP est coupé.":
        "To enter in your DHCP (Windows Server, router…) when the proxy DHCP is off.",
    "Dossier": "Folder",
    "Déposer une image ici suffit : elle paraît au menu. Un sous-dossier donne un sous-menu.":
        "Dropping an image here is enough: it shows in the menu. A subfolder gives a submenu.",
    "Dossier introuvable : {dossier}": "Folder not found: {dossier}",
    "Tenu à jour chaque jour ; version {v}": "Updated daily; version {v}",
    "Plus téléchargé": "No longer downloaded",
    "Sans choix de l'opérateur, le menu démarre l'entrée par défaut au bout du délai.":
        "If nobody chooses, the menu boots the default entry after the timeout.",
    "Délai": "Timeout",
    "{n} s": "{n} s",
    "Entrée par défaut": "Default entry",
    "Secondes": "Seconds",
    "0 : le menu attend un choix.": "0: the menu waits for a choice.",
    "Un nombre de secondes, de 0 à 3600.": "A number of seconds, from 0 to 3600.",
    "Disque local": "Local disk",
    "Recommandé": "Recommended",
    "retiré du menu": "removed from the menu",

    # --------------------------------------------------------------- renvois
    "Des entrées du menu vers d'autres serveurs de démarrage, dans cet ordre.":
        "Menu entries to other boot servers, in this order.",
    "Ajouter un renvoi": "Add a redirect",
    "Modifier": "Edit",
    "Monter": "Move up",
    "Descendre": "Move down",
    "Retirer": "Remove",
    "Retirer « {nom} » du menu ?": "Remove \"{nom}\" from the menu?",
    "Renvoi": "Redirect",
    "Type": "Type",
    "Adresse": "Address",
    "Quel type de serveur ?": "What kind of server?",
    "Windows Deployment Services, ou MECM/SCCM": "Windows Deployment Services, or MECM/SCCM",
    "Un autre serveur iPXE, FOG, netboot.xyz…": "Another iPXE server, FOG, netboot.xyz…",
    "PXE générique": "Generic PXE",
    "Tout autre serveur : pxelinux, GRUB…": "Any other server: pxelinux, GRUB…",
    "Nom au menu": "Menu name",
    "Adresse du script": "Script address",
    "L'adresse du serveur WDS : GatorPXE connaît les fichiers à demander.":
        "The WDS server address: GatorPXE knows which files to ask for.",
    "L'adresse du script de démarrage, en http:// ou https://.": "The boot script address, http:// or https://.",
    "Le serveur, et le fichier à charger en BIOS et en UEFI ; un seul suffit.":
        "The server, and the file to load for BIOS and for UEFI; one is enough.",
    "Donnez un nom : c'est lui qui paraît au menu.": "Give a name: it is what the menu shows.",
    "L'adresse est vide ou contient une espace.": "The address is empty or contains a space.",
    "L'adresse du script commence par http:// ou https://.": "The script address starts with http:// or https://.",
    "Donnez au moins un fichier, BIOS ou UEFI.": "Give at least one file, BIOS or UEFI.",
}

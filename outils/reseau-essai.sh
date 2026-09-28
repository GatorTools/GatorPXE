#!/bin/sh
# Réseau d'essai isolé de GatorPXE (plan §1.2).
#
#   reseau-essai.sh monter          le pont, le DHCP « existant », la sortie par NAT
#   reseau-essai.sh demonter        tout retirer, postes compris
#   reseau-essai.sh poste NOM MODE [IMAGE]
#                                   démarrer un poste QEMU en démarrage réseau ;
#                                   MODE : bios, uefi ou sb (UEFI Secure Boot) ;
#                                   IMAGE : son disque local, jamais modifié
#                                   (une ISO hybride démarrable, par exemple)
#   reseau-essai.sh ecran NOM       capture d'écran du poste (PNG)
#   reseau-essai.sh touches NOM T…  envoyer des touches au poste (noms QEMU : ret, down…)
#   reseau-essai.sh arreter NOM     arrêter un poste
#
# Le réseau de la station porte un WDS de production : aucune carte physique
# n'entre jamais dans le pont. Les postes sortent par NAT, dans ce sens
# seulement ; aucune diffusion (DHCP, démarrage réseau) ne franchit la station.
#
# Adresses : pont 192.168.199.0/24 ; la station (le serveur GatorPXE) en .1 ;
# le DHCP « existant », dans son espace de noms réseau, en .2, distribue
# .100 à .199 avec la station pour passerelle.
set -eu

PONT=gpxe-pont
NS=gpxe-dhcp
RESEAU=192.168.199
ETAT=/var/tmp/gatorpxe-essai
TABLE=gatorpxe_essai

mourir() { echo "reseau-essai : $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || mourir "il faut root"

monter() {
    mkdir -p "$ETAT"
    if ! ip link show "$PONT" >/dev/null 2>&1; then
        ip link add "$PONT" type bridge
        ip addr add "$RESEAU.1/24" dev "$PONT"
        ip link set "$PONT" up
    fi

    # Le DHCP « existant » : un dnsmasq ordinaire, isolé dans son espace de noms.
    if ! ip netns list | grep -qw "$NS"; then
        ip netns add "$NS"
        ip link add gpxe-dhcp0 type veth peer name gpxe-dhcp1
        ip link set gpxe-dhcp1 netns "$NS"
        ip link set gpxe-dhcp0 master "$PONT" up
        ip -n "$NS" addr add "$RESEAU.2/24" dev gpxe-dhcp1
        ip -n "$NS" link set gpxe-dhcp1 up
        ip -n "$NS" link set lo up
    fi
    if [ ! -f "$ETAT/dhcp.pid" ] || ! kill -0 "$(cat "$ETAT/dhcp.pid")" 2>/dev/null; then
        ip netns exec "$NS" dnsmasq \
            --conf-file=/dev/null --port=0 --interface=gpxe-dhcp1 --bind-interfaces \
            --dhcp-range="$RESEAU.100,$RESEAU.199,255.255.255.0,1h" \
            --dhcp-option=option:router,"$RESEAU.1" \
            --dhcp-option=option:dns-server,1.1.1.1,9.9.9.9 \
            --dhcp-leasefile="$ETAT/dhcp.baux" \
            --log-dhcp --log-facility="$ETAT/dhcp.log" \
            --pid-file="$ETAT/dhcp.pid"
    fi

    # Sortie par NAT : le pont vers le reste, et les réponses seulement en retour.
    sysctl -q net.ipv4.ip_forward=1
    nft delete table inet "$TABLE" 2>/dev/null || true
    nft -f - <<FIN
table inet $TABLE {
    chain transit {
        type filter hook forward priority 0; policy accept;
        iifname "$PONT" oifname != "$PONT" accept
        oifname "$PONT" ct state established,related accept
        oifname "$PONT" drop
    }
    chain sortie {
        type nat hook postrouting priority 100;
        ip saddr $RESEAU.0/24 oifname != "$PONT" masquerade
    }
}
FIN
    echo "réseau d'essai monté : $PONT ($RESEAU.1), DHCP existant en $RESEAU.2"
}

demonter() {
    for f in "$ETAT"/poste-*.pid; do
        [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true
        rm -f "$f"
    done
    [ -f "$ETAT/dhcp.pid" ] && kill "$(cat "$ETAT/dhcp.pid")" 2>/dev/null || true
    rm -f "$ETAT/dhcp.pid"
    nft delete table inet "$TABLE" 2>/dev/null || true
    ip netns del "$NS" 2>/dev/null || true
    ip link del gpxe-dhcp0 2>/dev/null || true
    for t in $(ip -br link | awk '/^gpxe-t-/ {print $1}' | cut -d@ -f1); do
        ip link del "$t"
    done
    ip link del "$PONT" 2>/dev/null || true
    # Le routage reste tel quel : d'autres usages de la station peuvent en dépendre.
    echo "réseau d'essai démonté"
}

poste() {
    nom=$1 mode=$2 image=${3:-}
    ip link show "$PONT" >/dev/null 2>&1 || mourir "réseau non monté"
    tap="gpxe-t-$nom"
    [ ${#tap} -le 15 ] || mourir "nom trop long : $nom"
    ip link show "$tap" >/dev/null 2>&1 || ip tuntap add "$tap" mode tap
    ip link set "$tap" master "$PONT" up

    # Adresse MAC stable par nom de poste, pour reconnaître les postes au journal.
    mac=$(printf '%s' "$nom" | md5sum | sed 's/^\(..\)\(..\)\(..\).*/52:54:00:\1:\2:\3/')
    if [ -n "$image" ]; then
        [ -f "$image" ] || mourir "image introuvable : $image"
        disque="file=$image,format=raw,snapshot=on"
    else
        [ -f "$ETAT/poste-$nom.qcow2" ] || qemu-img create -q -f qcow2 "$ETAT/poste-$nom.qcow2" 8G
        disque="file=$ETAT/poste-$nom.qcow2,format=qcow2"
    fi

    case $mode in
        bios)
            micro="" ;;
        uefi)
            [ -f "$ETAT/poste-$nom.vars" ] || cp /usr/share/OVMF/OVMF_VARS_4M.fd "$ETAT/poste-$nom.vars"
            micro="-drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd
                   -drive if=pflash,format=raw,file=$ETAT/poste-$nom.vars" ;;
        sb)
            [ -f "$ETAT/poste-$nom.vars" ] || cp /usr/share/OVMF/OVMF_VARS_4M.ms.fd "$ETAT/poste-$nom.vars"
            micro="-machine q35,smm=on -global driver=cfi.pflash01,property=secure,value=on
                   -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd
                   -drive if=pflash,format=raw,file=$ETAT/poste-$nom.vars" ;;
        *) mourir "mode inconnu : $mode (bios, uefi ou sb)" ;;
    esac

    # shellcheck disable=SC2086
    qemu-system-x86_64 $micro -m 2048 -smp 2 \
        -netdev tap,id=n0,ifname="$tap",script=no,downscript=no \
        -device virtio-net-pci,netdev=n0,mac="$mac",bootindex=1 \
        -drive "$disque",if=none,id=d0 -device virtio-blk-pci,drive=d0,bootindex=2 \
        -display none -vga std \
        -serial file:"$ETAT/poste-$nom.console" \
        -monitor unix:"$ETAT/poste-$nom.moniteur",server,nowait \
        -pidfile "$ETAT/poste-$nom.pid" -daemonize
    echo "poste $nom ($mode, $mac) démarré ; console : $ETAT/poste-$nom.console"
}

moniteur() {
    python3 - "$ETAT/poste-$1.moniteur" "$2" <<'FIN'
import socket, sys, time
s = socket.socket(socket.AF_UNIX)
s.connect(sys.argv[1])
s.sendall(sys.argv[2].encode() + b"\n")
time.sleep(0.5)
FIN
}

ecran() {
    rm -f "$ETAT/poste-$1.png"
    moniteur "$1" "screendump $ETAT/poste-$1.png -f png"
    sleep 1
    echo "$ETAT/poste-$1.png"
}

touches() {
    nom=$1; shift
    for t in "$@"; do moniteur "$nom" "sendkey $t"; done
}

arreter() {
    f="$ETAT/poste-$1.pid"
    [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
    ip link del "gpxe-t-$1" 2>/dev/null || true
}

case ${1:-} in
    monter) monter ;;
    demonter) demonter ;;
    poste) [ $# -ge 3 ] || mourir "usage : poste NOM MODE [IMAGE]"; poste "$2" "$3" "${4:-}" ;;
    ecran) ecran "$2" ;;
    touches) shift; touches "$@" ;;
    arreter) arreter "$2" ;;
    *) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac

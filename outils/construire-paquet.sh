#!/usr/bin/env bash
#
# Construit le paquet .deb de GatorPXE dans dist/ (§14 de l'analyse).
#
#   ./outils/construire-paquet.sh
#
# La version du paquet est celle de gatorpxe/__init__.py, complétée de la
# date et de l'heure du commit, et de son hachage : ce qui s'exécute doit
# toujours pouvoir être retrouvé. Un dépôt modifié mais non commité est refusé,
# pour la même raison.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain -- gatorpxe paquet)" ]; then
    echo "Des changements ne sont pas commités dans gatorpxe/ ou paquet/ : commitez d'abord." >&2
    exit 1
fi

base=$(python3 -c 'import gatorpxe; print(gatorpxe.VERSION)')
commit=$(git rev-parse --short HEAD)
# Date et heure du commit, à la minute : deux versions du même jour se suivent
# dans l'ordre, et apt accepte la mise à jour (le hachage seul n'est pas ordonné).
quand=$(git log -1 --format=%cd --date=format-local:%Y%m%d%H%M)
version="${base/-dev/~dev}+${quand}.g${commit}"

racine=$(mktemp -d)
trap 'rm -rf "$racine"' EXIT

install -d "$racine/DEBIAN" "$racine/usr/bin" "$racine/usr/lib/gatorpxe" \
           "$racine/usr/lib/systemd/system" "$racine/usr/share/doc/gatorpxe"
git archive HEAD gatorpxe | tar -x -C "$racine/usr/lib/gatorpxe"
# La version affichée par le logiciel est exactement celle du paquet.
sed -i "s/^VERSION = .*/VERSION = \"$version\"/" "$racine/usr/lib/gatorpxe/gatorpxe/__init__.py"

install -m 755 paquet/gatorpxe "$racine/usr/bin/gatorpxe"
install -m 644 paquet/gatorpxe.service "$racine/usr/lib/systemd/system/gatorpxe.service"
install -m 644 README.md "$racine/usr/share/doc/gatorpxe/README.md"
install -m 644 LICENSE "$racine/usr/share/doc/gatorpxe/copyright"
install -m 755 paquet/postinst paquet/prerm paquet/postrm "$racine/DEBIAN/"
sed "s/@VERSION@/$version/" paquet/control > "$racine/DEBIAN/control"

mkdir -p dist
dpkg-deb --root-owner-group --build "$racine" "dist/gatorpxe_${version}_all.deb" >/dev/null
echo "dist/gatorpxe_${version}_all.deb"

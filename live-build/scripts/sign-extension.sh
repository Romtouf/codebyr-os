#!/bin/sh
# sign-extension.sh — fait signer le bouclier anti-hameçonnage par Mozilla,
# puis l'installe dans le dépôt. Une seule commande, du début à la fin.
#
# POURQUOI C'EST OBLIGATOIRE : Firefox refuse de charger une extension non
# signée, et Codebyr n'abaisse plus ce contrôle (c'était un affaiblissement réel
# du navigateur). Un .xpi signé est SCELLÉ : modifier content.js dans le dépôt
# ne change rien tant que l'extension n'a pas été re-signée. D'où ce script.
#
# CE QU'IL FAUT, UNE SEULE FOIS :
#   1. un compte Firefox (le même que pour la synchronisation, si vous en avez un) ;
#   2. des identifiants d'API sur
#         https://addons.mozilla.org/fr/developers/addon/api/key/
#      (la page demande de se connecter d'abord : c'est normal, elle renvoie
#      ensuite sur le formulaire « Gérer les clés API » / « Manage API Keys »).
#      Elle donne deux valeurs : un « JWT issuer » et un « JWT secret ».
#   3. web-ext : `npm install -g web-ext` (déjà installé sur ce poste).
#
# COMMENT LUI DONNER LES IDENTIFIANTS (au choix) :
#   · un fichier ~/.codebyr-amo, HORS du dépôt, contenant :
#         AMO_KEY='user:12345678:123'
#         AMO_SECRET='le-long-secret'
#   · ou dans la commande :
#         AMO_KEY=... AMO_SECRET=... sh live-build/scripts/sign-extension.sh
#
# Le secret ne doit JAMAIS entrer dans le dépôt ni dans un message : il permet
# de publier des extensions sous votre identité.
set -e

REPO="${CODEBYR_REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
SRC="$REPO/live-build/config/includes.chroot_after_packages/usr/share/codebyr/antiphishing"
SIGNES="$SRC/signed"
OUT="$REPO/build-signature"
IDENTIFIANTS="${CODEBYR_AMO_FICHIER:-$HOME/.codebyr-amo}"

echo "==> Bouclier anti-hameçonnage — signature Mozilla"

# ── 1) Outil ────────────────────────────────────────────────────────────────
if command -v web-ext >/dev/null 2>&1; then
	WEBEXT="web-ext"
elif command -v npx >/dev/null 2>&1; then
	WEBEXT="npx --yes web-ext"
else
	echo "ERREUR : web-ext introuvable. Installez-le : npm install -g web-ext" >&2
	exit 1
fi

# ── 2) Identifiants ─────────────────────────────────────────────────────────
if [ -z "${AMO_KEY:-}" ] || [ -z "${AMO_SECRET:-}" ]; then
	if [ -f "$IDENTIFIANTS" ]; then
		# shellcheck disable=SC1090
		. "$IDENTIFIANTS"
	fi
fi
if [ -z "${AMO_KEY:-}" ] || [ -z "${AMO_SECRET:-}" ]; then
	cat >&2 <<AIDE
ERREUR : identifiants AMO absents.

  1. Ouvrez  https://addons.mozilla.org/fr/developers/addon/api/key/
     (connexion au compte Firefox demandée d'abord — c'est normal).
  2. Cliquez sur « Generate new credentials » / « Générer de nouveaux
     identifiants ». La page affiche alors :
        JWT issuer  →  ressemble à  user:12345678:123
        JWT secret  →  une longue chaîne, affichée UNE SEULE FOIS
  3. Créez le fichier $IDENTIFIANTS avec ces deux lignes :

        AMO_KEY='user:12345678:123'
        AMO_SECRET='collez-ici-le-secret'

  4. Relancez cette commande.
AIDE
	exit 1
fi

# ── 3) Version : AMO refuse deux fois le même numéro ────────────────────────
version="$(grep '"version"' "$SRC/manifest.json" | head -n1 \
	| sed 's/.*"version"[^"]*"\([^"]*\)".*/\1/')"
[ -n "$version" ] || { echo "ERREUR : version illisible dans manifest.json." >&2; exit 1; }
echo "    Version à signer : $version"
for ancien in "$SIGNES"/*.xpi; do
	[ -e "$ancien" ] || continue
	deja="$(basename "$ancien" .xpi | sed 's/.*-//')"
	if [ "$deja" = "$version" ]; then
		echo "ERREUR : la version $version a déjà été signée (voir $(basename "$ancien"))." >&2
		echo "         Mozilla refuse de signer deux fois le même numéro : montez" >&2
		echo "         la version dans $SRC/manifest.json, puis relancez." >&2
		exit 1
	fi
done

# ── 4) Dossier propre : on n'envoie QUE le code de l'extension ──────────────
# Signer $SRC directement embarquerait le sous-dossier signed/ (donc l'ancien
# .xpi, ~200 Ko) à l'intérieur du nouveau paquet.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp "$SRC/manifest.json" "$SRC/content.js" "$STAGE/"
[ -f "$SRC/.amo-upload-uuid" ] && cp "$SRC/.amo-upload-uuid" "$STAGE/"
echo "    Contenu envoyé : manifest.json, content.js"

# ── 5) Signature (canal « unlisted » : distribution privée, pas de revue) ───
mkdir -p "$OUT"
$WEBEXT sign --channel=unlisted \
	--source-dir "$STAGE" \
	--artifacts-dir "$OUT" \
	--api-key "$AMO_KEY" \
	--api-secret "$AMO_SECRET"

# web-ext met à jour ce marqueur : on le récupère pour les prochaines fois.
[ -f "$STAGE/.amo-upload-uuid" ] && cp "$STAGE/.amo-upload-uuid" "$SRC/"

# ── 6) Installation dans le dépôt ───────────────────────────────────────────
nouveau="$(ls -1t "$OUT"/*.xpi 2>/dev/null | head -n1)"
[ -n "$nouveau" ] || { echo "ERREUR : aucun .xpi produit." >&2; exit 1; }
mkdir -p "$SIGNES"
rm -f "$SIGNES"/*.xpi
cp "$nouveau" "$SIGNES/"
echo "==> Installé : $SIGNES/$(basename "$nouveau")"

# ── 7) Vérification : le .xpi correspond-il bien aux sources ? ──────────────
# Attention sous Windows : « python » existe souvent comme simple RACCOURCI vers
# le Microsoft Store — il répond à « command -v », affiche « Python est
# introuvable » et sort en erreur. On exige donc un interpréteur qui démarre
# vraiment, sinon on passe au candidat suivant.
PY=""
for essai in python3 python py; do
	if command -v "$essai" >/dev/null 2>&1 && "$essai" -c "import sys" >/dev/null 2>&1; then
		PY="$essai"
		break
	fi
done
if [ -z "$PY" ]; then
	echo "    (Python introuvable : vérification automatique du .xpi ignorée.)"
fi
if [ -n "$PY" ]; then
	"$PY" - "$SIGNES/$(basename "$nouveau")" "$SRC/content.js" <<'VERIF'
import sys, zipfile
xpi, source = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(xpi) as z:
    embarque = z.read("content.js").replace(b"\r\n", b"\n")
with open(source, "rb") as f:
    attendu = f.read().replace(b"\r\n", b"\n")
if embarque != attendu:
    sys.exit("ECHEC : le .xpi signe ne correspond pas a content.js du depot.")
print("    content.js du .xpi = content.js du depot : OK")
VERIF
	echo
	echo "Vérification complète :  $PY -m unittest discover -s tests"
fi

echo
echo "Terminé. Le bouclier corrigé partira dans la prochaine version :"
echo "  bash packaging/build-deb.sh   puis   bash packaging/publish-apt.sh"

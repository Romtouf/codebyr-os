# -*- coding: utf-8 -*-
"""Un compte Unix par Espace : les décisions, séparées du service privilégié.

── CE QUE CE CHANTIER CHANGE ───────────────────────────────────────────────
Jusqu'ici, tous les Espaces tournent sous le compte du bureau. Le bac à sable
les sépare par ce qu'ils VOIENT ; rien ne les sépare par ce qu'ils ont le DROIT
de toucher. Ce qui échappe au bac à sable — un descripteur qui fuit, un défaut
du noyau, un service lancé hors bwrap — retrouve l'accès à tous les autres
Espaces. Un compte Unix distinct par Espace fait de cette frontière une règle
du noyau, vérifiée à chaque ouverture de fichier.

── POURQUOI CE MODULE EST À PART ───────────────────────────────────────────
Ce qui suit décide QUI a le droit de demander QUOI, et sous quel compte un
Espace tournera. Ces décisions sont prises par un service qui tourne en root :
une erreur ici ne coûte pas une fonctionnalité, elle donne la machine. Elles
sont donc écrites sans accès au disque ni au réseau, et éprouvées une par une
(tests/test_comptes.py) — le service, lui, ne fait qu'exécuter.

── LES RÈGLES ──────────────────────────────────────────────────────────────
1. L'identité du demandeur vient du NOYAU (SO_PEERCRED), jamais d'un argument.
   Un client qui annonce « je suis l'utilisateur 1000 » n'est pas cru.
2. Un compte d'Espace ne peut RIEN demander. Sinon l'Espace « jetable »
   demanderait l'ouverture de « banque » et lirait ses fichiers — le chantier
   se retournerait contre lui-même.
3. Un Espace appartient à un utilisateur. Le nom du compte contient donc l'UID
   du propriétaire : deux utilisateurs de la même machine n'ont jamais le même
   Espace « travail ».
4. Rien de ce qui vient du client n'entre dans un chemin sans avoir été
   validé par une forme stricte.
"""
import re

# Le nom d'un compte Unix tient en 32 caractères ; « cbyr-<uid>-<espace> »
# laisse la place à un identifiant d'Espace de 20 caractères, ce que la forme
# ci-dessous impose déjà.
PREFIXE = "cbyr"
FORME_ESPACE = re.compile(r"[a-z][a-z0-9-]{0,19}\Z")
FORME_AFFICHAGE = re.compile(r"wayland-[0-9]{1,3}\Z")

# Racine des dossiers personnels des Espaces. Sous /var/lib et non sous le
# dossier de l'utilisateur : le compte du bureau ne doit pas pouvoir modifier
# ce qui appartient à un Espace, ni l'inverse.
RACINE_ESPACES = "/var/lib/codebyr/espaces"

# Les deux boîtes d'un Espace à compte dédié, PERSISTANTES — un fichier en
# route ne doit pas disparaître au redémarrage.
#
# · Départ : l'Espace y dépose ce qu'il envoie ailleurs ; le bureau relève.
#   Elle appartient à l'Espace ; le bureau y a un droit pour relever.
# · Arrivée : le bureau y dépose ce qu'on envoie à l'Espace ; l'Espace le
#   recueille à sa prochaine ouverture, en le RECOPIANT chez lui — un fichier
#   resté au bureau ne serait pas modifiable par l'Espace.
#
# Pourquoi des boîtes, et non une ouverture de l'Espace à chaque envoi : le
# lanceur relève les boîtes de TOUS les Espaces à chaque clic. S'il fallait
# pour cela ouvrir chaque compte d'Espace, chaque clic en coûterait autant.
#
# Ni l'une ni l'autre n'est dans le dossier de l'Espace : le bureau ne voit
# que ce que l'Espace a déposé exprès pour partir.
RACINE_ENVOIS = "/var/lib/codebyr/envois"
RACINE_ARRIVEES = "/var/lib/codebyr/arrivees"

# Dossier d'exécution d'un Espace : le sien, à la place où tout l'écosystème
# l'attend — /run/user/<uid de l'Espace>, exactement là où logind le mettrait
# s'il ouvrait une session pour ce compte. Root le crée, l'Espace le possède
# (0700), et root y présente les SEULS sockets auxquels cet Espace a droit.
#
# Il a remplacé en 1.16.0 un dossier à nous, /run/codebyr/passerelles/<compte>.
# Mesuré le 15/09/2026 : sous un chemin de notre invention, une application
# Flatpak ne démarre pas. Son bac à sable tente de créer « .dbus-proxy » sous
# ce chemin, remonte jusqu'à un dossier de root, et échoue — « Failed to sync
# with dbus proxy ». À sa place canonique, tout fonctionne.
#
# L'Espace peut y écrire, et il le faut : Flatpak y pose ses sockets. Cela ne
# lui donne aucune prise sur ce qu'on y présente — un montage lié ne peut être
# ni supprimé, ni renommé, ni remplacé par un lien piégé, fût-ce par le
# propriétaire du dossier (mesuré : « Device or resource busy » chaque fois).
#
# Le dossier d'exécution du BUREAU, lui, n'est jamais ouvert à un Espace —
# mesuré le 14/09/2026 : l'ouvrir rendait joignable le bus de session,
# c'est-à-dire la faille fermée en 1.1.0.
RACINE_RUNTIME = "/run/user"

# Dépôt : un dossier par Espace où le BUREAU dépose les sockets qu'il sert
# lui-même — notifications, filtre réseau. Root le tient, le bureau y écrit,
# l'Espace ne fait que le TRAVERSER.
#
# Ce n'est PAS le dossier d'exécution du bureau, et la différence est toute la
# leçon du 14/09/2026 : celui-là contient le bus de session, qu'aucun Espace ne
# doit joindre. Un dépôt ne contient que les sockets de CET Espace, déposées
# pour lui. L'Espace n'y reçoit ni lecture ni écriture : il ne peut donc ni
# découvrir ce qui s'y trouve, ni y fabriquer une socket pour se faire passer
# pour l'hôte auprès d'un autre.
RACINE_DEPOTS = "/run/codebyr/depots"

# Les sockets que le bureau dépose, et le chemin où chacune apparaît DANS
# l'Espace. Écrits ici parce que deux moitiés du système doivent s'accorder
# dessus : celle qui les crée (codebyr-space) et celle qui les monte
# (bac_a_sable.wrap_bwrap).
SOCKETS_DU_BUREAU = {"notif": "/run/codebyr-notif", "proxy": "/run/codebyr-proxy"}

# La socket par laquelle le bureau commande le premier processus de l'Espace.
# Elle vit dans le dépôt, mais n'est JAMAIS montée dans le bac à sable, et elle
# ne figure donc pas ci-dessus. Un programme qui s'échapperait de bubblewrap ne
# doit pas pouvoir se relancer hors du bac à sable, fût-ce sous son propre
# compte : sans cela, le chantier rendrait l'évasion plus confortable.
SOCKET_EXEC = "exec"

# En deçà, ce sont les comptes du système. Un utilisateur de bureau a un UID
# d'au moins 1000 sur Debian.
UID_MINIMAL = 1000

# Combien d'Espaces un utilisateur peut avoir sous compte dédié. Le service
# écoute pour tout le monde : sans ce plafond, un utilisateur local pourrait
# demander l'ouverture d'Espaces aux noms sans cesse différents et faire créer
# des milliers de comptes système. Largement au-dessus d'un usage réel — cinq
# Espaces sont livrés — et très en deçà de ce qui gênerait la machine.
ESPACES_MAX_PAR_UTILISATEUR = 32


def trop_d_espaces(comptes_existants, uid_proprietaire, nom_demande):
    """Ce nouvel Espace dépasserait-il le plafond de son propriétaire ?

    Un Espace DÉJÀ créé ne compte pas comme un dépassement : on ne veut pas
    qu'un utilisateur arrivé au plafond ne puisse plus ouvrir ceux qu'il a.
    """
    prefixe = "%s-%d-" % (PREFIXE, uid_proprietaire)
    siens = [n for n in comptes_existants if n.startswith(prefixe)]
    return nom_demande not in siens and len(siens) >= ESPACES_MAX_PAR_UTILISATEUR


# Plafonds d'un Espace. La règle vit ICI et non dans le bac à sable, parce que
# c'est le service root qui les pose désormais : ce qui vient du client et
# entre dans une commande lancée par root se valide du côté des décisions.
MEMOIRE_DEFAUT = "2G"
TACHES_DEFAUT = 800
FORME_MEMOIRE = re.compile(r"[1-9][0-9]*[KMGT]|[1-9][0-9]?%|100%")


def espace_valide(espace):
    return bool(espace) and bool(FORME_ESPACE.match(espace))


def affichage_valide(nom):
    """« wayland-0 » et rien d'autre : ni chemin, ni « .. », ni nom exotique."""
    return bool(nom) and bool(FORME_AFFICHAGE.match(nom))


def nom_compte(uid_proprietaire, espace):
    """Le compte Unix d'un Espace, dérivé de son propriétaire et de son nom."""
    if not espace_valide(espace):
        raise ValueError("Identifiant d'Espace invalide")
    if not isinstance(uid_proprietaire, int) or uid_proprietaire < UID_MINIMAL:
        raise ValueError("Propriétaire invalide")
    nom = "%s-%d-%s" % (PREFIXE, uid_proprietaire, espace)
    if len(nom) > 32:
        raise ValueError("Nom de compte trop long")
    return nom


def est_compte_d_espace(nom):
    """Ce compte est-il celui d'un Espace ? (règle 2 : il ne demande rien)"""
    return bool(re.match(r"%s-[0-9]+-" % PREFIXE, nom or ""))


def decomposer(nom):
    """(uid du propriétaire, identifiant d'Espace) d'un compte d'Espace, ou None.

    Sert à l'Espace lui-même pour retrouver ses boîtes, à partir de son NOM DE
    COMPTE — que le noyau garantit — plutôt que d'un chemin qu'on lui
    transmettrait.
    """
    m = re.match(r"%s-([0-9]+)-(.+)\Z" % PREFIXE, nom or "")
    if not m or not espace_valide(m.group(2)):
        return None
    uid = int(m.group(1))
    return (uid, m.group(2)) if uid >= UID_MINIMAL else None


def demandeur_autorise(uid, nom):
    """Le noyau dit que l'appelant est (uid, nom) : a-t-il le droit de demander ?

    Renvoie (autorisé, raison). La raison est destinée au journal, pas au
    client : on ne renseigne pas qui essaie.
    """
    # L'appartenance à un Espace se vérifie AVANT l'UID, et non l'inverse : un
    # compte d'Espace est aujourd'hui un compte système, donc refusé par la
    # règle suivante — mais cela tient à l'attribution des UID par useradd, pas
    # à une décision de Codebyr. Le jour où les UID système manqueraient, un
    # compte d'Espace naîtrait au-dessus de 1000 et passerait.
    if est_compte_d_espace(nom):
        return False, "un Espace ne demande pas l'ouverture d'un autre Espace"
    if uid < UID_MINIMAL:
        return False, "compte système (UID %d)" % uid
    return True, ""


def chemin_home(uid_proprietaire, espace):
    """Dossier personnel de l'Espace. Un niveau par propriétaire."""
    if not espace_valide(espace):
        raise ValueError("Identifiant d'Espace invalide")
    if not isinstance(uid_proprietaire, int) or uid_proprietaire < UID_MINIMAL:
        raise ValueError("Propriétaire invalide")
    return "%s/%d/%s" % (RACINE_ESPACES, uid_proprietaire, espace)


def _chemin_par_proprietaire(racine, uid_proprietaire, espace):
    if not espace_valide(espace):
        raise ValueError("Identifiant d'Espace invalide")
    if not isinstance(uid_proprietaire, int) or uid_proprietaire < UID_MINIMAL:
        raise ValueError("Propriétaire invalide")
    return "%s/%d/%s" % (racine, uid_proprietaire, espace)


def chemin_envois(uid_proprietaire, espace):
    """Boîte de départ d'un Espace dédié. Le bureau la calcule sans le service."""
    return _chemin_par_proprietaire(RACINE_ENVOIS, uid_proprietaire, espace)


def chemin_arrivees(uid_proprietaire, espace):
    """Boîte d'arrivée d'un Espace dédié. Le bureau la calcule sans le service."""
    return _chemin_par_proprietaire(RACINE_ARRIVEES, uid_proprietaire, espace)


def chemin_runtime(uid_espace):
    """Dossier d'exécution d'un Espace, où root lui présente ses sockets.

    Nommé par l'UID et non par le compte : c'est la place que logind aurait
    donnée, et ce que Flatpak — comme le reste de l'écosystème — suppose.
    """
    # Un compte d'Espace est un compte SYSTÈME : son UID est sous UID_MINIMAL.
    # Refuser tout le reste, c'est rendre impossible par construction que ce
    # chemin désigne le dossier d'exécution d'un utilisateur — que la
    # fermeture efface en entier. Le profil AppArmor l'interdit aussi ; on ne
    # laisse pas la sécurité du bureau reposer sur une seule barrière.
    if not isinstance(uid_espace, int) or isinstance(uid_espace, bool) \
            or not 0 < uid_espace < UID_MINIMAL:
        raise ValueError("UID d'Espace invalide")
    return "%s/%d" % (RACINE_RUNTIME, uid_espace)


def chemin_depot(compte):
    """Dossier où le bureau dépose les sockets qu'il sert à CET Espace."""
    if not est_compte_d_espace(compte):
        raise ValueError("Dépôt demandé pour un compte qui n'est pas un Espace")
    return "%s/%s" % (RACINE_DEPOTS, compte)


def unite_de_l_espace(compte):
    """Nom du cgroup où vit tout l'Espace : plafonds posés une fois pour toutes.

    Une seule portée pour l'Espace entier, et non une par application lancée :
    c'est l'Espace qu'on veut empêcher d'épuiser la machine, pas chacune de ses
    fenêtres séparément.
    """
    if not est_compte_d_espace(compte):
        raise ValueError("Portée demandée pour un compte qui n'est pas un Espace")
    return "codebyr-espace-%s.scope" % compte


def socket_du_bureau(uid_proprietaire, nom):
    """Chemin d'un socket DANS le dossier d'exécution du bureau.

    Construit ici, à partir de l'UID donné par le noyau et d'un nom validé :
    le client ne fournit jamais de chemin.
    """
    if not isinstance(uid_proprietaire, int) or uid_proprietaire < UID_MINIMAL:
        raise ValueError("Propriétaire invalide")
    if nom not in ("wayland", "pipewire") and not affichage_valide(nom):
        raise ValueError("Socket inconnue")
    fichier = {"pipewire": "pipewire-0"}.get(nom, nom)
    return "/run/user/%d/%s" % (uid_proprietaire, fichier)


def plafonds_valides(memoire, taches):
    """Ramène un couple (mémoire, tâches) à des valeurs sûres.

    Une valeur mal formée est remplacée par le défaut, jamais refusée : un
    plafond qu'on ne comprend pas ne doit ni lever la protection, ni empêcher
    l'ouverture d'un Espace. Mais rien de ce qui vient du client n'entre tel
    quel dans une commande que root exécutera.
    """
    if not (isinstance(memoire, str) and FORME_MEMOIRE.fullmatch(memoire)):
        memoire = MEMOIRE_DEFAUT
    if not (isinstance(taches, int) and not isinstance(taches, bool)
            and 64 <= taches <= 32768):
        taches = TACHES_DEFAUT
    return memoire, taches


def passages(affichage, son):
    """Ce qu'un Espace reçoit : l'affichage toujours, le son s'il y a droit.

    Une liste, pas une exception : ce qui n'y figure pas ne traverse jamais.
    Le bus de session de l'hôte n'y est pas, et n'y sera pas — c'est lui qui
    donnait accès à systemd --user, donc à l'exécution hors du bac à sable.
    """
    if not affichage_valide(affichage):
        raise ValueError("Affichage invalide")
    demandes = [(affichage, affichage)]
    if son:
        demandes.append(("pipewire", "pipewire-0"))
    return demandes


class Tenues:
    """Combien de lanceurs tiennent chaque Espace ouvert — et quand le refermer.

    Chaque application ouverte dans un Espace est lancée par son propre
    `codebyr-space`. Sans ce compte, fermer une fenêtre refermerait l'Espace
    entier, et toutes les autres fenêtres avec.

    Le JETON règle une course précise. L'utilisateur ferme l'Espace d'un geste
    (tout s'arrête), puis le rouvre aussitôt. Les lanceurs de la première
    ouverture rendent alors leur tenue un à un, en retard : sans jeton, le
    dernier d'entre eux ferait tomber le compte à zéro et refermerait l'Espace
    qui vient d'être rouvert, sous les yeux de l'utilisateur.

    Aucun accès au disque, au réseau ni au temps : le service l'utilise sous
    verrou, les tests l'éprouvent tel quel.
    """

    def __init__(self, maximum=256):
        self.maximum = maximum
        self._comptes = {}
        self._generations = {}

    def total(self):
        return sum(self._comptes.values())

    def prendre(self, compte):
        """Une tenue de plus. Renvoie le jeton à rendre, ou None si c'est trop."""
        if self.total() >= self.maximum:
            return None
        self._comptes[compte] = self._comptes.get(compte, 0) + 1
        return (compte, self._generations.get(compte, 0))

    def rendre(self, jeton):
        """Rend une tenue. Renvoie True s'il faut refermer l'Espace maintenant."""
        compte, generation = jeton
        if generation != self._generations.get(compte, 0):
            return False        # tenue d'une ouverture déjà refermée
        restant = self._comptes.get(compte, 0) - 1
        if restant > 0:
            self._comptes[compte] = restant
            return False
        self._comptes.pop(compte, None)
        return True

    def oublier(self, compte):
        """L'Espace a été refermé d'un geste : les tenues en cours ne comptent plus."""
        self._comptes.pop(compte, None)
        self._generations[compte] = self._generations.get(compte, 0) + 1

#!/usr/bin/env python3
"""Mesure, sur une machine d'essai : un AUTRE compte Unix peut-il tenir un Espace ?

NON INSTALLÉ dans le paquet. Outil d'administrateur, à lancer sur une VM.

── POURQUOI CETTE MESURE AVANT TOUT CODE ───────────────────────────────────
Aujourd'hui, tous les Espaces tournent sous le compte du bureau : ce qui
s'échappe d'un Espace lit les autres. Un UID par Espace corrige cela, mais un
autre compte perd d'un coup l'accès à ce qui appartient au vôtre — à commencer
par l'affichage. Le socket Wayland de GNOME vit dans /run/user/<vous>, un
dossier en 0700.

Trois issues possibles, de coûts très différents : ouvrir l'accès au socket,
interposer un relais d'affichage, ou imbriquer un compositeur par Espace. Tant
que la première n'est pas ESSAYÉE sur GNOME, tout plan reste une supposition.

Ce script essaie, puis remet tout en état :

  1. connexion Wayland depuis un autre compte, SANS rien changer ;
  2. la même, après avoir ouvert l'accès au seul socket (liste de contrôle) ;
  3. le son (PipeWire), même question ;
  4. une socket Unix créée par le bureau, comme celles de Codebyr
     (notifications, filtre réseau) ;
  5. ce qu'un client Wayland d'un autre compte peut ATTEINDRE une fois connecté ;
  6. la PASSERELLE : le socket présenté par un autre chemin, sans jamais ouvrir
     le dossier d'exécution du bureau.

── CE QUE LA MESURE DU 14/09/2026 A MONTRÉ ─────────────────────────────────
Sur GNOME 48, un client Wayland d'un AUTRE compte s'affiche : l'architecture
légère tient. Mais la façon évidente d'y parvenir — ouvrir la traversée de
/run/user/<vous> — rend joignable tout ce que ce dossier protégeait, à
commencer par le BUS DE SESSION : exactement la faille fermée en 1.1.0.

D'où l'étape 6 : root prépare un dossier à part, y présente le seul socket
Wayland (montage lié), et n'accorde le droit qu'à ce socket. Le dossier du
bureau reste fermé, et le bus de session inatteignable.

À la fin, les listes de contrôle sont retirées et le compte d'essai supprimé.

    sudo -E python3 tools/mesure_uid_bureau.py

« -E » est indispensable : le script a besoin de XDG_RUNTIME_DIR et de
WAYLAND_DISPLAY de VOTRE session.
"""
import os
import pwd
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap

COMPTE = "cbyr-mesure"
FENETRE = textwrap.dedent("""
    import sys
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib

    def au_demarrage(app):
        f = Gtk.ApplicationWindow(application=app, title="Mesure Codebyr")
        f.set_default_size(320, 120)
        f.present()
        print("FENETRE-AFFICHEE", flush=True)
        GLib.timeout_add_seconds(2, lambda: (app.quit(), False)[1])

    app = Gtk.Application(application_id="io.codebyr.Mesure")
    app.connect("activate", au_demarrage)
    sys.exit(app.run([]))
""")


def dire(etape, verdict, detail=""):
    marque = {"ok": "  OUI  ", "non": "  NON  ", "info": "       "}[verdict]
    print("%s %-52s %s" % (marque, etape, detail))


def commande(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, timeout=60, **kw)


def contexte():
    """Le compte du bureau, son dossier d'exécution et son socket Wayland."""
    uid = int(os.environ.get("SUDO_UID") or os.getuid())
    utilisateur = pwd.getpwuid(uid)
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % uid
    affichage = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
    socket_wl = affichage if affichage.startswith("/") else os.path.join(runtime, affichage)
    return utilisateur, runtime, socket_wl


def compte_essai(creer=True):
    """Compte système d'essai : sans mot de passe utilisable, sans shell."""
    try:
        return pwd.getpwnam(COMPTE)
    except KeyError:
        if not creer:
            return None
    commande(["/usr/sbin/useradd", "--system", "--user-group", "--no-create-home",
              "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin",
              "--password", "!", COMPTE])
    return pwd.getpwnam(COMPTE)


def essayer_fenetre(essai, runtime_perso, socket_wl, script):
    """Ouvre une fenêtre GTK sous le compte d'essai. Renvoie (réussi, message)."""
    r = commande([
        "/usr/bin/setpriv", "--reuid", str(essai.pw_uid), "--regid", str(essai.pw_gid),
        "--clear-groups", "--no-new-privs",
        "/usr/bin/env", "-i",
        "PATH=/usr/bin:/bin", "LANG=C.UTF-8", "HOME=" + runtime_perso,
        "XDG_RUNTIME_DIR=" + runtime_perso,
        "WAYLAND_DISPLAY=" + socket_wl,
        "GDK_BACKEND=wayland",
        "/usr/bin/python3", script])
    if "FENETRE-AFFICHEE" in r.stdout:
        return True, ""
    derniere = [l for l in (r.stderr or "").splitlines() if l.strip()]
    return False, (derniere[-1][:90] if derniere else "aucune sortie")


def peut_joindre(essai, chemin):
    """Le compte d'essai peut-il se connecter à cette socket Unix ?"""
    code = textwrap.dedent("""
        import socket, sys
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect(sys.argv[1])
        except OSError as e:
            print("REFUS", e.strerror)
            sys.exit(1)
        print("JOINT")
    """)
    r = commande(["/usr/bin/setpriv", "--reuid", str(essai.pw_uid),
                  "--regid", str(essai.pw_gid), "--clear-groups", "--no-new-privs",
                  "/usr/bin/python3", "-c", code, chemin])
    return "JOINT" in r.stdout, (r.stdout or "").strip()


def liste_de_controle(chemin, essai, droits):
    """Ouvre l'accès d'un seul compte à un seul chemin. Renvoie False si setfacl manque."""
    if not shutil.which("setfacl"):
        return False
    commande(["setfacl", "-m", "u:%d:%s" % (essai.pw_uid, droits), chemin])
    return True


def passerelle(socket_wl, essai, dossier="/run/codebyr-mesure"):
    """Présente le SEUL socket Wayland par un chemin que root contrôle.

    C'est la forme que prendra le service privilégié : l'Espace ne traverse
    jamais le dossier d'exécution du bureau, donc n'atteint aucun des autres
    sockets qui s'y trouvent — bus de session en tête.
    """
    os.makedirs(dossier, mode=0o711, exist_ok=True)
    os.chmod(dossier, 0o711)
    lien = os.path.join(dossier, "wayland-0")
    if not os.path.exists(lien):
        open(lien, "w").close()
    r = commande(["mount", "--bind", socket_wl, lien])
    if r.returncode != 0:
        return None, (r.stderr or "").strip()[:90]
    # Le droit est posé sur le socket lui-même, jamais sur un dossier.
    liste_de_controle(socket_wl, essai, "rw")
    return lien, ""


def fermer_passerelle(dossier="/run/codebyr-mesure"):
    lien = os.path.join(dossier, "wayland-0")
    if os.path.exists(lien):
        commande(["umount", lien])
        try:
            os.unlink(lien)
        except OSError:
            pass
    try:
        os.rmdir(dossier)
    except OSError:
        pass


def retirer_controle(chemins, essai):
    for chemin in chemins:
        if shutil.which("setfacl") and os.path.exists(chemin):
            commande(["setfacl", "-x", "u:%d" % essai.pw_uid, chemin])


def main():
    if os.geteuid() != 0:
        print("À lancer en administrateur : sudo -E python3 %s" % sys.argv[0], file=sys.stderr)
        return 2

    utilisateur, runtime, socket_wl = contexte()
    print("Mesure « un UID par Espace » — machine d'essai uniquement\n")
    dire("compte du bureau", "info", "%s (UID %d)" % (utilisateur.pw_name, utilisateur.pw_uid))
    dire("dossier d'exécution", "info", runtime)
    dire("socket Wayland", "info", socket_wl)
    if not os.path.exists(socket_wl):
        print("\nSocket Wayland introuvable : lancez depuis une session graphique, "
              "avec « sudo -E ».", file=sys.stderr)
        return 2
    mode_runtime = oct(os.stat(runtime).st_mode & 0o777)
    dire("droits du dossier d'exécution", "info", mode_runtime)
    dire("outil de listes de contrôle (setfacl)", "ok" if shutil.which("setfacl") else "non",
         "paquet « acl »" if not shutil.which("setfacl") else "")
    print()

    essai = compte_essai()
    runtime_perso = tempfile.mkdtemp(prefix="codebyr-mesure-")
    os.chown(runtime_perso, essai.pw_uid, essai.pw_gid)
    os.chmod(runtime_perso, 0o700)
    script = os.path.join(runtime_perso, "fenetre.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(FENETRE)
    os.chmod(script, 0o644)

    # Une socket Unix créée par le BUREAU, comme celles de Codebyr.
    dossier_socket = tempfile.mkdtemp(prefix="codebyr-mesure-sock-")
    os.chown(dossier_socket, utilisateur.pw_uid, utilisateur.pw_gid)
    os.chmod(dossier_socket, 0o700)
    chemin_socket = os.path.join(dossier_socket, "essai")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(chemin_socket)
    srv.listen(4)
    os.chown(chemin_socket, utilisateur.pw_uid, utilisateur.pw_gid)

    pipewire = os.path.join(runtime, "pipewire-0")
    poses = []
    try:
        print("── 1. Sans rien changer ──────────────────────────────────────────")
        ok, detail = essayer_fenetre(essai, runtime_perso, socket_wl, script)
        dire("fenêtre affichée depuis un autre compte", "ok" if ok else "non", detail)
        joint, detail = peut_joindre(essai, chemin_socket)
        dire("socket Unix du bureau joignable", "ok" if joint else "non", detail)
        print()

        print("── 2. Après ouverture ciblée de l'accès ──────────────────────────")
        if not shutil.which("setfacl"):
            dire("listes de contrôle", "non", "paquet « acl » absent : mesure impossible")
        else:
            for chemin, droits in ((runtime, "x"), (socket_wl, "rw"),
                                   (dossier_socket, "x"), (chemin_socket, "rw"),
                                   (pipewire, "rw")):
                if os.path.exists(chemin) and liste_de_controle(chemin, essai, droits):
                    poses.append(chemin)
            ok, detail = essayer_fenetre(essai, runtime_perso, socket_wl, script)
            dire("fenêtre affichée depuis un autre compte", "ok" if ok else "non", detail)
            joint, detail = peut_joindre(essai, chemin_socket)
            dire("socket Unix du bureau joignable", "ok" if joint else "non", detail)
            if os.path.exists(pipewire):
                son, detail = peut_joindre(essai, pipewire)
                dire("son (PipeWire) joignable", "ok" if son else "non", detail)
            else:
                dire("son (PipeWire)", "info", "socket absente sur cette machine")
        print()

        print("── 3. Ce que l'ouverture du DOSSIER rend joignable ───────────────")
        for chemin, quoi in ((os.path.join(runtime, "bus"), "bus de session du bureau"),
                             (os.path.join(runtime, "systemd", "private"), "systemd --user"),
                             ("/run/dbus/system_bus_socket", "bus système")):
            if os.path.exists(chemin):
                joint, _ = peut_joindre(essai, chemin)
                dire(quoi, "ok" if joint else "non",
                     "à refuser" if joint else "")
            else:
                dire(quoi, "info", "absent")
        print()
        print("── 4. La passerelle : le socket seul, sans ouvrir le dossier ─────")
        retirer_controle(poses, essai)   # on repart d'un dossier d'exécution FERMÉ
        poses = []
        lien, detail = passerelle(socket_wl, essai)
        if not lien:
            dire("montage de la passerelle", "non", detail)
        else:
            poses.append(socket_wl)
            ok, detail = essayer_fenetre(essai, runtime_perso, lien, script)
            dire("fenêtre affichée par la passerelle", "ok" if ok else "non", detail)
            joint, _ = peut_joindre(essai, os.path.join(runtime, "bus"))
            dire("bus de session du bureau", "ok" if joint else "non",
                 "à refuser" if joint else "hors d'atteinte — c'est le but")
            joint, _ = peut_joindre(essai, pipewire) if os.path.exists(pipewire) else (False, "")
            dire("son (PipeWire) par le dossier du bureau", "ok" if joint else "non",
                 "à refuser" if joint else "hors d'atteinte")

        print()
        print("── 5. Ce que ce compte atteint par ailleurs ──────────────────────")
        lisible = os.access(utilisateur.pw_dir, os.R_OK)
        r = commande(["/usr/bin/setpriv", "--reuid", str(essai.pw_uid),
                      "--regid", str(essai.pw_gid), "--clear-groups", "--no-new-privs",
                      "/usr/bin/test", "-r", utilisateur.pw_dir])
        dire("dossier personnel du bureau lisible", "ok" if r.returncode == 0 else "non",
             "à refuser" if r.returncode == 0 else "c'est le but recherché")
        print("       (%s, lisible par root : %s)" % (utilisateur.pw_dir, lisible))
    finally:
        fermer_passerelle()
        retirer_controle(poses, essai)
        srv.close()
        shutil.rmtree(dossier_socket, ignore_errors=True)
        shutil.rmtree(runtime_perso, ignore_errors=True)
        commande(["/usr/sbin/userdel", COMPTE])
        print("\nNettoyage : listes de contrôle retirées, compte d'essai supprimé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

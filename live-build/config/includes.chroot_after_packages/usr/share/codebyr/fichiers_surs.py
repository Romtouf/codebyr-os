"""Accès hôte aux fichiers non fiables des Espaces (Linux uniquement).

Chaque composante est ouverte avec O_NOFOLLOW et conservée par descripteur.
Les écritures remplacent un inode au lieu de tronquer une éventuelle cible
de lien dur. Pas de vérification realpath suivie d'un open vulnérable aux courses.
"""
import contextlib
import os
import secrets
import shutil
import stat


@contextlib.contextmanager
def dossier(chemin, creer=False):
    if os.name != "posix":
        raise OSError("Accès sécurisé disponible uniquement sous Linux")
    absolu = os.path.abspath(chemin)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for morceau in absolu.split("/")[1:]:
            if not morceau:
                continue
            if creer:
                try:
                    os.mkdir(morceau, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            suivant = os.open(morceau, os.O_RDONLY | os.O_DIRECTORY |
                              os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = suivant
        yield fd
    finally:
        os.close(fd)


def mkdir(chemin, exist_ok=True):
    with dossier(chemin, creer=True):
        pass


@contextlib.contextmanager
def ouvrir(chemin, mode="r", encoding=None):
    parent, nom = os.path.split(os.path.abspath(chemin))
    with dossier(parent) as fd:
        ecriture = mode[0] in "wax"
        temporaire = ".codebyr-" + secrets.token_hex(16)
        if ecriture:
            inode = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                            os.O_NOFOLLOW, 0o600, dir_fd=fd)
        else:
            inode = os.open(nom, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                            dir_fd=fd)
        try:
            st = os.fstat(inode)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                raise OSError("Fichier spécial ou lien dur refusé")
            flux = os.fdopen(inode, "wb" if "b" in mode else "w",
                             encoding=encoding) if ecriture else os.fdopen(
                                 inode, mode, encoding=encoding)
            inode = None
            with flux:
                if mode.startswith("a"):
                    try:
                        with ouvrir(chemin, "rb" if "b" in mode else "r",
                                    encoding=encoding) as ancien:
                            shutil.copyfileobj(ancien, flux)
                    except FileNotFoundError:
                        pass
                yield flux
                if ecriture:
                    flux.flush()
                    os.fsync(flux.fileno())
            if ecriture:
                if mode.startswith("x"):
                    os.link(temporaire, nom, src_dir_fd=fd, dst_dir_fd=fd,
                            follow_symlinks=False)
                else:
                    os.replace(temporaire, nom, src_dir_fd=fd, dst_dir_fd=fd)
        finally:
            if inode is not None:
                os.close(inode)
            if ecriture:
                try:
                    os.unlink(temporaire, dir_fd=fd)
                except FileNotFoundError:
                    pass


def copier(source, cible):
    with ouvrir(source, "rb") as entree, ouvrir(cible, "xb") as sortie:
        shutil.copyfileobj(entree, sortie)


def copier_unique(source, dossier_cible, nom, origine=None):
    """Création exclusive : deux transferts concurrents ne s'écrasent pas."""
    base, ext = os.path.splitext(nom)
    for n in range(1, 1000):
        candidat = nom if n == 1 else "%s (%d)%s" % (base, n, ext)
        cible = os.path.join(dossier_cible, candidat)
        try:
            with ouvrir(source, "rb") as entree, ouvrir(cible, "xb") as sortie:
                shutil.copyfileobj(entree, sortie)
                if origine:
                    os.setxattr(sortie.fileno(), "user.codebyr.origine",
                                origine.encode("ascii"))
            return candidat
        except FileExistsError:
            continue
    raise OSError("Trop de fichiers du même nom")

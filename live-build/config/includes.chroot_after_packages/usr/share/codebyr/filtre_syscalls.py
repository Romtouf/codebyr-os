"""Filtre seccomp complémentaire du Blindage ; échec fermé si indisponible.

Liste de refus volontairement limitée aux interfaces de privilèges et
d'inspection interprocessus. Ce n'est pas une liste exhaustive d'appels sûrs.
libseccomp génère les contrôles d'architecture et le BPF, jamais un assemblage
manuel dépendant des numéros de syscalls de la machine.
"""
import ctypes
import errno
import os
import sys

REFUSES = (
    "ptrace", "process_vm_readv", "process_vm_writev", "kcmp",
    "bpf", "perf_event_open", "userfaultfd", "open_by_handle_at",
    "init_module", "finit_module", "delete_module", "kexec_load",
    "kexec_file_load", "reboot", "swapon", "swapoff",
    "add_key", "request_key", "keyctl",
    # io_uring : deux raisons, et la seconde vide le filtre de son sens.
    #
    # C'est d'abord l'une des principales sources de failles d'elevation de
    # privileges du noyau de ces dernieres annees - ChromeOS et Android l'ont
    # desactive pour cela.
    #
    # Surtout, il CONTOURNE seccomp : les operations soumises dans l'anneau
    # (ouvrir, lire, ecrire, se connecter) ne passent pas par les appels
    # systeme correspondants, que le filtre ne voit donc jamais. Laisser
    # io_uring ouvert revient a offrir un second chemin vers tout ce que les
    # lignes precedentes refusent.
    "io_uring_setup", "io_uring_enter", "io_uring_register",
    # Voler un descripteur ouvert a un autre processus : meme famille que
    # process_vm_readv, refuse juste au-dessus.
    "pidfd_getfd",
    # Rejoindre l'espace de noms d'un autre processus - la sortie de bac a
    # sable la plus directe si un descripteur de namespace fuit.
    "setns",
)

# « unshare » n'est VOLONTAIREMENT pas refuse : Firefox construit son propre
# bac a sable avec, et le bloquer desactiverait une protection du navigateur
# pour en ajouter une ici. On ne troque pas une defense contre une autre.


def appliquer():
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    contexte = lib.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not contexte:
        raise OSError("Création du filtre seccomp impossible")
    try:
        for nom in REFUSES:
            numero = lib.seccomp_syscall_resolve_name(nom.encode("ascii"))
            if numero >= 0:
                rc = lib.seccomp_rule_add(contexte, 0x00050000 | errno.EPERM, numero, 0)
                if rc < 0:
                    raise OSError(-rc, "Règle seccomp impossible")
        rc = lib.seccomp_load(contexte)
        if rc < 0:
            raise OSError(-rc, "Chargement seccomp impossible")
    finally:
        lib.seccomp_release(contexte)


def main(args):
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        return 2
    try:
        appliquer()
        os.execvp(args[0], args)
    except OSError as exc:
        print("Blindage indisponible : %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

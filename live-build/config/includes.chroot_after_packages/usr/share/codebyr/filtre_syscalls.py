"""Filtre seccomp complémentaire du Blindage ; échec fermé si indisponible.

Liste de refus volontairement limitée aux interfaces de privilèges et
d'inspection interprocessus. Ce n'est pas une liste exhaustive d'appels sûrs.
libseccomp génère les contrôles d'architecture et le BPF, jamais un assemblage
manuel dépendant des numéros de syscalls de la machine.

── UNE LISTE D'AUTORISATION, DEPUIS LA 1.16.4 ──────────────────────────────
Partir de « tout est permis » laissait passer, par défaut, l'appel qu'un futur
noyau ajoutera. Le filtre n'autorise plus que les appels CONNUS, moins les
refus et les écartés. La bascule a été préparée en MESURANT ce que les
applications réelles des Espaces appellent (MESURE, tools/mesurer_seccomp.py),
et le même outil sert à mesurer une application nouvelle.
"""
import ctypes
import errno
import os
import sys

from traduction import _

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
# Les vignettes de Fichiers et les applications Electron s'en servent aussi
# (un bwrap imbriqué, le bac à sable de Chromium). Interdire seulement le
# réseau imbriqué casserait Firefox : il croirait les espaces de noms
# disponibles, puis échouerait à lancer ses onglets.

# ── LES SOCKETS, DEPUIS LA 1.20.0 ───────────────────────────────────────────
# Ce qu'un processus gagne en créant ses propres espaces de noms, c'est
# CAP_NET_ADMIN sur un réseau à lui — et, par là, les parties du noyau les
# plus visées par les failles d'élévation de privilèges de ces dernières
# années : nf_tables (pare-feu, par netlink), x_tables (par une socket brute),
# AF_PACKET, et des protocoles rares que le noyau charge à la demande à la
# première socket ouverte (SCTP, DCCP, TIPC, RDS, AF_ALG, VSOCK…). Aucune
# application d'un Espace n'en a l'usage. « socket » n'est donc plus permis
# sans condition : seules les familles ci-dessous passent, tout autre appel
# reçoit ENOSYS. Analyse externe du 01/10/2026, point 3.1.
#
# Ce qui reste ouvert, et SECURITY.md le dit : dans un réseau qu'il a créé,
# un processus peut encore régler la gestion du trafic (tc) par NETLINK_ROUTE,
# dont les interfaces réseau et la résolution de noms ont besoin.
AF_UNIX, AF_INET, AF_INET6, AF_NETLINK = 1, 2, 10, 16
SOCK_STREAM, SOCK_DGRAM = 1, 2
SOCK_TYPE_MASK = 0xf        # SOCK_NONBLOCK et SOCK_CLOEXEC vivent au-dessus
NETLINK_ROUTE, NETLINK_KOBJECT_UEVENT = 0, 15
SOCKETS_PERMIS = (
    # (famille, type, protocole) ; None : quel qu'il soit
    (AF_UNIX, None, None),
    (AF_INET, SOCK_STREAM, 0), (AF_INET, SOCK_STREAM, 6),         # TCP
    (AF_INET, SOCK_DGRAM, 0), (AF_INET, SOCK_DGRAM, 17),          # UDP
    (AF_INET, SOCK_DGRAM, 1),                                      # ping (ICMP)
    (AF_INET6, SOCK_STREAM, 0), (AF_INET6, SOCK_STREAM, 6),
    (AF_INET6, SOCK_DGRAM, 0), (AF_INET6, SOCK_DGRAM, 17),
    (AF_INET6, SOCK_DGRAM, 58),                                    # ping (ICMPv6)
    (AF_NETLINK, None, NETLINK_ROUTE),            # interfaces et adresses
    (AF_NETLINK, None, NETLINK_KOBJECT_UEVENT),   # événements udev
)
SOUS_CONDITION = ("socket",)

# Tous les appels x86_64 que connaissait libseccomp 2.6.0 (Debian 13), relevés
# le 29/09/2026. Liste FIGÉE, et c'est tout son intérêt : lue à l'exécution,
# elle grandirait avec chaque bibliothèque et laisserait entrer les appels de
# demain. Le Blindage n'autorise que ceux-ci, moins les refus et les écartés :
# un appel ajouté par un futur noyau reçoit ENOSYS, la réponse qui
# fait se rabattre la glibc sur l'appel plus ancien qu'elle sait remplacer.
CONNUS = (
    "read", "write", "open", "close", "stat", "fstat", "lstat", "poll",
    "lseek", "mmap", "mprotect", "munmap", "brk", "rt_sigaction",
    "rt_sigprocmask", "rt_sigreturn", "ioctl", "pread64", "pwrite64", "readv",
    "writev", "access", "pipe", "select", "sched_yield", "mremap", "msync",
    "mincore", "madvise", "shmget", "shmat", "shmctl", "dup", "dup2", "pause",
    "nanosleep", "getitimer", "alarm", "setitimer", "getpid", "sendfile",
    "socket", "connect", "accept", "sendto", "recvfrom", "sendmsg", "recvmsg",
    "shutdown", "bind", "listen", "getsockname", "getpeername", "socketpair",
    "setsockopt", "getsockopt", "clone", "fork", "vfork", "execve", "exit",
    "wait4", "kill", "uname", "semget", "semop", "semctl", "shmdt", "msgget",
    "msgsnd", "msgrcv", "msgctl", "fcntl", "flock", "fsync", "fdatasync",
    "truncate", "ftruncate", "getdents", "getcwd", "chdir", "fchdir", "rename",
    "mkdir", "rmdir", "creat", "link", "unlink", "symlink", "readlink",
    "chmod", "fchmod", "chown", "fchown", "lchown", "umask", "gettimeofday",
    "getrlimit", "getrusage", "sysinfo", "times", "ptrace", "getuid", "syslog",
    "getgid", "setuid", "setgid", "geteuid", "getegid", "setpgid", "getppid",
    "getpgrp", "setsid", "setreuid", "setregid", "getgroups", "setgroups",
    "setresuid", "getresuid", "setresgid", "getresgid", "getpgid", "setfsuid",
    "setfsgid", "getsid", "capget", "capset", "rt_sigpending",
    "rt_sigtimedwait", "rt_sigqueueinfo", "rt_sigsuspend", "sigaltstack",
    "utime", "mknod", "uselib", "personality", "ustat", "statfs", "fstatfs",
    "sysfs", "getpriority", "setpriority", "sched_setparam", "sched_getparam",
    "sched_setscheduler", "sched_getscheduler", "sched_get_priority_max",
    "sched_get_priority_min", "sched_rr_get_interval", "mlock", "munlock",
    "mlockall", "munlockall", "vhangup", "modify_ldt", "pivot_root", "_sysctl",
    "prctl", "arch_prctl", "adjtimex", "setrlimit", "chroot", "sync", "acct",
    "settimeofday", "mount", "umount2", "swapon", "swapoff", "reboot",
    "sethostname", "setdomainname", "iopl", "ioperm", "create_module",
    "init_module", "delete_module", "get_kernel_syms", "query_module",
    "quotactl", "nfsservctl", "getpmsg", "putpmsg", "afs_syscall", "tuxcall",
    "security", "gettid", "readahead", "setxattr", "lsetxattr", "fsetxattr",
    "getxattr", "lgetxattr", "fgetxattr", "listxattr", "llistxattr",
    "flistxattr", "removexattr", "lremovexattr", "fremovexattr", "tkill",
    "time", "futex", "sched_setaffinity", "sched_getaffinity",
    "set_thread_area", "io_setup", "io_destroy", "io_getevents", "io_submit",
    "io_cancel", "get_thread_area", "lookup_dcookie", "epoll_create",
    "epoll_ctl_old", "epoll_wait_old", "remap_file_pages", "getdents64",
    "set_tid_address", "restart_syscall", "semtimedop", "fadvise64",
    "timer_create", "timer_settime", "timer_gettime", "timer_getoverrun",
    "timer_delete", "clock_settime", "clock_gettime", "clock_getres",
    "clock_nanosleep", "exit_group", "epoll_wait", "epoll_ctl", "tgkill",
    "utimes", "vserver", "mbind", "set_mempolicy", "get_mempolicy", "mq_open",
    "mq_unlink", "mq_timedsend", "mq_timedreceive", "mq_notify",
    "mq_getsetattr", "kexec_load", "waitid", "add_key", "request_key",
    "keyctl", "ioprio_set", "ioprio_get", "inotify_init", "inotify_add_watch",
    "inotify_rm_watch", "migrate_pages", "openat", "mkdirat", "mknodat",
    "fchownat", "futimesat", "newfstatat", "unlinkat", "renameat", "linkat",
    "symlinkat", "readlinkat", "fchmodat", "faccessat", "pselect6", "ppoll",
    "unshare", "set_robust_list", "get_robust_list", "splice", "tee",
    "sync_file_range", "vmsplice", "move_pages", "utimensat", "epoll_pwait",
    "signalfd", "timerfd_create", "eventfd", "fallocate", "timerfd_settime",
    "timerfd_gettime", "accept4", "signalfd4", "eventfd2", "epoll_create1",
    "dup3", "pipe2", "inotify_init1", "preadv", "pwritev", "rt_tgsigqueueinfo",
    "perf_event_open", "recvmmsg", "fanotify_init", "fanotify_mark",
    "prlimit64", "name_to_handle_at", "open_by_handle_at", "clock_adjtime",
    "syncfs", "sendmmsg", "setns", "getcpu", "process_vm_readv",
    "process_vm_writev", "kcmp", "finit_module", "sched_setattr",
    "sched_getattr", "renameat2", "seccomp", "getrandom", "memfd_create",
    "kexec_file_load", "bpf", "execveat", "userfaultfd", "membarrier",
    "mlock2", "copy_file_range", "preadv2", "pwritev2", "pkey_mprotect",
    "pkey_alloc", "pkey_free", "statx", "io_pgetevents", "rseq", "uretprobe",
    "pidfd_send_signal", "io_uring_setup", "io_uring_enter",
    "io_uring_register", "open_tree", "move_mount", "fsopen", "fsconfig",
    "fsmount", "fspick", "pidfd_open", "clone3", "close_range", "openat2",
    "pidfd_getfd", "faccessat2", "process_madvise", "epoll_pwait2",
    "mount_setattr", "quotactl_fd", "landlock_create_ruleset",
    "landlock_add_rule", "landlock_restrict_self", "memfd_secret",
    "process_mrelease", "futex_waitv", "set_mempolicy_home_node", "cachestat",
    "fchmodat2", "map_shadow_stack", "futex_wake", "futex_wait",
    "futex_requeue", "statmount", "listmount", "lsm_get_self_attr",
    "lsm_set_self_attr", "lsm_list_modules", "mseal", "setxattrat",
    "getxattrat", "listxattrat", "removexattrat",
)

# Écartés : connus, mais qu'aucune application des Espaces n'a appelés pendant
# les deux mesures du 29/09/2026 sur la VM (Firefox et une vidéo, Fichiers et
# ses vignettes, une application Flatpak, la console). Ils reçoivent ENOSYS,
# comme un appel inconnu. Six candidats de départ ont servi, et restent donc
# permis : quotactl (Firefox, pour la place disque), mount et pivot_root (bwrap
# imbriqué : Flatpak, vignettes de Fichiers — avec eux toute la famille des
# montages, que libmount 2.41 emploie aussi), name_to_handle_at, fanotify_init
# et fanotify_mark (localsearch, la recherche de fichiers de GNOME). Et
# personality, jamais vu, reste permis : il ne sert qu'à lire ou régler un
# modèle d'exécution, et quelques programmes anciens le demandent.
ECARTES = (
    # administration de la machine : heure, noyau, quotas, journal, console
    "acct", "adjtimex", "clock_adjtime", "clock_settime", "settimeofday",
    "sethostname", "setdomainname", "iopl", "ioperm", "modify_ldt",
    "quotactl_fd", "syslog", "vhangup", "lookup_dcookie",
    "sysfs", "_sysctl", "ustat", "uselib",
    # mémoire NUMA et placement de pages d'autres processus
    "mbind", "set_mempolicy", "get_mempolicy", "set_mempolicy_home_node",
    "migrate_pages", "move_pages", "remap_file_pages",
    # mémoire secrète, attributs LSM
    "memfd_secret", "lsm_set_self_attr",
    # jamais implémentés par Linux : ENOSYS quoi qu'il arrive
    "create_module", "get_kernel_syms", "query_module", "nfsservctl",
    "getpmsg", "putpmsg", "afs_syscall", "tuxcall", "security", "vserver",
    "epoll_ctl_old", "epoll_wait_old",
)

# Mode mesure, posé par l'administrateur (« sudo touch »), jamais par un
# Espace : /etc y est en lecture seule. Les écartés — et tout appel absent de
# CONNUS — y sont PERMIS, mais le noyau journalise chaque appel (SCMP_ACT_LOG) :
# on voit ce qu'une application nouvelle réclamerait, sans rien casser ni
# recourir à ptrace, que ce filtre refuse justement. Les refus, eux, tiennent.
MESURE = "/etc/codebyr/seccomp-mesure"

SCMP_ACT_ALLOW = 0x7fff0000
SCMP_ACT_LOG = 0x7ffc0000
SCMP_ACT_ERRNO = 0x00050000
SCMP_FLTATR_CTL_OPTIMIZE = 8
SCMP_CMP_EQ = 4
SCMP_CMP_MASKED_EQ = 7


class _Comparaison(ctypes.Structure):
    """struct scmp_arg_cmp de libseccomp."""
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def autorises():
    """Ce que le Blindage laisse passer sans condition : les appels connus,
    moins refus, écartés, et ceux qui ne passent que sous condition."""
    return [n for n in CONNUS
            if n not in REFUSES and n not in ECARTES and n not in SOUS_CONDITION]


def comparaisons_socket(famille, type_, protocole):
    """Les arguments de socket() à comparer pour une entrée de SOCKETS_PERMIS :
    (numéro d'argument, opérateur, valeur A, valeur B)."""
    resultat = [(0, SCMP_CMP_EQ, famille, 0)]
    if type_ is not None:
        resultat.append((1, SCMP_CMP_MASKED_EQ, SOCK_TYPE_MASK, type_))
    if protocole is not None:
        resultat.append((2, SCMP_CMP_EQ, protocole, 0))
    return resultat


def appliquer(mesure=None):
    """Pose le filtre sur le processus courant ; tout ce qu'il lance en hérite.

    LISTE D'AUTORISATION depuis la 1.16.4 : ce qui n'est pas autorisé reçoit
    ENOSYS, « appel inexistant » — un appel ajouté par un futur noyau comme un
    écarté. ENOSYS plutôt qu'EPERM : c'est la réponse qui fait se rabattre la
    glibc, et les programmes bien écrits, sur l'appel plus ancien qu'ils
    savent remplacer. Les refus, eux, gardent EPERM : ce sont des interdits.
    """
    if mesure is None:
        mesure = os.path.exists(MESURE)
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.c_int, ctypes.c_uint]
    # La forme « tableau », et non la forme variadique : ctypes ne sait pas
    # passer une structure par valeur à une fonction variadique.
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                          ctypes.c_uint, ctypes.POINTER(_Comparaison)]
    lib.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    contexte = lib.seccomp_init(SCMP_ACT_LOG if mesure else SCMP_ACT_ERRNO | errno.ENOSYS)
    if not contexte:
        raise OSError("Création du filtre seccomp impossible")
    try:
        # Plus de trois cents règles : en arbre binaire, chaque appel n'en
        # examine qu'une dizaine au lieu de les parcourir toutes. Sans effet
        # sur ce qui est permis ou refusé ; ignoré si libseccomp ne le sait pas.
        lib.seccomp_attr_set(contexte, SCMP_FLTATR_CTL_OPTIMIZE, 2)
        regles = [(nom, SCMP_ACT_ERRNO | errno.EPERM) for nom in REFUSES]
        regles += [(nom, SCMP_ACT_ALLOW) for nom in autorises()]
        for nom, action in regles:
            numero = lib.seccomp_syscall_resolve_name(nom.encode("ascii"))
            if numero >= 0:
                rc = lib.seccomp_rule_add(contexte, action, numero, 0)
                if rc < 0:
                    raise OSError(-rc, "Règle seccomp impossible : %s" % nom)
        # socket() : une règle par entrée de SOCKETS_PERMIS. Ce qui n'en
        # vérifie aucune reçoit l'action par défaut — ENOSYS, ou un passage
        # noté au journal en mode mesure.
        numero = lib.seccomp_syscall_resolve_name(b"socket")
        for permis in SOCKETS_PERMIS:
            comparaisons = comparaisons_socket(*permis)
            tableau = (_Comparaison * len(comparaisons))(*[_Comparaison(*c) for c in comparaisons])
            rc = lib.seccomp_rule_add_array(contexte, SCMP_ACT_ALLOW, numero,
                                            len(comparaisons), tableau)
            if rc < 0:
                raise OSError(-rc, "Règle seccomp impossible : %s" % ("socket %r" % (permis,)))
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
        print(_("Blindage indisponible : %s") % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

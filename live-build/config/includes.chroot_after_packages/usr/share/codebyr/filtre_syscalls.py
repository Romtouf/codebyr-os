"""Filtre seccomp complémentaire du Blindage ; échec fermé si indisponible.

Liste de refus volontairement limitée aux interfaces de privilèges et
d'inspection interprocessus. Ce n'est pas une liste exhaustive d'appels sûrs.
libseccomp génère les contrôles d'architecture et le BPF, jamais un assemblage
manuel dépendant des numéros de syscalls de la machine.

── VERS UNE LISTE D'AUTORISATION ──────────────────────────────────────────
Partir de « tout est permis » laisse passer, par défaut, l'appel qu'un futur
noyau ajoutera. La bascule — n'autoriser que ce qui est connu — se prépare en
MESURANT, comme le reste du projet : CONNUS, A_MESURER et MESURE ci-dessous,
et tools/mesurer_seccomp.py pour relever ce que les applications appellent.
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

# Tous les appels x86_64 que connaissait libseccomp 2.6.0 (Debian 13), relevés
# le 29/09/2026. Liste FIGÉE, et c'est tout son intérêt : lue à l'exécution,
# elle grandirait avec chaque bibliothèque et laisserait entrer les appels de
# demain. Après la bascule, le Blindage n'autorisera que ceux-ci, moins les
# refus : un appel ajouté par un futur noyau recevra ENOSYS, la réponse qui
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

# Candidats au refus : ce qu'une application de bureau n'a pas de raison
# d'appeler. On ne les refusera qu'après avoir MESURÉ que les applications
# réelles des Espaces s'en passent — les vignettes de Fichiers, par exemple,
# passent par glycin, qui monte son propre bac à sable (mount, pivot_root).
A_MESURER = (
    # administration de la machine : heure, noyau, quotas, journal, console
    "acct", "adjtimex", "clock_adjtime", "clock_settime", "settimeofday",
    "sethostname", "setdomainname", "iopl", "ioperm", "modify_ldt",
    "quotactl", "quotactl_fd", "syslog", "vhangup", "lookup_dcookie",
    "sysfs", "_sysctl", "ustat", "uselib",
    # montages : un Espace n'en pose pas, sauf un bac à sable imbriqué
    "mount", "umount2", "pivot_root", "fsopen", "fsconfig", "fsmount",
    "fspick", "move_mount", "open_tree", "mount_setattr", "statmount",
    "listmount",
    # surveillance et désignation de fichiers hors de leur chemin
    "name_to_handle_at", "fanotify_init", "fanotify_mark",
    # mémoire NUMA et placement de pages d'autres processus
    "mbind", "set_mempolicy", "get_mempolicy", "set_mempolicy_home_node",
    "migrate_pages", "move_pages", "remap_file_pages",
    # divers : exécution d'un autre modèle, mémoire secrète, attributs LSM
    "personality", "memfd_secret", "lsm_set_self_attr",
    # jamais implémentés par Linux : ENOSYS quoi qu'il arrive
    "create_module", "get_kernel_syms", "query_module", "nfsservctl",
    "getpmsg", "putpmsg", "afs_syscall", "tuxcall", "security", "vserver",
    "epoll_ctl_old", "epoll_wait_old",
)

# Mode mesure, posé par l'administrateur (« sudo touch »), jamais par un
# Espace : /etc y est en lecture seule. Les candidats y restent PERMIS, mais le
# noyau journalise chaque appel (SCMP_ACT_LOG) — rien ne casse pendant qu'on
# regarde, et nul besoin de ptrace, que ce filtre refuse justement. Ce mode ne
# desserre rien : hors de lui aussi, tout ce qui n'est pas refusé passe.
MESURE = "/etc/codebyr/seccomp-mesure"

SCMP_ACT_ALLOW = 0x7fff0000
SCMP_ACT_LOG = 0x7ffc0000
SCMP_ACT_ERRNO = 0x00050000


def appliquer(mesure=None):
    """Pose le filtre sur le processus courant ; tout ce qu'il lance en hérite."""
    if mesure is None:
        mesure = os.path.exists(MESURE)
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    contexte = lib.seccomp_init(SCMP_ACT_LOG if mesure else SCMP_ACT_ALLOW)
    if not contexte:
        raise OSError("Création du filtre seccomp impossible")
    try:
        regles = [(nom, SCMP_ACT_ERRNO | errno.EPERM) for nom in REFUSES]
        if mesure:
            # Ce qui n'est ni refusé ni candidat passe sans bruit. Le reste —
            # les candidats, et tout appel absent de CONNUS — passe aussi,
            # mais journalisé : c'est ce que tools/mesurer_seccomp.py relève.
            regles += [(nom, SCMP_ACT_ALLOW) for nom in CONNUS
                       if nom not in REFUSES and nom not in A_MESURER]
        for nom, action in regles:
            numero = lib.seccomp_syscall_resolve_name(nom.encode("ascii"))
            if numero >= 0:
                rc = lib.seccomp_rule_add(contexte, action, numero, 0)
                if rc < 0:
                    raise OSError(-rc, "Règle seccomp impossible : %s" % nom)
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

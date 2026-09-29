#!/usr/bin/env python3
"""Relève les appels système que les applications des Espaces font vraiment.

NON INSTALLÉ. Sert à préparer la bascule du Blindage vers une liste
d'autorisation (voir filtre_syscalls.py) : on ne refuse un appel qu'après
avoir mesuré que les applications réelles s'en passent.

    sudo python3 tools/mesurer_seccomp.py activer     # mode mesure
    … ouvrir les Espaces blindés, s'en servir normalement …
    sudo python3 tools/mesurer_seccomp.py relever     # le relevé
    sudo python3 tools/mesurer_seccomp.py desactiver

En mode mesure, les appels écartés (ECARTES) et tout appel inconnu de la
liste figée (CONNUS) sont PERMIS, mais le noyau les journalise. Le relevé lit ce journal depuis le démarrage : il dit quel
programme a appelé quoi, et combien de fois. Un Espace déjà ouvert garde le
filtre qu'il avait : fermez-le avant d'activer.

Le journal du noyau est limité en débit : un appel très fréquent peut n'y
laisser qu'une partie de ses traces. Le relevé dit « au moins N fois ».
"""
import collections
import ctypes
import os
import re
import subprocess
import sys

LIB = "/usr/share/codebyr"
X86_64 = "c000003e"
ACTION_LOG = "0x7ffc0000"
CHAMP = re.compile(r'(\w+)=("[^"]*"|\S+)')

sys.dont_write_bytecode = True
sys.path.insert(0, LIB)
try:
    import filtre_syscalls
except ImportError:
    filtre_syscalls = None


def nommer():
    """Numéro → nom, par la libseccomp de la machine : jamais une table à nous."""
    lib = ctypes.CDLL("libseccomp.so.2")
    lib.seccomp_syscall_resolve_num_arch.argtypes = [ctypes.c_uint32, ctypes.c_int]
    lib.seccomp_syscall_resolve_num_arch.restype = ctypes.c_void_p
    libc = ctypes.CDLL(None)
    libc.free.argtypes = [ctypes.c_void_p]

    def nom(numero):
        p = lib.seccomp_syscall_resolve_num_arch(int(X86_64, 16), numero)
        if not p:
            return "appel n°%d (inconnu de libseccomp)" % numero
        try:
            return ctypes.string_at(p).decode()
        finally:
            libc.free(p)
    return nom


def traces(lignes):
    """Les appels journalisés par le mode mesure : (programme, numéro)."""
    for ligne in lignes:
        if "syscall=" not in ligne:
            continue
        champs = {k: v.strip('"') for k, v in CHAMP.findall(ligne)}
        if champs.get("code") != ACTION_LOG or champs.get("arch") != X86_64:
            continue
        try:
            yield champs.get("exe") or champs.get("comm", "?"), int(champs["syscall"])
        except (KeyError, ValueError):
            continue


def relever():
    journal = subprocess.run(["/usr/bin/journalctl", "-b", "-o", "cat", "--no-pager",
                              "--grep", "syscall="], capture_output=True, text=True)
    if journal.returncode not in (0, 1):
        print("Journal illisible : %s" % journal.stderr.strip(), file=sys.stderr)
        return 1
    nom = nommer()
    appels = collections.Counter()
    programmes = collections.defaultdict(collections.Counter)
    for exe, numero in traces(journal.stdout.splitlines()):
        appels[numero] += 1
        programmes[numero][os.path.basename(exe)] += 1
    if not appels:
        print("Aucun appel journalisé depuis le démarrage.")
        print("Le mode mesure est-il actif (« activer »), et les Espaces ouverts APRÈS ?")
        return 0
    candidats = set(filtre_syscalls.ECARTES) if filtre_syscalls else set()
    connus = set(filtre_syscalls.CONNUS) if filtre_syscalls else set()
    print("%-26s %8s  %s" % ("Appel", "au moins", "Programmes"))
    for numero, fois in appels.most_common():
        appel = nom(numero)
        marque = ("" if appel in candidats else
                  "  ← ABSENT DE CONNUS : un appel nouveau" if appel not in connus else "")
        qui = ", ".join("%s (%d)" % pq for pq in programmes[numero].most_common(4))
        print("%-26s %8d  %s%s" % (appel, fois, qui, marque))
    silencieux = sorted(candidats - {nom(n) for n in appels})
    print("\nÉcartés jamais appelés pendant la mesure (%d) :" % len(silencieux))
    print("  " + " ".join(silencieux))
    return 0


def main(args):
    if os.geteuid() != 0:
        print("À lancer en administrateur : sudo python3 %s …" % sys.argv[0], file=sys.stderr)
        return 2
    if filtre_syscalls is None:
        print("%s/filtre_syscalls.py introuvable : codebyr-tools est-il installé ?" % LIB,
              file=sys.stderr)
        return 2
    geste = args[0] if args else "relever"
    temoin = filtre_syscalls.MESURE
    if geste == "activer":
        with open("/proc/sys/kernel/seccomp/actions_logged", encoding="ascii") as f:
            if "log" not in f.read().split():
                print("Le noyau ne journalise pas l'action « log » : "
                      "/proc/sys/kernel/seccomp/actions_logged", file=sys.stderr)
                return 1
        os.makedirs(os.path.dirname(temoin), exist_ok=True)
        with open(temoin, "w", encoding="utf-8") as f:
            f.write("Mode mesure du filtre d'appels système (tools/mesurer_seccomp.py).\n")
        print("Mode mesure ACTIF. Fermez les Espaces ouverts, puis rouvrez-les :")
        print("seuls les Espaces ouverts à partir de maintenant sont mesurés.")
        return 0
    if geste == "desactiver":
        try:
            os.unlink(temoin)
        except FileNotFoundError:
            pass
        print("Mode mesure retiré : les Espaces rouverts reprennent le filtre ordinaire.")
        return 0
    if geste == "relever":
        if not os.path.exists(temoin):
            print("(le mode mesure n'est pas actif en ce moment)\n")
        return relever()
    print("Usage : %s activer | relever | desactiver" % sys.argv[0], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

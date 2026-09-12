"""Relais dans le namespace réseau : seul le proxy filtrant sort de l'Espace.

Le socket Unix monté est une capacité vers le filtre de CET Espace. Aucun
socket réseau de l'hôte ni interface externe n'est exposé au bac à sable.
"""
import os
import select
import socket
import subprocess
import sys
import threading


def relayer(client, chemin):
    with client, socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as amont:
        try:
            amont.connect(chemin)
            while True:
                prets, _, _ = select.select([client, amont], [], [], 60)
                if not prets:
                    return
                for source in prets:
                    bloc = source.recv(65536)
                    if not bloc:
                        return
                    (amont if source is client else client).sendall(bloc)
        except OSError:
            return


def servir(srv, chemin):
    places = threading.BoundedSemaphore(64)

    def traiter(client):
        try:
            relayer(client, chemin)
        finally:
            places.release()

    while True:
        try:
            client, _ = srv.accept()
        except OSError:
            return
        if not places.acquire(blocking=False):
            client.close()
            continue
        threading.Thread(target=traiter, args=(client,), daemon=True).start()


def main(args):
    chemin, port, *commande = args
    if commande and commande[0] == "--":
        commande = commande[1:]
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", int(port)))
        srv.listen(64)
        threading.Thread(target=servir, args=(srv, chemin), daemon=True).start()
        env = dict(os.environ)
        env.update(http_proxy="http://127.0.0.1:" + port,
                   https_proxy="http://127.0.0.1:" + port,
                   ALL_PROXY="socks5h://127.0.0.1:" + port,
                   no_proxy="", NO_PROXY="")
        return subprocess.call(commande, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

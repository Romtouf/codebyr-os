# -*- coding: utf-8 -*-
"""Le journal système de Codebyr : « journalctl -t codebyr ».

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de codebyr-space en 1.17.0 (découpage, audit point 8), pour que chaque
module puisse noter ce qu'il fait sans recopier ces lignes.
"""


def noter(message):
    """Trace une action dans le journal système.

    Sans trace, un utilisateur qui signale « ça n'a pas marché » ne peut être
    aidé par personne. On note l'Espace et l'action — jamais le nom du fichier
    ouvert ni l'adresse visitée : ce serait consigner sur disque exactement ce
    que les Espaces servent à cloisonner."""
    try:
        import syslog
        syslog.openlog("codebyr", syslog.LOG_PID, syslog.LOG_USER)
        syslog.syslog(syslog.LOG_INFO, message)
        syslog.closelog()
    except Exception:
        pass    # un journal absent ne doit jamais empêcher un lancement

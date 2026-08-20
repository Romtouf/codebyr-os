---
name: Signaler une anomalie
about: Quelque chose ne fonctionne pas comme prévu
labels: anomalie
---

<!--
⚠️ FAILLE DE SÉCURITÉ ? N'ouvrez pas d'issue publique.
Passez par « Security » → « Report a vulnerability » (signalement privé),
ou voir SECURITY.md.
-->

## Ce qui se passe

<!-- Décrivez ce que vous avez observé. Une photo de l'écran aide beaucoup. -->

## Ce que vous attendiez

## Pour le reproduire

1.
2.
3.

## Votre système

<!-- Collez la sortie de ces trois commandes : -->

```
cat /etc/os-release | head -2
dpkg -l codebyr-tools | tail -1
codebyr-space isolation
```

## Journal

<!-- Si le problème concerne un Espace ou une application qui ne démarre pas : -->

```
journalctl -t codebyr -n 30 --no-pager
```

## Machine

- Modèle / carte graphique :
- Démarrage : UEFI ou BIOS ?
- Installé sur disque, ou session live ?

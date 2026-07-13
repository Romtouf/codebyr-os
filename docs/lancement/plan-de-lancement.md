# Plan de lancement — Codebyr OS 1.0

Objectif : une **vague concentrée sur une seule journée** (le « jour J »), pas des
gouttes éparpillées. Un lancement groupé maximise les chances qu'un canal
s'emballe et entraîne les autres.

## Avant le jour J (prérequis, dans l'ordre)

- [x] **Captures d'écran** → voir [captures.md](captures.md). Sans elles, ne pas
      lancer : un README d'OS sans image ne convertit personne.
- [x] **README mis à jour** avec la galerie de captures.
- [x] **Site en ligne** → <https://os.codebyr.dev> (auto-hébergé, Docker + NPM,
      aucune ressource tierce). C'est l'URL du Show HN.
- [x] **Release vérifiée de bout en bout** : `gpg --verify SHA256SUMS.asc SHA256SUMS`
      → *Good signature*, et `sha256sum -c SHA256SUMS` → *OK*. Testé depuis une
      autre machine que celle de build.
- [ ] **Répondre présent le jour J** : bloquer la journée. Les 6 premières heures
      de commentaires décident du sort d'un post. Répondre vite, honnêtement,
      sans se défendre — le ton « voici ce que ça fait, voici ce que ça ne fait
      pas » est notre marque.

> Décision : **pas de vidéo de démo** pour le lancement 1.0. Les captures d'écran
> portent le message. ([video-demo.md](video-demo.md) reste en réserve pour plus tard.)

## Le jour J (un mardi ou mercredi, lancer le matin heure de Paris)

| Heure (Paris) | Canal | Contenu |
|---|---|---|
| 9 h | **LinuxFr** (journal) | [posts/linuxfr.md](posts/linuxfr.md) — le cœur francophone |
| 9 h 30 | **Mastodon + X** | [posts/mastodon-x.md](posts/mastodon-x.md) — avec 2 à 4 captures d'écran |
| 15 h | **Hacker News** (Show HN) | [posts/show-hn.md](posts/show-hn.md) — 15 h Paris = 9 h côte Est, le créneau HN |
| 15 h 15 | **r/linux** (Reddit) | [posts/reddit-r-linux.md](posts/reddit-r-linux.md) |

Ne PAS spammer d'autres subreddits le même jour (r/opensource, r/privacy
peuvent venir en semaine 2 si la sauce prend).

## Après

- **Semaine 1** : répondre à tout, corriger les bugs signalés vite (nos
  correctifs rapides sont un argument marketing en soi).
- **Semaine 2** : soumettre la fiche à **DistroWatch** (formulaire « submit
  distribution ») — long délai d'attente, autant lancer tôt.
- **En continu** : le protocole des 5 testeurs → [protocole-testeurs.md](protocole-testeurs.md).

## Messages clés (à marteler partout, sans en dévier)

1. **La compartimentation de Qubes, pour les gens normaux.** Des « Espaces »
   colorés au lieu de VM à configurer.
2. **La pièce jointe piégée qui explose dans le vide** : ouverte en Jetable =
   sans réseau, autodétruite. Démontrable en 20 secondes.
3. **Honnête** : « réduit drastiquement les dégâts », jamais « invulnérable ».
   Le modèle de menace est public (SECURITY.md).
4. **En français d'abord**, gratuit, GPL-3.0, base Debian stable.

## Ce qu'on ne dit JAMAIS

- « Aussi sûr que Qubes » (faux : namespaces ≠ VM matérielles).
- « Impossible de se faire pirater » (personne ne peut promettre ça).
- Attaquer d'autres distros. On se compare à un *problème* (l'hameçonnage,
  les pièces jointes), pas à des projets.

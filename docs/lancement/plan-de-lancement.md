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

## Le jour J — lancement 1.0 : **LinkedIn uniquement**

| Heure (Paris) | Canal | Contenu |
|---|---|---|
| 8 h – 10 h, mardi ou mercredi | **LinkedIn** | [posts/linkedin.md](posts/linkedin.md) — 3 à 4 captures, lien en 1er commentaire |

**Pourquoi ce choix, et ce qu'il coûte.** LinkedIn ne demande aucun compte à
mûrir : on peut publier tout de suite, sans risque de suppression automatique.
Mais l'audience est professionnelle et francophone, pas la communauté
Linux/sécurité : attendre de la visibilité et des encouragements, **peu de
testeurs réels**, et surtout **pas le retour adversarial** sur le modèle de
sécurité. C'est un lancement doux, assumé comme tel.

## Plus tard — les canaux techniques (si tu veux de vrais testeurs)

Les posts sont **déjà écrits et à jour** : [LinuxFr](posts/linuxfr.md),
[Show HN](posts/show-hn.md), [r/linux](posts/reddit-r-linux.md),
[Mastodon + X](posts/mastodon-x.md).

Le seul obstacle est l'**ancienneté des comptes** : r/linux (et, à un moindre
degré, HN) filtrent automatiquement les comptes neufs sans historique — un post
d'autopromotion depuis un compte créé le matin même a de fortes chances d'être
supprimé sans que tu t'en aperçoives.

La marche à suivre, si tu t'y lances :
1. Créer les comptes **maintenant** (le compteur d'ancienneté démarre).
2. Participer **sincèrement** 2 à 4 semaines, sans parler de Codebyr.
3. Lire les règles d'autopromotion de r/linux avant de poster.
4. Jamais de faux votes ni de comptes multiples : bannissement définitif.

Calendrier prévu le jour venu : LinuxFr 9 h → Mastodon 9 h 30 → Show HN 15 h
(= 9 h côte Est) → r/linux 15 h 15. Ne PAS spammer d'autres subreddits le même
jour.

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

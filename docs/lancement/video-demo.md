# Vidéo démo — 30 secondes qui disent tout

**Le pitch en une phrase** : une pièce jointe piégée s'ouvre dans une bulle sans
réseau qui s'autodétruit — regardez.

## Tournage (sur le Envy, session propre)

Enregistreur d'écran intégré GNOME : **Ctrl + Maj + Alt + R** (ou Impr écran →
onglet vidéo). Format webm, prêt pour le web. Pas besoin de son : sous-titres
incrustés au montage (beaucoup regardent sans le son).

## Storyboard (7 plans, ~30 s)

| # | Durée | À l'écran | Sous-titre incrusté |
|---|---|---|---|
| 1 | 3 s | Bureau Codebyr, dossier avec `facture-urgente.pdf` | « Une pièce jointe douteuse ? » |
| 2 | 4 s | Clic droit → Ouvrir avec… → **Ouvrir en Jetable** | « Ouvrez-la en Jetable. » |
| 3 | 5 s | Le PDF s'ouvre, **liseré rouge** autour de la fenêtre | « Elle s'ouvre dans une bulle isolée… » |
| 4 | 5 s | Terminal dans la bulle : `ping google.fr` → échec | « …coupée d'internet : rien ne peut fuiter. » |
| 5 | 4 s | On ferme la fenêtre → terminal : `Espace jetable détruit.` | « On ferme : la bulle s'autodétruit. » |
| 6 | 5 s | Menu du Sceau ouvert, les 5 Espaces colorés | « Codebyr OS : votre vie numérique, en bulles étanches. » |
| 7 | 4 s | Logo Sceau + « codebyr OS » + URL GitHub | « Gratuit, open source, en français. » |

Pour le plan 4 : `codebyr-space launch jetable -- kgx` ouvre un terminal *dans*
la bulle (le ping y échouera — c'est la preuve visuelle du hors-ligne).

## Montage

N'importe quel outil fait l'affaire (Kdenlive sur Codebyr même, ou CapCut/Canva).
Sous-titres gros et lisibles sur mobile. Exporter en 1080p, format MP4 **et**
une version carrée pour Mastodon/X si possible.

## Où la publier

- En tête du README (GitHub lit les .mp4 dans les issues/releases ; sinon GIF)
- Jointe aux posts Mastodon/X (autoplay = énorme avantage)
- En lien dans le journal LinuxFr et les commentaires HN/Reddit

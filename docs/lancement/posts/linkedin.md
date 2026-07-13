# LinkedIn — post de lancement

**Quand :** mardi ou mercredi, entre 8 h et 10 h (heure de Paris). C'est le
créneau où LinkedIn pousse le plus.

**Images à joindre** (LinkedIn favorise les posts avec visuels — 3 à 4 captures) :

1. `captures_ecran/01-bureau.png` — le bureau (l'aperçu, la plus « belle »)
2. `captures_ecran/02-menu-sceau.png` — les Espaces colorés
3. `captures_ecran/05-lisere-fenetre.png` — le liseré coloré d'une fenêtre
4. `captures_ecran/04-lien-jetable.png` — « Ouvrir un lien en Jetable »

⚠️ **Le lien** : LinkedIn réduit fortement la portée des posts contenant un lien
externe dans le corps du texte. Deux options :
- **(recommandé)** ne PAS mettre le lien dans le post, et le poster en
  **premier commentaire**, immédiatement après publication. Ajouter alors à la
  fin du post : « 🔗 Lien en commentaire. »
- ou l'assumer dans le corps si tu préfères la simplicité.

---

## Le post

Un proche a failli se faire avoir par un faux mail de sa banque. Deux fois.

La deuxième fois, j'ai réalisé quelque chose d'inconfortable : je peux lui
expliquer les bons réflexes pendant des heures, il suffit d'**un** moment de
fatigue, d'un mail bien imité, et tout tombe.

Le problème n'est pas les gens. Le problème est que nos ordinateurs mélangent
tout : la banque, les mails, les téléchargements douteux, le travail — dans le
même espace, avec les mêmes droits. Un seul piège, et tout est exposé.

Alors j'ai passé plusieurs mois à construire ce que j'aurais voulu pouvoir lui
installer.

**Codebyr OS** — un système d'exploitation libre, basé sur Debian, qui cloisonne
votre vie numérique en **Espaces** isolés, chacun avec sa couleur :

🔵 Personnel — votre quotidien
🟣 Travail — vos documents pro
🟢 Banque — UNIQUEMENT les sites de votre banque, rien d'autre n'y entre
🟠 Navigation — le web ordinaire, isolé du reste
🔴 Jetable — éphémère, s'autodétruit à la fermeture

Chaque fenêtre porte un liseré à la couleur de son Espace. Aucun jargon, aucune
configuration : **la couleur dit tout**.

Concrètement, une pièce jointe suspecte s'ouvre d'un clic droit dans une bulle
**sans aucun accès réseau**, qui s'efface entièrement à la fermeture. Le piège
explose dans le vide : il ne peut rien voler, rien contacter, rien laisser
derrière lui.

L'idée n'est pas de moi — c'est celle de Qubes OS, un système brillant mais
réservé aux experts, qui exige 16 Go de RAM et une patience infinie. J'ai voulu
la rendre accessible : Codebyr tourne sur un portable de 2015 avec 8 Go.

**Et je préfère être honnête sur ce que ça ne fait pas.**

Ce n'est pas Qubes. L'isolation repose sur les mécanismes du noyau Linux, pas
sur des machines virtuelles matérielles — une faille noyau pourrait
théoriquement s'en échapper. Codebyr réduit **drastiquement** les dégâts des
menaces du quotidien. Il ne rend pas invulnérable, et je ne le prétendrai
jamais. Le modèle de sécurité complet est documenté publiquement, limites
comprises.

C'est gratuit, open source (GPL-3.0), en français, et l'ISO est signée.

Je cherche maintenant des **testeurs** — et surtout des retours francs, y compris
sur ce qui ne va pas.

🔗 Lien en commentaire.

#Cybersécurité #Linux #OpenSource #ViePrivée #Debian

---

**Premier commentaire (à poster immédiatement) :**

Le site (captures d'écran, modèle de sécurité détaillé) : https://os.codebyr.dev
Le code et l'ISO signée : https://github.com/Romtouf/codebyr-os

Tout est ouvert : le code, la charte, l'architecture, et les limites.

---

**Notes à toi-même :**
- **Répondre à TOUS les commentaires** dans les premières heures. LinkedIn
  mesure l'engagement précoce pour décider de la diffusion.
- Ne pas modifier le post dans les 30 premières minutes (ça pénalise la portée).
- Si quelqu'un signale une faille : remercier publiquement, ouvrir une issue,
  corriger vite. C'est le meilleur signal possible.
- Ton public est majoritairement non-Linux : ne pas te laisser entraîner dans un
  débat technique de niche. Reste sur le « pourquoi », pas sur bubblewrap.

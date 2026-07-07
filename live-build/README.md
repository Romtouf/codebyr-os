# Codebyr OS — construction de l'ISO (Phase 1)

Cette configuration `live-build` produit l'ISO **Codebyr OS** : Debian 13 (trixie)
+ GNOME, durcie et brandée, démarrable en live et installable.

## Prérequis (déjà en place sur cette machine)

- **WSL2** avec la distribution **`Codebyr-Build`** (Debian 13 trixie).
- La chaîne de build : `live-build`, `debootstrap`, `xorriso`, `squashfs-tools`,
  `librsvg2-bin`… installée par [scripts/provision-wsl.sh](scripts/provision-wsl.sh).

Pour reprovisionner de zéro depuis Windows :

```powershell
wsl -d Codebyr-Build -u root -- bash -c "sed 's/\r$//' /mnt/c/Users/pcrom/codebyros/live-build/scripts/provision-wsl.sh | bash"
```

## Construire l'ISO

Depuis Windows (PowerShell) :

```powershell
wsl -d Codebyr-Build -u root -- bash -c "sed 's/\r$//' /mnt/c/Users/pcrom/codebyros/live-build/scripts/build.sh > /tmp/build.sh; CODEBYR_REPO=/mnt/c/Users/pcrom/codebyros bash /tmp/build.sh"
```

> `CODEBYR_REPO` indique au script la racine du dépôt ; il refuse de démarrer
> sans une config live-build valide (garde-fou anti-copie accidentelle).

L'ISO apparaît dans [`dist/`](../dist/) sous le nom
`codebyr-os-1.0-AAAAMMJJ-amd64.iso`.

> **Pourquoi recopier la config ?** `live-build` fait des `chroot`, des montages
> et manipule les attributs étendus : impossible sur `/mnt/c` (9p). Le script
> `build.sh` recopie donc la config dans `/var/tmp/codebyr-build` (ext4 natif de
> WSL) et n'y rapatrie que l'ISO finale.

Nettoyer l'arbre de build : ajoutez `clean` à la fin de la commande `build.sh`.

## Ce que contient l'image

| Domaine | Détail |
|---|---|
| **Base** | Debian 13 trixie, amd64, `main contrib non-free non-free-firmware` |
| **Bureau** | GNOME (Shell, GDM, Fichiers, Logiciels), Firefox ESR, Flatpak + Flathub |
| **Durcissement** | AppArmor (enforce), nftables (entrée fermée), MAJ auto, sysctl durci, LUKS prêt |
| **Branding** | os-release « Codebyr OS », fonds d'écran clair/sombre, accent GNOME teal, thème Plymouth « codebyr », favoris de la barre |
| **Installateur** | Debian Installer (live) — Calamares brandé viendra en Phase 4 |

## Arborescence

```
live-build/
├── auto/config                         Options lb config
├── config/
│   ├── package-lists/
│   │   ├── desktop.list.chroot         GNOME + apps
│   │   ├── hardening.list.chroot       apparmor, nftables, firmware, LUKS…
│   │   └── codebyr.list.chroot         plymouth + outils Codebyr
│   ├── hooks/normal/
│   │   ├── 0100-branding.hook.chroot   os-release, wallpapers, plymouth, dconf
│   │   └── 0200-hardening.hook.chroot  pare-feu, MAJ auto, sysctl
│   └── includes.chroot/                Fichiers injectés (thème Plymouth, dconf…)
├── scripts/
│   ├── provision-wsl.sh                Prépare l'environnement de build
│   └── build.sh                        Construit l'ISO
└── README.md
```

## Tester l'ISO

- **VirtualBox / VMware / GNOME Boxes** : démarrer la VM sur l'ISO (mode UEFI).
- **Hyper-V** (déjà présent sur cette machine) : VM de 2e génération, Secure Boot
  désactivé, démarrer sur l'ISO.
- **Clé USB réelle** : `dd` ou Rufus (l'ISO est hybride).

Donnez à la VM au moins **2 Go de RAM** et **20 Go de disque** pour un essai
confortable (l'installation avec chiffrement en demande un peu plus).

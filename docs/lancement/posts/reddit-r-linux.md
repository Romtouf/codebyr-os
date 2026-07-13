# r/linux — flair "Fluff" ou "Development" selon disponibilité

**Title:**

I built Codebyr OS: a Debian-based distro bringing Qubes-style compartmentalization to non-technical users (color-coded isolated "Spaces", no-network disposable sandboxes for attachments)

**Body:**

After watching family members nearly fall for phishing twice, I spent the last
months building the distro I wished I could install for them.

**Codebyr OS** takes the compartmentalization idea from Qubes and strips away
everything that makes it expert-only. Users get five color-coded **Spaces**
(Personal, Work, Bank, Browsing, Disposable) — every window wears a colored
border, isolation is the default, nothing to configure.

Highlights:

- **Right-click any sketchy attachment → "Open in Disposable"** → opens in a
  bubblewrap sandbox with an unshared network namespace (zero connectivity)
  that self-destructs on close.
- **Bank Space** can only reach a whitelist of *your* bank's domains; other
  Spaces get a look-alike-domain phishing detector in Firefox.
- Per-Space snapshots ("time machine"), auto-wiping guest mode, local-only
  security assistant, ~150 locales (French-first), Calamares installer that
  works fully offline, Flathub out of the box.
- Hardened mode: userns + cap-drop ALL + new session + cgroup memory/task
  caps + private D-Bus per Space.

**Honesty section**: it's namespaces, not VMs — this is *not* Qubes-grade
isolation and the README/SECURITY.md say so explicitly. KVM micro-VMs are the
planned next tier (hardware detection already ships). The promise is
"drastically reduce everyday damage", not "unhackable".

GPL-3.0, reproducible with live-build in 3 commands. Releases are GPG-signed
and the verification steps in the README work end-to-end.

- Site + screenshots: https://os.codebyr.dev
- Source + signed ISO: https://github.com/Romtouf/codebyr-os

Feedback — especially adversarial security feedback — very welcome.

---

**Notes :** répondre vite, ton posé. r/linux est dur avec les nouvelles distros
(« yet another Debian respin ») → réponse préparée : « Fair! The différence is
the userland: the Space engine, the disposable pipeline, the phishing shield
and the per-Space networking are all purpose-built (~3k lines), not a theme. »

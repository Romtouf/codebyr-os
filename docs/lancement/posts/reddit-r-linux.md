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
- **Bank Space**'s browser can only reach an allow-list of *your* bank's
  domains: the Space has no network interface of its own, everything goes
  through an AppArmor-confined filter. Other Spaces get a Mozilla-signed
  look-alike-domain phishing detector in Firefox.
- Per-Space snapshots ("time machine"), auto-wiping guest mode, local-only
  security assistant, French and English, Calamares installer that works
  fully offline, Flathub out of the box.
- Each Space runs under its own Unix account. Hardened mode: userns +
  cap-drop ALL + new session + cgroup memory/task caps + allow-list seccomp
  + Landlock; private D-Bus per Space.

**Honesty section**: it's namespaces, not VMs — this is *not* Qubes-grade
isolation and the README/SECURITY.md say so explicitly. A kernel 0-day escapes
a namespace; that's an accepted limitation of the model. The promise is
"drastically reduce everyday damage", not "unhackable".

GPL-3.0. The ISO is reproducible: rebuilt from the published source, it is
byte-for-byte identical. Releases are GPG-signed and the verification steps
in the README work end-to-end. No professional audit yet; an outside code
review (October 2026) found four defects, all fixed — see SECURITY.md.

- Site + screenshots: https://os.codebyr.dev
- Source + signed ISO: https://github.com/Romtouf/codebyr-os

Feedback — especially adversarial security feedback — very welcome.

---

**Notes :** répondre vite, ton posé. r/linux est dur avec les nouvelles distros
(« yet another Debian respin ») → réponse préparée : « Fair! The différence is
the userland: the Space engine, the disposable pipeline, the phishing shield
and the per-Space networking are all purpose-built (~13k lines), not a theme. »
Avant de poster : relire la section « Analyse externe » de SECURITY.md.

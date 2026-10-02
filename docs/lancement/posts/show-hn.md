# Show HN — submit at ~9am US Eastern (15h Paris)

**Title (80 chars max):**

Show HN: Codebyr OS – Qubes-style compartmentalization for non-technical users

**URL:** https://os.codebyr.dev

**First comment (post it yourself immediately after submitting — sets the tone):**

Hi HN! Solo builder here. Codebyr OS is a Debian-based distro that takes the
core idea of Qubes OS — security through compartmentalization — and makes it
usable by people who will never read a wiki.

Instead of VMs/domains/templates, users get color-coded "Spaces": Personal
(blue), Work (purple), Bank (green), Browsing (orange), Disposable (red).
Every window gets a colored border showing which Space it lives in.

The three features I'm most proud of:

- **Disposable attachments**: right-click a sketchy file → "Open in
  Disposable" → it opens in a sandbox with *no network* (unshared netns)
  that self-destructs on close. A malicious PDF can't phone home and
  leaves nothing behind.
- **Bank Space**: its browser can reach *your* bank's domains and nothing
  else. The Space has no network interface of its own — everything goes
  through an allow-list filter, itself confined by AppArmor, which also
  refuses LAN addresses. Other Spaces get a Mozilla-signed look-alike-domain
  detector, homographs included.
- **`codebyr-space verifier-isolation`**: it launches a probe *inside a real
  sandbox* and reports what a Space can actually reach — host session bus,
  systemd --user, X11 socket, network, home directory — against what each
  situation is supposed to allow. It measures instead of claiming. There's a
  companion `verifier-poste` that checks the installed machine the same way:
  guest account passwordless, home dirs 0700, apt keyring current, unattended
  upgrades actually armed. Every check exists because that exact thing broke
  here once, silently.

Isolation is bubblewrap (kernel namespaces), and **each Space runs under
its own Unix account**, so a sandbox escape still can't read the other
Spaces' files. Hardened mode adds: user namespace, cap-drop ALL, new session,
memory/task cgroup limits, an allow-list seccomp filter and a Landlock
scope; private D-Bus per Space.

**What it is NOT**: this is not Qubes. No hardware virtualization — isolation
is kernel-based, so a kernel 0-day escapes a namespace. That's an accepted
limitation, spelled out in SECURITY.md — the promise is "drastically reduces
damage from everyday
threats", never "unhackable".

State: v1.20 (October 2026), live ISO, installable (Calamares, works
fully offline), tested on real hardware, updates through apt, French and
English, GPL-3.0. **The ISO is reproducible**: rebuilt from the published
source, it is byte-for-byte identical.
Releases are GPG-signed by a subkey whose master key lives offline on
removable media — the verification steps are in the README and they actually
work end-to-end, from a clean keyring.

Two things you should weigh before trying it: **no professional audit** —
an outside code review in October 2026 found four defects, all fixed — and
as far as the download counters tell me, **I'm still the only person running
it**. That's the honest state, and it's most of why I'm posting. The security
fix history — including a sandbox escape closed in 1.1.0 and two privilege
escalations I found by re-reading the code — is in SECURITY.md rather than
buried in commits.

Source + signed ISO: https://github.com/Romtouf/codebyr-os
(Screenshots in the README, and the site serves no third-party requests —
self-hosted fonts, no analytics, no CDN. Seemed like the least I could do
for a project that sells privacy.)

I'd genuinely value adversarial feedback on the security model — that's
how it gets better. Happy to answer anything.

---

**Notes à moi-même :**
- Répondre à TOUS les commentaires les 6 premières heures.
- Si quelqu'un trouve une faille : remercier publiquement, ouvrir une issue,
  corriger vite. C'est le meilleur marketing possible.
- Ne pas éditer le titre après coup (HN pénalise).
- Avant de poster : mettre à jour le numéro de version, et relire la section
  « Analyse externe » de SECURITY.md.

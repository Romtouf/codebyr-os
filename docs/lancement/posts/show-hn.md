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
- **Bank Space**: its browser is forced through a local allow-list proxy
  (*your* bank's domains only — a guardrail against human error, not yet a
  system-level network rule; documented in SECURITY.md), plus a
  look-alike-domain detector in other Spaces' browsers.
- **`codebyr-space verifier-isolation`**: it launches a probe *inside a real
  sandbox* and reports what a Space can actually reach — host session bus,
  systemd --user, X11 socket, network, home directory — against what each
  situation is supposed to allow. It measures instead of claiming. There's a
  companion `verifier-poste` that checks the installed machine the same way:
  guest account passwordless, home dirs 0700, apt keyring current, unattended
  upgrades actually armed. Every check exists because that exact thing broke
  here once, silently.

Isolation is bubblewrap (kernel namespaces) with a hardened mode: user
namespace, cap-drop ALL, new session, memory/task cgroup limits, private
D-Bus per Space.

**What it is NOT**: this is not Qubes. No hardware virtualization — isolation
is kernel-based, so a kernel 0-day escapes a namespace. That's an accepted
limitation, spelled out in SECURITY.md — the promise is "drastically reduces
damage from everyday
threats", never "unhackable".

State: v1.5.5 live ISO, installable (Calamares, works fully offline),
tested on real hardware, French-first but ~150 locales, GPL-3.0.
Releases are GPG-signed by a subkey whose master key lives offline on
removable media — the verification steps are in the README and they actually
work end-to-end, from a clean keyring.

Two things you should weigh before trying it: **no external audit**, and as
far as the download counters tell me, **I'm still the only person running
it**. That's the honest state, and it's most of why I'm posting. The security
fix history — including a sandbox escape I found and closed in 1.1.0 — is in
SECURITY.md rather than buried in commits.

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

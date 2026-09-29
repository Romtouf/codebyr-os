/* Codebyr OS — Bouclier anti-hameçonnage (content script).
 * Compare le domaine visité aux domaines de banque protégés. Si le site
 * RESSEMBLE à une banque sans être son domaine officiel, il barre la page
 * d'un avertissement.
 *
 * Les domaines protégés sont lus via le STOCKAGE MANAGÉ (storage.managed),
 * écrit par codebyr-space par Espace. Le code de l'extension reste donc
 * STATIQUE — condition nécessaire pour qu'il puisse être signé par Mozilla
 * (une extension signée est scellée : on ne peut plus y injecter les domaines).
 *
 * PRINCIPE DE CONCEPTION : un avertissement pleine page qu'on apprend à
 * écarter est PIRE que pas d'avertissement du tout — il détruit le réflexe
 * qu'on veut créer. Deux conséquences :
 *   1. on ne déclenche que sur des signaux précis (ci-dessous), jamais sur une
 *      simple sous-chaîne présente n'importe où dans le nom d'hôte ;
 *   2. l'utilisateur peut lever l'alerte pour un site donné, définitivement.
 */
(async function () {
    "use strict";

    const api = (typeof browser !== "undefined") ? browser
              : (typeof chrome !== "undefined") ? chrome : null;
    if (!api || !api.storage || !api.storage.managed)
        return;

    // Récupère les domaines protégés depuis le stockage managé (repli : rien).
    let PROTEGES = [];
    try {
        const res = await api.storage.managed.get("domaines");
        PROTEGES = (res && Array.isArray(res.domaines)) ? res.domaines : [];
    } catch (e) {
        return;   // aucune configuration managée disponible
    }
    if (!PROTEGES.length)
        return;

    const host = (location.hostname || "").toLowerCase();
    if (!host)
        return;

    // Site que l'utilisateur a explicitement déclaré légitime : on se tait.
    try {
        const vus = await api.storage.local.get("approuves");
        if (vus && Array.isArray(vus.approuves) && vus.approuves.indexOf(host) !== -1)
            return;
    } catch (e) { /* storage.local indisponible : on continue à protéger */ }

    // Le navigateur donne le nom d'hôte sous sa forme ASCII, dite « punycode » :
    // « mаbanque.fr », écrit avec un « а » cyrillique, arrive ici comme
    // « xn--mbanque-3ve.fr », qui ne ressemble à rien — et le bouclier se
    // taisait. On relit donc chaque étiquette comme l'utilisateur la VOIT
    // (RFC 3492). Une forme invalide est rendue telle quelle.
    function depunycode(etiquette) {
        if (etiquette.indexOf("xn--") !== 0 || etiquette.length > 63)
            return etiquette;
        const code = etiquette.slice(4);
        const base = 36, tmin = 1, tmax = 26;
        const fin = code.lastIndexOf("-");
        const sortie = fin >= 0 ? Array.from(code.slice(0, fin)) : [];
        let n = 128, i = 0, biais = 72, pos = fin >= 0 ? fin + 1 : 0;
        while (pos < code.length) {
            const avant = i;
            for (let w = 1, k = base; ; k += base) {
                if (pos >= code.length)
                    return etiquette;
                const c = code.charCodeAt(pos++);
                const chiffre = (c >= 48 && c <= 57) ? c - 22
                              : (c >= 97 && c <= 122) ? c - 97 : base;
                if (chiffre >= base)
                    return etiquette;
                i += chiffre * w;
                const t = k <= biais ? tmin : k >= biais + tmax ? tmax : k - biais;
                if (chiffre < t)
                    break;
                w *= base - t;
            }
            // Adaptation du biais (RFC 3492, § 6.1).
            const total = sortie.length + 1;
            let delta = Math.floor((i - avant) / (avant === 0 ? 700 : 2));
            delta += Math.floor(delta / total);
            let k = 0;
            for (; delta > 455; k += base)
                delta = Math.floor(delta / 35);
            biais = k + Math.floor(36 * delta / (delta + 38));
            n += Math.floor(i / total);
            i %= total;
            if (n > 0x10FFFF)
                return etiquette;
            sortie.splice(i++, 0, String.fromCodePoint(n));
        }
        return sortie.join("");
    }

    // Lettres d'autres alphabets qui se font passer pour des lettres latines :
    // « раураl », tout en cyrillique, s'affiche comme « paypal ». La table
    // s'en tient aux sosies qui trompent vraiment à l'écran. Elle est écrite
    // en codes : dans une table de sosies, « а » et « a » ne se relisent pas.
    // Les accents, eux, tombent avec la décomposition Unicode.
    const SOSIES = {
        // cyrillique : а с ԁ е һ і ј к ӏ о р ԛ ѕ у х ԝ ь
        "а": "a", "с": "c", "ԁ": "d", "е": "e", "һ": "h",
        "і": "i", "ј": "j", "к": "k", "ӏ": "l", "о": "o",
        "р": "p", "ԛ": "q", "ѕ": "s", "у": "y", "х": "x",
        "ԝ": "w", "ь": "b",
        // grec : α ε η ι κ ν ο ρ τ υ χ γ ω
        "α": "a", "ε": "e", "η": "n", "ι": "i", "κ": "k",
        "ν": "v", "ο": "o", "ρ": "p", "τ": "t", "υ": "u",
        "χ": "x", "γ": "y", "ω": "w",
        // arménien : ս օ ո հ ց զ
        "ս": "u", "օ": "o", "ո": "n", "հ": "h", "ց": "g",
        "զ": "q",
        // latin étendu : ı ɑ ɡ ɩ ȷ
        "ı": "i", "ɑ": "a", "ɡ": "g", "ɩ": "i", "ȷ": "j"
    };

    // Ce que l'œil prend pour des lettres latines : « mаbánque » → « mabanque ».
    // La décomposition NFKD défait aussi les pleines chasses et les ligatures.
    function silhouette(nom) {
        let s = "";
        for (const c of nom.normalize("NFKD").replace(/\p{M}/gu, ""))
            s += SOSIES[c] || c;
        return s;
    }

    // Un nom tel qu'il s'AFFICHE. Le registre n'accepte que de l'ASCII : un
    // domaine protégé accentué y est donc inscrit en punycode, lui aussi.
    function lire(nom) {
        return nom.split(".").map(depunycode).join(".");
    }

    // L'hôte tel qu'il s'affiche, et tel que l'œil le lit.
    const hoteLu = lire(host);
    const hoteVu = silhouette(hoteLu);

    function officiel(h, p) {
        return h === p || h.endsWith("." + p);
    }

    // « www.mabanque.fr » → « mabanque » : le nom, sans le www ni l'extension.
    function coeur(d) {
        d = (d || "").toLowerCase().replace(/^www\./, "");
        const parts = d.split(".");
        return parts.length > 1 ? parts[parts.length - 2] : d;
    }

    // Confusions visuelles courantes dans les noms de domaine frauduleux.
    function normaliser(s) {
        return s.replace(/0/g, "o").replace(/1/g, "l").replace(/3/g, "e")
                .replace(/5/g, "s").replace(/rn/g, "m").replace(/vv/g, "w");
    }

    function leven(a, b) {
        const m = a.length, n = b.length;
        const dp = [];
        for (let i = 0; i <= m; i++) dp[i] = [i];
        for (let j = 0; j <= n; j++) dp[0][j] = j;
        for (let i = 1; i <= m; i++)
            for (let j = 1; j <= n; j++)
                dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1,
                                    dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        return dp[m][n];
    }

    // Renvoie le domaine protégé imité, ou null. Trois signaux SEULEMENT :
    //   a) même nom, autre extension        mabanque.fr   → mabanque.com
    //   b) nom quasi identique (typo)       mabanque.fr   → nabanque.fr
    //   c) le nom apparaît comme ÉTIQUETTE   mabanque.fr  → mabanque.piege.com
    //                                                     → mabanque-securite.com
    // Ce dernier point est la correction clé : chercher le nom n'importe où dans
    // l'hôte faisait crier le bouclier sur « revolution.com » pour « revolut ».
    // Une page d'aide officielle hébergée chez un tiers (« revolut.zendesk.com »)
    // alerte en revanche, et c'est voulu : elle a la forme exacte de
    // « mabanque.piege.com ». L'utilisateur la déclare légitime une fois.
    //
    // Les trois signaux portent sur la SILHOUETTE de l'hôte : « mаbanque.fr »
    // en cyrillique est « mabanque.fr » pour l'œil, donc pour le bouclier.
    function imposteur() {
        const etiquettes = hoteVu.split(".");
        const coeurHote = coeur(hoteVu);
        for (let k = 0; k < PROTEGES.length; k++) {
            const p = String(PROTEGES[k]).toLowerCase().replace(/^\*\./, "");
            if (!p)
                continue;
            // Domaine officiel exact (ou sous-domaine) : ce n'est PAS un
            // imposteur. Comparé tel qu'il circule ET tel qu'il s'affiche.
            if (officiel(host, p) || officiel(hoteLu, lire(p)))
                return null;
            const cp = coeur(silhouette(lire(p)));
            if (!cp || cp.length < 4)
                continue;   // un nom trop court produit trop de collisions

            // a) même nom, autre extension
            if (coeurHote === cp)
                return p;

            // b) faute de frappe / homoglyphe sur le nom lui-même
            const d = leven(normaliser(coeurHote), normaliser(cp));
            if (d > 0 && d <= 2 && Math.abs(coeurHote.length - cp.length) <= 2)
                return p;

            // c) le nom protégé sert d'étiquette ou de préfixe d'étiquette
            for (let i = 0; i < etiquettes.length; i++) {
                const e = etiquettes[i];
                if (e === cp || e.indexOf(cp + "-") === 0 || e.indexOf("-" + cp) !== -1)
                    return p;
            }
        }
        return null;
    }

    const banque = imposteur();
    if (!banque)
        return;

    async function approuver() {
        try {
            const vus = await api.storage.local.get("approuves");
            const liste = (vus && Array.isArray(vus.approuves)) ? vus.approuves : [];
            if (liste.indexOf(host) === -1)
                liste.push(host);
            await api.storage.local.set({approuves: liste});
        } catch (e) { /* rien à faire : au pire l'alerte reviendra */ }
    }

    function bloc(texte, style) {
        const el = document.createElement("div");
        el.setAttribute("style", style);
        el.textContent = texte;      // jamais innerHTML avec une donnée du site
        return el;
    }

    function afficher() {
        if (document.getElementById("codebyr-antiphishing"))
            return;
        const o = document.createElement("div");
        o.id = "codebyr-antiphishing";
        o.setAttribute("style",
            "position:fixed;inset:0;z-index:2147483647;background:#7f1d1d;color:#fff;" +
            "display:flex;align-items:center;justify-content:center;padding:24px;" +
            "font-family:system-ui,sans-serif;");

        const carte = document.createElement("div");
        carte.setAttribute("style", "max-width:560px;text-align:center;");
        carte.appendChild(bloc("⚠️", "font-size:60px;line-height:1;"));
        carte.appendChild(bloc("Attention — site suspect",
            "font-size:26px;font-weight:700;margin:14px 0 8px;"));
        carte.appendChild(bloc(
            "Ce site (" + host + ") ressemble au site de votre banque (" + banque +
            ") mais ce n'en est pas le site officiel.",
            "font-size:17px;line-height:1.6;"));
        // L'adresse affichée par le navigateur peut être identique à l'œil
        // à celle de la banque : on dit pourquoi elle ne l'est pas.
        if (hoteLu !== host)
            carte.appendChild(bloc(
                "Son adresse imite des lettres ordinaires avec des caractères " +
                "d'un autre alphabet, ou accentués : sous son apparence, elle " +
                "s'écrit « " + host + " ».",
                "font-size:17px;line-height:1.6;margin-top:12px;"));
        carte.appendChild(bloc(
            "N'entrez jamais vos identifiants ici. Pour votre banque, utilisez " +
            "l'Espace Banque de Codebyr OS.",
            "font-size:17px;line-height:1.6;margin-top:12px;font-weight:700;"));

        const boutons = document.createElement("div");
        boutons.setAttribute("style",
            "margin-top:18px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;");

        const quitter = document.createElement("button");
        quitter.textContent = "Quitter ce site";
        quitter.setAttribute("style",
            "padding:11px 22px;font-size:15px;border:0;border-radius:10px;" +
            "background:#fff;color:#7f1d1d;font-weight:700;cursor:pointer;");
        quitter.addEventListener("click", function () { location.href = "about:blank"; });
        boutons.appendChild(quitter);

        // Soupape indispensable : sans elle, un seul faux positif transforme le
        // bouclier en gêne qu'on apprend à ignorer.
        const continuer = document.createElement("button");
        continuer.textContent = "Ce site est légitime, ne plus me prévenir";
        continuer.setAttribute("style",
            "padding:11px 22px;font-size:15px;border:1px solid rgba(255,255,255,.5);" +
            "border-radius:10px;background:transparent;color:#fff;cursor:pointer;");
        continuer.addEventListener("click", async function () {
            await approuver();
            o.remove();
        });
        boutons.appendChild(continuer);

        carte.appendChild(boutons);
        carte.appendChild(bloc("Protection Codebyr OS",
            "margin-top:18px;opacity:.75;font-size:13px;"));
        o.appendChild(carte);
        (document.body || document.documentElement).appendChild(o);
    }

    if (document.body) afficher();
    document.addEventListener("DOMContentLoaded", afficher);
    const iv = setInterval(function () {
        if (document.body) { afficher(); clearInterval(iv); }
    }, 40);
    setTimeout(function () { clearInterval(iv); }, 6000);
})();

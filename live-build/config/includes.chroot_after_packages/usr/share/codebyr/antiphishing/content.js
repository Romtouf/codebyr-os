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
 *
 * Ce fichier DÉTECTE ; il ne dessine plus l'alerte que par secours. Le dessin
 * est dans rendu.js (chargé avant lui), la page d'alerte dans alerte.html.
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

    // ── L'ALERTE, DEPUIS LA 1.5 ─────────────────────────────────────────────
    // Jusqu'à la 1.4, l'alerte était un élément posé DANS la page piégée : un
    // script de cette page pouvait la retirer, la masquer, ou cliquer « Ce
    // site est légitime » à la place de l'utilisateur (analyse externe du
    // 01/10/2026). Le cas normal est désormais une page de l'EXTENSION, qui
    // remplace l'onglet (background.js) : la page piégée ne peut ni la voir,
    // ni la toucher, ni y cliquer, et seule cette page approuve un site.
    try {
        const reponse = await api.runtime.sendMessage(
            {codebyr: "imposteur", hote: host, lu: hoteLu, banque: banque});
        if (reponse && reponse.ok)
            return;
    } catch (e) { /* arrière-plan injoignable : secours ci-dessous */ }

    // Secours, si la page d'alerte n'a pas pu s'ouvrir : l'alerte dans la
    // page, mais enfermée (racine d'ombre fermée : aucun script de la page
    // n'atteint ses boutons), remise en place si la page la retire, et
    // sourde aux clics simulés (codebyrCarteAlerte).
    //
    // Les textes viennent de _locales/<langue>/messages.json, dans la langue
    // de Firefox, l'anglais à défaut, comme le reste de Codebyr.
    function texte(cle, valeurs) {
        return (api.i18n && api.i18n.getMessage(cle, valeurs || [])) || cle;
    }

    const STYLE_HOTE = "all:initial !important;position:fixed !important;inset:0 !important;" +
                       "z-index:2147483647 !important;display:block !important;";
    let leve = false;
    const enveloppe = document.createElement("div");
    const ombre = enveloppe.attachShadow({mode: "closed"});
    const fond = document.createElement("div");
    fond.setAttribute("style", "position:fixed;inset:0;" + codebyrFondAlerte());
    fond.appendChild(codebyrCarteAlerte(document, texte, {hote: host, lu: hoteLu, banque: banque}, {
        quitter: function () { location.href = "about:blank"; },
        legitime: async function () {
            leve = true;
            await codebyrApprouver(api, host);
            enveloppe.remove();
        },
    }));
    ombre.appendChild(fond);

    function poser() {
        if (leve)
            return;
        if (enveloppe.getAttribute("style") !== STYLE_HOTE)
            enveloppe.setAttribute("style", STYLE_HOTE);
        const racine = document.documentElement;
        if (racine && enveloppe.parentNode !== racine)
            racine.appendChild(enveloppe);
    }
    poser();
    setInterval(poser, 200);
})();

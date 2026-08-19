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
    // l'hôte faisait crier le bouclier sur « revolut.zendesk.com » ou sur toute
    // page d'aide officielle hébergée sur un sous-domaine tiers.
    function imposteur() {
        const etiquettes = host.split(".");
        const coeurHote = coeur(host);
        for (let k = 0; k < PROTEGES.length; k++) {
            const p = String(PROTEGES[k]).toLowerCase().replace(/^\*\./, "");
            if (!p)
                continue;
            // Domaine officiel exact (ou sous-domaine) : ce n'est PAS un imposteur.
            if (host === p || host.endsWith("." + p))
                return null;
            const cp = coeur(p);
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

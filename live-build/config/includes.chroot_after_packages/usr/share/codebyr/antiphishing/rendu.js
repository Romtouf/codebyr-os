/* Codebyr OS — Bouclier anti-hameçonnage : le dessin de l'alerte.
 *
 * Partagé par la page d'alerte de l'extension (alerte.html, le cas normal) et
 * par l'alerte de secours que content.js pose dans la page quand cette page
 * ne peut pas s'ouvrir. Un seul dessin, donc un seul texte à tenir.
 *
 * Les valeurs (le site, la banque) viennent du site visité : elles ne passent
 * que par textContent, jamais par du HTML interprété.
 */
"use strict";

// Des FONCTIONS, et non des constantes : entre deux scripts de contenu
// (rendu.js puis content.js), seules les déclarations de fonction sont
// assurément partagées.
function codebyrFondAlerte() {
    return "background:#7f1d1d;color:#fff;display:flex;align-items:center;" +
           "justify-content:center;padding:24px;font-family:system-ui,sans-serif;";
}

// « Ce site est légitime » : retenu pour ce nom d'hôte, définitivement.
async function codebyrApprouver(api, hote) {
    try {
        const vus = await api.storage.local.get("approuves");
        const liste = (vus && Array.isArray(vus.approuves)) ? vus.approuves : [];
        if (liste.indexOf(hote) === -1)
            liste.push(hote);
        await api.storage.local.set({approuves: liste});
    } catch (e) { /* rien à faire : au pire l'alerte reviendra */ }
}

function codebyrCarteAlerte(document, texte, donnees, actions) {
    function bloc(contenu, style) {
        const el = document.createElement("div");
        el.setAttribute("style", style);
        el.textContent = contenu;
        return el;
    }

    const carte = document.createElement("div");
    carte.setAttribute("style", "max-width:560px;text-align:center;");
    carte.appendChild(bloc("⚠️", "font-size:60px;line-height:1;"));
    carte.appendChild(bloc(texte("titre"),
        "font-size:26px;font-weight:700;margin:14px 0 8px;"));
    carte.appendChild(bloc(texte("ressemble", [donnees.hote, donnees.banque]),
        "font-size:17px;line-height:1.6;"));
    // L'adresse affichée par le navigateur peut être identique à l'œil à
    // celle de la banque : on dit pourquoi elle ne l'est pas.
    if (donnees.lu && donnees.lu !== donnees.hote)
        carte.appendChild(bloc(texte("deguise", [donnees.hote]),
            "font-size:17px;line-height:1.6;margin-top:12px;"));
    carte.appendChild(bloc(texte("jamais"),
        "font-size:17px;line-height:1.6;margin-top:12px;font-weight:700;"));

    const boutons = document.createElement("div");
    boutons.setAttribute("style",
        "margin-top:18px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;");

    // Un clic VRAI seulement : un script peut appeler .click() ou fabriquer
    // un événement, il ne peut pas le rendre « isTrusted ». Analyse externe
    // du 01/10/2026 : un script de la page piégée approuvait le site à la
    // place de l'utilisateur.
    function surVraiClic(bouton, action) {
        bouton.addEventListener("click", function (evenement) {
            if (evenement && evenement.isTrusted === true)
                return action();
            return undefined;
        });
    }

    const quitter = document.createElement("button");
    quitter.textContent = texte("quitter");
    quitter.setAttribute("style",
        "padding:11px 22px;font-size:15px;border:0;border-radius:10px;" +
        "background:#fff;color:#7f1d1d;font-weight:700;cursor:pointer;");
    surVraiClic(quitter, actions.quitter);
    boutons.appendChild(quitter);

    // Soupape indispensable : sans elle, un seul faux positif transforme le
    // bouclier en gêne qu'on apprend à ignorer.
    const continuer = document.createElement("button");
    continuer.textContent = texte("legitime");
    continuer.setAttribute("style",
        "padding:11px 22px;font-size:15px;border:1px solid rgba(255,255,255,.5);" +
        "border-radius:10px;background:transparent;color:#fff;cursor:pointer;");
    surVraiClic(continuer, actions.legitime);
    boutons.appendChild(continuer);

    carte.appendChild(boutons);
    carte.appendChild(bloc(texte("protection"),
        "margin-top:18px;opacity:.75;font-size:13px;"));
    return carte;
}

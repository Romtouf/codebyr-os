/* Codebyr OS — Bouclier : la page « site hors de la liste » (depuis la 1.6).
 *
 * Ouverte par filtre.js à la place d'un site que le filtre réseau de l'Espace
 * a refusé. Elle explique, et rien d'autre : aucun bouton n'autorise le site.
 * La liste se modifie dans « Configuration Codebyr », hors du navigateur —
 * une page, même de l'extension, n'a pas à pouvoir l'élargir.
 *
 * Paramètres (posés par filtre.js) : « hote », le site refusé ; « espace »,
 * le nom de l'Espace. Tous deux sont écrits en TEXTE, jamais en balisage.
 */
"use strict";

(function () {
    const api = (typeof browser !== "undefined") ? browser : chrome;
    const parametres = new URLSearchParams(location.search);
    const hote = (parametres.get("hote") || "").slice(0, 253);
    const espace = (parametres.get("espace") || "").slice(0, 80);

    function texte(cle, valeurs) {
        return (api.i18n && api.i18n.getMessage(cle, valeurs || [])) || cle;
    }

    function bloc(balise, contenu, style) {
        const el = document.createElement(balise);
        el.setAttribute("style", style);
        el.textContent = contenu;
        return el;
    }

    document.title = texte("refus_onglet");
    if (api.i18n && api.i18n.getUILanguage)
        document.documentElement.setAttribute("lang", api.i18n.getUILanguage());
    document.body.setAttribute("style",
        "margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
        + "background:#0B1419;color:#E7EEF1;font-family:system-ui,sans-serif;");

    const carte = document.createElement("div");
    carte.setAttribute("style", "max-width:600px;padding:24px;text-align:center;");
    carte.appendChild(bloc("div", texte("protection"),
        "display:inline-block;margin-bottom:14px;padding:4px 14px;border-radius:99px;"
        + "background:#2FA36B33;color:#5FD39B;font-size:14px;font-weight:700;"));
    carte.appendChild(bloc("h1",
        espace ? texte("refus_titre", [espace]) : texte("refus_titre_sans_nom"),
        "font-size:26px;margin:0 0 12px;"));
    carte.appendChild(bloc("p", texte("refus_detail", [hote || "?"]),
        "font-size:17px;line-height:1.6;margin:0 0 12px;"));
    carte.appendChild(bloc("p", texte("refus_ajouter"),
        "font-size:17px;line-height:1.6;margin:0 0 12px;"));
    carte.appendChild(bloc("p", texte("refus_ailleurs"),
        "font-size:17px;line-height:1.6;margin:0 0 18px;color:#93A6B0;"));

    const retour = bloc("button", texte("refus_retour"),
        "font:inherit;font-size:16px;font-weight:700;padding:10px 22px;border:0;"
        + "border-radius:8px;background:#E7EEF1;color:#0B1419;cursor:pointer;");
    retour.addEventListener("click", function () {
        if (history.length > 1)
            history.back();
        else
            location.replace("about:blank");
    });
    carte.appendChild(retour);
    document.body.appendChild(carte);
})();

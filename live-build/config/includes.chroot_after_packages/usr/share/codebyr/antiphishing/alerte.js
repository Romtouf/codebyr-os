/* Codebyr OS — Bouclier anti-hameçonnage : la page d'alerte (depuis la 1.5).
 *
 * Ouverte par background.js à la place d'un site qui imite une banque. C'est
 * une page de l'extension : le site piégé n'y a aucun accès, et c'est la
 * seule à pouvoir déclarer un site légitime — sur un vrai clic seulement.
 *
 * Paramètres (posés par background.js) : « retour », l'adresse du site telle
 * que le navigateur l'a donnée ; « lu », son nom tel qu'il s'affiche ;
 * « banque », le domaine imité. Le nom d'hôte est tiré de « retour », jamais
 * pris tel quel : c'est lui qui sera approuvé.
 */
"use strict";

(function () {
    const api = (typeof browser !== "undefined") ? browser : chrome;
    const parametres = new URLSearchParams(location.search);
    const retour = parametres.get("retour") || "";
    const lu = parametres.get("lu") || "";
    const banque = parametres.get("banque") || "";

    let hote = null;
    try {
        const u = new URL(retour);
        if (u.protocol === "http:" || u.protocol === "https:")
            hote = u.hostname;
    } catch (e) { /* adresse illisible : rien à approuver */ }

    function texte(cle, valeurs) {
        return (api.i18n && api.i18n.getMessage(cle, valeurs || [])) || cle;
    }

    document.title = texte("titre");
    if (api.i18n && api.i18n.getUILanguage)
        document.documentElement.setAttribute("lang", api.i18n.getUILanguage());
    document.body.setAttribute("style", "margin:0;min-height:100vh;" + codebyrFondAlerte());
    document.body.appendChild(codebyrCarteAlerte(document, texte,
        {hote: hote || "?", lu: lu, banque: banque}, {
            quitter: function () { location.replace("about:blank"); },
            legitime: async function () {
                if (!hote)
                    return;
                await codebyrApprouver(api, hote);
                location.replace(retour);
            },
        }));
})();

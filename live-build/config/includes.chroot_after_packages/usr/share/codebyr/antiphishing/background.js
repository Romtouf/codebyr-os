/* Codebyr OS — Bouclier anti-hameçonnage : l'arrière-plan (depuis la 1.5).
 *
 * Quand content.js reconnaît un imposteur, il le dit ici, et l'onglet est
 * remplacé par la page d'alerte de l'extension (alerte.html). Cette page
 * n'est pas « accessible au web » : aucun site ne peut l'ouvrir, l'encadrer
 * ou y écrire. La page piégée ne peut donc ni retirer l'alerte, ni cliquer à
 * la place de l'utilisateur — ce qu'elle pouvait tant que l'alerte vivait
 * dans son propre document (analyse externe du 01/10/2026).
 *
 * « loadReplace » : la page piégée quitte aussi l'historique. Le bouton
 * Précédent ne la rouvre pas.
 */
"use strict";

const api = (typeof browser !== "undefined") ? browser : chrome;

function hoteDe(adresse) {
    try {
        const u = new URL(adresse);
        return (u.protocol === "http:" || u.protocol === "https:") ? u.hostname : null;
    } catch (e) {
        return null;
    }
}

// Une demande ne compte que venue de NOTRE script de contenu, dans le cadre
// principal d'un onglet, et pour la page qu'il y voit vraiment : l'adresse
// de retour est celle que le navigateur donne (sender.url), pas une valeur
// du message.
function demandeValide(message, sender) {
    if (!message || message.codebyr !== "imposteur")
        return false;
    if (!sender || sender.id !== api.runtime.id || !sender.tab
            || typeof sender.tab.id !== "number" || sender.frameId !== 0)
        return false;
    const hote = hoteDe(sender.url);
    if (!hote || hote !== message.hote)
        return false;
    return ["lu", "banque"].every(function (cle) {
        return typeof message[cle] === "string" && message[cle].length > 0
            && message[cle].length <= 253;
    });
}

function adresseAlerte(message, sender) {
    const parametres = new URLSearchParams(
        {retour: sender.url, lu: message.lu, banque: message.banque});
    return api.runtime.getURL("alerte.html") + "?" + parametres.toString();
}

// Pas de réponse (undefined) : content.js pose alors l'alerte de secours.
api.runtime.onMessage.addListener(function (message, sender) {
    if (!demandeValide(message, sender))
        return undefined;
    return api.tabs.update(sender.tab.id,
                           {url: adresseAlerte(message, sender), loadReplace: true})
        .then(function () { return {ok: true}; },
              function () { return {ok: false}; });
});

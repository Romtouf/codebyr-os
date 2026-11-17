/* Codebyr OS — Bouclier : un site refusé s'explique (depuis la 1.6).
 *
 * Dans un Espace à liste de sites (Banque), le filtre réseau de Codebyr
 * refuse tout site hors de la liste. Pour un site en HTTPS, Firefox ne montre
 * jamais ce que le filtre répond : seulement « La connexion a été refusée par
 * le serveur proxy ». L'utilisateur y voyait une panne, pas une protection,
 * et ne savait pas qu'il pouvait autoriser le site.
 *
 * Ce script ne PROTÈGE rien : c'est le filtre qui refuse, hors du navigateur,
 * et il continue de le faire si ce script se tait. Il ne fait qu'expliquer :
 * quand un onglet part vers un site hors de la liste, il le remplace par une
 * page de l'extension (refus.html) qui dit quoi faire. Il ne peut pas
 * modifier la liste — elle lui arrive en lecture seule, par le stockage
 * managé, comme les domaines protégés (clé « filtre », absente hors d'un
 * Espace à liste : ce script ne fait alors rien).
 *
 * Seule la PAGE demandée est concernée : les ressources qu'une page de banque
 * appelle en arrière-plan (traqueurs, publicités) sont refusées en silence,
 * à chaque visite — les signaler apprendrait à ignorer le message.
 */
"use strict";

(function () {
    const api = (typeof browser !== "undefined") ? browser : chrome;
    if (!api || !api.tabs || !api.tabs.onUpdated || !api.storage || !api.storage.managed)
        return;

    function codebyrHotePropre(brut) {
        let h = String(brut || "").trim().toLowerCase().replace(/^\.+|\.+$/g, "");
        if (h.startsWith("[") && h.endsWith("]"))
            h = h.slice(1, -1);
        return h;
    }

    // La règle du filtre, à l'identique (codebyr-net-proxy, autorise) : un
    // motif « *.banque.fr » couvre banque.fr et ses sous-domaines, un nom
    // seul ne couvre que lui. Un test confronte les deux sur les mêmes cas.
    function codebyrAutorise(hote, motifs) {
        const h = codebyrHotePropre(hote);
        for (let i = 0; i < motifs.length; i++) {
            const p = String(motifs[i]).toLowerCase().trim();
            if (p.startsWith("*.")) {
                const base = p.slice(2);
                if (h === base || h.endsWith("." + base))
                    return true;
            } else if (h === p) {
                return true;
            }
        }
        return false;
    }

    function hoteDe(adresse) {
        try {
            const u = new URL(adresse);
            return (u.protocol === "http:" || u.protocol === "https:") ? u : null;
        } catch (e) {
            return null;
        }
    }

    // Relu à chaque réveil de l'arrière-plan (Firefox l'endort) ; null : cet
    // Espace n'a pas de liste, rien à expliquer.
    let lecture = null;
    function reglage() {
        if (!lecture) {
            lecture = api.storage.managed.get(["filtre", "espace"]).then(function (r) {
                if (!r || !Array.isArray(r.filtre))
                    return null;
                return {motifs: r.filtre.filter(function (m) { return typeof m === "string"; }),
                        espace: (typeof r.espace === "string") ? r.espace : ""};
            }, function () { return null; });
        }
        return lecture;
    }

    api.tabs.onUpdated.addListener(async function (onglet, changement) {
        if (!changement || typeof changement.url !== "string")
            return;
        const cible = hoteDe(changement.url);
        if (!cible)
            return;
        const r = await reglage();
        if (!r || codebyrAutorise(cible.hostname, r.motifs))
            return;
        // Le filtre note ce qu'il refuse, et « Configuration Codebyr » le
        // propose ensuite d'un clic (« Sites bloqués ») : on s'assure qu'il
        // voie la demande, même si l'onglet est remplacé avant de l'envoyer.
        try {
            fetch(cible.origin + "/", {mode: "no-cors", credentials: "omit"})
                .catch(function () {});
        } catch (e) { /* le refus est attendu */ }
        const parametres = new URLSearchParams({hote: cible.hostname, espace: r.espace});
        try {
            await api.tabs.update(onglet, {
                url: api.runtime.getURL("refus.html") + "?" + parametres.toString(),
                loadReplace: true});
        } catch (e) { /* onglet fermé entre-temps */ }
    });
})();

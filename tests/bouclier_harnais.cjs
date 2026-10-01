// Banc d'essai du bouclier anti-hameçonnage : exécute le VRAI content.js sous
// node, comme Firefox le ferait, avec un faux « browser » et un faux document.
//
// Le nom d'hôte est obtenu par « new URL(adresse).hostname » : c'est la forme
// que le navigateur donne au script (punycode pour un domaine international),
// et c'est précisément celle qui trompait le bouclier.
//
// Deux modes, sur l'entrée standard (JSON) :
//   {"mode": "adresses", "proteges": [...], "adresses": [...], "langue": "fr"}
//       → pour chaque adresse : {adresse, hote, alerte, textes}
//   {"mode": "punycode", "etiquettes": [...]}
//       → le décodeur du bouclier comparé à celui de node, étiquette par étiquette
"use strict";
const fs = require("fs");
const path = require("path");
const url = require("url");
const vm = require("vm");

const SOURCE = path.join(__dirname, "..", "live-build", "config", "includes.chroot_after_packages",
                         "usr", "share", "codebyr", "antiphishing", "content.js");
const code = fs.readFileSync(SOURCE, "utf8");

function faux_element(tag) {
    return {
        tag, id: "", textContent: "", enfants: [], attributs: {},
        setAttribute(k, v) { this.attributs[k] = v; },
        appendChild(e) { this.enfants.push(e); return e; },
        addEventListener() {},
        remove() { this.retire = true; },
    };
}

function textes(e) {
    return [e.textContent].concat(...e.enfants.map(textes)).filter(Boolean);
}

// browser.i18n.getMessage, comme Firefox : le message dans la langue du
// navigateur, sinon dans la langue par défaut du manifeste ; « $HOTE$ » est
// remplacé par sa marque (« $1 »), elle-même par la valeur donnée.
const LOCALES = path.join(path.dirname(SOURCE), "_locales");
const MANIFESTE = JSON.parse(fs.readFileSync(path.join(path.dirname(SOURCE), "manifest.json"), "utf8"));

function messages(langue) {
    const chemin = path.join(LOCALES, langue, "messages.json");
    return fs.existsSync(chemin) ? JSON.parse(fs.readFileSync(chemin, "utf8")) : {};
}

function faux_i18n(langue) {
    const propres = messages(langue), defaut = messages(MANIFESTE.default_locale);
    return {
        getMessage(cle, valeurs) {
            const entree = propres[cle] || defaut[cle];
            if (!entree)
                return "";
            const marques = entree.placeholders || {};
            return entree.message.replace(/\$([A-Za-z0-9_@]+)\$/g, (tout, nom) => {
                const marque = marques[nom.toLowerCase()];
                if (!marque)
                    return tout;
                return marque.content.replace(/\$(\d)/g, (_t, n) => String((valeurs || [])[n - 1] ?? ""));
            });
        },
    };
}

async function une_adresse(proteges, adresse, langue) {
    const hote = new URL(adresse).hostname;
    const corps = faux_element("body");
    const document = {
        body: corps, documentElement: corps,
        createElement: faux_element,
        getElementById: (id) => corps.enfants.find((e) => e.id === id) || null,
        addEventListener() {},
    };
    const browser = {storage: {
        managed: {get: async () => ({domaines: proteges})},
        local: {get: async () => ({}), set: async () => {}},
    }, i18n: faux_i18n(langue || "fr")};
    const contexte = vm.createContext({
        browser, document, location: {hostname: hote},
        setInterval: () => 0, clearInterval() {}, setTimeout: () => 0,
    });
    await vm.runInContext(code, contexte);
    const alerte = corps.enfants.find((e) => e.id === "codebyr-antiphishing");
    return {adresse, hote, alerte: Boolean(alerte), textes: alerte ? textes(alerte) : []};
}

function decodeur_du_bouclier() {
    // La fonction elle-même, extraite du fichier livré : on éprouve CE code-là.
    const debut = code.indexOf("function depunycode(");
    const fin = code.indexOf("\n    }\n", debut);
    if (debut < 0 || fin < 0)
        throw new Error("depunycode introuvable dans content.js");
    return vm.runInNewContext("(" + code.slice(debut, fin + 6) + ")");
}

async function principal() {
    const demande = JSON.parse(fs.readFileSync(0, "utf8"));
    if (demande.mode === "adresses") {
        const resultats = [];
        for (const adresse of demande.adresses)
            resultats.push(await une_adresse(demande.proteges, adresse, demande.langue));
        process.stdout.write(JSON.stringify(resultats));
    } else if (demande.mode === "punycode") {
        const depunycode = decodeur_du_bouclier();
        const ecarts = [];
        let comparees = 0;
        for (const etiquette of demande.etiquettes) {
            const ascii = url.domainToASCII(etiquette);
            if (!ascii || ascii.indexOf("xn--") !== 0)
                continue;       // restée en ASCII, ou refusée par IDNA
            comparees++;
            const attendu = url.domainToUnicode(ascii);
            const obtenu = depunycode(ascii);
            if (obtenu !== attendu)
                ecarts.push({etiquette, ascii, attendu, obtenu});
        }
        // Une forme invalide doit revenir telle quelle, sans exception.
        for (const invalide of ["xn--", "xn--a", "xn--zzzzzzzz", "xn--99999999999", "xn--ab-"])
            if (depunycode(invalide) === undefined)
                ecarts.push({etiquette: invalide, obtenu: "undefined"});
        process.stdout.write(JSON.stringify({comparees, ecarts}));
    }
}

principal().catch((e) => { process.stderr.write(String(e.stack || e)); process.exit(1); });

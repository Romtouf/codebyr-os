// Banc d'essai du bouclier anti-hameçonnage : exécute les VRAIS fichiers de
// l'extension sous node, comme Firefox le ferait, avec un faux « browser » et
// un faux document.
//
// Le nom d'hôte est obtenu par « new URL(adresse).hostname » : c'est la forme
// que le navigateur donne au script (punycode pour un domaine international),
// et c'est précisément celle qui trompait le bouclier.
//
// Modes, sur l'entrée standard (JSON) :
//   {"mode": "adresses", "proteges": [...], "adresses": [...], "langue": "fr"}
//       → pour chaque adresse : {adresse, hote, alerte, message, textes} ;
//         l'alerte est la page de l'extension (alerte.js), ouverte avec ce que
//         content.js a transmis à l'arrière-plan
//   {"mode": "secours", "proteges": [...], "adresse": "...", "langue": "fr"}
//       → l'arrière-plan ne répond pas : l'alerte de secours dans la page
//   {"mode": "fond", "cas": [{message, sender}, ...]}
//       → ce que background.js fait de chaque demande
//   {"mode": "page", "recherche": "?retour=…", "clic": "legitime", "vrai": true}
//       → la page d'alerte : textes, et ce que fait un clic vrai ou simulé
//   {"mode": "punycode", "etiquettes": [...]}
//       → le décodeur du bouclier comparé à celui de node, étiquette par étiquette
"use strict";
const fs = require("fs");
const path = require("path");
const url = require("url");
const vm = require("vm");

const DOSSIER = path.join(__dirname, "..", "live-build", "config", "includes.chroot_after_packages",
                          "usr", "share", "codebyr", "antiphishing");
const lire = (nom) => fs.readFileSync(path.join(DOSSIER, nom), "utf8");
const code = lire("content.js");
const rendu = lire("rendu.js");
const fond = lire("background.js");
const page = lire("alerte.js");

// ── Un faux DOM, juste ce que le bouclier emploie ───────────────────────────
function faux_element(tag) {
    return {
        tag, id: "", textContent: "", enfants: [], attributs: {}, ecouteurs: {},
        parentNode: null, ombre: null,
        setAttribute(k, v) { this.attributs[k] = v; },
        getAttribute(k) { return k in this.attributs ? this.attributs[k] : null; },
        appendChild(e) {
            if (e.parentNode) e.parentNode.enfants = e.parentNode.enfants.filter((x) => x !== e);
            this.enfants.push(e); e.parentNode = this; return e;
        },
        addEventListener(type, f) { (this.ecouteurs[type] = this.ecouteurs[type] || []).push(f); },
        remove() {
            if (this.parentNode) this.parentNode.enfants = this.parentNode.enfants.filter((x) => x !== this);
            this.parentNode = null;
        },
        attachShadow(options) {
            this.ombre = faux_element("#shadow-root");
            this.ombre.mode = options.mode;
            return this.ombre;
        },
    };
}

function textes(e) {
    const dedans = e.ombre ? [e.ombre] : [];
    return [e.textContent].concat(...e.enfants.concat(dedans).map(textes)).filter(Boolean);
}

function boutons(e) {
    const dedans = e.ombre ? [e.ombre] : [];
    return (e.tag === "button" ? [e] : []).concat(...e.enfants.concat(dedans).map(boutons));
}

async function cliquer(bouton, vrai) {
    for (const f of bouton.ecouteurs.click || [])
        await f({isTrusted: vrai});
}

// browser.i18n.getMessage, comme Firefox : le message dans la langue du
// navigateur, sinon dans la langue par défaut du manifeste ; « $HOTE$ » est
// remplacé par sa marque (« $1 »), elle-même par la valeur donnée.
const LOCALES = path.join(DOSSIER, "_locales");
const MANIFESTE = JSON.parse(lire("manifest.json"));

function messages(langue) {
    const chemin = path.join(LOCALES, langue, "messages.json");
    return fs.existsSync(chemin) ? JSON.parse(fs.readFileSync(chemin, "utf8")) : {};
}

function faux_i18n(langue) {
    const propres = messages(langue), defaut = messages(MANIFESTE.default_locale);
    return {
        getUILanguage: () => langue,
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

function faux_stockage(approuves) {
    const donnees = {approuves: approuves || []};
    return {donnees, get: async () => JSON.parse(JSON.stringify(donnees)),
            set: async (o) => Object.assign(donnees, o)};
}

// ── La détection : content.js, après rendu.js, comme le manifeste les charge ─
async function une_adresse(proteges, adresse, langue, repondre) {
    const hote = new URL(adresse).hostname;
    const racine = faux_element("html");
    const document = {documentElement: racine, body: racine, createElement: faux_element,
                      addEventListener() {}};
    const envois = [];
    const intervalles = [];
    const local = faux_stockage();
    const location = {hostname: hote, href: adresse};
    const browser = {
        storage: {managed: {get: async () => ({domaines: proteges})}, local},
        i18n: faux_i18n(langue || "fr"),
        runtime: {sendMessage: async (m) => { envois.push(m); return repondre(m); }},
    };
    const contexte = vm.createContext({
        browser, document, location, URL,
        setInterval: (f) => { intervalles.push(f); return intervalles.length; },
        clearInterval() {}, setTimeout: () => 0,
    });
    vm.runInContext(rendu, contexte);
    await vm.runInContext(code, contexte);
    return {hote, racine, envois, intervalles, local, location};
}

// ── La page d'alerte : alerte.js, après rendu.js, comme alerte.html ─────────
async function la_page(recherche, langue, approuves) {
    const corps = faux_element("body");
    const racine = faux_element("html");
    const document = {documentElement: racine, body: corps, title: "", createElement: faux_element};
    const local = faux_stockage(approuves);
    const location = {search: recherche, remplacee: null,
                      replace(a) { this.remplacee = a; }};
    const browser = {storage: {local}, i18n: faux_i18n(langue || "fr")};
    const contexte = vm.createContext({browser, document, location, URL, URLSearchParams});
    vm.runInContext(rendu, contexte);
    vm.runInContext(page, contexte);
    return {corps, document, racine, local, location};
}

// ── L'arrière-plan : background.js ──────────────────────────────────────────
function l_arriere_plan() {
    let ecouteur = null;
    const mises_a_jour = [];
    const browser = {
        runtime: {id: "antiphishing@codebyr.io",
                  getURL: (p) => "moz-extension://uuid-du-profil/" + p,
                  onMessage: {addListener: (f) => { ecouteur = f; }}},
        tabs: {update: async (id, proprietes) => { mises_a_jour.push({id, proprietes}); return {}; }},
    };
    vm.runInContext(fond, vm.createContext({browser, URL, URLSearchParams}));
    return {ecouteur, mises_a_jour};
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
        for (const adresse of demande.adresses) {
            const r = await une_adresse(demande.proteges, adresse, demande.langue,
                                        async () => ({ok: true}));
            const message = r.envois[0] || null;
            let vus = [];
            if (message) {
                // La page que l'arrière-plan ouvrirait pour ce message.
                const p = new URLSearchParams({retour: adresse, lu: message.lu, banque: message.banque});
                vus = textes((await la_page("?" + p.toString(), demande.langue)).corps);
            }
            resultats.push({adresse, hote: r.hote, alerte: Boolean(message), message,
                            textes: vus, dans_la_page: r.racine.enfants.length});
        }
        process.stdout.write(JSON.stringify(resultats));
    } else if (demande.mode === "secours") {
        const r = await une_adresse(demande.proteges, demande.adresse, demande.langue,
                                    async () => { throw new Error("injoignable"); });
        const enveloppe = r.racine.enfants[0];
        const sortie = {posee: Boolean(enveloppe), ombre: enveloppe && enveloppe.ombre
                            ? enveloppe.ombre.mode : null,
                        textes: enveloppe ? textes(enveloppe) : [],
                        style: enveloppe ? enveloppe.getAttribute("style") : null};
        // La page retire l'alerte, puis touche à son style : remise en place.
        enveloppe.remove();
        enveloppe.setAttribute("style", "display:none !important");
        r.intervalles.forEach((f) => f());
        sortie.remise = r.racine.enfants.includes(enveloppe)
                        && enveloppe.getAttribute("style") === sortie.style;
        // Un clic simulé par un script de la page, puis un vrai.
        const legitime = boutons(enveloppe).find((b) => b.textContent === faux_i18n(demande.langue || "fr").getMessage("legitime"));
        await cliquer(legitime, false);
        sortie.apres_clic_simule = {approuves: r.local.donnees.approuves.slice(),
                                    presente: r.racine.enfants.includes(enveloppe)};
        await cliquer(legitime, true);
        r.intervalles.forEach((f) => f());
        sortie.apres_vrai_clic = {approuves: r.local.donnees.approuves.slice(),
                                  presente: r.racine.enfants.includes(enveloppe)};
        process.stdout.write(JSON.stringify(sortie));
    } else if (demande.mode === "fond") {
        const resultats = [];
        for (const cas of demande.cas) {
            const f = l_arriere_plan();
            const reponse = await f.ecouteur(cas.message, cas.sender);
            resultats.push({reponse: reponse === undefined ? null : reponse,
                            mises_a_jour: f.mises_a_jour});
        }
        process.stdout.write(JSON.stringify(resultats));
    } else if (demande.mode === "page") {
        const p = await la_page(demande.recherche, demande.langue);
        const sortie = {titre: p.document.title, langue: p.racine.getAttribute("lang"),
                        textes: textes(p.corps)};
        if (demande.clic) {
            const libelle = faux_i18n(demande.langue || "fr").getMessage(demande.clic);
            const bouton = boutons(p.corps).find((b) => b.textContent === libelle);
            await cliquer(bouton, Boolean(demande.vrai));
        }
        sortie.approuves = p.local.donnees.approuves;
        sortie.navigation = p.location.remplacee;
        process.stdout.write(JSON.stringify(sortie));
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

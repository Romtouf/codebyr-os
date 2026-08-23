/* Codebyr OS — extension GNOME « Espaces » (Phase 2 v1.1)
 *
 *   1) sélecteur d'Espaces dans la barre du haut ;
 *   2) liserés colorés autour des fenêtres d'un Espace.
 *
 * L'app_id Wayland est parfois défini APRÈS la création de la fenêtre :
 * on re-tente donc l'association quand la classe/app_id change.
 * Une notification de diagnostic affiche l'identifiant réel (DIAG).
 */

import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';
import * as SystemActions from 'resource:///org/gnome/shell/misc/systemActions.js';

const REGISTRE_SYSTEME = '/etc/codebyr/espaces.json';
const DIAG = false;  // notifications de diagnostic
const EP = 3;        // épaisseur du liseré

function registreUtilisateur() {
    return GLib.get_home_dir() + '/.config/codebyr/espaces.json';
}

function lireRegistre(chemin) {
    try {
        if (!GLib.file_test(chemin, GLib.FileTest.EXISTS))
            return {espaces: [], apps: []};
        const [ok, bytes] = GLib.file_get_contents(chemin);
        if (!ok)
            return {espaces: [], apps: []};
        const data = JSON.parse(new TextDecoder().decode(bytes));
        return {espaces: data.espaces || [], apps: data.apps || []};
    } catch (e) {
        logError(e, 'Codebyr: registre illisible (' + chemin + ')');
        return {espaces: [], apps: []};
    }
}

// Les deux registres se SUPERPOSENT, clé par clé : les valeurs par défaut du
// système d'abord, recouvertes par les personnalisations de l'utilisateur.
// Choisir « l'un OU l'autre », comme avant, figeait les défauts au jour où
// l'utilisateur touchait son premier réglage : plus aucune valeur livrée par
// une mise à jour ne pouvait plus l'atteindre. Même règle que le module Python
// /usr/share/codebyr/registre.py — les deux sont vérifiés par les tests.
// Le registre est relu à chaque fenêtre créée. Deux fichiers ouverts, décodés
// et analysés en JSON pour chaque fenêtre qui s'ouvre — inutile, et c'est le
// compositeur qui paie. On garde donc le résultat, invalidé dès que l'un des
// deux fichiers change : une signature (date de modification + taille) coûte
// deux appels système, contre deux lectures et deux analyses.
let _fusionCache = null;
let _fusionSignature = '';

function signatureRegistres() {
    let signature = '';
    for (const chemin of [REGISTRE_SYSTEME, registreUtilisateur()]) {
        try {
            const info = Gio.File.new_for_path(chemin).query_info(
                'time::modified,standard::size', Gio.FileQueryInfoFlags.NONE, null);
            signature += chemin + ':' + info.get_attribute_uint64('time::modified')
                + ':' + info.get_size() + ';';
        } catch (e) {
            signature += chemin + ':absent;';
        }
    }
    return signature;
}

function fusionner() {
    const signature = signatureRegistres();
    if (_fusionCache && signature === _fusionSignature)
        return _fusionCache;

    const sys = lireRegistre(REGISTRE_SYSTEME);
    const usr = lireRegistre(registreUtilisateur());
    const perso = new Map();
    for (const e of usr.espaces) {
        if (e && e.id)
            perso.set(e.id, e);
    }
    const espaces = [];
    const vus = new Set();
    for (const base of sys.espaces) {
        if (!base || !base.id)
            continue;
        const espace = Object.assign({}, base, perso.get(base.id) || {});
        espace._systeme = true;
        espaces.push(espace);
        vus.add(base.id);
    }
    for (const e of usr.espaces) {
        if (!e || !e.id || vus.has(e.id))
            continue;
        const espace = Object.assign({}, e);
        espace._systeme = false;
        espaces.push(espace);
        vus.add(e.id);
    }
    _fusionCache = {espaces, apps: (usr.apps.length ? usr.apps : sys.apps)};
    _fusionSignature = signature;
    return _fusionCache;
}

function chargerEspaces() {
    return fusionner().espaces;
}

const APPS_DEFAUT = [
    {nom: 'Navigateur', cmd: 'firefox-esr'},
    {nom: 'Fichiers', cmd: 'nautilus'},
    {nom: 'Terminal', cmd: 'kgx'},
    {nom: 'Éditeur de texte', cmd: 'gnome-text-editor'},
];

function chargerApps() {
    const apps = fusionner().apps;
    return (apps && apps.length) ? apps : APPS_DEFAUT;
}

function classeDe(win) {
    let wm = '';
    let app = '';
    try { wm = win.get_wm_class() || ''; } catch (e) {}
    try { app = win.get_gtk_application_id?.() || ''; } catch (e) {}
    return {wm, app, combo: (wm + ' ' + app).toLowerCase()};
}

function espacePourFenetre(win, espaces) {
    const c = classeDe(win).combo;
    for (const e of espaces) {
        if (c.includes('codebyr-' + e.id))
            return e;
    }
    return null;
}

// PPid d'un processus, lu dans /proc
function ppid(pid) {
    try {
        const [ok, bytes] = GLib.file_get_contents('/proc/' + pid + '/status');
        if (!ok)
            return 0;
        const m = new TextDecoder().decode(bytes).match(/^PPid:\s*(\d+)/m);
        return m ? parseInt(m[1], 10) : 0;
    } catch (e) {
        return 0;
    }
}

// Association par filiation : on remonte les processus parents de la fenêtre
// jusqu'à trouver un marqueur « pid-<N> » posé par codebyr-space.
function espaceParProcessus(win, espaces, rundir) {
    let pid = 0;
    try { pid = win.get_pid(); } catch (e) {}
    if (!pid || pid <= 1)
        return null;
    let cur = pid;
    for (let i = 0; i < 12 && cur > 1; i++) {
        try {
            const [ok, bytes] = GLib.file_get_contents(rundir + '/pid-' + cur);
            if (ok) {
                const id = new TextDecoder().decode(bytes).trim();
                const esp = espaces.find(e => e.id === id);
                if (esp)
                    return esp;
            }
        } catch (e) {}
        cur = ppid(cur);
    }
    return null;
}

// « #RRGGBB » → composantes 0..1 pour Cairo.
function hexVersRGB(hex) {
    let s = (hex || '#000000').replace('#', '');
    if (s.length === 3)
        s = s.split('').map(c => c + c).join('');
    const n = parseInt(s, 16) || 0;
    return {r: ((n >> 16) & 255) / 255, g: ((n >> 8) & 255) / 255, b: (n & 255) / 255};
}

// Chemin d'un rectangle à coins arrondis.
function cheminArrondi(cr, x, y, w, h, r) {
    const Q = Math.PI / 2;
    cr.newSubPath();
    cr.arc(x + w - r, y + r,     r, -Q, 0);
    cr.arc(x + w - r, y + h - r, r,  0, Q);
    cr.arc(x + r,     y + h - r, r,  Q, Math.PI);
    cr.arc(x + r,     y + r,     r,  Math.PI, Math.PI + Q);
    cr.closePath();
}

const Lisere = GObject.registerClass(
class Lisere extends St.DrawingArea {
    _init(espace) {
        // St ne rend PAS les bordures CSS « dashed » (toujours pleines) : on
        // dessine donc le liseré à la main avec Cairo. Les Espaces éphémères
        // (Jetable) obtiennent un vrai trait pointillé — la couleur seule ne
        // suffit pas (accessibilité daltonisme, cf. charte).
        super._init({reactive: false, can_focus: false, track_hover: false});
        this._espace = espace;
        this.connect('repaint', () => this._dessiner());
        const etiq = new St.Label({
            text: espace.nom,
            style: `background-color: ${espace.couleur}; color: #0A1318;` +
                   `font-weight: 700; font-size: 10px; padding: 1px 8px;` +
                   `border-radius: 6px;`,
        });
        etiq.set_position(12, -8);
        this.add_child(etiq);
    }
    _dessiner() {
        let cr = null;
        try {
            const [w, h] = this.get_surface_size();
            if (w <= EP || h <= EP)
                return;
            cr = this.get_context();
            const {r, g, b} = hexVersRGB(this._espace.couleur);
            cr.setLineWidth(EP);
            cr.setSourceRGBA(r, g, b, 1);
            if (this._espace.ephemere)
                cr.setDash([9, 6], 0);   // pointillé : Jetable
            cheminArrondi(cr, EP / 2, EP / 2, w - EP, h - EP, 11);
            cr.stroke();
        } catch (e) {
            logError(e, 'Codebyr: dessin du liseré');
        } finally {
            if (cr)
                cr.$dispose();
        }
    }
    majGeometrie(rect) {
        // le liseré épouse le bord de la fenêtre (visible même maximisée)
        this.set_position(rect.x, rect.y);
        this.set_size(rect.width, rect.height);
        this.queue_repaint();
    }
});

class Coloriage {
    constructor(espaces) {
        this._espaces = espaces;
        this._suivis = new Map();   // MetaWindow -> {lisere, signals:[]}
        this._displaySignals = [];
        this._rundir = GLib.get_user_runtime_dir() + '/codebyr';
    }

    activer() {
        this._displaySignals.push(
            global.display.connect('window-created', (_d, win) => this._suivre(win, true)));
        // À chaque réempilement des fenêtres, on remet chaque liseré juste
        // au-dessus de SA fenêtre (sinon il passe dessous et on ne voit rien).
        this._displaySignals.push(
            global.display.connect('restacked', () => this._reempiler()));
        for (const actor of global.get_window_actors())
            this._suivre(actor.meta_window, false);
    }

    _reempiler() {
        for (const [win, rec] of this._suivis) {
            if (!rec.lisere)
                continue;
            const actor = win.get_compositor_private();
            if (actor) {
                try { global.window_group.set_child_above_sibling(rec.lisere, actor); } catch (e) {}
            }
        }
    }

    _suivre(win, diag) {
        if (!win || this._suivis.has(win))
            return;
        // Relecture des Espaces (Espaces personnalisés compris) : passe par le
        // cache ci-dessus, donc sans coût quand rien n'a changé.
        this._espaces = chargerEspaces();
        const rec = {lisere: null, signals: []};
        this._suivis.set(win, rec);

        if (diag && DIAG) {
            const c = classeDe(win);
            Main.notify('Codebyr — fenêtre détectée',
                'classe : ' + (c.wm || '—') + '   ·   app_id : ' + (c.app || '—'));
        }

        const tenter = () => {
            if (rec.lisere)
                return;
            const esp = espacePourFenetre(win, this._espaces)
                || espaceParProcessus(win, this._espaces, this._rundir);
            if (esp)
                this._colorer(win, rec, esp);
        };

        tenter();
        // l'app_id/wm-class peut arriver après la création : on re-tente.
        // On re-tente aussi un peu plus tard (la fenêtre/le processus peut
        // n'être pleinement identifiable qu'après coup).
        try { rec.signals.push(win.connect('notify::wm-class', () => {
            if (DIAG) Main.notify('Codebyr — classe mise à jour', classeDe(win).wm || '—');
            tenter();
        })); } catch (e) {}
        try { rec.signals.push(win.connect('notify::gtk-application-id', tenter)); } catch (e) {}
        for (const delai of [200, 700, 1500]) {
            const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delai, () => {
                tenter();
                return GLib.SOURCE_REMOVE;
            });
            rec.retryTimeouts = rec.retryTimeouts || [];
            rec.retryTimeouts.push(id);
        }
        rec.signals.push(win.connect('unmanaged', () => this._retirer(win)));
    }

    _colorer(win, rec, esp) {
        try {
            const lisere = new Lisere(esp);
            global.window_group.add_child(lisere);
            const actor = win.get_compositor_private();
            if (actor)
                global.window_group.set_child_above_sibling(lisere, actor);
            const sync = () => {
                try { lisere.majGeometrie(win.get_frame_rect()); } catch (e) {}
            };
            rec.lisere = lisere;
            rec.signals.push(win.connect('position-changed', sync));
            rec.signals.push(win.connect('size-changed', sync));
            sync();
            // La taille finale de la fenêtre arrive souvent APRÈS la pose du
            // liseré (fenêtre à 0 px au départ) : on resynchronise plusieurs
            // fois pour attraper la géométrie définitive.
            rec.timeouts = [];
            for (const delai of [120, 350, 800, 1500]) {
                const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delai, () => {
                    sync();
                    return GLib.SOURCE_REMOVE;
                });
                rec.timeouts.push(id);
            }
            if (DIAG)
                Main.notify('Codebyr — liseré posé', esp.nom);
        } catch (e) {
            logError(e, 'Codebyr: dessin du liseré');
        }
    }

    _retirer(win) {
        const rec = this._suivis.get(win);
        if (!rec)
            return;
        for (const id of rec.signals) {
            try { win.disconnect(id); } catch (e) {}
        }
        for (const liste of [rec.timeouts, rec.retryTimeouts]) {
            if (liste) {
                for (const id of liste) {
                    try { GLib.Source.remove(id); } catch (e) {}
                }
            }
        }
        if (rec.lisere)
            rec.lisere.destroy();
        this._suivis.delete(win);
    }

    detruire() {
        for (const id of this._displaySignals) {
            try { global.display.disconnect(id); } catch (e) {}
        }
        this._displaySignals = [];
        for (const win of [...this._suivis.keys()])
            this._retirer(win);
    }
}

// Espace de la fenêtre actuellement focalisée (par classe, sinon filiation).
function espaceFocalise(espaces, rundir) {
    let win = null;
    try { win = global.display.focus_window; } catch (e) {}
    if (!win)
        return null;
    return espacePourFenetre(win, espaces) || espaceParProcessus(win, espaces, rundir);
}

// ── Presse-papiers inter-Espaces ─────────────────────────────────────────
// Sous un compositeur Wayland partagé, tous les Espaces voient le MÊME
// presse-papiers : un secret copié dans Banque resterait lisible en basculant
// vers Navigation. Pour l'éviter, on VIDE le presse-papiers dès que le focus
// passe à un Espace différent de celui qui l'a rempli. Le transfert volontaire
// reste possible, mais EXPLICITE et confirmé (menu « Transférer vers… »).
//
// Limite assumée : ce n'est pas l'isolation matérielle de Qubes (compositeur
// partagé). La protection est temporelle — réduire la fenêtre de fuite. Soupape
// utilisateur : créer ~/.config/codebyr/presse-papiers-libre désactive tout
// nettoyage automatique.
class PressePapiers {
    constructor(getEspaces, rundir) {
        this._getEspaces = getEspaces;
        this._rundir = rundir;
        this._dernier = null;        // id du dernier Espace focalisé (non nul)
        this._transfert = null;      // {dest} transfert explicite autorisé
        this._focusId = 0;
        this._nettoyageId = 0;
        this._clip = St.Clipboard.get_default();
    }

    _actif() {
        const f = GLib.get_home_dir() + '/.config/codebyr/presse-papiers-libre';
        return !GLib.file_test(f, GLib.FileTest.EXISTS);
    }

    _espace() {
        return espaceFocalise(this._getEspaces(), this._rundir);
    }

    activer() {
        // Approche robuste : on ne dépend PAS du signal de sélection Wayland
        // (owner-changed ne capte pas fiablement les copies des clients comme
        // Firefox). On surveille simplement le focus : dès qu'on ENTRE dans un
        // Espace différent du précédent, on vide le presse-papiers. Ainsi un
        // secret copié dans Banque n'est jamais collable dans Navigation.
        const esp = this._espace();
        this._dernier = esp ? esp.id : null;
        try {
            this._focusId = global.display.connect('notify::focus-window',
                () => this._surFocus());
        } catch (e) {
            logError(e, 'Codebyr: presse-papiers (focus)');
        }
    }

    // Un Espace « sensible » est celui dont on ne veut rien laisser filtrer :
    // Blindage actif, ou réseau restreint (donc Banque).
    _sensible(id) {
        const esp = this._getEspaces().find(e => e.id === id);
        if (!esp)
            return false;
        return esp.blindage === 'renforce'
            || (esp.reseau && esp.reseau.mode === 'liste-blanche');
    }

    _surFocus() {
        if (!this._actif())
            return;
        const esp = this._espace();

        if (!esp) {
            // Bureau, Réglages, une application lancée hors Espace… On ne
            // cassait rien ici, pour ne pas gêner. Mais c'était un passage :
            // copier dans Banque, cliquer sur le bureau, puis ouvrir n'importe
            // quelle application — le secret était encore là, intact. La
            // frontière ne se franchissait pas d'Espace à Espace, elle se
            // contournait par le bureau.
            //
            // On vide donc aussi en SORTANT d'un Espace sensible. Pour les
            // Espaces ordinaires, on ne touche à rien : coller une adresse
            // depuis Navigation dans une note doit rester possible.
            if (this._dernier && this._sensible(this._dernier)) {
                this._vider();
                this._dernier = null;
            }
            return;
        }

        // Transfert explicite en cours vers CET Espace : on laisse le contenu
        // arriver (une fois), puis nettoyage différé pour qu'il ne traîne pas.
        if (this._transfert && esp.id === this._transfert.dest) {
            this._dernier = esp.id;
            this._planifierNettoyage();
            return;
        }

        // On entre dans un Espace différent du dernier → le presse-papiers ne
        // franchit pas la frontière : on le vide.
        if (this._dernier && esp.id !== this._dernier)
            this._vider();
        this._dernier = esp.id;
    }

    _vider() {
        try {
            this._clip.set_text(St.ClipboardType.CLIPBOARD, '');
            this._clip.set_text(St.ClipboardType.PRIMARY, '');
        } catch (e) {}
    }

    _planifierNettoyage() {
        if (this._nettoyageId)
            return;
        this._nettoyageId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 45, () => {
            this._vider();
            this._transfert = null;
            this._nettoyageId = 0;
            return GLib.SOURCE_REMOVE;
        });
    }

    // Autorise le contenu actuel à franchir la frontière vers un Espace donné.
    autoriserTransfert(destId) {
        this._transfert = {dest: destId};
    }

    // Y a-t-il un contenu copié à transférer ? (callback avec le texte)
    lireContenu(cb) {
        try {
            this._clip.get_text(St.ClipboardType.CLIPBOARD, (_c, texte) => cb(texte || ''));
        } catch (e) {
            cb('');
        }
    }

    detruire() {
        if (this._focusId) {
            try { global.display.disconnect(this._focusId); } catch (e) {}
        }
        if (this._nettoyageId) {
            try { GLib.Source.remove(this._nettoyageId); } catch (e) {}
        }
    }
}

const Indicateur = GObject.registerClass(
class Indicateur extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, 'Codebyr Espaces');
        this._extension = extension;

        const boite = new St.BoxLayout({style_class: 'panel-status-menu-box'});
        boite.add_child(new St.Icon({
            gicon: Gio.icon_new_for_string(extension.path + '/icons/codebyr-symbolic.svg'),
            style_class: 'system-status-icon',
        }));
        this.add_child(boite);

        // Menu reconstruit à chaque ouverture : reflète les Espaces personnalisés.
        this.menu.connect('open-state-changed', (m, open) => {
            if (open)
                this._rebuild();
        });
        this._rebuild();
    }

    _rebuild() {
        this.menu.removeAll();
        this._apps = chargerApps();
        const espaces = chargerEspaces();

        const entete = new PopupMenu.PopupMenuItem('Ouvrir une app dans un Espace', {reactive: false});
        entete.label.add_style_class_name('codebyr-entete');
        this.menu.addMenuItem(entete);

        for (const e of espaces) {
            if (e.ephemere)
                continue;
            this._ajouterEspace(e, false);
        }
        this.menu.addAction('＋  Créer un Espace…', () => this._dialogueCreer());
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const jetable = espaces.find(e => e.ephemere);
        if (jetable)
            this._ajouterEspace(jetable, true);
        this.menu.addAction('Ouvrir un lien en Jetable…', () => this._dialogueLienJetable());
        this.menu.addAction('Mode invité (prêter le PC)', () => this._modeInvite());
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this.menu.addAction('📋  Transférer le presse-papiers vers…',
            () => this._dialogueTransfert(espaces));
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this.menu.addAction('🛡  Assistant de sécurité',
            () => this._executer('/usr/bin/codebyr-assistant',
                'Assistant de sécurité indisponible'));
        this.menu.addAction('⚙  Configuration Codebyr',
            () => this._executer('/usr/bin/codebyr-config',
                'Configuration Codebyr indisponible'));
    }

    _styleSwatch(couleur, choisie) {
        return `background-color: ${couleur}; width: 32px; height: 32px; border-radius: 8px;` +
            (choisie ? 'border: 3px solid #E7EEF1;' : 'border: 3px solid rgba(255,255,255,0.15);');
    }

    _dialogueCreer() {
        const dlg = new ModalDialog.ModalDialog({destroyOnClose: true});
        const boite = new St.BoxLayout({vertical: true, style: 'spacing: 12px; min-width: 470px;'});
        boite.add_child(new St.Label({text: 'Créer un Espace',
            style: 'font-weight: 700; font-size: 15px;'}));
        boite.add_child(new St.Label({
            text: 'Un compartiment isolé et persistant, avec sa couleur.',
            style: 'color: #93A6B0;'}));
        const entry = new St.Entry({
            hint_text: 'Nom (ex. Achats, Études, Association…)',
            can_focus: true, x_expand: true, style: 'margin-top: 4px;'});
        boite.add_child(entry);
        boite.add_child(new St.Label({text: 'Couleur :', style: 'margin-top: 4px;'}));

        const palette = ['#4E8FEF', '#8F6CF0', '#2FA36B', '#E09A32',
            '#E25551', '#43C7DF', '#E5679B', '#6E7E89'];
        const rang = new St.BoxLayout({style: 'spacing: 8px;'});
        const boutons = [];
        const etat = {couleur: palette[5]};
        for (const c of palette) {
            const b = new St.Button({style: this._styleSwatch(c, c === etat.couleur), can_focus: true});
            b.connect('clicked', () => {
                etat.couleur = c;
                for (let i = 0; i < boutons.length; i++)
                    boutons[i].set_style(this._styleSwatch(palette[i], palette[i] === etat.couleur));
            });
            boutons.push(b);
            rang.add_child(b);
        }
        boite.add_child(rang);
        dlg.contentLayout.add_child(boite);

        const creer = () => {
            const nom = entry.get_text().trim();
            dlg.close();
            if (nom) {
                this._executer('/usr/bin/codebyr-space create '
                    + GLib.shell_quote(nom) + ' ' + GLib.shell_quote(etat.couleur),
                    'Création de l\'Espace « ' + nom + ' » impossible');
                Main.notify('Codebyr', 'Espace créé : ' + nom);
            }
        };
        dlg.setButtons([
            {label: 'Annuler', action: () => dlg.close(), key: Clutter.KEY_Escape},
            {label: 'Créer', action: creer, default: true},
        ]);
        entry.clutter_text.connect('activate', creer);
        dlg.open();
        global.stage.set_key_focus(entry.clutter_text);
    }

    _modeInvite() {
        try {
            SystemActions.getDefault().activateSwitchUser();
        } catch (e) {
            Main.notify('Codebyr — Mode invité',
                'Ouvre le menu en haut à droite → Changer d\'utilisateur → Invité '
                + '(aucun mot de passe demandé).');
        }
    }

    _dialogueLienJetable() {
        const dlg = new ModalDialog.ModalDialog({destroyOnClose: true});
        const boite = new St.BoxLayout({vertical: true, style: 'spacing: 10px; min-width: 440px;'});
        boite.add_child(new St.Label({
            text: 'Ouvrir un lien en Jetable',
            style: 'font-weight: 700; font-size: 15px;',
        }));
        boite.add_child(new St.Label({
            text: "Le lien s'ouvrira dans une bulle isolée qui s'autodétruit à la fermeture.",
            style: 'color: #93A6B0;',
        }));
        const entry = new St.Entry({
            hint_text: 'https://…', can_focus: true, x_expand: true,
            style: 'margin-top: 6px;',
        });
        boite.add_child(entry);
        dlg.contentLayout.add_child(boite);

        const ouvrir = () => {
            const u = entry.get_text().trim();
            dlg.close();
            if (u)
                this._executer('/usr/bin/codebyr-jetable ' + GLib.shell_quote(u),
                    'Ouverture en Jetable impossible');
        };
        dlg.setButtons([
            {label: 'Annuler', action: () => dlg.close(), key: Clutter.KEY_Escape},
            {label: 'Ouvrir en Jetable', action: ouvrir, default: true},
        ]);
        entry.clutter_text.connect('activate', ouvrir);
        dlg.open();
        global.stage.set_key_focus(entry.clutter_text);
    }

    _dialogueTransfert(espaces) {
        const pp = this._extension.pressePapiers;
        if (!pp) {
            Main.notify('Codebyr', 'Presse-papiers inter-Espaces indisponible.');
            return;
        }
        pp.lireContenu((texte) => {
            if (!texte || !texte.trim()) {
                Main.notify('Codebyr — Presse-papiers',
                    'Rien à transférer. Copiez d\'abord un texte (Ctrl+C) dans un Espace, '
                    + 'puis rouvrez ce menu.');
                return;
            }
            this._ouvrirTransfert(espaces, texte, pp);
        });
    }

    _ouvrirTransfert(espaces, texte, pp) {
        const rundir = GLib.get_user_runtime_dir() + '/codebyr';
        const source = espaceFocalise(espaces, rundir);
        const dlg = new ModalDialog.ModalDialog({destroyOnClose: true});
        const boite = new St.BoxLayout({vertical: true, style: 'spacing: 10px; min-width: 460px;'});
        boite.add_child(new St.Label({
            text: 'Transférer le presse-papiers',
            style: 'font-weight: 700; font-size: 15px;',
        }));
        // On n'affiche JAMAIS le contenu (ce peut être un mot de passe) : seulement
        // sa taille et l'Espace d'origine. Le transfert entre Espaces est une
        // action délibérée, pas une fuite silencieuse.
        boite.add_child(new St.Label({
            text: (source ? 'Contenu copié depuis « ' + source.nom + ' »' : 'Contenu copié')
                + ' (' + texte.length + ' caractère' + (texte.length > 1 ? 's' : '') + ').'
                + '\nVers quel Espace l\'autoriser ?',
            style: 'color: #93A6B0;',
        }));
        for (const e of espaces) {
            if (source && e.id === source.id)
                continue;   // inutile de transférer vers soi-même
            const b = new St.Button({
                label: e.nom, can_focus: true, x_align: Clutter.ActorAlign.FILL,
                style: 'padding: 9px 14px; border-radius: 8px; margin-top: 2px;'
                    + 'background-color: ' + (e.couleur || '#43C7DF') + '22;'
                    + 'border-left: 4px solid ' + (e.couleur || '#43C7DF') + ';',
            });
            b.connect('clicked', () => {
                dlg.close();
                pp.autoriserTransfert(e.id);
                Main.notify('Codebyr — Presse-papiers',
                    'Autorisé vers « ' + e.nom + ' ». Basculez sur cet Espace et collez '
                    + '(Ctrl+V). Le presse-papiers sera ensuite effacé.');
            });
            boite.add_child(b);
        }
        dlg.contentLayout.add_child(boite);
        dlg.setButtons([{label: 'Annuler', action: () => dlg.close(),
            key: Clutter.KEY_Escape, default: true}]);
        dlg.open();
    }

    _ajouterEspace(e, jetable) {
        const blinde = e.blindage === 'renforce';
        const titre = (jetable ? 'Jetable (éphémère)' : e.nom) + (blinde ? '  🛡' : '');
        const sub = new PopupMenu.PopupSubMenuMenuItem(titre);
        const pastille = new St.Widget({
            style: `background-color: ${e.couleur}; border-radius: 6px;` +
                   (jetable ? 'border: 1.5px dashed #0A1318;' : ''),
            width: 12, height: 12,
            y_align: Clutter.ActorAlign.CENTER,
        });
        sub.insert_child_at_index(pastille, 1);
        // Applications propres à l'Espace si définies (e.apps), sinon liste commune.
        const apps = (Array.isArray(e.apps) && e.apps.length) ? e.apps : this._apps;
        for (const app of apps)
            sub.menu.addAction(app.nom, () => this._lancer(e.id, app.cmd));
        // Toute application installée (par n'importe quel moyen : magasin, apt,
        // Flatpak…) est lançable ici, sans passer par un enregistrement manuel.
        sub.menu.addAction('➕  Autres applications…', () => this._dialogueApps(e));
        sub.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        sub.menu.addAction('Fermer cet Espace', () => this._gerer('close', e.id, e.nom));
        if (!jetable) {
            sub.menu.addAction('Vider ses données', () => this._gerer('purge', e.id, e.nom));
            sub.menu.addAction('Créer un instantané (sauvegarde)', () => this._gerer('export', e.id, e.nom));
            sub.menu.addAction('Revenir à un instantané…', () => this._dialogueInstantanes(e.id, e.nom));
            if (!e._systeme)
                sub.menu.addAction('Supprimer cet Espace', () => this._gerer('delete', e.id, e.nom));
        }
        this.menu.addMenuItem(sub);
    }

    // Toutes les applications installées (magasin, apt, Flatpak…), via leurs
    // .desktop. Gio.AppInfo fait le parsing pour nous.
    _appsInstallees() {
        const out = [];
        try {
            for (const info of Gio.AppInfo.get_all()) {
                if (!info.should_show())
                    continue;
                const nom = info.get_name();
                let cmd = info.get_commandline() || '';
                cmd = cmd.replace(/\s*%[a-zA-Z]/g, '').trim();   // retire %U, %f…
                if (nom && cmd)
                    out.push({nom, cmd});
            }
        } catch (e) {
            logError(e, 'Codebyr: liste des applications');
        }
        out.sort((a, b) => a.nom.localeCompare(b.nom, 'fr'));
        return out;
    }

    _dialogueApps(esp) {
        const toutes = this._appsInstallees();
        const dlg = new ModalDialog.ModalDialog({destroyOnClose: true});
        const boite = new St.BoxLayout({vertical: true, style: 'spacing: 10px; min-width: 480px;'});
        boite.add_child(new St.Label({
            text: 'Ouvrir une application dans « ' + esp.nom + ' »',
            style: 'font-weight: 700; font-size: 15px;',
        }));
        const recherche = new St.Entry({
            hint_text: 'Rechercher une application…', can_focus: true, x_expand: true,
        });
        boite.add_child(recherche);

        const scroll = new St.ScrollView({style: 'max-height: 360px;', x_expand: true});
        const liste = new St.BoxLayout({vertical: true, style: 'spacing: 2px;'});
        try { scroll.add_child(liste); } catch (e) { scroll.add_actor(liste); }
        boite.add_child(scroll);
        dlg.contentLayout.add_child(boite);

        const remplir = (filtre) => {
            liste.destroy_all_children();
            const f = (filtre || '').trim().toLowerCase();
            let n = 0;
            for (const app of toutes) {
                if (f && !app.nom.toLowerCase().includes(f))
                    continue;
                if (n >= 200)
                    break;
                n++;
                const b = new St.Button({
                    label: app.nom, can_focus: true, x_align: Clutter.ActorAlign.FILL,
                    style: 'padding: 9px 12px; border-radius: 8px;'
                        + 'background-color: rgba(67,199,223,0.08);',
                });
                b.connect('clicked', () => {
                    dlg.close();
                    this._lancer(esp.id, app.cmd);
                });
                liste.add_child(b);
            }
            if (n === 0)
                liste.add_child(new St.Label({
                    text: 'Aucune application trouvée.',
                    style: 'color: #93A6B0; padding: 9px 12px;',
                }));
        };
        remplir('');
        recherche.clutter_text.connect('text-changed', () => remplir(recherche.get_text()));

        dlg.setButtons([{label: 'Fermer', action: () => dlg.close(),
            key: Clutter.KEY_Escape, default: true}]);
        dlg.open();
        global.stage.set_key_focus(recherche.clutter_text);
    }

    // Lance une commande et SURVEILLE son sort. Avant, on lançait sans jamais
    // regarder : quand une application ne démarrait pas, il ne se passait
    // simplement rien à l'écran, et l'utilisateur n'avait aucun moyen de
    // savoir pourquoi.
    _executer(ligne, echec) {
        let argv;
        try {
            const [ok, parse] = GLib.shell_parse_argv(ligne);
            if (!ok)
                throw new Error('ligne de commande illisible');
            argv = parse;
        } catch (e) {
            Main.notify('Codebyr', echec);
            return;
        }
        let proc;
        try {
            // Aucun tuyau sur la sortie : une application bavarde (un
            // navigateur, par exemple) remplirait la mémoire de GNOME Shell.
            // Le détail va déjà dans le journal — « journalctl -t codebyr ».
            proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
        } catch (e) {
            Main.notify('Codebyr', echec);
            return;
        }
        const debut = GLib.get_monotonic_time();
        proc.wait_check_async(null, (p, res) => {
            try {
                p.wait_check_finish(res);
            } catch (e) {
                // Un échec RAPIDE, c'est un lancement qui n'a pas abouti. Un
                // code de sortie non nul après plusieurs secondes, c'est
                // l'application qui a fini ainsi : ça ne nous regarde pas.
                const secondes = (GLib.get_monotonic_time() - debut) / 1000000;
                if (secondes < 3) {
                    Main.notify('Codebyr — ' + echec,
                        'Détail : ouvrez un terminal et tapez  journalctl -t codebyr -n 20');
                }
            }
        });
    }

    _lancer(id, cmd) {
        let commande = '/usr/bin/codebyr-space launch ' + id;
        if (cmd)
            commande += ' -- ' + cmd;
        this._executer(commande, 'Impossible d\'ouvrir l\'Espace ' + id);
    }

    _gerer(action, id, nom) {
        try {
            this._executer('/usr/bin/codebyr-space ' + action + ' ' + id,
                'Action « ' + action + ' » impossible sur ' + nom);
            const msgs = {
                close: 'Espace fermé : ',
                purge: 'Données effacées : ',
                export: 'Sauvegardé (dossier « Espaces-Codebyr ») : ',
                import: 'Restauré depuis la dernière sauvegarde : ',
                delete: 'Espace supprimé : ',
            };
            Main.notify('Codebyr', (msgs[action] || '') + nom);
        } catch (e) {
            Main.notify('Codebyr', 'Action impossible sur ' + nom);
        }
    }

    _dateLisible(fichier) {
        const m = fichier.match(/-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})\.tar\.gz$/);
        if (!m)
            return fichier;
        return m[3] + '/' + m[2] + '/' + m[1] + ' à ' + m[4] + 'h' + m[5];
    }

    _dialogueInstantanes(id, nom) {
        const dir = GLib.get_home_dir() + '/Espaces-Codebyr';
        const fichiers = [];
        try {
            const en = Gio.File.new_for_path(dir).enumerate_children(
                'standard::name', Gio.FileQueryInfoFlags.NONE, null);
            let info;
            while ((info = en.next_file(null)) !== null) {
                const n = info.get_name();
                if (n.startsWith(id + '-') && n.endsWith('.tar.gz'))
                    fichiers.push(n);
            }
            en.close(null);
        } catch (e) {}
        fichiers.sort().reverse();
        if (!fichiers.length) {
            Main.notify('Codebyr',
                'Aucun instantané pour ' + nom + '. Faites d\'abord « Créer un instantané ».');
            return;
        }
        const dlg = new ModalDialog.ModalDialog({destroyOnClose: true});
        const boite = new St.BoxLayout({vertical: true, style: 'spacing: 8px; min-width: 470px;'});
        boite.add_child(new St.Label({
            text: 'Revenir à un instantané de « ' + nom + ' »',
            style: 'font-weight: 700; font-size: 15px;',
        }));
        boite.add_child(new St.Label({
            text: "Choisissez la date à laquelle restaurer cet Espace :",
            style: 'color: #93A6B0; margin-bottom: 4px;',
        }));
        for (const f of fichiers) {
            const label = this._dateLisible(f);
            const b = new St.Button({
                label: label, can_focus: true, x_align: Clutter.ActorAlign.FILL,
                style: 'padding: 9px 14px; border-radius: 8px; background-color: rgba(67,199,223,0.12);',
            });
            b.connect('clicked', () => {
                dlg.close();
                this._executer(
                    '/usr/bin/codebyr-space import ' + id + ' ' + GLib.shell_quote(dir + '/' + f),
                    'Restauration de ' + nom + ' impossible');
                Main.notify('Codebyr', nom + ' restauré à l\'instantané du ' + label);
            });
            boite.add_child(b);
        }
        dlg.contentLayout.add_child(boite);
        dlg.setButtons([{label: 'Annuler', action: () => dlg.close(),
            key: Clutter.KEY_Escape, default: true}]);
        dlg.open();
    }
});

export default class CodebyrExtension extends Extension {
    enable() {
        this._espaces = chargerEspaces();
        this._apps = chargerApps();
        this._indicateur = new Indicateur(this);
        Main.panel.addToStatusArea('codebyr-espaces', this._indicateur, 1, 'right');
        try {
            this._coloriage = new Coloriage(this._espaces);
            this._coloriage.activer();
        } catch (e) {
            logError(e, 'Codebyr: activation du coloriage');
        }
        try {
            this.pressePapiers = new PressePapiers(
                () => chargerEspaces(), GLib.get_user_runtime_dir() + '/codebyr');
            this.pressePapiers.activer();
        } catch (e) {
            logError(e, 'Codebyr: activation du presse-papiers');
        }
    }

    disable() {
        this._coloriage?.detruire();
        this._coloriage = null;
        this.pressePapiers?.detruire();
        this.pressePapiers = null;
        this._indicateur?.destroy();
        this._indicateur = null;
        this._espaces = null;
    }
}

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

const REGISTRY = '/etc/codebyr/espaces.json';
const DIAG = false;  // notifications de diagnostic
const EP = 3;        // épaisseur du liseré
const BUILTIN = ['personnel', 'travail', 'banque', 'navigation', 'jetable'];

function registrePath() {
    const u = GLib.get_home_dir() + '/.config/codebyr/espaces.json';
    return GLib.file_test(u, GLib.FileTest.EXISTS) ? u : REGISTRY;
}

function chargerEspaces() {
    try {
        const [ok, bytes] = GLib.file_get_contents(registrePath());
        if (!ok)
            return [];
        return JSON.parse(new TextDecoder().decode(bytes)).espaces || [];
    } catch (e) {
        logError(e, 'Codebyr: registre illisible');
        return [];
    }
}

const APPS_DEFAUT = [
    {nom: 'Navigateur', cmd: 'firefox-esr'},
    {nom: 'Fichiers', cmd: 'nautilus'},
    {nom: 'Terminal', cmd: 'kgx'},
    {nom: 'Éditeur de texte', cmd: 'gnome-text-editor'},
];

function chargerApps() {
    try {
        const [ok, bytes] = GLib.file_get_contents(registrePath());
        if (ok) {
            const apps = JSON.parse(new TextDecoder().decode(bytes)).apps;
            if (apps && apps.length)
                return apps;
        }
    } catch (e) {}
    return APPS_DEFAUT;
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

const Lisere = GObject.registerClass(
class Lisere extends St.Widget {
    _init(espace) {
        super._init({reactive: false, can_focus: false, track_hover: false});
        this.set_style(
            `border: ${EP}px solid ${espace.couleur};` +
            `border-radius: 12px;`);
        const etiq = new St.Label({
            text: espace.nom,
            style: `background-color: ${espace.couleur}; color: #0A1318;` +
                   `font-weight: 700; font-size: 10px; padding: 1px 8px;` +
                   `border-radius: 6px;`,
        });
        etiq.set_position(12, -8);
        this.add_child(etiq);
    }
    majGeometrie(rect) {
        // le liseré épouse le bord de la fenêtre (visible même maximisée)
        this.set_position(rect.x, rect.y);
        this.set_size(rect.width, rect.height);
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
        // Recharge le registre pour reconnaître aussi les Espaces personnalisés.
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
        this.menu.addAction('🛡  Assistant de sécurité', () => {
            try {
                GLib.spawn_command_line_async('/usr/bin/codebyr-assistant');
            } catch (e) {
                Main.notify('Codebyr', 'Assistant indisponible');
            }
        });
        this.menu.addAction('⚙  Configuration Codebyr', () => {
            try {
                GLib.spawn_command_line_async('/usr/bin/codebyr-config');
            } catch (e) {
                Main.notify('Codebyr', 'Configuration indisponible');
            }
        });
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
                GLib.spawn_command_line_async('/usr/bin/codebyr-space create '
                    + GLib.shell_quote(nom) + ' ' + GLib.shell_quote(etat.couleur));
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
                'Ouvre le menu en haut à droite → Changer d\'utilisateur → Invité (mot de passe : invite).');
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
                GLib.spawn_command_line_async('/usr/bin/codebyr-jetable ' + GLib.shell_quote(u));
        };
        dlg.setButtons([
            {label: 'Annuler', action: () => dlg.close(), key: Clutter.KEY_Escape},
            {label: 'Ouvrir en Jetable', action: ouvrir, default: true},
        ]);
        entry.clutter_text.connect('activate', ouvrir);
        dlg.open();
        global.stage.set_key_focus(entry.clutter_text);
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
        for (const app of this._apps)
            sub.menu.addAction(app.nom, () => this._lancer(e.id, app.cmd));
        sub.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        sub.menu.addAction('Fermer cet Espace', () => this._gerer('close', e.id, e.nom));
        if (!jetable) {
            sub.menu.addAction('Vider ses données', () => this._gerer('purge', e.id, e.nom));
            sub.menu.addAction('Créer un instantané (sauvegarde)', () => this._gerer('export', e.id, e.nom));
            sub.menu.addAction('Revenir à un instantané…', () => this._dialogueInstantanes(e.id, e.nom));
            if (!BUILTIN.includes(e.id))
                sub.menu.addAction('Supprimer cet Espace', () => this._gerer('delete', e.id, e.nom));
        }
        this.menu.addMenuItem(sub);
    }

    _lancer(id, cmd) {
        try {
            let commande = '/usr/bin/codebyr-space launch ' + id;
            if (cmd)
                commande += ' -- ' + cmd;
            GLib.spawn_command_line_async(commande);
        } catch (e) {
            Main.notify('Codebyr', 'Impossible d\'ouvrir l\'Espace ' + id);
        }
    }

    _gerer(action, id, nom) {
        try {
            GLib.spawn_command_line_async('/usr/bin/codebyr-space ' + action + ' ' + id);
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
                GLib.spawn_command_line_async(
                    '/usr/bin/codebyr-space import ' + id + ' ' + GLib.shell_quote(dir + '/' + f));
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
    }

    disable() {
        this._coloriage?.detruire();
        this._coloriage = null;
        this._indicateur?.destroy();
        this._indicateur = null;
        this._espaces = null;
    }
}

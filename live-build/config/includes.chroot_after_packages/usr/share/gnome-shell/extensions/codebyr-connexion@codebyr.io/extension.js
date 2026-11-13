// Codebyr OS — le fond de l'écran de connexion.
//
// GNOME ne propose aucun réglage pour ce fond : il vient du thème de GNOME
// Shell, et remplacer ce thème casserait à chaque version de GNOME. Une
// extension, elle, peut ajouter sa feuille de style. Celle-ci ne déclare que le
// mode « gdm » (metadata.json) : GNOME ne la charge que sur l'écran de
// connexion, jamais dans une session. Elle est activée par le réglage par
// défaut de enabled-extensions (90_codebyr.gschema.override), que la session
// de l'écran de connexion lit comme toute autre.
//
// Tout tient dans stylesheet.css, que GNOME charge à l'activation et retire à
// la désactivation : rien à faire ici.
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class CodebyrConnexion extends Extension {
    enable() {}

    disable() {}
}

/* Diaporama d'installation — Codebyr OS */
import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    id: presentation

    function onActivate() { presentation.startCarousel() }
    function onLeave()    { presentation.stopCarousel() }

    // ── Langue ──────────────────────────────────────────────────────────────
    // Le diaporama suit la langue de la session live (choisie au menu de
    // démarrage de l'ISO). Le français est écrit ici, dans les traduire("…") ;
    // les traductions ci-dessous sont ÉCRITES par
    // « python3 packaging/traductions.py extraire », depuis po/<langue>.po —
    // ne les modifiez pas à la main. Une langue sans traduction reçoit
    // l'anglais, comme le reste de Codebyr.
    // traductions:début
    readonly property var traductions: ({"en": {"Bienvenue dans Codebyr OS\n\nLa sécurité par compartimentation, simple pour tout le monde.": "Welcome to Codebyr OS\n\nSecurity through compartmentalization, simple for everyone.", "Installation en cours…\n\nDans quelques minutes, votre ordinateur sera à la fois sûr et simple.": "Installing…\n\nIn a few minutes, your computer will be both secure and simple.", "Le Blindage\n\nBac à sable renforcé, coupure réseau et zéro privilège pour les tâches sensibles.": "Hardening\n\nReinforced sandbox, network cut-off and zero privileges for sensitive tasks.", "Vos Espaces isolés et colorés\n\nPersonnel, Travail, Banque, Navigation, Jetable. Si l'un est piégé, les autres restent intacts.": "Your isolated, color-coded Spaces\n\nPersonal, Work, Bank, Browsing, Disposable. If one is compromised, the others stay intact."}})
    // traductions:fin

    function traduire(texte) {
        var langue = Qt.locale().name.split("_")[0]
        if (langue === "fr" || langue === "C" || langue === "")
            return texte
        var table = traductions[langue] || traductions["en"] || {}
        return table[texte] || texte
    }

    Slide {
        Rectangle {
            anchors.fill: parent
            color: "#0E1B24"
            Text {
                anchors.centerIn: parent
                width: parent.width * 0.8
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: "#FFFFFF"
                font.pixelSize: 26
                text: traduire("Bienvenue dans Codebyr OS\n\nLa sécurité par compartimentation, simple pour tout le monde.")
            }
        }
    }
    Slide {
        Rectangle {
            anchors.fill: parent
            color: "#0E1B24"
            Text {
                anchors.centerIn: parent
                width: parent.width * 0.8
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: "#FFFFFF"
                font.pixelSize: 26
                text: traduire("Vos Espaces isolés et colorés\n\nPersonnel, Travail, Banque, Navigation, Jetable. Si l'un est piégé, les autres restent intacts.")
            }
        }
    }
    Slide {
        Rectangle {
            anchors.fill: parent
            color: "#0E1B24"
            Text {
                anchors.centerIn: parent
                width: parent.width * 0.8
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: "#FFFFFF"
                font.pixelSize: 26
                // « Renforcé », et non plus « matériel » : les Espaces reposent
                // sur le noyau Linux, pas sur du matériel ni des machines
                // virtuelles — Codebyr le dit partout ailleurs.
                text: traduire("Le Blindage\n\nBac à sable renforcé, coupure réseau et zéro privilège pour les tâches sensibles.")
            }
        }
    }
    Slide {
        Rectangle {
            anchors.fill: parent
            color: "#0E1B24"
            Text {
                anchors.centerIn: parent
                width: parent.width * 0.8
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: "#43C7DF"
                font.pixelSize: 26
                text: traduire("Installation en cours…\n\nDans quelques minutes, votre ordinateur sera à la fois sûr et simple.")
            }
        }
    }
}

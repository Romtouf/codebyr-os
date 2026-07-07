/* Diaporama d'installation — Codebyr OS */
import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    id: presentation

    function onActivate() { presentation.startCarousel() }
    function onLeave()    { presentation.stopCarousel() }

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
                text: "Bienvenue dans Codebyr OS\n\nLa sécurité par compartimentation, simple pour tout le monde."
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
                text: "Vos Espaces isolés et colorés\n\nPersonnel, Travail, Banque, Navigation, Jetable. Si l'un est piégé, les autres restent intacts."
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
                text: "Le Blindage\n\nBac à sable matériel, coupure réseau et zéro privilège pour les tâches sensibles."
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
                text: "Installation en cours…\n\nDans quelques minutes, votre ordinateur sera à la fois sûr et simple."
            }
        }
    }
}

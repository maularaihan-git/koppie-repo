// Koppie Linux - Calamares slideshow v1 (gambar statis: screenshot desktop Koppie)
import QtQuick 2.0

Rectangle {
    anchors.fill: parent
    color: "#1e1e2e"
    Image {
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        source: "slideshow.png"
    }
}

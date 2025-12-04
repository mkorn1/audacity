/*
* Audacity: A Digital Audio Editor
* Preview panel for showing operation previews (for future use)
*/
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Muse.Ui
import Muse.UiComponents

Rectangle {
    id: root

    property string previewText: ""
    property var affectedItems: []
    property bool isVisible: previewText.length > 0 || (affectedItems && affectedItems.length > 0)

    color: ui.theme.backgroundSecondaryColor
    border.color: ui.theme.accentColor
    border.width: 2
    radius: 6

    visible: isVisible
    height: visible ? contentLayout.height + 16 : 0

    Behavior on height {
        NumberAnimation { duration: 200 }
    }

    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            StyledTextLabel {
                text: "📋 Preview"
                font: ui.theme.titleBoldFont
                color: ui.theme.fontPrimaryColor
            }

            Item { Layout.fillWidth: true }
        }

        // Preview description
        StyledTextLabel {
            visible: root.previewText.length > 0
            Layout.fillWidth: true
            text: root.previewText
            wrapMode: Text.Wrap
            font: ui.theme.bodyFont
            color: ui.theme.fontPrimaryColor
        }

        // Affected items list
        ColumnLayout {
            visible: root.affectedItems && root.affectedItems.length > 0
            Layout.fillWidth: true
            spacing: 4

            StyledTextLabel {
                text: "Will affect:"
                font: ui.theme.tabFont
                color: ui.theme.fontSecondaryColor
            }

            Repeater {
                model: root.affectedItems
                StyledTextLabel {
                    Layout.fillWidth: true
                    text: "  • " + modelData
                    wrapMode: Text.Wrap
                    font: ui.theme.bodyFont
                    color: ui.theme.fontSecondaryColor
                }
            }
        }
    }
}


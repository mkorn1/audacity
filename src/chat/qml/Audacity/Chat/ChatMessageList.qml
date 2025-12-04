/*
* Audacity: A Digital Audio Editor
*/
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Muse.Ui
import Muse.UiComponents

import Audacity.Chat 1.0

ScrollView {
    id: root

    property var model: null

    clip: true
    ScrollBar.vertical.policy: ScrollBar.AsNeeded

    ListView {
        id: listView
        anchors.fill: parent
        model: root.model
        spacing: 12
        bottomMargin: 12
        topMargin: 12

        delegate: ChatMessageItem {
            width: listView.width
            message: model
        }

        onCountChanged: {
            // Auto-scroll to bottom when new messages arrive
            Qt.callLater(() => {
                if (count > 0) {
                    positionViewAtEnd()
                }
            })
        }
    }
}


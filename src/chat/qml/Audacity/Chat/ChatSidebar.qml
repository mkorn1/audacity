/*
* Audacity: A Digital Audio Editor
*/
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Muse.Ui
import Muse.UiComponents

import Audacity.Chat 1.0

Item {
    id: root

    anchors.fill: parent

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 0
        spacing: 0

        // Messages area
        ChatMessageList {
            id: messageList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: chatViewModel
        }

        // Approval panel (shown when needed)
        ApprovalPanel {
            id: approvalPanel
            Layout.fillWidth: true
            Layout.preferredHeight: approvalPanel.hasApproval ? 120 : 0
            visible: hasApproval
            model: chatViewModel
        }

        // Input area - always visible at bottom
        ChatInput {
            id: inputArea
            Layout.fillWidth: true
            Layout.minimumHeight: 120
            Layout.preferredHeight: 120
            Layout.maximumHeight: 200
            model: chatViewModel
        }
    }

    ChatViewModel {
        id: chatViewModel
    }
}


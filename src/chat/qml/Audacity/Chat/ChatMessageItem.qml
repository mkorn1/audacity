/*
* Audacity: A Digital Audio Editor
*/
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Muse.Ui
import Muse.UiComponents

Rectangle {
    id: root

    // Model role properties (from QAbstractListModel)
    property var message: null  // Contains role data when used with model delegate
    property var chatViewModel: null  // ChatViewModel instance for calling methods

    // Access role data - either from message object or fallback
    readonly property int messageRole: message ? (message.role !== undefined ? message.role : 0) : 0
    readonly property string messageContent: message ? (message.content !== undefined ? message.content : "") : ""
    readonly property string messageTimestamp: message ? (message.timestamp !== undefined ? message.timestamp : "") : ""
    readonly property bool messageIsPending: message ? (message.isPending !== undefined ? message.isPending : false) : false
    readonly property bool messageCanUndo: message ? (message.canUndo !== undefined ? message.canUndo : false) : false

    height: contentLayout.height + 16
    color: {
        switch (messageRole) {
        case 0: // User
            return ui.theme.accentColor
        case 1: // Assistant
            return ui.theme.backgroundPrimaryColor
        case 2: // System
            return ui.theme.warningColor
        default:
            return ui.theme.backgroundPrimaryColor
        }
    }
    radius: 8

    RowLayout {
        id: contentLayout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.top: parent.top
        anchors.topMargin: 8
        spacing: 12

        // Avatar/Icon
        Rectangle {
            Layout.preferredWidth: 32
            Layout.preferredHeight: 32
            radius: 16
            color: {
                switch (messageRole) {
                case 0: // User
                    return ui.theme.accentColor
                case 1: // Assistant
                    return ui.theme.buttonColor
                default:
                    return ui.theme.strokeColor
                }
            }

            StyledTextLabel {
                anchors.centerIn: parent
                text: {
                    switch (messageRole) {
                    case 0: return "U"
                    case 1: return "AI"
                    default: return "!"
                    }
                }
                font: ui.theme.defaultFont
                color: ui.theme.fontPrimaryColor
            }
        }

        // Message content
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            TextEdit {
                Layout.fillWidth: true
                text: messageContent
                wrapMode: TextEdit.Wrap
                font: ui.theme.bodyFont
                color: ui.theme.fontPrimaryColor
                readOnly: true
                selectByMouse: true
                selectByKeyboard: true
            }

            // Timestamp (if available)
            StyledTextLabel {
                visible: messageTimestamp.length > 0
                text: messageTimestamp
                font: ui.theme.tabFont
                color: ui.theme.fontSecondaryColor
            }

            // Pending indicator
            Rectangle {
                visible: messageIsPending
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
                radius: 8
                color: ui.theme.accentColor

                SequentialAnimation on opacity {
                    running: messageIsPending
                    loops: Animation.Infinite
                    NumberAnimation { from: 0.3; to: 1.0; duration: 1000 }
                    NumberAnimation { from: 1.0; to: 0.3; duration: 1000 }
                }
            }

            // Undo button (for assistant messages that completed operations)
            RowLayout {
                visible: messageRole === 1 && !messageIsPending && messageCanUndo
                Layout.fillWidth: true
                spacing: 8

                Item { Layout.fillWidth: true }

                FlatButton {
                    id: undoButton
                    text: "Undo"

                    // Visual feedback animation
                    SequentialAnimation on opacity {
                        id: undoAnimation
                        running: false
                        loops: 1
                        NumberAnimation {
                            from: 1.0
                            to: 0.5
                            duration: 150
                        }
                        NumberAnimation {
                            from: 0.5
                            to: 1.0
                            duration: 150
                        }
                    }

                    onClicked: {
                        // Visual feedback
                        undoAnimation.start()

                        // Dispatch undo action through ChatViewModel
                        if (chatViewModel) {
                            chatViewModel.undo()
                        }
                    }
                }
            }
        }
    }
}


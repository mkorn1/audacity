/*
* Audacity: A Digital Audio Editor
*/
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Muse.Ui
import Muse.UiComponents

import Audacity.Chat 1.0

Rectangle {
    id: root

    property var model: null

    function sendMessage() {
        if (inputField.text.trim().length > 0 && model) {
            var message = inputField.text.trim()
            model.sendMessage(message)
            inputField.text = ""
            inputField.forceActiveFocus()
        }
    }

    color: ui.theme.backgroundPrimaryColor

    // Minimum height to ensure input is always visible
    implicitHeight: 120

    SeparatorLine {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // Input field with better styling
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            color: ui.theme.backgroundSecondaryColor
            border.color: inputField.activeFocus ? ui.theme.accentColor : ui.theme.strokeColor
            border.width: inputField.activeFocus ? 2 : 1
            radius: 6

            TextArea {
                id: inputField
                anchors.fill: parent
                anchors.margins: 12
                placeholderText: "Type your message here... (e.g., 'Select the first 30 seconds', 'Apply noise reduction', 'Split the clip')"
                wrapMode: TextArea.Wrap
                font: ui.theme.bodyFont
                color: ui.theme.fontPrimaryColor
                selectByMouse: true
                background: null // Remove default background, use parent Rectangle

                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        if (event.modifiers & Qt.ControlModifier || event.modifiers & Qt.ShiftModifier) {
                            // Allow new line with Ctrl+Enter or Shift+Enter
                            return
                        }
                        event.accepted = true
                        if (sendButton.enabled) {
                            root.sendMessage()
                        }
                    }
                }

                onTextChanged: {
                    // Auto-resize if needed (optional)
                }
            }
        }

        // Send button row
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // Helpful hint text
            StyledTextLabel {
                text: "Press Enter to send, Ctrl+Enter for new line"
                font: ui.theme.tabFont
                color: ui.theme.fontSecondaryColor
                visible: !inputField.text
            }

            Item { Layout.fillWidth: true }

            FlatButton {
                id: sendButton
                text: "Send"
                enabled: inputField.text.trim().length > 0 && (!model || !model.isProcessing)
                onClicked: root.sendMessage()
            }
        }
    }

    // Focus input field when component is shown
    Component.onCompleted: {
        Qt.callLater(() => {
            inputField.forceActiveFocus()
        })
    }
}


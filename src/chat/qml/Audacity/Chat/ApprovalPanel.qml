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
    property bool hasApproval: model ? model.hasPendingApproval : false

    color: ui.theme.backgroundSecondaryColor

    visible: hasApproval
    height: visible ? contentLayout.height + 24 : 0

    SeparatorLine {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
    }

    Behavior on height {
        NumberAnimation { duration: 200 }
    }

    ColumnLayout {
        id: contentLayout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 12
        spacing: 12

        // Step indicator for step-by-step approvals
        RowLayout {
            visible: model && model.approvalStepTotal > 1
            Layout.fillWidth: true
            spacing: 8

            StyledTextLabel {
                text: "Step " + (model ? model.approvalStepCurrent + 1 : 0) + " of " + (model ? model.approvalStepTotal : 0)
                font: ui.theme.tabFont
                color: ui.theme.accentColor
            }

            Item { Layout.fillWidth: true }

            // Progress bar
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 4
                radius: 2
                color: ui.theme.backgroundPrimaryColor
                border.color: ui.theme.strokeColor
                border.width: 1

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: parent.width * (model ? (model.approvalStepCurrent + 1) / model.approvalStepTotal : 0)
                    radius: 2
                    color: ui.theme.accentColor

                    Behavior on width {
                        NumberAnimation { duration: 200 }
                    }
                }
            }
        }

        StyledTextLabel {
            Layout.fillWidth: true
            text: model ? model.approvalDescription : ""
            wrapMode: Text.Wrap
            font: ui.theme.bodyFont
            color: ui.theme.fontPrimaryColor
        }

        // Preview info (if available)
        StyledTextLabel {
            visible: model && model.approvalPreview
            Layout.fillWidth: true
            text: model ? "Preview: " + model.approvalPreview : ""
            wrapMode: Text.Wrap
            font: ui.theme.tabFont
            color: ui.theme.fontSecondaryColor
        }

        // Batch approval option (for multi-step operations)
        RowLayout {
            visible: model && model.approvalStepTotal > 1
            Layout.fillWidth: true
            spacing: 8

            FlatButton {
                text: "Approve All Steps"
                accentButton: true
                onClicked: {
                    if (model) {
                        model.approveOperation(true, true) // true = batch mode
                    }
                }
            }

            Item { Layout.fillWidth: true }
        }

        // Action buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            FlatButton {
                Layout.fillWidth: true
                text: "Cancel"
                onClicked: {
                    if (model) {
                        model.cancelApproval()
                    }
                }
            }

            FlatButton {
                Layout.fillWidth: true
                text: "Approve"
                accentButton: true
                onClicked: {
                    if (model) {
                        model.approveOperation(true)
                    }
                }
            }
        }
    }
}


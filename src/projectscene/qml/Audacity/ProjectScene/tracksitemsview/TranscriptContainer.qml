import QtQuick

import Muse.Ui
import Muse.UiComponents

import Audacity.ProjectScene

Rectangle {
    id: root

    property var context: null
    property int containerHeight: 30
    
    implicitHeight: containerHeight
    
    // Visual debug: make container visible even when empty (temporarily)
    color: "#FF000020" // Light red tint for debugging
    border.color: "#FF0000"
    border.width: 1

    TranscriptListModel {
        id: transcriptModel
        context: root.context
    }

    onContextChanged: {
        console.log("TranscriptContainer: context changed", context != null)
        if (context) {
            transcriptModel.init()
        }
    }

    // TEMPORARILY always visible for debugging - will restore rowCount check later
    visible: true // repeater.count > 0

    Component.onCompleted: {
        console.log("TranscriptContainer: Component completed")
        console.log("  - x:", x, "y:", y, "width:", width, "height:", height)
        console.log("  - visible:", visible)
        console.log("  - parent:", parent)
        console.log("  - root.width:", root.width, "root.height:", root.height)
    }
    
    onXChanged: console.log("TranscriptContainer: x changed to", x)
    onYChanged: console.log("TranscriptContainer: y changed to", y)
    onWidthChanged: console.log("TranscriptContainer: width changed to", width)
    onHeightChanged: console.log("TranscriptContainer: height changed to", height)

    onVisibleChanged: {
        console.log("TranscriptContainer: visible changed to", visible)
    }

    Connections {
        target: transcriptModel
        function onRowsInserted() {
            console.log("TranscriptContainer: rows inserted, repeater count:", repeater.count)
        }
        function onRowsRemoved() {
            console.log("TranscriptContainer: rows removed, repeater count:", repeater.count)
        }
    }

    Rectangle {
        id: transcriptContainer
        anchors.fill: parent
        clip: true
        
        // Visual debug: show inner container bounds
        color: "#00FF0020" // Light green tint for debugging
        border.color: "#00FF00"
        border.width: 1

        Component.onCompleted: {
            console.log("TranscriptContainer: inner container completed")
            console.log("  - width:", width, "height:", height)
            console.log("  - parent width:", parent.width, "parent height:", parent.height)
        }

        onWidthChanged: {
            console.log("TranscriptContainer: inner container width changed to", width)
            console.log("  - This affects item visibility calculations")
        }

        onHeightChanged: {
            console.log("TranscriptContainer: inner container height changed to", height)
        }

        Repeater {
            id: repeater
            model: transcriptModel

            Component.onCompleted: {
                console.log("TranscriptContainer: Repeater completed, count:", count)
            }

            onItemAdded: {
                console.log("TranscriptContainer: Repeater item added at index", index, "total items:", count)
            }

            delegate: Rectangle {
                id: wordBubble

                property var itemData: model.item

                x: itemData ? itemData.x : 0
                y: 2
                width: itemData ? Math.max(itemData.width, 20) : 20
                height: parent.height - 4

                // Improved visibility check: show item if any part is visible (handles negative x positions)
                property bool isVisible: itemData && (itemData.x + itemData.width) >= 0 && itemData.x <= transcriptContainer.width
                visible: isVisible

                Component.onCompleted: {
                    if (itemData) {
                        console.log("TranscriptContainer: Delegate created, index:", index,
                                  "title:", itemData.title,
                                  "x:", x, "width:", width,
                                  "container width:", transcriptContainer.width,
                                  "visible:", isVisible,
                                  "itemData.x:", itemData.x, "itemData.width:", itemData.width)
                    } else {
                        console.log("TranscriptContainer: Delegate created, index:", index, "itemData is null")
                    }
                }

                onVisibleChanged: {
                    console.log("TranscriptContainer: Delegate visibility changed, index:", index, "visible:", visible,
                              "x:", x, "width:", width, "container width:", transcriptContainer.width)
                }

                onXChanged: {
                    if (itemData) {
                        console.log("TranscriptContainer: Delegate x changed, index:", index, "x:", x, "itemData.x:", itemData.x)
                    }
                }

                onWidthChanged: {
                    if (itemData) {
                        console.log("TranscriptContainer: Delegate width changed, index:", index, "width:", width, "itemData.width:", itemData.width)
                    }
                }

                color: itemData && itemData.isFiller ? "#E0E0E0" : "#F5F5F5"
                border.color: "#CCCCCC"
                border.width: 1
                radius: 4

                Text {
                    id: wordText
                    anchors.fill: parent
                    anchors.margins: 4
                    text: itemData ? itemData.title : ""
                    font.pixelSize: 11
                    color: "#333333"
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (itemData && root.context && itemData.time) {
                            var startTime = itemData.time.startTime
                            if (typeof startTime === 'number' && !isNaN(startTime) && isFinite(startTime)) {
                                try {
                                    // Seek to word start time
                                    root.context.insureVisible(startTime)
                                } catch (e) {
                                    console.error("TranscriptContainer: Error calling insureVisible:", e)
                                }
                            } else {
                                console.warn("TranscriptContainer: Invalid startTime:", startTime)
                            }
                        } else {
                            console.warn("TranscriptContainer: Missing itemData, context, or time:", {
                                itemData: !!itemData,
                                context: !!root.context,
                                time: itemData ? !!itemData.time : false
                            })
                        }
                    }
                }
            }
        }
    }
}


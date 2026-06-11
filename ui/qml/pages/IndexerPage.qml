import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../dialogs"

Kirigami.ScrollablePage {
    title: "Indexer"

    function reloadStatus() {
        var status = backend.getIndexerStatus();
        progressBar.visible = status.active;
        progressBar.value = status.active ? (status.filesDone / Math.max(status.filesTotal, 1)) : 0;
        fileLabel.text = status.active ? "Indexing: " + status.currentFile : "No active indexing";
        countLabel.text = status.active ? (status.filesDone + " / " + status.filesTotal + " files") : "";
        etaLabel.text = status.active ? ("ETA: " + status.eta) : "";
        pauseBtn.text = "Pause";
        pauseBtn.visible = status.active;
        stopBtn.visible = status.active;
    }

    Component.onCompleted: reloadStatus()

    // ── Actions ──────────────────────────────────────────────────────────
    actions: [
        Kirigami.Action {
            icon.name: "view-refresh"
            text: "Refresh"
            onTriggered: reloadStatus()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        // ── Progress Card ────────────────────────────────────────────────
        Kirigami.AbstractCard {
            Layout.fillWidth: true
            visible: progressBar.visible

            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing
                implicitWidth: parent ? parent.width : Kirigami.Units.gridUnit * 20

                QQC2.Label {
                    id: fileLabel
                    text: "No active indexing"
                    font.bold: true
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }

                QQC2.ProgressBar {
                    id: progressBar
                    Layout.fillWidth: true
                    from: 0.0
                    to: 1.0
                    value: 0.0
                    visible: false
                }

                RowLayout {
                    Layout.fillWidth: true

                    QQC2.Label {
                        id: countLabel
                        color: Kirigami.Theme.disabledTextColor
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                    }

                    Item { Layout.fillWidth: true }

                    QQC2.Label {
                        id: etaLabel
                        color: Kirigami.Theme.disabledTextColor
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                    }
                }

                // ── Pause / Stop ──────────────────────────────────────────
                RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    QQC2.Button {
                        id: pauseBtn
                        text: "Pause"
                        icon.name: "media-playback-pause"
                        visible: false
                        onClicked: {
                            if (text === "Pause") {
                                backend.pauseIndexing();
                                text = "Resume";
                            } else {
                                backend.resumeIndexing();
                                text = "Pause";
                            }
                        }
                    }

                    QQC2.Button {
                        id: stopBtn
                        text: "Stop"
                        icon.name: "media-playback-stop"
                        visible: false
                        onClicked: {
                            backend.stopIndexing();
                            reloadStatus();
                        }
                    }
                }
            }
        }

        // ── Chunker Configuration ────────────────────────────────────────
        Kirigami.Heading {
            level: 2
            text: "Chunker Configuration"
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true

            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    QQC2.Label { text: "Strategy:" }
                    QQC2.ComboBox {
                        id: chunkerCombo
                        model: ["ast", "by_size", "by_lines", "hybrid"]
                        currentIndex: 0
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    QQC2.Label { text: "Max Chunk Size:" }
                    QQC2.SpinBox {
                        id: chunkSizeSpin
                        from: 100
                        to: 2000
                        value: 500
                        stepSize: 50
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    QQC2.Label { text: "Overlap:" }
                    QQC2.SpinBox {
                        id: overlapSpin
                        from: 0
                        to: 500
                        value: 50
                        stepSize: 10
                        Layout.fillWidth: true
                    }
                }
            }
        }

        // ── No Indexing Placeholder ──────────────────────────────────────
        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: !progressBar.visible
            text: "No indexing in progress"
            explanation: "Start indexing from the Repositories page or CLI."
        }
    }
}

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../dialogs"

Kirigami.ScrollablePage {
    title: "Settings"

    function loadSettings() {
        var s = backend.getSettings();
        qdrantHostField.text = s.qdrantHost || "";
        qdrantPortField.text = String(s.qdrantPort || 6333);
        collectionField.text = s.collectionName || "";
        providerCombo.currentIndex = findProviderIndex(s.embeddingProvider || "LM Studio");
        modelField.text = s.embeddingModel || "";
        endpointField.text = s.embeddingEndpoint || "";
        watcherSwitch.checked = s.watcherEnabled !== false;
        debounceSlider.value = s.watcherDebounce || 2.0;
    }

    function findProviderIndex(name) {
        for (var i = 0; i < providerCombo.model.length; i++) {
            if (providerCombo.model[i] === name) return i;
        }
        return 0;
    }

    function collectSettings() {
        return {
            "qdrantHost": qdrantHostField.text,
            "qdrantPort": parseInt(qdrantPortField.text) || 6333,
            "collectionName": collectionField.text,
            "embeddingProvider": providerCombo.currentText,
            "embeddingModel": modelField.text,
            "embeddingEndpoint": endpointField.text,
            "watcherEnabled": watcherSwitch.checked,
            "watcherDebounce": debounceSlider.value,
        };
    }

    Component.onCompleted: loadSettings()

    // ── Actions ──────────────────────────────────────────────────────────
    actions: [
        Kirigami.Action {
            icon.name: "document-save"
            text: "Save"
            onTriggered: {
                backend.saveSettings(collectSettings());
                passNotification.show("Settings saved", 2000);
            }
        },
        Kirigami.Action {
            icon.name: "document-revert"
            text: "Reset"
            onTriggered: {
                loadSettings();
                passNotification.show("Defaults restored", 2000);
            }
        }
    ]

    // ── Passive Notification (toast) ─────────────────────────────────────
    Rectangle {
        id: passNotification
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Kirigami.Units.largeSpacing
        width: Math.min(implicitWidth + Kirigami.Units.largeSpacing * 2, parent.width - Kirigami.Units.largeSpacing * 2)
        height: implicitHeight + Kirigami.Units.largeSpacing
        radius: Kirigami.Units.smallSpacing
        color: Kirigami.Theme.backgroundColor
        border.color: Kirigami.Theme.disabledTextColor
        border.width: 1
        visible: false
        z: 100

        QQC2.Label {
            id: passText
            anchors.centerIn: parent
            text: ""
            color: Kirigami.Theme.textColor
        }

        Timer {
            id: passTimer
            interval: 2000
            onTriggered: passNotification.visible = false
        }

        function show(msg, duration) {
            passText.text = msg;
            passTimer.interval = duration || 2000;
            passNotification.visible = true;
            passTimer.restart();
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        // ── Qdrant Settings ──────────────────────────────────────────────
        Kirigami.Heading {
            level: 2
            text: "Qdrant Connection"
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true

                    QQC2.Label { text: "Host:"; Layout.minimumWidth: Kirigami.Units.gridUnit * 4 }
                    QQC2.TextField { id: qdrantHostField; placeholderText: "localhost"; Layout.fillWidth: true }
                }

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true

                    QQC2.Label { text: "Port:"; Layout.minimumWidth: Kirigami.Units.gridUnit * 4 }
                    QQC2.TextField { id: qdrantPortField; placeholderText: "6333"; Layout.fillWidth: true }
                }

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true

                    QQC2.Label { text: "Collection:"; Layout.minimumWidth: Kirigami.Units.gridUnit * 4 }
                    QQC2.TextField { id: collectionField; placeholderText: "hivemind_code"; Layout.fillWidth: true }
                }
            }
        }

        // ── Embedding Model Settings ──────────────────────────────────────
        Kirigami.Heading {
            level: 2
            text: "Embedding Model"
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true

                    QQC2.Label { text: "Provider:"; Layout.minimumWidth: Kirigami.Units.gridUnit * 4 }
                    QQC2.ComboBox {
                        id: providerCombo
                        model: ["LM Studio", "OpenAI", "Ollama"]
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true

                    QQC2.Label { text: "Model:"; Layout.minimumWidth: Kirigami.Units.gridUnit * 4 }
                    QQC2.TextField { id: modelField; placeholderText: "qwen3-4B-embedding"; Layout.fillWidth: true }
                }

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true

                    QQC2.Label { text: "Endpoint:"; Layout.minimumWidth: Kirigami.Units.gridUnit * 4 }
                    QQC2.TextField { id: endpointField; placeholderText: "http://localhost:1234/v1"; Layout.fillWidth: true }
                }
            }
        }

        // ── File Watcher Settings ─────────────────────────────────────────
        Kirigami.Heading {
            level: 2
            text: "File Watcher"
        }

        Kirigami.AbstractCard {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true

                    QQC2.Label { text: "Enabled:"; Layout.minimumWidth: Kirigami.Units.gridUnit * 4 }
                    QQC2.Switch { id: watcherSwitch; checked: true }
                    Item { Layout.fillWidth: true }
                }

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true

                    QQC2.Label { text: "Debounce (s):"; Layout.minimumWidth: Kirigami.Units.gridUnit * 4 }
                    QQC2.Slider {
                        id: debounceSlider
                        from: 0.5
                        to: 30.0
                        value: 2.0
                        stepSize: 0.5
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        text: debounceSlider.value.toFixed(1) + "s"
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        Layout.minimumWidth: Kirigami.Units.gridUnit * 3
                    }
                }
            }
        }
    }
}

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../dialogs"

Kirigami.ScrollablePage {
    title: "Server"

    property var _stats: ({})

    function reloadStats() {
        _stats = backend.getServerStats();
        var running = _stats.status === "running";
        statusBanner.type = running ? Kirigami.MessageType.Positive : Kirigami.MessageType.Warning;
        statusBanner.text = running ? "MCP Server is running" : "MCP Server is stopped";
        statusBanner.visible = true;
        startBtn.visible = !running;
        stopBtn.visible = running;
        clientsCard.value = _stats.connectedClients;
        requestsCard.value = _stats.requestsServed;
        uptimeCard.value = _stats.uptime;

        toolListModel.clear();
        var tools = _stats.tools || [];
        for (var i = 0; i < tools.length; i++) {
            toolListModel.append({"name": tools[i]});
        }
    }

    Component.onCompleted: reloadStats()

    // ── Actions ──────────────────────────────────────────────────────────
    actions: [
        Kirigami.Action {
            icon.name: "view-refresh"
            text: "Refresh"
            onTriggered: reloadStats()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        // ── Status Banner ───────────────────────────────────────────────
        Kirigami.InlineMessage {
            id: statusBanner
            Layout.fillWidth: true
            visible: true
        }

        // ── Start / Stop ────────────────────────────────────────────────
        RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true

            QQC2.Button {
                id: startBtn
                text: "Start Server"
                icon.name: "media-playback-start"
                onClicked: {
                    backend.startServer();
                    reloadStats();
                }
            }

            QQC2.Button {
                id: stopBtn
                text: "Stop Server"
                icon.name: "media-playback-stop"
                visible: false
                onClicked: {
                    backend.stopServer();
                    reloadStats();
                }
            }

            QQC2.Button {
                text: "View Log"
                icon.name: "view-list-details"
                onClicked: logSheet.open()
            }

            Item { Layout.fillWidth: true }
        }

        // ── Server Stats ────────────────────────────────────────────────
        Kirigami.Heading {
            level: 2
            text: "Server Statistics"
        }

        Kirigami.CardsLayout {
            StatusCard {
                id: clientsCard
                iconName: "network-connect"
                label: "Connected Clients"
                value: "0"
                color: Kirigami.Theme.activeTextColor
            }

            StatusCard {
                id: requestsCard
                iconName: "mail-send"
                label: "Requests Served"
                value: "0"
                color: Kirigami.Theme.linkColor
            }

            StatusCard {
                id: uptimeCard
                iconName: "chronometer"
                label: "Uptime"
                value: "0s"
                color: Kirigami.Theme.textColor
            }
        }

        // ── Registered Tools ─────────────────────────────────────────────
        Kirigami.Heading {
            level: 2
            text: "Registered MCP Tools"
        }

        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: contentHeight
            interactive: false
            spacing: Kirigami.Units.smallSpacing

            model: ListModel { id: toolListModel }

            delegate: Kirigami.AbstractCard {
                width: parent.width
                contentItem: RowLayout {
                    Kirigami.Icon {
                        source: "code-class"
                        Layout.preferredWidth: Kirigami.Units.iconSizes.small
                        Layout.preferredHeight: width
                    }
                    QQC2.Label {
                        text: model.name
                        font.family: "monospace"
                        Layout.fillWidth: true
                    }
                }
            }

            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                visible: toolListModel.count === 0
                text: "Start the server to see registered tools"
            }
        }
    }

    // ── Server Log Sheet ─────────────────────────────────────────────
    ServerLogSheet {
        id: logSheet
    }
}

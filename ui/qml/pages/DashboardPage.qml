import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../dialogs"

Kirigami.ScrollablePage {
    title: "Dashboard"

    actions: [
        Kirigami.Action {
            icon.name: "view-refresh"
            text: "Refresh"
            onTriggered: reloadStats()
        }
    ]

    function reloadStats() {
        var stats = backend.getDashboardStats();
        chunksCard.value = stats.indexedChunks;
        filesCard.value = stats.indexedFiles;
        reposCard.value = stats.indexedRepos;
        timeCard.value = stats.avgSearchTime;
        recentListModel.clear();
        for (var i = 0; i < stats.recentSearches.length; i++) {
            recentListModel.append(stats.recentSearches[i]);
        }
    }

    Component.onCompleted: reloadStats()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        // ── Status Cards Grid ────────────────────────────────────────────
        Kirigami.CardsLayout {
            Layout.fillWidth: true

            StatusCard {
                id: chunksCard
                iconName: "document-edit"
                label: "Indexed Chunks"
                value: "0"
                color: Kirigami.Theme.positiveTextColor
            }

            StatusCard {
                id: filesCard
                iconName: "text-x-generic"
                label: "Indexed Files"
                value: "0"
                color: Kirigami.Theme.activeTextColor
            }

            StatusCard {
                id: reposCard
                iconName: "folder"
                label: "Indexed Repos"
                value: "0"
                color: Kirigami.Theme.linkColor
            }

            StatusCard {
                id: timeCard
                iconName: "chronometer"
                label: "Avg Search Time"
                value: "—"
                color: Kirigami.Theme.textColor
            }
        }

        // ── Server Status Banner ─────────────────────────────────────────
        Kirigami.InlineMessage {
            id: serverBanner
            Layout.fillWidth: true
            visible: true

            function updateStatus() {
                var status = backend.serverStatus;
                if (status === "running") {
                    serverBanner.type = Kirigami.MessageType.Positive;
                    serverBanner.text = "MCP Server is running";
                } else {
                    serverBanner.type = Kirigami.MessageType.Warning;
                    serverBanner.text = "MCP Server is stopped";
                }
            }
        }

        // ── Recent Searches ──────────────────────────────────────────────
        Kirigami.Heading {
            level: 2
            text: "Recent Searches"
        }

        ListView {
            id: recentView
            Layout.fillWidth: true
            Layout.preferredHeight: contentHeight
            interactive: false
            spacing: Kirigami.Units.smallSpacing

            model: ListModel { id: recentListModel }

            delegate: Kirigami.AbstractCard {
                width: parent.width
                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Icon {
                        source: "edit-find"
                        Layout.preferredWidth: Kirigami.Units.iconSizes.small
                        Layout.preferredHeight: width
                    }
                    QQC2.Label {
                        text: model.query
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    QQC2.Label {
                        text: model.timestamp
                        color: Kirigami.Theme.disabledTextColor
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                    }
                }
            }
        }

        // ── Placeholder when no recent activity ──────────────────────────
        Kirigami.PlaceholderMessage {
            id: emptyPlaceholder
            Layout.fillWidth: true
            visible: recentListModel.count === 0
            text: "No recent search activity"
        }
    }
}

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

/**
 * RepoDelegate — A card representing a single repository in the list.
 *
 * Properties:
 *   model     — The RepoListModel entry with roles: name, path, indexed, chunks
 */
Kirigami.AbstractCard {
    id: root

    property var modelData: ({})

    signal removeRequested(string path)
    signal reindexRequested(string path)

    implicitWidth: parent ? parent.width : Kirigami.Units.gridUnit * 30
    implicitHeight: Kirigami.Units.gridUnit * 5

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Icon {
            source: modelData.indexed ? "emblem-default" : "folder"
            Layout.preferredWidth: Kirigami.Units.iconSizes.medium
            Layout.preferredHeight: width
            color: modelData.indexed ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            QQC2.Label {
                text: modelData.name || ""
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            QQC2.Label {
                text: modelData.path || ""
                color: Kirigami.Theme.disabledTextColor
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                elide: Text.ElideMiddle
                Layout.fillWidth: true
            }

            QQC2.Label {
                text: modelData.indexed ? (modelData.chunks + " chunks indexed") : "Not indexed"
                color: modelData.indexed ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }
        }

        // ── Action Buttons ───────────────────────────────────────────────
        RowLayout {
            spacing: Kirigami.Units.smallSpacing

            QQC2.Button {
                text: "Reindex"
                visible: modelData.indexed
                icon.name: "view-refresh"
                onClicked: root.reindexRequested(modelData.path || "")
            }

            QQC2.Button {
                text: "Remove"
                icon.name: "edit-delete"
                onClicked: root.removeRequested(modelData.path || "")
            }
        }
    }
}

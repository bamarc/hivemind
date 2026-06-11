import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

/**
 * SearchResultDelegate — A card showing a single semantic search result.
 *
 * Displays: file path with line number, code snippet, relevance score,
 * and programming language.
 */
Kirigami.AbstractCard {
    id: root

    property var modelData: ({})

    implicitWidth: parent ? parent.width : Kirigami.Units.gridUnit * 30
    implicitHeight: contentItem.implicitHeight + Kirigami.Units.largeSpacing * 2

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        // ── Header: file path + line ─────────────────────────────────────
        RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true

            Kirigami.Icon {
                source: "text-x-generic"
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: width
            }

            QQC2.Label {
                text: (modelData.filePath || "") + ":" + (modelData.lineNumber || "")
                font.family: "monospace"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: Kirigami.Theme.linkColor
                Layout.fillWidth: true
                elide: Text.ElideMiddle
            }

            // ── Language badge ──────────────────────────────────────────
            QQC2.Label {
                text: modelData.language || ""
                color: Kirigami.Theme.disabledTextColor
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                background: Rectangle {
                    color: Kirigami.Theme.backgroundColor
                    radius: Kirigami.Units.smallSpacing
                    border.color: Kirigami.Theme.disabledTextColor
                    border.width: 1
                }
                leftPadding: Kirigami.Units.smallSpacing
                rightPadding: Kirigami.Units.smallSpacing
                bottomPadding: Kirigami.Units.tinySpacing
                topPadding: Kirigami.Units.tinySpacing
            }

            // ── Score badge ─────────────────────────────────────────────
            QQC2.Label {
                text: Math.round((modelData.score || 0) * 100) + "%"
                color: {
                    var s = modelData.score || 0;
                    if (s >= 0.8) return Kirigami.Theme.positiveTextColor;
                    if (s >= 0.5) return Kirigami.Theme.neutralTextColor;
                    return Kirigami.Theme.disabledTextColor;
                }
                font.bold: true
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }
        }

        // ── Code snippet ────────────────────────────────────────────────
        QQC2.Label {
            text: modelData.content || ""
            font.family: "monospace"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.iconSizes.small + Kirigami.Units.smallSpacing
            color: Kirigami.Theme.textColor
        }
    }
}

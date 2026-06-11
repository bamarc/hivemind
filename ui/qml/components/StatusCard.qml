import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

/**
 * StatusCard — A Kirigami card displaying a single metric.
 *
 * Properties:
 *   iconName   — Kirigami icon name
 *   label      — Human-readable label
 *   value      — The metric value (string)
 *   color      — Accent color for the value text
 */
Kirigami.AbstractCard {
    id: root

    property string iconName: "unknown"
    property string label: ""
    property string value: ""
    property color color: Kirigami.Theme.textColor

    implicitWidth: Kirigami.Units.gridUnit * 14
    implicitHeight: Kirigami.Units.gridUnit * 6

    contentItem: Item {
        implicitWidth: root.implicitWidth
        implicitHeight: root.implicitHeight

        Kirigami.Icon {
            id: icon
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.margins: Kirigami.Units.largeSpacing
            width: Kirigami.Units.iconSizes.medium
            height: width
            source: root.iconName
        }

        QQC2.Label {
            anchors.top: parent.top
            anchors.left: icon.right
            anchors.right: parent.right
            anchors.margins: Kirigami.Units.largeSpacing
            text: root.label
            font.pointSize: Kirigami.Theme.defaultFont.pointSize
            color: Kirigami.Theme.disabledTextColor
            elide: Text.ElideRight
        }

        QQC2.Label {
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Kirigami.Units.largeSpacing
            text: root.value
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.8
            font.bold: true
            color: root.color
            elide: Text.ElideRight
        }
    }
}

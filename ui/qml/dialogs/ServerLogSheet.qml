import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

/**
 * ServerLogSheet — OverlaySheet showing recent server log entries.
 */
Kirigami.OverlaySheet {
    id: sheet
    title: "Server Log"

    function reload() {
        var stats = backend.getServerStats();
        var logs = stats.recentLogs || [];
        logListModel.clear();
        for (var i = 0; i < logs.length; i++) {
            logListModel.append({"text": logs[i]});
        }
    }

    onVisibleChanged: {
        if (visible) reload();
    }

    ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        QQC2.Button {
            text: "Refresh"
            icon.name: "view-refresh"
            onClicked: reload()
        }

        ListView {
            id: logView
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Kirigami.Units.smallSpacing

            model: ListModel { id: logListModel }

            delegate: QQC2.Label {
                text: model.text
                font.family: "monospace"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                wrapMode: Text.WordWrap
                width: parent ? parent.width : Kirigami.Units.gridUnit * 20
                color: {
                    if (model.text.indexOf("[ERROR]") >= 0) return Kirigami.Theme.negativeTextColor;
                    if (model.text.indexOf("[WARNING]") >= 0) return Kirigami.Theme.neutralTextColor;
                    return Kirigami.Theme.textColor;
                }
            }

            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                visible: logListModel.count === 0
                text: "No log entries"
            }
        }
    }
}

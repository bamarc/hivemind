import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

/**
 * AddRepoSheet — OverlaySheet for adding a new repository.
 *
 * Signals:
 *   repoAdded(path, chunker) — emitted when user confirms
 */
Kirigami.OverlaySheet {
    id: sheet

    signal repoAdded(string path, string chunker)

    title: "Add Repository"

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        QQC2.Label {
            text: "Enter the filesystem path to a repository to index."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        QQC2.TextField {
            id: pathField
            placeholderText: "/path/to/repository"
            Layout.fillWidth: true
            implicitWidth: Kirigami.Units.gridUnit * 16
        }

        RowLayout {
            spacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true

            QQC2.Label {
                text: "Chunker:"
            }

            QQC2.ComboBox {
                id: chunkerCombo
                model: ["ast", "by_size", "by_lines", "hybrid"]
                currentIndex: 0
                Layout.fillWidth: true
            }
        }

        QQC2.Button {
            text: "Add & Index"
            enabled: pathField.text.trim().length > 0
            icon.name: "list-add"
            Layout.fillWidth: true
            onClicked: {
                sheet.repoAdded(pathField.text.trim(), chunkerCombo.currentText);
                pathField.text = "";
                sheet.close();
            }
        }
    }
}

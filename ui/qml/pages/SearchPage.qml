import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../dialogs"

Kirigami.ScrollablePage {
    title: "Search"

    property var _languageFilters: ({})
    property ListModel filterModel: ListModel {}

    function doSearch() {
        var results = backend.search(queryField.text, 20);
        resultListModel.clear();
        _languageFilters = {};
        for (var i = 0; i < results.length; i++) {
            resultListModel.append(results[i]);
            var lang = results[i].language || "text";
            if (!_languageFilters.hasOwnProperty(lang)) {
                _languageFilters[lang] = true;
            }
        }
        rebuildFilterCheckboxes();
        applyFilters();
    }

    function applyFilters() {
        var activeLangs = {};
        for (var i = 0; i < filterRepeater.count; i++) {
            var cb = filterRepeater.itemAt(i);
            if (cb && cb.checked) {
                activeLangs[cb.text] = true;
            }
        }
        // Filter the list view
        for (var row = 0; row < resultListModel.count; row++) {
            var lang = resultListModel.get(row).language || "text";
            resultView.itemAtIndex(row).visible = activeLangs.hasOwnProperty(lang);
        }
    }

    function rebuildFilterCheckboxes() {
        var langs = Object.keys(_languageFilters);
        filterModel.clear();
        for (var i = 0; i < langs.length; i++) {
            filterModel.append({"name": langs[i], "checked": true});
        }
    }

    actions: [
        Kirigami.Action {
            icon.name: "edit-find"
            text: "Search"
            onTriggered: doSearch()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        // ── Search Bar ───────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            Kirigami.SearchField {
                id: queryField
                placeholderText: "Search your codebase… e.g. 'authentication flow'"
                Layout.fillWidth: true
                onAccepted: doSearch()
            }

            QQC2.Button {
                text: "Search"
                icon.name: "edit-find"
                enabled: queryField.text.trim().length > 0
                onClicked: doSearch()
            }
        }

        // ── Language Filters ─────────────────────────────────────────────
        Flow {
            id: filterBar
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            visible: filterModel.count > 0

            Repeater {
                id: filterRepeater
                model: filterModel

                delegate: QQC2.CheckBox {
                    text: name
                    checked: true
                    onCheckedChanged: applyFilters()
                }
            }
        }

        // ── Results List ─────────────────────────────────────────────────
        Kirigami.CardsListView {
            id: resultView
            Layout.fillWidth: true
            Layout.fillHeight: true

            model: ListModel { id: resultListModel }

            delegate: SearchResultDelegate {
                modelData: model
            }

            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                visible: resultListModel.count === 0
                text: queryField.text.trim().length > 0 ? "No results found" : "Enter a query to search"
            }
        }
    }
}

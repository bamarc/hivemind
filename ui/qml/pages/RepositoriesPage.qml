import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../components"
import "../dialogs"

Kirigami.ScrollablePage {
    title: "Repositories"

    actions: [
        Kirigami.Action {
            icon.name: "list-add"
            text: "Add Repository"
            onTriggered: addSheet.open()
        }
    ]

    // ── Add Repo Sheet ────────────────────────────────────────────────
    AddRepoSheet {
        id: addSheet
        onRepoAdded: function(path, chunker) {
            backend.addRepo(path, chunker);
            reloadRepos();
        }
    }

    function reloadRepos() {
        var repos = backend.getRepos();
        repoListModel.clear();
        for (var i = 0; i < repos.length; i++) {
            repoListModel.append(repos[i]);
        }
    }

    Component.onCompleted: reloadRepos()

    // ── Repo List View ────────────────────────────────────────────────
    Kirigami.CardsListView {
        id: repoListView
        model: ListModel { id: repoListModel }

        delegate: RepoDelegate {
            modelData: model
            onRemoveRequested: function(path) {
                backend.removeRepo(path);
                reloadRepos();
            }
            onReindexRequested: function(path) {
                backend.reindexRepo(path);
                reloadRepos();
            }
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: repoListModel.count === 0
            text: "No repositories configured"
            helpfulAction: Kirigami.Action {
                icon.name: "list-add"
                text: "Add Repository"
                onTriggered: addSheet.open()
            }
        }
    }
}

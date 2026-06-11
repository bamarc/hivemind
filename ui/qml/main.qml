import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "pages"
import "components"
import "dialogs"

Kirigami.ApplicationWindow {
    id: root
    title: "Hivemind"
    width: 960
    height: 640

    // Helper to resolve page URLs relative to this file
    function pageUrl(name) {
        return Qt.resolvedUrl("pages/" + name);
    }

    // ── Global Drawer (Sidebar) ──────────────────────────────────────
    globalDrawer: Kirigami.GlobalDrawer {
        id: drawer
        title: "Hivemind"
        titleIcon: "network-server-symbolic"

        actions: [
            Kirigami.Action {
                text: "Dashboard"
                icon.name: "view-grid-symbolic"
                onTriggered: {
                    pageStack.clear();
                    pageStack.push(root.pageUrl("DashboardPage.qml"));
                    drawer.close();
                }
            },
            Kirigami.Action {
                text: "Repositories"
                icon.name: "folder-symbolic"
                onTriggered: {
                    pageStack.clear();
                    pageStack.push(root.pageUrl("RepositoriesPage.qml"));
                    drawer.close();
                }
            },
            Kirigami.Action {
                text: "Search"
                icon.name: "edit-find-symbolic"
                onTriggered: {
                    pageStack.clear();
                    pageStack.push(root.pageUrl("SearchPage.qml"));
                    drawer.close();
                }
            },
            Kirigami.Action {
                text: "Server"
                icon.name: "network-server-symbolic"
                onTriggered: {
                    pageStack.clear();
                    pageStack.push(root.pageUrl("ServerPage.qml"));
                    drawer.close();
                }
            },
            Kirigami.Action {
                text: "Indexer"
                icon.name: "document-save-symbolic"
                onTriggered: {
                    pageStack.clear();
                    pageStack.push(root.pageUrl("IndexerPage.qml"));
                    drawer.close();
                }
            },
            Kirigami.Action {
                text: "Settings"
                icon.name: "settings-configure-symbolic"
                onTriggered: {
                    pageStack.clear();
                    pageStack.push(root.pageUrl("SettingsPage.qml"));
                    drawer.close();
                }
            }
        ]
    }

    // ── Page Stack ───────────────────────────────────────────────────
    pageStack.initialPage: root.pageUrl("DashboardPage.qml")
}

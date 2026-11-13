workspace {
    model {
        user = person "User"
        app = softwareSystem "App" {
            web = container "Web"
            db = container "Store"
        }
        user -> web "uses"
        web -> db "reads"
    }
    views {
        systemContext app {
            include *
        }
        container app {
            include *
        }
    }
}

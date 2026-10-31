workspace "shop" {
  model {
    user = person "User"
    system = softwareSystem "shop" {
      app = container "Application" "python-cli" {
        c1 = component "domain" "Rules with no I/O"
        c2 = component "feature:cli-shop" "cli:shop: أمر واحد، لا تلمس بيانات"
      }
    }
    user -> app "uses"
  }
  views {
    systemContext system {
      include *
      autolayout
    }
    container system {
      include *
      autolayout
    }
    component app {
      include *
      autolayout
    }
  }
}

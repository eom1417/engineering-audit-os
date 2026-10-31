workspace "shop" {
  model {
    user = person "User"
    system = softwareSystem "shop" {
      app = container "Application" "python-cli" {
        c1 = component "app" "It is already where the target puts it, breaks no layer rule, carries no critical risk, and is simple and unduplicated. (6 file(s), 0 to move (0%), 0 forbidden import(s), complexity_max 1, duplicated_"
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

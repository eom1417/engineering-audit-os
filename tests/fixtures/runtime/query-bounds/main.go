package main

func ListAll(db *sql.DB) error {
    return db.Query("SELECT * FROM orders") // no LIMIT
}

func ListLimited(db *sql.DB) error {
    return db.Query("SELECT * FROM orders LIMIT 100")
}

func FindGORM(db *gorm.DB) error {
    return db.Find(&orders) // no .Limit()
}

func FindBounded(db *gorm.DB) error {
    return db.Limit(50).Find(&orders)
}

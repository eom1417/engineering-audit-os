def find(cursor, name, table):
    # ruleid: eaos.security.string-built-sql-python
    cursor.execute(f"SELECT * FROM users WHERE name = '{name}'")
    # ruleid: eaos.security.string-built-sql-python
    cursor.execute("SELECT * FROM " + table)
    # ruleid: eaos.security.string-built-sql-python
    cursor.execute("SELECT * FROM users WHERE name = '%s'" % name)
    # ok: eaos.security.string-built-sql-python
    cursor.execute("SELECT * FROM users WHERE name = ?", (name,))

async function find(db: any, name: string) {
  // ruleid: eaos.security.string-built-sql-js
  await db.query(`SELECT * FROM users WHERE name = '${name}'`);
  // ok: eaos.security.string-built-sql-js
  await db.query("SELECT * FROM users WHERE name = $1", [name]);
  // ok: eaos.security.string-built-sql-js
  await api.query(`/users/${name}`);
}

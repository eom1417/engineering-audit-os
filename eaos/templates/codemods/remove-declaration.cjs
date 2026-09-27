// Generated for EAOS: remove one top-level declaration by name (--name=<symbol>), exported or not.
// Functions, classes, variables (one declarator of a declaration), interfaces, type aliases, enums, and
// the matching specifier of an `export { ... }`. An import only the removed code used goes with it: a leftover
// import fails a linter that forbids unused names. Nothing else in the file changes.
module.exports = function removeDeclaration(file, api, options) {
  const j = api.jscodeshift;
  const name = options.name;
  const root = j(file.source);
  const named = (node) => node && node.id && node.id.name === name;
  const kinds = ['FunctionDeclaration', 'ClassDeclaration', 'TSInterfaceDeclaration', 'TSTypeAliasDeclaration', 'TSEnumDeclaration'];
  // How often each name is used outside import statements: an import the removal leaves unused goes too.
  const uses = () => {
    const count = new Map();
    root.find(j.Identifier).forEach((path) => {
      if (j(path).closest(j.ImportDeclaration).size()) return;
      count.set(path.node.name, (count.get(path.node.name) || 0) + 1);
    });
    root.find(j.JSXIdentifier).forEach((path) => count.set(path.node.name, (count.get(path.node.name) || 0) + 1));
    return count;
  };
  const before = uses();
  let changed = false;
  root.find(j.Program).forEach((program) => {
    program.node.body = program.node.body.filter((statement) => {
      const inner = statement.type === 'ExportNamedDeclaration' && statement.declaration ? statement.declaration : statement;
      if (kinds.includes(inner.type) && named(inner)) { changed = true; return false; }
      if (inner.type === 'VariableDeclaration') {
        const kept = inner.declarations.filter((d) => !(d.id && d.id.name === name));
        if (kept.length !== inner.declarations.length) {
          changed = true;
          if (!kept.length) return false;
          inner.declarations = kept;
        }
      }
      if (statement.type === 'ExportNamedDeclaration' && !statement.declaration && statement.specifiers) {
        const kept = statement.specifiers.filter((s) => s.local.name !== name);
        if (kept.length !== statement.specifiers.length) {
          changed = true;
          if (!kept.length) return false;
          statement.specifiers = kept;
        }
      }
      return true;
    });
  });
  if (changed) {
    const after = uses();
    root.find(j.ImportDeclaration).forEach((path) => {
      const specifiers = path.node.specifiers || [];
      if (!specifiers.length) return;   // a side-effect import is kept for its effect
      const kept = specifiers.filter((s) => !(before.get(s.local.name) && !after.get(s.local.name)));
      if (kept.length === specifiers.length) return;
      if (kept.length) path.node.specifiers = kept; else j(path).remove();
    });
  }
  return changed ? root.toSource() : null;
};

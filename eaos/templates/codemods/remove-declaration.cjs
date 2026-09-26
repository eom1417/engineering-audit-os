// Generated for EAOS: remove one top-level declaration by name (--name=<symbol>), exported or not.
// Functions, classes, variables (one declarator of a declaration), interfaces, type aliases, enums, and
// the matching specifier of an `export { ... }`. Nothing else in the file changes.
module.exports = function removeDeclaration(file, api, options) {
  const j = api.jscodeshift;
  const name = options.name;
  const root = j(file.source);
  const named = (node) => node && node.id && node.id.name === name;
  const kinds = ['FunctionDeclaration', 'ClassDeclaration', 'TSInterfaceDeclaration', 'TSTypeAliasDeclaration', 'TSEnumDeclaration'];
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
  return changed ? root.toSource() : null;
};

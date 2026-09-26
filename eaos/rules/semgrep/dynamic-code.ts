function run(text: string) {
  // ruleid: eaos.security.dynamic-code-js
  eval(text);
  // ruleid: eaos.security.dynamic-code-js
  const f = new Function("a", text);
  // ok: eaos.security.dynamic-code-js
  JSON.parse(text);
  return f;
}

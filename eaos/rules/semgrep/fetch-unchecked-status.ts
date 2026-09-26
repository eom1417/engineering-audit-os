async function a(url: string) {
  // ruleid: eaos.dataflow.fetch-unchecked-status
  return (await fetch(url)).json();
}
function b(url: string) {
  // ruleid: eaos.dataflow.fetch-unchecked-status
  return fetch(url).then((r) => r.json());
}
async function c(url: string) {
  const response = await fetch(url);
  // ruleid: eaos.dataflow.fetch-unchecked-status
  return response.json();
}
async function d(url: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(String(response.status));
  // ok: eaos.dataflow.fetch-unchecked-status
  return response.json();
}

async function load(supabase: any) {
  // ruleid: eaos.dataflow.supabase-unchecked-error
  const { data } = await supabase.from("accounts").select("*").eq("id", 1);
  // ruleid: eaos.dataflow.supabase-unchecked-error
  const { data: rows } = await supabase.rpc("totals");
  // ok: eaos.dataflow.supabase-unchecked-error
  const { data: checked, error } = await supabase.from("accounts").select("*");
  if (error) throw error;
  return [data, rows, checked];
}
async function renamed(supabase: any) {
  // ok: eaos.dataflow.supabase-unchecked-error
  const { data, error: failure } = await supabase.from("cards").select("*");
  if (failure) throw failure;
  return data;
}

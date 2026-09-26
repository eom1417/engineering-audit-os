// ruleid: eaos.security.service-role-in-frontend
const key = import.meta.env.VITE_SUPABASE_SERVICE_ROLE_KEY;
// ok: eaos.security.service-role-in-frontend
const anon = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
export { key, anon };

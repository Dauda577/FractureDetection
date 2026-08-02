let client = null;

async function getSupabase() {
  if (client) return client;
  const { createClient } = await import('@supabase/supabase-js');
  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;
  client = createClient(supabaseUrl, supabaseAnonKey);
  return client;
}

export { getSupabase };

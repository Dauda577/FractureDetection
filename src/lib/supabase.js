let client = null;

async function getSupabase() {
  if (client) return client;
  if (typeof window !== 'undefined' && window.__fracturedetectSupabase) {
    client = window.__fracturedetectSupabase;
    return client;
  }
  const { createClient } = await import('@supabase/supabase-js');
  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;
  client = createClient(supabaseUrl, supabaseAnonKey);
  if (typeof window !== 'undefined') {
    window.__fracturedetectSupabase = client;
  }
  return client;
}

export { getSupabase };

import { supabase } from '../lib/supabase.js'

export async function register(name, email, password) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: name } }
  })
  if (error) return { ok: false, error: error.message }
  return { ok: true, user: data.user }
}

export async function login(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password })
  if (error) return { ok: false, error: error.message }
  return { ok: true, user: data.user }
}

export async function logout() {
  await supabase.auth.signOut()
}

export async function getUser() {
  const { data } = await supabase.auth.getSession()
  if (!data.session) return null
  const user = data.session.user
  return {
    id: user.id,
    email: user.email,
    name: user.user_metadata?.full_name || user.email?.split('@')[0] || 'User',
    avatarUrl: user.user_metadata?.avatar_url || user.user_metadata?.picture || null,
    createdAt: user.created_at
  }
}

export async function isSignedIn() {
  const user = await getUser()
  return !!user
}

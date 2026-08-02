import { getSupabase } from '../lib/supabase.js'

export async function register(name, email, password) {
  const supabase = await getSupabase()
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: name } }
  })
  if (error) return { ok: false, error: error.message }
  return { ok: true, user: data.user }
}

export async function login(email, password) {
  const supabase = await getSupabase()
  const { data, error } = await supabase.auth.signInWithPassword({ email, password })
  if (error) return { ok: false, error: error.message }
  return { ok: true, user: data.user }
}

export async function logout() {
  const supabase = await getSupabase()
  await supabase.auth.signOut()
}

export async function getUser() {
  const supabase = await getSupabase()
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

export async function signInWithGoogle() {
  const supabase = await getSupabase()
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin + '/account' }
  })
  if (error) return { ok: false, error: error.message }
  return { ok: true, data }
}

export async function sendResetEmail(email) {
  const supabase = await getSupabase()
  const { data, error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: window.location.origin + '/update-password'
  })
  if (error) return { ok: false, error: error.message }
  return { ok: true, data }
}

export async function updatePassword(newPassword) {
  const supabase = await getSupabase()
  const { data, error } = await supabase.auth.updateUser({ password: newPassword })
  if (error) return { ok: false, error: error.message }
  return { ok: true, data }
}

export async function onAuthStateChange(callback) {
  const supabase = await getSupabase()
  return supabase.auth.onAuthStateChange(callback)
}

export async function updateProfile({ name }) {
  const supabase = await getSupabase()
  const { data, error } = await supabase.auth.updateUser({
    data: { full_name: name }
  })
  if (error) return { ok: false, error: error.message }
  return { ok: true, user: data.user }
}

import { supabase } from '../lib/supabase.js'

export async function savePatient(name, age, gender, medicalRecordId, notes) {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return null

  const { data, error } = await supabase.from('patients').insert({
    user_id: session.user.id,
    name: name,
    age: age || null,
    gender: gender || null,
    medical_record_id: medicalRecordId || null,
    notes: notes || null
  }).select('id').single()

  if (error) return null
  return data.id
}

export async function getPatients() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return []

  const { data, error } = await supabase
    .from('patients')
    .select('id, name, age, gender, medical_record_id, notes, created_at')
    .order('created_at', { ascending: false })
    .limit(50)

  if (error) return []
  return data || []
}

export async function getPatient(id) {
  const { data, error } = await supabase
    .from('patients')
    .select('*')
    .eq('id', id)
    .single()

  if (error) return null
  return data
}

export async function deletePatient(id) {
  const { error } = await supabase.from('patients').delete().eq('id', id)
  return !error
}

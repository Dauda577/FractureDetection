import { getSupabase } from '../lib/supabase.js'

export async function savePatient(name, age, gender, medicalRecordId, notes) {
  const supabase = await getSupabase()
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

  supabase.from('notifications').insert({
    user_id: session.user.id,
    type: 'patient',
    message: 'New patient registered: ' + name
  }).then(function () {});

  return data.id
}

export async function getPatients() {
  const supabase = await getSupabase()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return []

  const { data, error } = await supabase
    .from('patients')
    .select('id, name, age, gender, medical_record_id, notes, created_at')
    .eq('user_id', session.user.id)
    .order('created_at', { ascending: false })
    .limit(50)

  if (error) return []
  return data || []
}

export async function getPatient(id) {
  const supabase = await getSupabase()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return null

  const { data, error } = await supabase
    .from('patients')
    .select('*')
    .eq('id', id)
    .eq('user_id', session.user.id)
    .single()

  if (error) return null
  return data
}

export async function deletePatient(id) {
  const supabase = await getSupabase()
  const { error } = await supabase.from('patients').delete().eq('id', id)
  return !error
}

export async function checkMrnUnique(medicalRecordId, excludePatientId) {
  if (!medicalRecordId) return true
  const supabase = await getSupabase()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return true

  var query = supabase.from('patients')
    .select('id')
    .eq('user_id', session.user.id)
    .eq('medical_record_id', medicalRecordId)

  if (excludePatientId) query = query.neq('id', excludePatientId)

  const { data, error } = await query
  if (error) return true
  return data.length === 0
}

import { getSupabase } from '../lib/supabase.js'

export async function saveAnalysis(imageData, prediction, confidence, inferenceTime, findings, patientId) {
  const supabase = await getSupabase()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return null

  const userId = session.user.id
  const fileName = userId + '/' + Date.now() + '.png'

  if (!imageData) return null
  const blob = dataURLToBlob(imageData)
  const { data: uploadData, error: uploadError } = await supabase.storage
    .from('analysis-images')
    .upload(fileName, blob, { contentType: 'image/png', upsert: false })
  if (uploadError) return null

  const record = {
    user_id: userId,
    image_path: fileName,
    prediction: prediction,
    confidence: confidence,
    inference_time: inferenceTime,
    findings: findings || []
  }
  if (patientId) record.patient_id = patientId

  const { data, error } = await supabase.from('analyses').insert(record).select('id').single()

  if (error) return null

  var predLabel = prediction === 'fracture' ? 'Fracture detected' : 'Normal';
  var confPct = (confidence * 100).toFixed(1) + '%';
  supabase.from('notifications').insert({
    user_id: userId,
    type: 'analysis',
    message: 'Analysis complete — ' + predLabel + ' (' + confPct + ' confidence)'
  }).then(function () {});

  return data.id
}

export async function getAnalyses(patientId) {
  const supabase = await getSupabase()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return []

  let query = supabase
    .from('analyses')
    .select('id, image_path, prediction, confidence, inference_time, created_at, findings, patient_id, patients(name, medical_record_id)')
    .eq('user_id', session.user.id)
    .order('created_at', { ascending: false })
    .limit(20)

  if (patientId) query = query.eq('patient_id', patientId)

  const { data, error } = await query

  if (error) return []
  return data || []
}

export async function getAnalysisImageUrl(path) {
  const supabase = await getSupabase()
  const { data } = supabase.storage.from('analysis-images').getPublicUrl(path)
  return data.publicUrl
}

export async function deleteAnalysis(id, imagePath) {
  const supabase = await getSupabase()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return false

  if (imagePath) {
    await supabase.storage.from('analysis-images').remove([imagePath])
  }
  const { error } = await supabase.from('analyses').delete().eq('id', id)
  return !error
}

export async function getAnalysisById(id) {
  const supabase = await getSupabase()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return null

  const { data, error } = await supabase
    .from('analyses')
    .select('id, image_path, prediction, confidence, inference_time, created_at, findings, patient_id, patients(name, medical_record_id)')
    .eq('id', id)
    .eq('user_id', session.user.id)
    .single()

  if (error) return null
  return data
}

export async function getLatestAnalysisForPatient(patientId) {
  const supabase = await getSupabase()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) return null

  const { data, error } = await supabase
    .from('analyses')
    .select('id, image_path, prediction, confidence, inference_time, created_at, findings, patient_id, patients(name, medical_record_id)')
    .eq('patient_id', patientId)
    .eq('user_id', session.user.id)
    .order('created_at', { ascending: false })
    .limit(1)
    .single()

  if (error) return null
  return data
}

export async function imageUrlToDataURL(url) {
  return new Promise(function (resolve) {
    var img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = function () {
      var canvas = document.createElement('canvas')
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      var ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0)
      resolve(canvas.toDataURL('image/png'))
    }
    img.onerror = function () { resolve(null) }
    img.src = url
  })
}

function dataURLToBlob(dataURL) {
  var parts = dataURL.split(',')
  var mime = parts[0].match(/:(.*?);/)[1]
  var bytes = atob(parts[1])
  var len = bytes.length
  var buf = new ArrayBuffer(len)
  var view = new Uint8Array(buf)
  for (var i = 0; i < len; i++) view[i] = bytes.charCodeAt(i)
  return new Blob([buf], { type: mime })
}

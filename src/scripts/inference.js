const API_URL = import.meta.env.PUBLIC_FRACNET_API_URL || 'http://localhost:8000';
const TIMEOUT_MS = 120000;

function dataURLToBlob(dataURL) {
  const parts = dataURL.split(',');
  const mime = parts[0].match(/:(.*?);/)[1];
  const bytes = atob(parts[1]);
  const buf = new ArrayBuffer(bytes.length);
  const view = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i++) view[i] = bytes.charCodeAt(i);
  return new Blob([buf], { type: mime });
}

export async function runInference(imageDataUrl) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const blob = dataURLToBlob(imageDataUrl);
    const formData = new FormData();
    formData.append('file', blob, 'xray.png');

    const response = await fetch(`${API_URL}/predict`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      let detail = `Server error (${response.status})`;
      try {
        const errorBody = await response.json();
        if (errorBody.detail) detail = errorBody.detail;
      } catch (_) {}
      throw new Error(detail);
    }

    const data = await response.json();
    validateResponse(data);
    return data;
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out. The model server may be overloaded. Please try again.');
    }
    if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
      throw new Error('Cannot reach the model server. Is it running on ' + API_URL + '?');
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

function validateResponse(data) {
  const required = ['prediction', 'confidence_display', 'ood_score', 'ood_threshold', 'is_novel', 'cross_head_disagreement', 'heatmap_png_base64'];
  for (const field of required) {
    if (!(field in data)) {
      throw new Error(`Model response missing required field: ${field}`);
    }
  }
  if (data.prediction !== 'Fractured' && data.prediction !== 'Healthy') {
    throw new Error(`Unexpected prediction value: ${data.prediction}`);
  }
}

export async function checkHealth() {
  try {
    const response = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5000) });
    return response.ok;
  } catch (_) {
    return false;
  }
}

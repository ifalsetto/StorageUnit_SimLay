import { SimLayApi } from './api.js';
import { detectBarcodes } from './barcode.js';
import './styles/capture.css';

const ownerSelect = document.getElementById('capture-owner');
const runLabel = document.getElementById('capture-run');
const takePhotoButton = document.getElementById('take-photo');
const choosePhotoButton = document.getElementById('choose-photo');
const cameraInput = document.getElementById('camera-input');
const libraryInput = document.getElementById('library-input');
const statusBox = document.getElementById('capture-status');
const preview = document.getElementById('capture-preview');
const previewImage = document.getElementById('capture-preview-image');
const previewName = document.getElementById('capture-preview-name');
const previewResult = document.getElementById('capture-preview-result');

const OWNER_KEY = 'simlay.quickCapture.owner';
let activeRun = null;
let quickProfile = 'default';
let busy = false;
let previewUrl = '';

function currentOwner() {
  return ownerSelect.value || 'Unassigned';
}

function setStatus(message, tone = 'info') {
  statusBox.textContent = message;
  statusBox.dataset.tone = tone;
}

function setBusy(next) {
  busy = next;
  takePhotoButton.disabled = next;
  choosePhotoButton.disabled = next;
  ownerSelect.disabled = next;
}

function showRun() {
  runLabel.textContent = activeRun?.run_short
    ? `${activeRun.run_short} · ${activeRun.owner || currentOwner()}`
    : `New ${currentOwner()} run will be created with the first photo`;
}

function showPreview(file, resultText) {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  previewImage.src = previewUrl;
  previewName.textContent = file.name || 'Camera photo';
  previewResult.textContent = resultText;
  preview.hidden = false;
}

async function findRunForOwner() {
  const data = await SimLayApi.listRuns();
  const owner = currentOwner();
  activeRun = (data.runs || []).find((candidate) =>
    (candidate.owner || 'Unassigned') === owner && (candidate.media_type || 'photos') === 'photos'
  ) || null;
  showRun();
  return activeRun;
}

async function ensureCaptureRun() {
  if (activeRun?.run_id && (activeRun.owner || 'Unassigned') === currentOwner()) return activeRun;
  const created = await SimLayApi.createRun({
    profile_name: quickProfile,
    media_type: 'photos',
    owner: currentOwner(),
  });
  activeRun = created;
  showRun();
  return created;
}

async function uploadPhoto(file) {
  if (!file || busy) return;
  setBusy(true);
  setStatus('Uploading photo…', 'working');
  showPreview(file, 'Uploading…');
  try {
    const targetRun = await ensureCaptureRun();
    const result = await SimLayApi.uploadMedia(targetRun.run_id, [file]);
    const count = result.uploaded?.length || 0;
    const message = `${count || 1} photo uploaded to ${targetRun.run_short}`;
    setStatus(message, 'success');
    previewResult.textContent = 'Uploaded to SimLay';
  } catch (error) {
    const detail = error?.message || 'Upload failed';
    setStatus(`Upload failed: ${detail}`, 'error');
    previewResult.textContent = 'Not uploaded';
  } finally {
    cameraInput.value = '';
    libraryInput.value = '';
    setBusy(false);
  }
}

async function initialize() {
  const savedOwner = localStorage.getItem(OWNER_KEY);
  if (['Thomas', 'Mine', 'Unassigned'].includes(savedOwner)) ownerSelect.value = savedOwner;

  try {
    await SimLayApi.health();
    const profileData = await SimLayApi.listProfiles().catch(() => ({ profiles: ['default'] }));
    const profiles = profileData.profiles || ['default'];
    quickProfile = profiles.includes('default') ? 'default' : (profiles[0] || 'default');
    await findRunForOwner();
    setStatus('Ready. Take a photo and it will upload automatically.', 'success');
  } catch (error) {
    showRun();
    setStatus(`SimLay backend is unavailable: ${error?.message || 'connection failed'}`, 'error');
  }
}

takePhotoButton.addEventListener('click', () => cameraInput.click());
choosePhotoButton.addEventListener('click', () => libraryInput.click());
cameraInput.addEventListener('change', () => uploadPhoto(cameraInput.files?.[0]));
libraryInput.addEventListener('change', () => uploadPhoto(libraryInput.files?.[0]));
ownerSelect.addEventListener('change', async () => {
  localStorage.setItem(OWNER_KEY, currentOwner());
  activeRun = null;
  setStatus(`Switching capture to ${currentOwner()}…`, 'working');
  try {
    await findRunForOwner();
    setStatus(`Ready for ${currentOwner()} photos.`, 'success');
  } catch (error) {
    showRun();
    setStatus(`Could not load runs: ${error?.message || 'connection failed'}`, 'error');
  }
});

initialize();


const scanBarcodeButton = document.getElementById('scan-barcode');
const barcodeInput = document.getElementById('barcode-input');
const barcodeResult = document.getElementById('barcode-result');
scanBarcodeButton.addEventListener('click', () => barcodeInput.click());
barcodeInput.addEventListener('change', async () => {
  const file = barcodeInput.files?.[0];
  if (!file) return;
  scanBarcodeButton.disabled = true;
  barcodeResult.textContent = 'Decoding locally…';
  try {
    const result = await detectBarcodes(file);
    if (result.status === 'detected') {
      barcodeResult.textContent = 'Unverified barcode evidence: ' +
        result.codes.map((code) => code.format + ': ' + code.value).join(' · ') +
        '. Confirm the item before using this code.';
    } else if (result.status === 'unsupported') {
      barcodeResult.textContent = 'Local barcode detection is unavailable in this browser. No image was uploaded.';
    } else {
      barcodeResult.textContent = result.status === 'none' ? 'No barcode found in this image.' : 'Could not decode the barcode locally.';
    }
  } finally {
    barcodeInput.value = '';
    scanBarcodeButton.disabled = false;
  }
});

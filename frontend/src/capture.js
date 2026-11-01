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
const barcodePanel = document.getElementById('barcode-evidence-panel');
const barcodeCode = document.getElementById('barcode-code');
const barcodeItem = document.getElementById('barcode-item');
const saveBarcodeButton = document.getElementById('save-barcode');
let pendingCodes = [];
let pendingImageName = '';
let barcodeRunId = '';
let barcodeOwner = '';

function clearBarcodeEvidence() {
  pendingCodes = [];
  barcodeRunId = '';
  barcodeOwner = '';
  pendingImageName = '';
  barcodePanel.hidden = true;
  saveBarcodeButton.disabled = true;
  barcodeCode.replaceChildren();
  barcodeItem.replaceChildren();
}

function addSelectOption(select, label, value) {
  const option = document.createElement('option');
  option.textContent = label;
  option.value = value;
  select.appendChild(option);
}

async function loadBarcodeItemChoices(ownerSnapshot) {
  barcodeItem.replaceChildren();
  addSelectOption(barcodeItem, 'Choose item to link', '');
  saveBarcodeButton.disabled = true;
  if (!activeRun?.run_id || (activeRun.owner || 'Unassigned') !== ownerSnapshot) {
    barcodeResult.textContent = 'Barcode decoded. Upload and process a photo into an owner-specific SimLay run before linking this code to an item.';
    return;
  }
  const runId = activeRun.run_id;
  const itemData = await SimLayApi.listItems(runId);
  if (ownerSnapshot !== currentOwner() || runId !== activeRun?.run_id) return;
  const candidates = (itemData.items || itemData.inventory || []).filter((item) =>
    !item.deleted_at && ((item.owner || 'Unassigned') === ownerSnapshot || (item.owner || 'Unassigned') === 'Unassigned')
  );
  for (const item of candidates) {
    addSelectOption(barcodeItem, item.final_name || item.raw_name || item.item_id, item.item_id);
  }
  barcodeOwner = ownerSnapshot;
  barcodeRunId = runId;
  if (!candidates.length) {
    barcodeResult.textContent = 'Barcode decoded. This run has no eligible inventory items yet; process the uploaded photo in the dashboard first.';
  } else {
    barcodeResult.textContent = 'Barcode decoded locally. Choose the exact inventory item and then save this unverified observation.';
  }
}

barcodeItem.addEventListener('change', () => {
  saveBarcodeButton.disabled = !barcodeItem.value || !barcodeCode.value;
});
barcodeCode.addEventListener('change', () => {
  saveBarcodeButton.disabled = !barcodeItem.value || !barcodeCode.value;
});

scanBarcodeButton.addEventListener('click', () => barcodeInput.click());
barcodeInput.addEventListener('change', async () => {
  const file = barcodeInput.files?.[0];
  if (!file) return;
  const ownerSnapshot = currentOwner();
  clearBarcodeEvidence();
  scanBarcodeButton.disabled = true;
  barcodeResult.textContent = 'Decoding locally…';
  try {
    const result = await detectBarcodes(file);
    if (ownerSnapshot !== currentOwner()) {
      barcodeResult.textContent = 'Owner changed during scan. Scan again for the correct owner.';
      return;
    }
    if (result.status === 'detected') {
      pendingCodes = result.codes;
      pendingImageName = (file.name || 'Camera image').slice(0, 100);
      for (const [index, code] of pendingCodes.entries()) {
        addSelectOption(barcodeCode, code.format + ': ' + code.value, String(index));
      }
      barcodePanel.hidden = false;
      try {
        await loadBarcodeItemChoices(ownerSnapshot);
      } catch (error) {
        barcodeResult.textContent = 'Decoded locally, but inventory items could not be loaded: ' + (error?.message || 'connection failure');
      }
    } else if (result.status === 'unsupported') {
      barcodeResult.textContent = 'Local barcode detection is unavailable in this browser. No image was uploaded.';
    } else {
      barcodeResult.textContent = result.status === 'none' ? 'No barcode found in this image.' : 'Could not decode the barcode locally.';
    }
  } catch (error) {
    barcodeResult.textContent = 'Scan failed: ' + (error?.message || 'invalid image');
  } finally {
    barcodeInput.value = '';
    scanBarcodeButton.disabled = false;
  }
});

saveBarcodeButton.addEventListener('click', async () => {
  const itemId = barcodeItem.value;
  const code = pendingCodes[Number(barcodeCode.value)];
  if (!itemId || !code || !barcodeRunId || barcodeOwner !== currentOwner() ||
      activeRun?.run_id !== barcodeRunId) {
    barcodeResult.textContent = 'Choose a code and item from the active owner run before saving.';
    return;
  }
  saveBarcodeButton.disabled = true;
  barcodeResult.textContent = 'Checking and saving unpriced barcode evidence…';
  const title = 'Barcode ' + code.format + ': ' + code.value;
  try {
    const prior = await SimLayApi.listEvidence(itemId);
    if ((prior.evidence || []).some((row) => row.source_type === 'barcode' && row.url_title === title)) {
      barcodeResult.textContent = 'This barcode is already saved to the selected item. Nothing duplicated.';
      return;
    }
    const notes = ('Unverified local barcode observation. Format: ' + code.format +
      '; Code: ' + code.value + '; Source image: ' + pendingImageName +
      '; Manually linked to selected item. Product identity not confirmed.').slice(0, 500);
    await SimLayApi.addEvidence({
      item_id: itemId,
      source_type: 'barcode',
      source_name: 'local_barcode_scan',
      listing_type: 'observation',
      url_title: title,
      price: null,
      notes,
    });
    barcodeResult.textContent = 'Saved to the selected item as an unverified, unpriced barcode observation. No automatic valuation or item identification.';
  } catch (error) {
    barcodeResult.textContent = 'Barcode evidence was not saved: ' + (error?.message || 'connection failure');
  } finally {
    saveBarcodeButton.disabled = !barcodeItem.value || !barcodeCode.value;
  }
});

ownerSelect.addEventListener('change', clearBarcodeEvidence);

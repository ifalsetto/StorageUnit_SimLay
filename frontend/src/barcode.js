// Optional local barcode detection. No network calls, uploads, valuation, or inventory mutations.
export const BARCODE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "qr_code"];
export async function detectBarcodes(file, { Detector = globalThis.BarcodeDetector, createBitmap = globalThis.createImageBitmap } = {}) {
  if (!file || !String(file.type || "").startsWith("image/")) throw new TypeError("Choose an image.");
  if (typeof Detector !== "function" || typeof createBitmap !== "function") {
    return { status: "unsupported", codes: [] };
  }
  const supported = typeof Detector.getSupportedFormats === "function"
    ? await Detector.getSupportedFormats() : BARCODE_FORMATS;
  const formats = BARCODE_FORMATS.filter((format) => supported.includes(format));
  if (!formats.length) return { status: "unsupported", codes: [] };
  let bitmap;
  try {
    bitmap = await createBitmap(file);
    const detected = await new Detector({ formats }).detect(bitmap);
    const codes = [...new Map((detected || []).filter((item) =>
      typeof item.rawValue === "string" && item.rawValue.length > 0 && item.rawValue.length <= 256
    ).map((item) => [item.format + ":" + item.rawValue, {
      format: item.format, value: item.rawValue, source: "local-photo", verification: "unverified"
    }])).values()];
    return { status: codes.length ? "detected" : "none", codes };
  } catch {
    return { status: "failed", codes: [] };
  } finally {
    bitmap?.close?.();
  }
}

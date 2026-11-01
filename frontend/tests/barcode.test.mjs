import test from "node:test";
import assert from "node:assert/strict";
import { detectBarcodes } from "../src/barcode.js";

const file = { type: "image/jpeg" };
test("local decode returns unverified evidence without network requests", async () => {
  let closed = false;
  class Detector {
    static async getSupportedFormats() { return ["ean_13"]; }
    async detect() { return [{ format: "ean_13", rawValue: "1234567890123" }, { format: "ean_13", rawValue: "1234567890123" }]; }
  }
  const result = await detectBarcodes(file, { Detector, createBitmap: async () => ({ close() { closed = true; } }) });
  assert.equal(result.status, "detected");
  assert.equal(result.codes.length, 1);
  assert.equal(result.codes[0].verification, "unverified");
  assert.equal(closed, true);
});
test("unsupported browser does not decode or upload", async () => {
  assert.deepEqual(await detectBarcodes(file, { Detector: null }), { status: "unsupported", codes: [] });
});
test("invalid file rejected", async () => {
  await assert.rejects(detectBarcodes({ type: "text/plain" }), TypeError);
});
test("decoding failure closes bitmap and fails closed", async () => {
  let closed = false;
  class Detector { static async getSupportedFormats() { return ["qr_code"]; } async detect() { throw Error("decode"); } }
  const result = await detectBarcodes(file, { Detector, createBitmap: async () => ({ close() { closed = true; } }) });
  assert.equal(result.status, "failed");
  assert.equal(closed, true);
});

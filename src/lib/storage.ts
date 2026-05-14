import { promises as fs } from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const DRIVER = process.env.STORAGE_DRIVER || "local";
const LOCAL_DIR = process.env.STORAGE_LOCAL_DIR || "./storage";

export type StoredFile = {
  storageKey: string;
  sizeBytes: number;
  checksum: string;
  mimeType?: string;
};

export async function saveUpload(
  companyId: string,
  filename: string,
  buffer: Buffer,
  mimeType?: string,
): Promise<StoredFile> {
  if (DRIVER === "local") return saveLocal(companyId, filename, buffer, mimeType);
  throw new Error(`Storage driver "${DRIVER}" not yet implemented`);
}

export async function readUpload(storageKey: string): Promise<Buffer> {
  if (DRIVER === "local") {
    const full = path.resolve(LOCAL_DIR, storageKey);
    if (!full.startsWith(path.resolve(LOCAL_DIR))) throw new Error("Invalid storage key");
    return fs.readFile(full);
  }
  throw new Error(`Storage driver "${DRIVER}" not yet implemented`);
}

async function saveLocal(
  companyId: string,
  filename: string,
  buffer: Buffer,
  mimeType?: string,
): Promise<StoredFile> {
  const safeName = filename.replace(/[^a-zA-Z0-9._-]+/g, "_");
  const checksum = crypto.createHash("sha256").update(buffer).digest("hex");
  const key = path.posix.join(companyId, `${Date.now()}-${checksum.slice(0, 8)}-${safeName}`);
  const full = path.resolve(LOCAL_DIR, key);
  await fs.mkdir(path.dirname(full), { recursive: true });
  await fs.writeFile(full, buffer);
  return { storageKey: key, sizeBytes: buffer.byteLength, checksum, mimeType };
}

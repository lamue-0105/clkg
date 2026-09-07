/** Cloudflare Worker entry point for the vinext-starter template. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  BACKUPS: R2Bucket;
  BACKUP_ENCRYPTION_KEY?: string;
  IMAGES: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

type StoredResponse = {
  id: number;
  schema_version: string;
  answers_json: string;
  submitted_at: string;
};

const encoder = new TextEncoder();

function base64Url(bytes: Uint8Array) {
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function base64UrlBytes(value: string) {
  const base64 = value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - value.length % 4) % 4);
  return Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
}

async function allResponses(db: D1Database) {
  const responses: StoredResponse[] = [];
  let lastId = 0;

  for (;;) {
    const page = await db.prepare(
      "SELECT id, schema_version, answers_json, submitted_at FROM survey_responses WHERE id > ? ORDER BY id ASC LIMIT 500",
    ).bind(lastId).all<StoredResponse>();
    const records = page.results;
    responses.push(...records);
    if (records.length < 500) return responses;
    lastId = records.at(-1)?.id ?? lastId;
  }
}

async function encryptBackup(plainText: string, encodedKey: string) {
  const rawKey = base64UrlBytes(encodedKey);
  if (rawKey.byteLength !== 32) throw new Error("BACKUP_ENCRYPTION_KEY 必须是 32 字节的 base64url 密钥。");

  const key = await crypto.subtle.importKey("raw", rawKey, { name: "AES-GCM" }, false, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const cipherText = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, encoder.encode(plainText));
  return JSON.stringify({
    format: "clkg-survey-encrypted-backup-v1",
    algorithm: "AES-256-GCM",
    iv: base64Url(iv),
    ciphertext: base64Url(new Uint8Array(cipherText)),
  });
}

async function backUpResponses(env: Env) {
  if (!env.BACKUP_ENCRYPTION_KEY) throw new Error("未设置 BACKUP_ENCRYPTION_KEY，已拒绝生成未加密备份。");

  const responses = await allResponses(env.DB);
  const createdAt = new Date().toISOString();
  const payload = JSON.stringify({
    format: "clkg-survey-backup-v1",
    createdAt,
    responseCount: responses.length,
    responses,
  });
  const encrypted = await encryptBackup(payload, env.BACKUP_ENCRYPTION_KEY);
  const objectKey = `survey-responses/${createdAt.replaceAll(":", "-")}.json.enc`;

  await env.BACKUPS.put(objectKey, encrypted, {
    httpMetadata: { contentType: "application/json" },
    customMetadata: { format: "clkg-survey-encrypted-backup-v1", createdAt, responseCount: String(responses.length) },
  });
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      return handleImageOptimization(request, {
        fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
    }

    return handler.fetch(request, env, ctx);
  },

  async scheduled(_controller: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(backUpResponses(env));
  },
};

export default worker;

import { readFile, writeFile } from "node:fs/promises";

const [inputPath, outputPath] = process.argv.slice(2);
const encodedKey = process.env.BACKUP_ENCRYPTION_KEY;

if (!inputPath || !outputPath || !encodedKey) {
  throw new Error("用法：BACKUP_ENCRYPTION_KEY=<密钥> node scripts/decrypt-backup.mjs <加密备份> <恢复文件>");
}

function base64UrlBytes(value) {
  const base64 = value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - value.length % 4) % 4);
  return Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
}

const envelope = JSON.parse(await readFile(inputPath, "utf8"));
if (envelope.format !== "clkg-survey-encrypted-backup-v1" || envelope.algorithm !== "AES-256-GCM") {
  throw new Error("不是受支持的 CLKG 加密备份文件。");
}

const rawKey = base64UrlBytes(encodedKey);
if (rawKey.byteLength !== 32) throw new Error("BACKUP_ENCRYPTION_KEY 必须是 32 字节的 base64url 密钥。");

const key = await crypto.subtle.importKey("raw", rawKey, { name: "AES-GCM" }, false, ["decrypt"]);
const plainText = await crypto.subtle.decrypt(
  { name: "AES-GCM", iv: base64UrlBytes(envelope.iv) },
  key,
  base64UrlBytes(envelope.ciphertext),
);
await writeFile(outputPath, plainText);
console.log(`已恢复到 ${outputPath}`);

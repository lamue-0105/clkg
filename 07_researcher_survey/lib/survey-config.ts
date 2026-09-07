export const SURVEY_SCHEMA_VERSION = "researcher-needs-v1.0";

export function isNonEmptySelection(value: unknown): value is string[] {
  return Array.isArray(value) && value.some((item) => typeof item === "string" && item.trim().length > 0);
}

export function isNonEmptyText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

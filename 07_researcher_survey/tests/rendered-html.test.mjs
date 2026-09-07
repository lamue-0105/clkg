import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("survey source contains the finished CLKG questionnaire", async () => {
  const [page, form] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/survey-form.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(page, /SurveyForm/);
  assert.match(form, /文化遗产跨类型数据组织与研究需求调查/);
  assert.match(form, /CLKG · 研究者需求调研/);
  assert.match(form, /提交匿名答卷/);
  assert.doesNotMatch(form, /Your site is taking shape|Building your site|react-loading-skeleton/);
});

test("uses finished survey metadata instead of starter metadata", async () => {
  const [page, layout] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(page, /SurveyForm/);
  assert.match(layout, /文化遗产跨类型数据组织与研究需求调查/);
  assert.match(layout, /robots:\s*\{ index: false, follow: false \}/);
  assert.doesNotMatch(layout, /Starter Project|codex-preview|_sites-preview/);
});

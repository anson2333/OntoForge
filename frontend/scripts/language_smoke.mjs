import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const language = () => page.getByRole('combobox', { name: '语言 / Language' });
try {
  await page.goto('http://127.0.0.1:5173');
  await page.getByRole('button', { name: '登录', exact: true }).last().waitFor();
  assert.equal(await page.locator('html').getAttribute('lang'), 'zh-CN');
  await language().selectOption('en');
  await page.getByRole('button', { name: 'Sign in', exact: true }).last().waitFor();
  await page.reload();
  await page.getByRole('button', { name: 'Sign in', exact: true }).last().waitFor();
  assert.equal(await language().inputValue(), 'en');
  await language().selectOption('zh-CN');
  await page.locator('input[autocomplete="username"]').fill('demo');
  await page.locator('input[type="password"]').fill('demo1234');
  await page.locator('button[type="submit"]').click();
  await page.getByRole('button', { name: /论文指标对比/ }).waitFor();
  await page.getByRole('button', { name: '模型接口', exact: true }).click();
  await page.getByRole('heading', { name: '模型接口设置' }).waitFor();
  await page.getByRole('button', { name: '关闭接口设置' }).click();
  await language().selectOption('en');
  await page.getByRole('button', { name: /Compare papers/ }).waitFor();
  await page.getByRole('button', { name: 'Model connection', exact: true }).click();
  await page.getByRole('heading', { name: 'Model connection settings' }).waitFor();
  await page.locator('dialog header button').click();
  await page.getByRole('button', { name: /Coverage & gaps/ }).click();
  await page.getByRole('heading', { name: 'Coverage & research gaps' }).waitFor();
  await language().selectOption('zh-CN');
  await page.getByRole('heading', { name: '研究覆盖与候选空白' }).waitFor();
  await page.getByRole('button', { name: /关系图谱/ }).click();
  await page.locator('canvas.graph-canvas').waitFor();
  await mkdir('demo-screenshots/language', { recursive: true });
  await page.screenshot({ path: 'demo-screenshots/language/zh-graph.png' });
  await page.getByRole('button', { name: /论文指标对比/ }).click();
  await page.screenshot({ path: 'demo-screenshots/language/zh-matrix.png' });
  assert.deepEqual(errors, []);
  console.log('PASS: login/app language switching, reload persistence, model settings, coverage, graph; no browser runtime errors.');
} finally {
  await browser.close();
}

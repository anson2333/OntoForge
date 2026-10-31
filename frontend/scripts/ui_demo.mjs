/**
 * Automated UI demo for OntoForge.
 *
 * Opens the Vite dev server in Chromium, signs in with the seeded demo account,
 * and walks through Matrix -> evidence -> Graph -> workspace -> domain pack,
 * saving a screenshot at every step.
 *
 * Usage:
 *   node scripts/ui_demo.mjs                 # headed, closes after a short hold
 *   node scripts/ui_demo.mjs --headless      # no window, screenshots only
 *   node scripts/ui_demo.mjs --url=http://localhost:5173 --slow=2000 --hold=5000
 */

import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const args = new Map(
  process.argv.slice(2).map((arg) => {
    const [key, value = 'true'] = arg.replace(/^--/, '').split('=');
    return [key, value];
  })
);

const url = args.get('url') || process.env.ONTOFORGE_UI_URL || 'http://localhost:5173';
const username = args.get('username') || 'demo';
const password = args.get('password') || 'demo1234';
const headless = args.has('headless');
const stepDelay = Number(args.get('slow') || 1200);
const finalHold = Number(args.get('hold') || 5000);
const screenshotDir = path.resolve(
  args.get('out') || path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'demo-screenshots')
);

const log = (message) => console.log(`[demo] ${message}`);

async function main() {
  if (!Number.isFinite(stepDelay) || stepDelay < 0 || !Number.isFinite(finalHold) || finalHold < 0) {
    throw new Error('--slow and --hold must be non-negative numbers');
  }

  await mkdir(screenshotDir, { recursive: true });

  const browser = await chromium.launch({ headless });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.setDefaultTimeout(30000);

  page.on('console', (message) => {
    if (message.type() === 'error') {
      console.error(`[browser] ${message.text()}`);
    }
  });

  const shot = async (name) => {
    const file = path.join(screenshotDir, `${name}.png`);
    await page.waitForTimeout(stepDelay);
    await page.screenshot({ path: file, fullPage: false });
    log(`截图: ${file}`);
  };

  try {
    log(`打开 ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded' });

    // Login screen appears when no valid session exists.
    const loginForm = page.locator('form input[autocomplete="username"]');
    await Promise.race([
      loginForm.waitFor({ state: 'visible', timeout: 15000 }),
      page.locator('.tab-bar').waitFor({ state: 'visible', timeout: 15000 }),
    ]);

    if (await loginForm.isVisible().catch(() => false)) {
      log(`登录 ${username}`);
      await loginForm.fill(username);
      await page.locator('form input[type="password"]').fill(password);
      await page.locator('form button[type="submit"]').click();
      await page.locator('.tab-bar').waitFor({ state: 'visible' });
    }

  // 1. Matrix: papers x metrics.
    log('步骤 1: Matrix 矩阵');
    await page.getByRole('button', { name: /Matrix/ }).click();
    await page.locator('.matrix-table tbody tr').first().waitFor({ state: 'visible' });
    const paperCount = await page.locator('.matrix-table tbody tr').count();
    const metricCount = await page.locator('.matrix-table thead th').count();
    log(`  论文 ${paperCount} 行，指标 ${metricCount - 1} 列`);
    await shot('01-matrix');

  // 2. Evidence panel for the first populated cell.
    log('步骤 2: 点击有数据的单元格，打开证据面板');
    const populatedCell = page.locator('td.matrix-cell').filter({ has: page.locator('.cell-value') }).first();
    await populatedCell.click();
    await page.locator('.evidence-inspector').waitFor({ state: 'visible' });
    await shot('02-evidence');

  // 3. Graph view.
    log('步骤 3: Graph 知识图谱');
    await page.locator('.tab', { hasText: 'Graph' }).click();
    await page.locator('canvas.graph-canvas').waitFor({ state: 'visible' });
    await shot('03-graph');

    // 4. Coverage and ranked gaps.
    log('步骤 4: Coverage 覆盖分析与候选空白');
    await page.locator('.tab', { hasText: 'Coverage' }).click();
    await page.locator('.coverage-table').first().waitFor({ state: 'visible' });
    await shot('04-coverage');

    // 5. Workspace overview from the sidebar.
    log('步骤 5: Workspace 总览');
    await page.locator('.tab', { hasText: 'Matrix' }).click();
    await page.locator('.workspace-root-name').first().click();
    await page.locator('.workspace-domain-row').first().waitFor({ state: 'visible' });
    await shot('05-workspace');

    // 6. Domain pack detail (taxonomy + papers).
    log('步骤 6: 领域包详情');
    await page.locator('.workspace-domain-row').first().click();
    await page.locator('.domain-pack-view').waitFor({ state: 'visible' });
    const upload = page.getByRole('button', { name: '上传论文 PDF', exact: true });
    await upload.waitFor({ state: 'visible' });
    const chooserReady = page.waitForEvent('filechooser');
    await upload.click();
    const chooser = await chooserReady;
    if (!chooser.isMultiple()) throw new Error('PDF upload must allow multiple papers');
    await chooser.setFiles([]);
    await page.getByRole('button', { name: '配置模型接口', exact: true }).click();
    await page.getByRole('dialog', { name: '模型接口设置' }).waitFor({ state: 'visible' });
    await page.getByRole('button', { name: '关闭接口设置', exact: true }).click();
    await shot('06-domain-pack');

    log(`演示结束，截图目录: ${screenshotDir}`);
    await page.waitForTimeout(finalHold);
  } catch (error) {
    const failureFile = path.join(screenshotDir, 'failure.png');
    await page.screenshot({ path: failureFile, fullPage: true }).catch(() => {});
    throw new Error(`${error.message} (失败截图: ${failureFile})`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(`[demo] 失败: ${error.message}`);
  process.exitCode = 1;
});

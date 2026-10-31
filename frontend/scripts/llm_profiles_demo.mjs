/** Browser regression for saved endpoint profiles; uses a local HTTP fixture, never a paid LLM. */
import { chromium } from 'playwright';
import http from 'node:http';
import { mkdir } from 'node:fs/promises';

let calls = 0;
const fixture = http.createServer(async (request, response) => {
  let body = '';
  for await (const chunk of request) body += chunk;
  if (!['/v1/chat/completions', '/v1/messages'].includes(request.url) || request.headers.authorization !== 'Bearer fixture-only-key') {
    response.writeHead(request.headers.authorization !== 'Bearer fixture-only-key' ? 401 : 400); response.end('Invalid fixture request'); return;
  }
  const payload = JSON.parse(body);
  calls++;
  if (payload.response_format || payload.format) { response.writeHead(400); response.end("Text probe must not force JSON"); return; }
  if (request.url === '/v1/messages') {
    if (!payload.system || !payload.max_tokens || payload.response_format || payload.temperature !== undefined) {
      response.writeHead(400); response.end('Invalid Messages payload'); return;
    }
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify({ model: payload.model, content: [{ type: 'text', text: 'Hello, connection works.' }], stop_reason: 'end_turn', usage: { input_tokens: 4, output_tokens: 4 } }));
    return;
  }
  response.setHeader('Content-Type', 'application/json');
  response.end(JSON.stringify({ model: 'fixture-a', choices: [{ message: { content: 'Hello, connection works.' }, finish_reason: 'stop' }], usage: { total_tokens: 8 } }));
});
await new Promise(resolve => fixture.listen(0, '127.0.0.1', resolve));
const address = `http://127.0.0.1:${fixture.address().port}/v1`;
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1040 } });
  page.setDefaultTimeout(20000);
  await page.goto(process.env.ONTOFORGE_UI_URL || 'http://localhost:25173');
  await page.locator('form input[autocomplete="username"]').fill('demo');
  await page.locator('form input[type="password"]').fill('demo1234');
  await page.locator('form button[type="submit"]').click();
  await page.getByRole('button', { name: '模型接口', exact: true }).click();
  const modal = page.getByRole('dialog', { name: '模型接口设置' });
  await modal.getByRole('button', { name: '＋ 新增接口' }).waitFor();
  const vendors = [
    ['deepseek', 'https://api.deepseek.com', 'openai_compatible'],
    ['zhipu', 'https://open.bigmodel.cn/api/paas/v4', 'openai_compatible'],
    ['kimi', 'https://api.moonshot.cn/v1', 'openai_compatible'],
    ['claude', 'https://api.anthropic.com/v1', 'anthropic']
  ];
  for (const [vendor, base, protocol] of vendors) {
    await modal.getByLabel('厂商预设', { exact: false }).selectOption(vendor);
    if (await modal.getByLabel(/^Base URL/).inputValue() !== base) throw new Error(`Incorrect ${vendor} endpoint`);
    if (await modal.getByLabel('接口类型', { exact: true }).inputValue() !== protocol) throw new Error(`Incorrect ${vendor} protocol`);
    if (!(await modal.getByLabel('模型名称', { exact: true }).inputValue())) throw new Error(`Missing ${vendor} model`);
  }
  await mkdir('demo-screenshots', { recursive: true });
  await page.screenshot({ path: 'demo-screenshots/08-vendor-presets.png' });
  // Clean up only prior fixture profiles belonging to the seeded demo user.
  while (await modal.locator('.llm-profile').filter({ hasText: 'UI Fixture' }).count()) {
    await modal.locator('.llm-profile').filter({ hasText: 'UI Fixture' }).first().click();
    await modal.getByRole('button', { name: '删除此接口', exact: true }).click();
    await modal.getByText('接口已删除。', { exact: false }).waitFor();
  }
  async function create(name, model) {
    await modal.getByRole('button', { name: '＋ 新增接口' }).click();
    await modal.getByLabel('配置名称', { exact: true }).fill(name);
    await modal.getByLabel(/^Base URL/).fill(address);
    await modal.getByLabel('模型名称', { exact: true }).fill(model);
    await modal.getByLabel(/^API Key/).fill('fixture-only-key');
    await modal.getByRole('button', { name: '验证并启用', exact: true }).click();
    await modal.getByText('验证通过，已保存并启用。下一次模型请求将使用此接口。', { exact: true }).waitFor();
  }
  await create('UI Fixture A', 'fixture-a');
  await modal.getByLabel(/^API Key/).fill('fixture-invalid-key');
  await modal.getByRole('button', { name: '验证并启用', exact: true }).click();
  await modal.getByRole('alert').filter({ hasText: 'HTTP 401' }).waitFor();
  await page.screenshot({ path: 'demo-screenshots/09-key-validation-error.png' });
  await modal.locator('.llm-profile').filter({ hasText: 'UI Fixture A' }).click();

  await modal.getByRole('button', { name: '测试已保存接口', exact: true }).click();
  await modal.getByText(/连接验证成功，模型已正常回复/).waitFor();
  await create('UI Fixture B', 'fixture-b');
  await modal.getByLabel('模型名称', { exact: true }).fill('fixture-b-edited');
  await modal.getByRole('button', { name: '验证并保存配置', exact: true }).click();
  await modal.getByText('连接验证通过，配置已保存。', { exact: true }).waitFor();
  await page.reload();
  await page.getByRole('button', { name: '模型接口', exact: true }).click();
  await modal.locator('.llm-settings-current').getByText('UI Fixture B · fixture-b-edited', { exact: true }).waitFor();
  await modal.locator('.llm-profile').filter({ hasText: 'UI Fixture A' }).click();
  if (await modal.getByLabel(/^API Key/).inputValue() !== '') throw new Error('Saved credential leaked into browser input');
  await modal.getByRole('button', { name: '切换到此接口', exact: true }).click();
  await modal.locator('.llm-settings-current').getByText('UI Fixture A · fixture-a', { exact: true }).waitFor();
  await mkdir('demo-screenshots', { recursive: true });
  await page.screenshot({ path: 'demo-screenshots/07-llm-profiles.png' });
  const localState = await page.evaluate(() => JSON.stringify({ ...localStorage }));
  if (localState.includes('fixture-only-key')) throw new Error('API key leaked into localStorage');
  if (calls !== 4) throw new Error(`Unexpected model calls during save/switch/status: ${calls}`);
  for (const name of ['UI Fixture A', 'UI Fixture B']) {
    await modal.locator('.llm-profile').filter({ hasText: name }).click();
    await modal.getByRole('button', { name: '删除此接口', exact: true }).click();
    await modal.getByText('接口已删除。', { exact: false }).waitFor();
  }
  await modal.locator('.llm-settings-current').getByText('服务器 .env 配置', { exact: true }).waitFor();
  await modal.getByRole('button', { name: '＋ 新增接口' }).click();
  await modal.getByLabel('厂商预设', { exact: false }).selectOption('claude');
  await modal.getByLabel('配置名称', { exact: true }).fill('UI Fixture Claude');
  await modal.getByLabel(/^Base URL/).fill(address);
  await modal.getByLabel(/^API Key/).fill('fixture-only-key');
  await modal.getByRole('button', { name: '验证并启用', exact: true }).click();
  await modal.getByText('验证通过，已保存并启用。下一次模型请求将使用此接口。', { exact: true }).waitFor();
  await modal.getByRole('button', { name: '测试已保存接口', exact: true }).click();
  await modal.getByText(/连接验证成功，模型已正常回复/).waitFor();
  if (calls !== 6) throw new Error('Native Claude fixture was not called exactly once');
  await modal.getByLabel('厂商预设', { exact: false }).selectOption('kimi');
  if (!(await modal.getByLabel('清除此接口已保存的密钥', { exact: true }).isChecked())) throw new Error('Switching vendors retained an old key');
  await modal.locator('.llm-profile').filter({ hasText: 'UI Fixture Claude' }).click();
  await modal.getByRole('button', { name: '删除此接口', exact: true }).click();
  await modal.getByText('接口已删除。', { exact: false }).waitFor();
  console.log('[profiles] vendor presets, native Claude Messages, CRUD, switching, reload persistence and credential isolation passed');
} finally {
  await browser.close();
  await new Promise(resolve => fixture.close(resolve));
}

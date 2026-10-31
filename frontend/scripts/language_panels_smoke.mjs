/** Render real components with in-memory fixtures. Never writes research data. */
import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
page.setDefaultTimeout(15000);
const runtimeErrors = [];
const translations = JSON.parse(await readFile(new URL('../renderer/locales/ui.json', import.meta.url), 'utf8'));
page.on('pageerror', error => runtimeErrors.push(error.message));
await page.route('**/__locale_panels__', route => route.fulfill({ contentType: 'text/html', body:
  '<html><head></head><body data-theme="dark"><div id="root"></div></body></html>' }));
try {
  await page.goto('http://127.0.0.1:5173/__locale_panels__');
  await page.evaluate(async () => {
    const RefreshRuntime = (await import('/@react-refresh')).default;
    RefreshRuntime.injectIntoGlobalHook(window);
    window.$RefreshReg$ = () => {};
    window.$RefreshSig$ = () => type => type;
    window.__vite_plugin_react_preamble_installed__ = true;
  });
  await page.evaluate(async () => {
    const React = (await import('/node_modules/.vite/deps/react.js')).default;
    const { createRoot } = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
    // Resolve Vite's current HMR URL so the harness and real components share
    // the same language store rather than loading two module instances.
    const graphSource = await fetch('/renderer/components/GraphView.tsx').then(response => response.text());
    const localeModuleUrl = graphSource.match(/from ["']([^"']*\/i18n\.tsx[^"']*)["']/)[1];
    const { LanguageSelector, useLanguage } = await import(localeModuleUrl);
    await import('/renderer/index.css');
    const { useWorkspaceStore } = await import('/renderer/services/workspace.ts');
    const { sspClient } = await import('/renderer/services/ssp_client.ts');
    const { intentService } = await import('/renderer/services/intent_service.ts');
    const stamp = '2026-10-30T08:00:00Z';
    const workspace = { id: 'memory_only', name: '本地文案验收', root: '', status: 'active', owner_id: 'fixture', metadata: {}, created_at: stamp };
    const config = { schema_version: '1.0', domain: { id: 'domain.test', name: '领域示例', taxonomy_tree: [{ name: 'method', values: ['fixture_method'], subdomain_map: { fixture_method: 'fixture_area' } }] },
      core_metrics: [{ name: 'fixture_metric', expected_unit: 'ms', aliases: [], value_type: 'float' }], validation: { required_context_keys: [], unit_normalization: {} } };
    const metric = { name: 'fixture_metric', full_name: 'test:fixture_metric', namespace: 'test', unit: 'ms', aliases: [], value_type: 'float' };
    const pack = { namespace: 'test', config, metrics: [metric], enabled: true, source: 'file' };
    const paper = { id: 'fixture_paper', title: 'Original paper title stays English', authors: ['Fixture Author'], year: 2020,
      venue: 'Fixture Venue', domain_pack_namespace: 'test', ingestion_status: 'ingested' };
    const cell = { paperId: paper.id, metricName: metric.full_name, value: '12.5', unit: 'ms', status: 'resolved', confidence: 0.65, evidenceCount: 1 };
    const evidence = { id: 'fixture_c01', type: 'chunk', paper_id: paper.id, raw_text: 'Original source evidence stays English.',
      bounding_box: { page: 1, coordinate_precision: 'page_only', box: [0, 0, 0, 0] }, verification_status: 'raw', confidence_score: 0.65, modification_count: 1,
      revisions: [{ version: 1, timestamp: stamp, user_id: 'fixture_user', status: 'raw' }] };
    const pending = { id: 'fixture_import', workspace_id: workspace.id, domain_pack_namespace: 'test', status: 'preview_ready',
      warning: 'Rejected fixture_metric: incompatible unit (conversion is not implicit) Page-only source locations; precise PDF bounding boxes are unavailable.',
      title: paper.title, file_name: 'fixture.pdf', file_size: 1024, source: 'picker', created_at: stamp, upload_id: 'memory_upload', preview_id: 'memory_preview',
      preview: { title: paper.title, authors: paper.authors, year: 2020, chunk_count: 1, formula_count: 0, assertion_count: 1, evidence_count: 1 } };
    const profile = { user_id: 'fixture', learned_patterns: [{ pattern_id: 'fixture_pattern', confidence: 0.85, applications: 1, last_used: stamp, intent_type: 'priority', description: '研究规则示例', matched_arbitrator_ids: [] }],
      active_goals: [{ goal_id: 'fixture_goal', description: '研究目标示例', constraints: {}, active_from: stamp, status: 'active' }], preferred_units: {}, evidence_ranking: [], subdomain_focus: [], learned_priorities: {}, temporal_preferences: {}, confidence_threshold: 0.7, total_intents_captured: 1 };
    useWorkspaceStore.setState({ workspace, currentWorkspaceId: workspace.id, workspaces: [workspace], domainPacks: [pack], activeDomainPackNamespaces: ['test'], metrics: [metric], papers: [paper], paperImports: [pending], cellData: new Map([[`${paper.id}:${metric.full_name}`, cell]]), allCellData: new Map([[`${paper.id}:${metric.full_name}`, cell]]) });
    // Block real network calls and override only this isolated browser's client.
    sspClient.call = async method => {
      if (method === 'listDomainPacks') return { domain_packs: [pack] };
      if (method === 'listWorkspaceMembers') return { members: [{ user_id: 'fixture', username: 'fixture_user', role: 'viewer' }] };
      if (method === 'listLLMProfiles') return { profiles: [], active_id: null, credential_protection: 'DPAPI (Windows user)' };
      if (method === 'listLLMPresets') return { presets: [] };
      if (method === 'getEvidence') return { evidence: [evidence] };
      if (method === 'getCoverageAnalysis') return { coverage: { metrics: ['test:fixture_metric'], methods: ['unspecified'], scenarios: ['unspecified'], matrix: [{ method: 'unspecified', scenario: 'unspecified', cells: { 'test:fixture_metric': { count: 1, paper_ids: [paper.id], assertion_ids: ['fixture_assertion'] } } }], coverage: { covered_cells: 1, total_cells: 1, ratio: 1 }, gaps: [], gap_count: 0 } };
      return {};
    };
    sspClient.request = sspClient.call;
    sspClient.listDomainPacks = async () => ({ domain_packs: [pack] });
    intentService.queryIntentProfile = async () => profile;
    intentService.getCurrentBranch = () => null;
    const modules = {};
    for (const path of [
      'GraphView', 'MatrixGrid', 'CoverageView', 'domain/DomainPackPanel', 'domain/TaxonomyFilter',
      'workspace/RootView', 'workspace/WorkspaceView', 'workspace/DomainPackView', 'workspace/SubdomainView',
      'workspace/MetricsView', 'workspace/MetricView', 'workspace/PaperPreviewView', 'workspace/PaperStatusModal',
      'workspace/CreateWorkspaceModal', 'workspace/AddDomainPackModal', 'workspace/WorkspaceMembersModal',
      'evidence/EvidenceInspector', 'evidence/EvidenceEditor', 'evidence/EvidenceHistory', 'evidence/EvidenceReviewQueue',
      'intent/IntentDeclarationModal', 'intent/IntentMetadataForm', 'intent/IntentProfilePanel', 'intent/IntentBranchSelector', 'settings/LLMSettingsModal'
    ]) {
      const module = await import(`/renderer/components/${path}.tsx`);
      modules[path] = module.default || module[path.split('/').pop()];
    }
    const noop = () => {};
    const common = { hierarchyItems: [{ label: '本地文案验收' }], onClose: noop, onCancel: noop, onSave: noop, onDelete: noop,
      onOpenWorkspace: noop, onOpenDomainPack: noop, onOpenMetrics: noop, onOpenMetric: noop, onEditMetric: noop, onDeleteMetric: noop, onAddMetric: noop,
      onOpenSubdomain: noop, onOpenPaper: noop, onOpenPaperImport: noop, onUploadPapers: noop, onConfigureModel: noop, onCommit: noop, onRetry: noop };
    const props = {
      'GraphView': {}, 'MatrixGrid': { onCellClick: noop }, 'CoverageView': { workspaceId: workspace.id, domainPacks: [pack] },
      'domain/DomainPackPanel': {}, 'domain/TaxonomyFilter': { dimensions: config.domain.taxonomy_tree, selectedFilters: {}, onFilterChange: noop, onClearAll: noop },
      'workspace/RootView': { workspaces: [workspace], currentWorkspaceId: workspace.id },
      'workspace/WorkspaceView': { workspace, domainPacks: [pack], papers: [paper], paperImports: [pending] },
      'workspace/DomainPackView': { domainPack: pack, papers: [paper], paperImports: [pending], subdomains: ['fixture_area'] },
      'workspace/SubdomainView': { domainPack: pack, subdomainId: 'fixture_area', papers: [paper], metrics: [metric] },
      'workspace/MetricsView': { domainPack: pack, mode: 'registry' },
      'workspace/MetricView': { metric, domainPack: pack, papers: [paper], cellData: new Map([[`${paper.id}:${metric.full_name}`, cell]]) },
      'workspace/PaperPreviewView': { paperImport: pending }, 'workspace/PaperStatusModal': { paperImport: pending },
      'workspace/CreateWorkspaceModal': { onCreateWorkspace: noop }, 'workspace/AddDomainPackModal': { onAddDomainPack: noop },
      'workspace/WorkspaceMembersModal': { workspaceId: workspace.id, workspaceName: workspace.name, canManage: true },
      'evidence/EvidenceInspector': { evidenceList: [evidence], onVerify: noop, onCorrect: noop, onReject: noop, onBatchOperation: noop, contextLabel: paper.title, status: 'pending' },
      'evidence/EvidenceEditor': { evidence, onSave: noop }, 'evidence/EvidenceHistory': { evidence, onRestore: noop },
      'evidence/EvidenceReviewQueue': { evidenceList: [evidence], onReview: noop },
      'intent/IntentDeclarationModal': { isOpen: true, onSuccess: noop },
      'intent/IntentMetadataForm': { onSubmit: noop, context: 'conflict_resolution' }, 'intent/IntentProfilePanel': { userId: 'fixture' },
      'intent/IntentBranchSelector': {}, 'settings/LLMSettingsModal': { onChanged: noop }
    };
    const root = createRoot(document.getElementById('root'));
    window.renderLocalePanel = (name, overrides = {}) => {
      const Component = modules[name];
      function Panel() {
        useLanguage();
        return React.createElement(React.Fragment, null,
          React.createElement('div', { id: 'locale-toolbar', style: { position: 'fixed', top: 0, right: 0, zIndex: 100000, background: '#222', padding: 12 } }, React.createElement(LanguageSelector)),
          React.createElement('div', { id: 'locale-surface', style: { paddingTop: 52, height: 1000, color: '#ddd' } }, React.createElement(Component, { ...common, ...props[name], ...overrides })));
      }
      root.render(React.createElement(Panel, { key: name + JSON.stringify(overrides) }));
    };
  });
  const panels = [
    ['GraphView', '图例'], ['MatrixGrid', '论文'], ['CoverageView', '研究覆盖与候选空白'],
    ['domain/DomainPackPanel', '领域规则设置'], ['workspace/RootView', '我的工作区'], ['workspace/WorkspaceView', '待处理论文'],
    ['workspace/DomainPackView', '上传论文 PDF'], ['workspace/SubdomainView', '分类对应关系'],
    ['workspace/MetricsView', '提取指标列表'], ['workspace/MetricView', '指标定义'],
    ['workspace/PaperPreviewView', '提取完成，请检查后入库'], ['workspace/PaperStatusModal', '提取结果'],
    ['workspace/CreateWorkspaceModal', '工作区名称'], ['workspace/AddDomainPackModal', '导入已有规则'],
    ['workspace/WorkspaceMembersModal', '工作区成员与权限'], ['evidence/EvidenceInspector', '全部证据'],
    ['evidence/EvidenceEditor', '修改提取内容'], ['evidence/EvidenceHistory', '修改记录'], ['evidence/EvidenceReviewQueue', '待复核证据'],
    ['intent/IntentDeclarationModal', '设置研究目标'], ['intent/IntentMetadataForm', '记录研究决策'],
    ['intent/IntentProfilePanel', '研究决策总数'], ['intent/IntentBranchSelector', '全部研究内容'], ['settings/LLMSettingsModal', '模型接口设置']
  ];
  const failures = [];
  const headingKeys = {
    GraphView: 'Legend', MatrixGrid: 'Paper', CoverageView: 'Coverage Analysis',
    'domain/DomainPackPanel': 'Domain Pack Configuration', 'workspace/RootView': 'Workspaces',
    'workspace/WorkspaceView': 'Pending Imports', 'workspace/DomainPackView': '上传论文 PDF',
    'workspace/SubdomainView': 'Taxonomy Mapping', 'workspace/MetricsView': 'Metric Registry',
    'workspace/MetricView': 'Definition', 'workspace/PaperPreviewView': 'Preview ready',
    'workspace/PaperStatusModal': 'Extracted Content', 'workspace/CreateWorkspaceModal': 'Workspace name',
    'workspace/AddDomainPackModal': '📁 Upload File', 'workspace/WorkspaceMembersModal': 'Workspace Access',
    'evidence/EvidenceInspector': '📋 All Evidence (', 'evidence/EvidenceEditor': 'Edit Text',
    'evidence/EvidenceHistory': 'Revision History:', 'evidence/EvidenceReviewQueue': '🔍 Review Queue',
    'intent/IntentDeclarationModal': 'Declare Research Intent', 'intent/IntentMetadataForm': 'Capture Intent',
    'intent/IntentProfilePanel': 'Total Intents:', 'intent/IntentBranchSelector': 'No Active Context',
    'settings/LLMSettingsModal': '模型接口设置'
  };
  await mkdir('demo-screenshots/language', { recursive: true });
  for (const [name, expected] of panels) {
    console.log(`Checking ${name}`);
    await page.evaluate(name => window.renderLocalePanel(name), name);
    await page.getByText(expected, { exact: false }).first().waitFor();
    await page.waitForTimeout(120);
    // Content and technical identifiers deliberately retain their source language.
    const english = await page.evaluate(() => {
      const walker = document.createTreeWalker(document.getElementById('locale-surface'), NodeFilter.SHOW_TEXT);
      const unexpected = [];
      while (walker.nextNode()) {
        const node = walker.currentNode;
        if (!node.parentElement?.checkVisibility() || node.parentElement.closest('pre,textarea,script,style,input')) continue;
        const text = node.textContent.replace(/Original paper title stays English|Original source evidence stays English\.|Fixture Author|Fixture Venue|fixture_\w+|fixture (?:metric|area)|fixture\.pdf|domain\.test|\btest\b|\/chat\/completions|\/messages|\b(?:PDF|JSON|YAML|API|Ollama|DPAPI|Windows|KB|MB|ms|c01|v\d*|A-Z)\b/gi, '').trim();
        if (/[A-Za-z]{2}/.test(text)) unexpected.push(text);
      }
      return unexpected;
    });
    if (english.length) failures.push({ name, english });
    // Modal dialogs put themselves in the top layer, so use keyboard-independent
    // selection events rather than pointer clicks on the background toolbar.
    const selector = page.getByRole('combobox', { name: '语言 / Language' });
    await selector.selectOption('en');
    const translatedHeading = translations[headingKeys[name]];
    assert.ok(translatedHeading, `Missing English expectation for ${name}`);
    await page.getByText(translatedHeading[1], { exact: false }).first().waitFor();
    await selector.selectOption('zh-CN');
    await page.getByText(expected, { exact: false }).first().waitFor();
    if (name === 'workspace/PaperPreviewView') {
      await page.getByText('Original paper title stays English', { exact: true }).first().waitFor();
    }
    if (name === 'evidence/EvidenceInspector') {
      await page.getByText('Original source evidence stays English.', { exact: true }).first().waitFor();
      await page.screenshot({ path: 'demo-screenshots/language/zh-evidence.png' });
    }
  }
  assert.deepEqual(failures, [], JSON.stringify(failures, null, 2));
  // A changed selection must still submit the original protocol value.
  await page.evaluate(() => window.renderLocalePanel('intent/IntentDeclarationModal'));
  await page.locator('#intent-message').fill('Original user input stays English');
  assert.equal(await page.locator('#intent-message').inputValue(), 'Original user input stays English');
  await page.evaluate(() => window.renderLocalePanel('workspace/MetricsView', { mode: 'add' }));
  await page.getByRole('option', { name: '整数', exact: true }).waitFor({ state: 'attached' });
  const types = page.locator('select').filter({ has: page.getByRole('option', { name: '整数', exact: true }) });
  await types.selectOption('int');
  assert.equal(await types.inputValue(), 'int');
  assert.deepEqual(runtimeErrors, []);
  await page.screenshot({ path: 'demo-screenshots/language/zh-metric-form.png' });
  await page.evaluate(() => window.renderLocalePanel('workspace/MetricView'));
  const confirmation = page.waitForEvent('dialog').then(async dialog => {
    assert.ok(dialog.message().startsWith('确定删除指标“fixture_metric”吗？'));
    await dialog.dismiss();
  });
  await Promise.all([confirmation, page.getByRole('button', { name: '删除指标', exact: true }).click()]);
  console.log(`PASS: ${panels.length} populated panels, bilingual switching, no unexplained English UI text, preserved source text and enum values. No research data was created.`);
} finally {
  await browser.close();
}

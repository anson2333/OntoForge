import { useSyncExternalStore } from 'react';

import messages from './locales/ui.json';
const catalog: Record<string, readonly string[]> = messages;
export type Language = 'zh-CN' | 'en';
const storageKey = 'ontoforge-language';
let language: Language = localStorage.getItem(storageKey) === 'en' ? 'en' : 'zh-CN';
const listeners = new Set<() => void>();
function subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
function update(next: Language) {
  language = next;
  document.documentElement.lang = next;
  listeners.forEach(listener => listener());
}
document.documentElement.lang = language;
window.addEventListener('storage', event => {
  if (event.key === storageKey) update(event.newValue === 'en' ? 'en' : 'zh-CN');
});
export function t(key: string, values: Record<string, string | number> = {}): string {
  const text = catalog[key]?.[language === 'en' ? 1 : 0] ?? key;
  return text.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : placeholder);
}
export function getLocale(): Language { return language; }
const stockDomainNames = new Set(['Historical object detection (cutoff 2016-06-30)', 'Optical Networks', 'Wireless Networks', '目标检测：准确率与推理速度']);
export function domainTitle(name: string): string { return stockDomainNames.has(name) ? t(name) : name; }
// Only use this for application enums, never for paper titles or evidence text.
const enumLabels: Record<string, string> = {
  active: 'Active', archived: 'Archived', completed: 'Completed', paused: 'Paused',
  pending: 'Pending', resolved: 'Verified', verified: 'Verified', raw: 'Raw',
  conflict: 'Conflict!', unresolved: 'Pending', locked: 'Locked',
  under_correction: 'Editing', pending_verification: 'Pending Review', rejected: 'Rejected',
  queued: 'Queued', validating: 'Preparing Preview', preview_ready: 'Preview Ready',
  ingesting: 'Committing', ingested: 'Ingested', error: 'Error', under_review: 'Pending Review',
  workspace: 'Workspace', domain: 'Domain Pack', subdomain: 'Subdomain', paper: 'Paper', assertion: 'Assertion',
  chunk: 'Chunk', formula: 'Formula', owner: 'Owner', editor: 'Editor', viewer: 'Viewer',
  correction: 'Correction', preference: 'Preference', priority: 'Priority', constraint: 'Constraint', goal: 'Goal',
  local: 'Local', pattern: 'Pattern', global: 'Global', float: 'Float', int: 'Integer', string: 'String', bool: 'Boolean',
  metrics: 'Metrics', taxonomy: 'Domain Taxonomy', validation: 'Validation Rules', raw_config: 'Raw Configuration',
  method: 'Method', scenario: 'Scenario', unspecified: 'Unspecified',
  contains: 'Includes', has_domain: 'Includes', has_subdomain: 'Classified as', evidenced_by: 'Supported by',
  typo: 'Typo', unit_error: 'Unit error', extraction_error: 'Extraction error', context_missing: 'Missing context',
  ocr_error: 'OCR error', numeric_correction: 'Numeric correction', formula_fix: 'Formula fix',
  unit_correction: 'Unit correction', formatting_fix: 'Formatting fix', missing_text: 'Missing text',
};
export function uiLabel(value: string): string { return t(enumLabels[value] ?? value); }
const diagnosticSentences = [
  'Page-only source locations; precise PDF bounding boxes are unavailable.',
  'Parsing used raw_text fallback instead of PDF bytes.',
  'No text chunks were extracted from the PDF.',
  'No backend domain-pack config was resolved for assertion grounding; preview includes metadata, markdown, and chunks only.',
  'No domain-grounded assertions were extracted from the parsed chunks.',
  'LLM extraction was unavailable; assertions were produced by the rule-based heuristic extractor.',
  'Simulated mock-provider assertions; this is not a real LLM extraction.',
  'Marker 1.10+ did not extract text chunks from markdown.',
  'Marker did not return any text-like blocks for this PDF.',
  'Re-upload the PDF if its temporary upload expired.',
];
/** Translate application diagnostics while leaving source evidence untouched. */
export function localizeMessage(message: string): string {
  if (catalog[message]) return t(message);
  // Feedback may have been stored in state before the language changed.
  const existing = Object.entries(catalog).find(([, translations]) => translations.includes(message));
  if (existing) return t(existing[0]);
  let result = message;
  for (const sentence of diagnosticSentences) result = result.split(sentence).join(t(sentence));
  result = result.replace(/Rejected ([\w:]+): (missing evidence|unknown evidence ID|unsupported predicate|low confidence|incompatible unit \(conversion is not implicit\)|invalid numeric value|reported value absent from cited evidence|excluded result role|detector family does not match document|excluded ensemble or comparison result|value outside configured range)/g, (_match, metric: string, reason: string) =>
    t('Metric result excluded: {metric} — {reason}', { metric, reason: t(reason.trim()) }));
  result = result.replace(/Page (\d+) did not yield extractable text\./g, (_match, page: string) =>
    t('Page {page} has no extractable text.', { page }));
  result = result.replace(/Metric "([^"]+)" already exists/g, (_match, name: string) => t('Metric {name} already exists.', { name }));
  result = result.replace(/Domain pack "([^"]+)" was not found/g, (_match, name: string) => t('Domain rules {name} were not found.', { name }));
  const prefix = result.match(/^Failed to ([^:]+):\s*([\s\S]*)$/);
  if (prefix) return t('Operation failed: {action}. {detail}', { action: t(prefix[1]), detail: localizeMessage(prefix[2]) });
  return result;
}
export function useLanguage() { return useSyncExternalStore(subscribe, () => language); }
export function LanguageSelector() {
  const value = useLanguage();
  return <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
    <span>语言 / Language</span>
    <select aria-label="语言 / Language" value={value} onChange={event => {
      const next = event.target.value as Language;
      localStorage.setItem(storageKey, next);
      update(next);
    }} style={{ padding: '6px 8px', color: 'var(--text-primary)', background: 'var(--surface-bg)', border: '1px solid var(--border-strong)', borderRadius: 4 }}>
      <option value="zh-CN">简体中文</option><option value="en">English</option>
    </select>
  </label>;
}

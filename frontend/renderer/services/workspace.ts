/**
 * Workspace State Management
 * Manages workspace, multiple domain packs, papers, metrics, matrix data, and intent context
 * Enhanced for multi-domain-pack architecture (Section 2.0)
 */

import { create } from 'zustand';
import { IntentBranch, UserIntentProfile, IntentPattern } from './intent_service';
import { DomainPackConfig } from '../components/domain';
import { sspClient } from './ssp_client';

export interface WorkspaceInfo {
  id: string;
  name: string;
  description?: string;
  root: string;
  created_at: string;
  last_modified_at?: string;
  status: 'active' | 'archived' | 'readonly';
  owner_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface CreateWorkspaceInput {
  name: string;
  description?: string;
  root?: string;
}

export interface LoadedDomainPack {
  namespace: string;
  config: DomainPackConfig;
  enabled: boolean;
  metrics: Metric[];  // Cached metrics for this domain pack
}

export interface Paper {
  id: string;
  doi: string;
  title: string;
  authors: string[];
  year: number;
  venue: string;
  domain_pack_namespace?: string;  // Which domain pack this paper belongs to
  ingestion_status: 'ingested' | 'error';
  paper_source?: 'backend';
  file_name?: string;
  ingested_at?: string;  // ISO timestamp of when paper was ingested
}

export interface PaperImportPreview {
  title: string;
  authors: string[];
  year: number;
  venue: string;
  chunk_count: number;
  formula_count: number;
  assertion_count: number;
  evidence_count: number;
}

export interface PaperImportEntry {
  id: string;
  workspace_id: string;
  domain_pack_namespace: string;
  source: 'drop' | 'file_picker';
  file_name: string;
  file_size: number;
  file_last_modified: number;
  title: string;
  created_at: string;
  status: 'queued' | 'validating' | 'preview_ready' | 'ingesting' | 'error';
  upload_id?: string;
  warning?: string;
  error_message?: string;
  markdown_text?: string;
  preview?: PaperImportPreview;
  local_file?: File;
}

export interface Metric {
  name: string;  // Base name without namespace
  full_name: string;  // Namespaced name (e.g., "optical:reconfiguration_delay")
  namespace: string;  // Domain pack namespace
  unit: string;
  aliases: string[];
  value_type?: 'float' | 'int' | 'string' | 'bool';
}

export interface MetricInput {
  name: string;
  expected_unit: string;
  aliases: string[];
  value_type: 'float' | 'int' | 'string' | 'bool';
}

export interface CellData {
  paperId: string;
  metricName: string;
  value: string | null;
  unit: string | null;
  status: 'pending' | 'resolved' | 'conflict' | 'locked';
  confidence: number;
  evidenceCount: number;
}

export interface SelectedSubdomain {
  namespace: string;
  id: string;
}

export interface Evidence {
  type: 'chunk' | 'formula';
  id: string;
  text: string;
  confidence: number;
  boundingBox?: {
    page: number;
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

interface WorkspaceState {
  // Workspace info
  workspaces: WorkspaceInfo[];
  workspace: WorkspaceInfo | null;
  currentOwnerId: string;
  currentWorkspaceId: string;  // Current workspace for data isolation
  
  // Multi-domain-pack state (Section 2.0)
  domainPacks: LoadedDomainPack[];  // Array of loaded domain packs
  activeDomainPackNamespaces: string[];  // Active domain packs for matrix filtering
  
  // Papers and data
  papers: Paper[];
  paperImports: PaperImportEntry[];
  selectedRootView: boolean;
  selectedWorkspaceViewId: string | null;
  selectedDomainPackNamespace: string | null;
  selectedPaperId: string | null;
  selectedPaperImportId: string | null;  // Selected import in any lifecycle state
  selectedMetricsNamespace: string | null;
  selectedMetricsMode: 'registry' | 'add';
  selectedMetricFullName: string | null;
  selectedSubdomain: SelectedSubdomain | null;
  metrics: Metric[];  // Combined metrics from all active domain packs
  allCellData: Map<string, CellData>;
  cellData: Map<string, CellData>;
  isLoading: boolean;
  
  // Intent Framework State (Section 2.6)
  activeIntentBranch: IntentBranch | null;
  userIntentProfile: UserIntentProfile | null;
  learnedPatterns: IntentPattern[];
  confidenceThreshold: number;
  
  // Actions
  loadWorkspaces: () => Promise<void>;
  loadWorkspace: (workspaceId: string) => Promise<void>;
  switchWorkspace: (workspaceId: string) => Promise<void>;
  createWorkspace: (input: CreateWorkspaceInput) => Promise<WorkspaceInfo>;
  deleteWorkspace: (workspaceId: string) => Promise<void>;
  refreshData: () => Promise<void>;
  enqueuePaperImports: (namespace: string, files: File[], source: 'drop' | 'file_picker') => void;
  retryPaperImport: (paperImportId: string) => void;
  commitPaperImport: (paperImportId: string) => Promise<void>;
  removePaperImport: (paperImportId: string) => void;
  removePaper: (paperId: string) => void;
  selectRoot: () => void;
  selectWorkspaceView: (workspaceId: string | null) => void;
  selectDomainPack: (namespace: string | null) => void;
  selectPaper: (paperId: string | null) => void;
  selectPaperImport: (paperImportId: string | null) => void;
  selectMetrics: (namespace: string | null, mode?: 'registry' | 'add') => void;
  selectMetric: (metricFullName: string | null) => void;
  selectSubdomain: (subdomain: SelectedSubdomain | null) => void;
  addMetric: (namespace: string, metric: MetricInput) => void;
  updateMetric: (namespace: string, originalName: string, metric: MetricInput) => void;
  deleteMetric: (namespace: string, metricName: string) => void;
  getCellData: (paperId: string, metricName: string) => CellData | null;
  getEvidence: (paperId: string, metricName: string) => Promise<Evidence[]>;
  
  // Domain Pack Actions
  addDomainPack: (namespace: string, config: DomainPackConfig | string) => Promise<void>;
  removeDomainPack: (namespace: string) => void;
  setActiveDomainPacks: (namespaces: string[]) => void;
  getDomainPack: (namespace: string) => LoadedDomainPack | null;
  
  // Intent Actions
  setActiveIntentBranch: (branch: IntentBranch | null) => void;
  setUserIntentProfile: (profile: UserIntentProfile) => void;
  setLearnedPatterns: (patterns: IntentPattern[]) => void;
  setConfidenceThreshold: (threshold: number) => void;
}

// Local workspace metadata until the backend exposes workspace/domain-pack endpoints
const MOCK_WORKSPACE: WorkspaceInfo = {
  id: 'workspace_5g_backhaul_2026',
  name: '5G Backhaul Comparison Study',
  description: 'Comparing optical and wireless backhaul technologies for 5G networks',
  root: 'file:///Users/scholar/research/5g_backhaul_study',
  created_at: '2026-05-24T00:00:00Z',
  status: 'active',
  owner_id: 'local-dev-user'
};

const DEFAULT_OWNER_ID = 'local-dev-user';
const PAPER_REGISTRY_STORAGE_KEY = 'ontoforge-paper-registry-v1';
const DOMAIN_PACK_REGISTRY_KEY = 'ontoforge-domain-pack-registry-v1';
const PAPER_INGESTION_TIMESTAMPS_KEY = 'ontoforge-paper-ingestion-timestamps-v1';
const BOOTSTRAPPED_DOMAIN_PACKS_KEY = 'ontoforge-bootstrapped-domain-packs-v1';

interface PaperRegistryState {
  paperImportsByWorkspace: Record<string, PaperImportEntry[]>;
  removedPaperIdsByWorkspace: Record<string, string[]>;
}

interface DomainPackRegistryState {
  explicitDomainPacksByWorkspace: Record<string, string[]>; // workspace_id -> namespace[]
}

interface BootstrappedDomainPacksState {
  configsByNamespace: Record<string, DomainPackConfig>; // namespace -> config
}

function loadPaperRegistryState(): PaperRegistryState {
  if (typeof window === 'undefined') {
    return { paperImportsByWorkspace: {}, removedPaperIdsByWorkspace: {} };
  }

  try {
    const raw = window.localStorage.getItem(PAPER_REGISTRY_STORAGE_KEY);
    if (!raw) {
      return { paperImportsByWorkspace: {}, removedPaperIdsByWorkspace: {} };
    }
    const parsed = JSON.parse(raw) as PaperRegistryState;
    return {
      paperImportsByWorkspace: parsed.paperImportsByWorkspace || {},
      removedPaperIdsByWorkspace: parsed.removedPaperIdsByWorkspace || {},
    };
  } catch (error) {
    console.warn('Failed to load paper registry state:', error);
    return { paperImportsByWorkspace: {}, removedPaperIdsByWorkspace: {} };
  }
}

function persistPaperRegistryState(state: PaperRegistryState): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(PAPER_REGISTRY_STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn('Failed to persist paper registry state:', error);
  }
}

function loadDomainPackRegistryState(): DomainPackRegistryState {
  if (typeof window === 'undefined') {
    return { explicitDomainPacksByWorkspace: {} };
  }

  try {
    const raw = window.localStorage.getItem(DOMAIN_PACK_REGISTRY_KEY);
    if (!raw) {
      return { explicitDomainPacksByWorkspace: {} };
    }
    const parsed = JSON.parse(raw) as DomainPackRegistryState;
    return {
      explicitDomainPacksByWorkspace: parsed.explicitDomainPacksByWorkspace || {}
    };
  } catch (error) {
    console.warn('Failed to load domain pack registry state:', error);
    return { explicitDomainPacksByWorkspace: {} };
  }
}

function persistDomainPackRegistryState(state: DomainPackRegistryState): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(DOMAIN_PACK_REGISTRY_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn('Failed to persist domain pack registry state:', error);
  }
}

function updateDomainPackRegistryState(mutator: (current: DomainPackRegistryState) => DomainPackRegistryState): DomainPackRegistryState {
  const current = loadDomainPackRegistryState();
  const updated = mutator(current);
  persistDomainPackRegistryState(updated);
  return updated;
}

// === Paper Ingestion Timestamps ===
function loadPaperIngestionTimestamps(): Record<string, string> {
  if (typeof window === 'undefined') {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(PAPER_INGESTION_TIMESTAMPS_KEY);
    if (!raw) {
      return {};
    }
    return JSON.parse(raw) as Record<string, string>;
  } catch (error) {
    console.warn('Failed to load paper ingestion timestamps:', error);
    return {};
  }
}

function setPaperIngestionTimestamp(paperId: string, timestamp: string): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    const timestamps = loadPaperIngestionTimestamps();
    timestamps[paperId] = timestamp;
    window.localStorage.setItem(PAPER_INGESTION_TIMESTAMPS_KEY, JSON.stringify(timestamps));
  } catch (error) {
    console.warn('Failed to persist paper ingestion timestamp:', error);
  }
}

// === Bootstrapped Domain Packs ===
function loadBootstrappedDomainPacks(): BootstrappedDomainPacksState {
  if (typeof window === 'undefined') {
    return { configsByNamespace: {} };
  }

  try {
    const raw = window.localStorage.getItem(BOOTSTRAPPED_DOMAIN_PACKS_KEY);
    if (!raw) {
      return { configsByNamespace: {} };
    }
    return JSON.parse(raw) as BootstrappedDomainPacksState;
  } catch (error) {
    console.warn('Failed to load bootstrapped domain packs:', error);
    return { configsByNamespace: {} };
  }
}

function persistBootstrappedDomainPacks(state: BootstrappedDomainPacksState): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(BOOTSTRAPPED_DOMAIN_PACKS_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn('Failed to persist bootstrapped domain packs:', error);
  }
}

function saveBootstrappedDomainPack(namespace: string, config: DomainPackConfig): void {
  const state = loadBootstrappedDomainPacks();
  state.configsByNamespace[namespace] = config;
  persistBootstrappedDomainPacks(state);
}

function removeBootstrappedDomainPack(namespace: string): void {
  const state = loadBootstrappedDomainPacks();
  delete state.configsByNamespace[namespace];
  persistBootstrappedDomainPacks(state);
}

function metricDefinitionToMetric(namespace: string, metric: MetricInput): Metric {
  return {
    name: metric.name,
    full_name: `${namespace}:${metric.name}`,
    namespace,
    unit: metric.expected_unit,
    aliases: metric.aliases || [],
    value_type: metric.value_type
  };
}

function updateDomainPackMetricDefinitions(
  pack: LoadedDomainPack,
  coreMetrics: MetricInput[]
): LoadedDomainPack {
  const config: DomainPackConfig = {
    ...pack.config,
    core_metrics: coreMetrics.map(metric => ({
      name: metric.name,
      expected_unit: metric.expected_unit,
      aliases: metric.aliases || [],
      value_type: metric.value_type
    }))
  };

  return {
    ...pack,
    config,
    metrics: config.core_metrics.map(metric => metricDefinitionToMetric(pack.namespace, metric))
  };
}

function normalizeMetricName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function slugifyPaperLabel(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\.pdf$/i, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'paper';
}

function inferPaperTitle(fileName: string): string {
  return fileName
    .replace(/\.pdf$/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeBackendPapers(papers: Paper[]): Paper[] {
  return papers.map(paper => ({
    ...paper,
    ingestion_status: 'ingested',
    paper_source: 'backend'
  }));
}

function getWorkspacePaperImports(workspaceId: string): PaperImportEntry[] {
  const registry = loadPaperRegistryState();
  return (registry.paperImportsByWorkspace[workspaceId] || []).map(entry => {
    if (!entry.local_file && (entry.status === 'queued' || entry.status === 'validating' || entry.status === 'ingesting')) {
      return {
        ...entry,
        status: 'error',
        error_message: 'Import interrupted: File reference lost (app was restarted or file handle expired). Please drop the PDF again to retry ingestion.'
      };
    }
    return entry;
  });
}

function mergeWorkspacePapers(workspaceId: string, backendPapers: Paper[]): Paper[] {
  const registry = loadPaperRegistryState();
  const removedIds = new Set(registry.removedPaperIdsByWorkspace[workspaceId] || []);
  const timestamps = loadPaperIngestionTimestamps();
  const normalizedBackend = normalizeBackendPapers(backendPapers)
    .filter(paper => !removedIds.has(paper.id))
    .map(paper => ({
      ...paper,
      ingested_at: timestamps[paper.id] || paper.ingested_at
    }));
  return normalizedBackend;
}

function updatePaperRegistryState(mutator: (current: PaperRegistryState) => PaperRegistryState): PaperRegistryState {
  const next = mutator(loadPaperRegistryState());
  persistPaperRegistryState(next);
  return next;
}

function persistWorkspacePaperImports(workspaceId: string, paperImports: PaperImportEntry[]): void {
  updatePaperRegistryState(current => ({
    ...current,
    paperImportsByWorkspace: {
      ...current.paperImportsByWorkspace,
      [workspaceId]: paperImports.map(({ local_file, ...entry }) => entry)
    }
  }));
}

function extractYearFromLabel(value: string): number | undefined {
  const match = value.match(/(19|20)\d{2}/);
  if (!match) {
    return undefined;
  }
  return Number.parseInt(match[0], 10);
}

function buildImportPreviewFromBackend(result: any, fileName: string): PaperImportPreview {
  const metadata = result?.paper_metadata || {};
  const chunks = Array.isArray(result?.chunks) ? result.chunks : [];
  const formulas = Array.isArray(result?.formulas) ? result.formulas : [];
  const assertions = Array.isArray(result?.assertions) ? result.assertions : [];
  const inferredYear = typeof metadata.year === 'number'
    ? metadata.year
    : extractYearFromLabel(fileName) || new Date().getFullYear();
  const evidenceCount = assertions.reduce((total: number, assertion: any) => {
    const links = Array.isArray(assertion?.evidence_links) ? assertion.evidence_links.length : 0;
    return total + links;
  }, 0);

  return {
    title: metadata.title || inferPaperTitle(fileName) || fileName,
    authors: Array.isArray(metadata.authors) && metadata.authors.length > 0 ? metadata.authors : ['Unknown authors'],
    year: inferredYear,
    venue: metadata.venue || 'Unknown venue',
    chunk_count: chunks.length,
    formula_count: formulas.length,
    assertion_count: assertions.length,
    evidence_count: evidenceCount
  };
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== 'string') {
        reject(new Error('Failed to read PDF payload.'));
        return;
      }
      const [, base64Payload = ''] = result.split(',', 2);
      resolve(base64Payload);
    };
    reader.onerror = () => {
      reject(reader.error || new Error('Failed to read PDF payload.'));
    };
    reader.readAsDataURL(file);
  });
}

function createPaperImportEntry(
  workspaceId: string,
  namespace: string,
  file: File,
  source: 'drop' | 'file_picker',
  index: number
): PaperImportEntry {
  const title = inferPaperTitle(file.name);
  const slug = slugifyPaperLabel(file.name);
  const now = Date.now();
  return {
    id: `paper_import_${workspaceId}_${namespace}_${slug}_${now}_${index}`,
    workspace_id: workspaceId,
    domain_pack_namespace: namespace,
    source,
    file_name: file.name,
    file_size: file.size,
    file_last_modified: file.lastModified,
    title: title || file.name,
    created_at: new Date(now).toISOString(),
    status: 'queued',
    local_file: file,
  };
}

// Load all available domain packs (mock + bootstrapped)
function createMockDomainPacks(): LoadedDomainPack[] {
  // Load bootstrapped configs from localStorage
  const bootstrappedState = loadBootstrappedDomainPacks();
  const bootstrappedPacks: LoadedDomainPack[] = Object.entries(bootstrappedState.configsByNamespace).map(([namespace, config]) => {
    const metrics = config.core_metrics.map(m => ({
      name: m.name,
      full_name: `${namespace}:${m.name}`,
      namespace: namespace,
      unit: m.expected_unit,
      aliases: m.aliases || [],
      value_type: m.value_type
    }));
    
    return {
      namespace,
      config,
      enabled: true,
      metrics
    };
  });
  
  // Create mock hardcoded packs
  const opticalConfig: DomainPackConfig = {
    schema_version: '1.0',
    domain: {
      id: 'domain.networking.optical',
      name: 'Optical Access Networks',
      taxonomy_tree: [
        {
          name: 'topology',
          values: ['mesh', 'ring', 'star', 'free_space'],
          subdomain_map: {
            'free_space': 'domain.networking.optical.fso',
            'mesh': 'domain.networking.optical.access'
          },
          description: 'Network topology types'
        },
        {
          name: 'switching_mechanism',
          values: ['wdm', 'optical_packet', 'burst_switching'],
          subdomain_map: {
            'wdm': 'domain.networking.optical.wdm',
            'optical_packet': 'domain.networking.optical.ops'
          },
          description: 'Switching technologies'
        }
      ]
    },
    core_metrics: [
      {
        name: 'reconfiguration_delay',
        expected_unit: 'ms',
        aliases: ['switching_delay', 'matrix_latency'],
        value_type: 'float'
      },
      {
        name: 'cross_talk',
        expected_unit: 'dB',
        aliases: ['crosstalk', 'channel_isolation'],
        value_type: 'float'
      },
      {
        name: 'insertion_loss',
        expected_unit: 'dB',
        aliases: ['optical_loss'],
        value_type: 'float'
      },
      {
        name: 'power_consumption',
        expected_unit: 'W',
        aliases: ['energy_consumption'],
        value_type: 'float'
      }
    ],
    validation: {
      required_context_keys: ['network_load', 'topology'],
      unit_normalization: {
        'ms': ['ms', 'millisecond'],
        'dB': ['dB', 'db'],
        'W': ['W', 'watt']
      }
    }
  };

  const wirelessConfig: DomainPackConfig = {
    schema_version: '1.0',
    domain: {
      id: 'domain.networking.wireless',
      name: 'Wireless Communications',
      taxonomy_tree: [
        {
          name: 'frequency_band',
          values: ['mmWave', 'sub_6ghz', 'terahertz'],
          subdomain_map: {
            'mmWave': 'domain.networking.wireless.mmwave',
            'sub_6ghz': 'domain.networking.wireless.sub6'
          },
          description: 'Frequency bands'
        }
      ]
    },
    core_metrics: [
      {
        name: 'throughput',
        expected_unit: 'Gbps',
        aliases: ['data_rate', 'bandwidth'],
        value_type: 'float'
      },
      {
        name: 'latency',
        expected_unit: 'ms',
        aliases: ['delay', 'response_time'],
        value_type: 'float'
      },
      {
        name: 'coverage_radius',
        expected_unit: 'km',
        aliases: ['range', 'reach'],
        value_type: 'float'
      },
      {
        name: 'energy_efficiency',
        expected_unit: 'bits/J',
        aliases: ['power_efficiency'],
        value_type: 'float'
      }
    ],
    validation: {
      required_context_keys: ['frequency', 'antenna_config'],
      unit_normalization: {
        'Gbps': ['Gbps', 'Gbit/s'],
        'ms': ['ms', 'millisecond'],
        'km': ['km', 'kilometer']
      }
    }
  };

  const opticalMetrics: Metric[] = opticalConfig.core_metrics.map(m => ({
    name: m.name,
    full_name: `optical:${m.name}`,
    namespace: 'optical',
    unit: m.expected_unit,
    aliases: m.aliases,
    value_type: m.value_type
  }));

  const wirelessMetrics: Metric[] = wirelessConfig.core_metrics.map(m => ({
    name: m.name,
    full_name: `wireless:${m.name}`,
    namespace: 'wireless',
    unit: m.expected_unit,
    aliases: m.aliases,
    value_type: m.value_type
  }));

  const mockPacks = [
    {
      namespace: 'optical',
      config: opticalConfig,
      enabled: true,
      metrics: opticalMetrics
    },
    {
      namespace: 'wireless',
      config: wirelessConfig,
      enabled: true,
      metrics: wirelessMetrics
    }
  ];
  
  // Combine bootstrapped and mock packs, prioritizing bootstrapped
  const allPacks = [...bootstrappedPacks];
  const bootstrappedNamespaces = new Set(bootstrappedPacks.map(p => p.namespace));
  
  // Add mock packs only if they haven't been bootstrapped
  for (const pack of mockPacks) {
    if (!bootstrappedNamespaces.has(pack.namespace)) {
      allPacks.push(pack);
    }
  }
  
  return allPacks;
}

async function fetchCellDataFromBackend(): Promise<Map<string, CellData>> {
  const { currentWorkspaceId, currentOwnerId } = useWorkspaceStore.getState();
  return fetchCellDataForWorkspace(currentWorkspaceId, currentOwnerId);
}

async function fetchCellDataForWorkspace(
  workspaceId: string,
  ownerId: string
): Promise<Map<string, CellData>> {
  // Fetch assertions from backend and convert to cellData format
  const cellData = new Map<string, CellData>();
  
  try {
    const response = await sspClient.getAssertions({ workspace_id: workspaceId, owner_id: ownerId });
    if (response && response.assertions) {
      response.assertions.forEach((assertion: any) => {
        const key = `${assertion.paperId}:${assertion.metricName}`;
        cellData.set(key, {
          paperId: assertion.paperId,
          metricName: assertion.metricName,
          value: assertion.value,
          unit: assertion.unit,
          status: assertion.status,
          confidence: assertion.confidence,
          evidenceCount: assertion.evidenceCount
        });
      });
      console.log(`✅ Loaded ${cellData.size} assertions from database`);
    }
  } catch (error) {
    console.warn('Failed to fetch assertions from backend:', error);
  }
  
  return cellData;
}

function deriveWorkspaceDomainPacks(papers: Paper[], paperImports: PaperImportEntry[], workspaceId: string): {
  domainPacks: LoadedDomainPack[];
  activeNamespaces: string[];
  metrics: Metric[];
} {
  const availablePacks = createMockDomainPacks();
  
  // Get explicitly added domain packs for this workspace
  const registry = loadDomainPackRegistryState();
  const explicitNamespaces = registry.explicitDomainPacksByWorkspace[workspaceId] || [];
  
  // Get namespaces from papers and imports (implicit)
  const implicitNamespaces = Array.from(
    new Set(
      [
        ...papers.map(paper => paper.domain_pack_namespace),
        ...paperImports.map(entry => entry.domain_pack_namespace)
      ].filter((namespace): namespace is string => Boolean(namespace))
    )
  );
  
  // Combine explicit and implicit namespaces
  const namespaces = Array.from(new Set([...explicitNamespaces, ...implicitNamespaces]));

  const domainPacks = availablePacks.filter(pack => namespaces.includes(pack.namespace));
  const activeNamespaces = domainPacks.map(pack => pack.namespace);
  const metrics = combineMetrics(domainPacks, activeNamespaces);

  return { domainPacks, activeNamespaces, metrics };
}

function filterCellData(
  cellData: Map<string, CellData>,
  papers: Paper[],
  metrics: Metric[]
): Map<string, CellData> {
  const visiblePaperIds = new Set(papers.map(paper => paper.id));
  const visibleMetricNames = new Set(metrics.map(metric => metric.full_name));
  const filtered = new Map<string, CellData>();

  cellData.forEach((value, key) => {
    if (visiblePaperIds.has(value.paperId) && visibleMetricNames.has(value.metricName)) {
      filtered.set(key, value);
    }
  });

  return filtered;
}

function combineMetrics(domainPacks: LoadedDomainPack[], activeNamespaces: string[]): Metric[] {
  const allMetrics: Metric[] = [];
  
  domainPacks.forEach(pack => {
    if (activeNamespaces.includes(pack.namespace)) {
      allMetrics.push(...pack.metrics);
    }
  });
  
  return allMetrics;
}

// Store implementation
export const useWorkspaceStore = create<WorkspaceState>((set, get) => {
  return {
    // Workspace info
    workspaces: [],
    workspace: MOCK_WORKSPACE,
    currentOwnerId: DEFAULT_OWNER_ID,
    currentWorkspaceId: '550e8400-e29b-41d4-a716-446655440000',  // Default workspace UUID for data isolation
    
    // Multi-domain-pack state
    domainPacks: [],
    activeDomainPackNamespaces: [],
    
    // Papers and data
    papers: [],
    paperImports: [],
    selectedRootView: true,
    selectedWorkspaceViewId: null,
    selectedDomainPackNamespace: null,
    selectedPaperId: null,
    selectedPaperImportId: null,
    selectedMetricsNamespace: null,
    selectedMetricsMode: 'registry',
    selectedMetricFullName: null,
    selectedSubdomain: null,
    metrics: [],
    allCellData: new Map<string, CellData>(),
    cellData: new Map<string, CellData>(),
    isLoading: false,
    
    // Intent State
    activeIntentBranch: null,
    userIntentProfile: null,
    learnedPatterns: [],
    confidenceThreshold: 0.8,

    loadWorkspaces: async () => {
      try {
        const ownerId = get().currentOwnerId;
        const response = await sspClient.listWorkspaces({ owner_id: ownerId });
        const workspaces: WorkspaceInfo[] = response?.workspaces || [];

        if (workspaces.length === 0) {
          set({
            workspaces: [],
            workspace: null,
            papers: [],
            paperImports: [],
            selectedRootView: true,
            selectedWorkspaceViewId: null,
            selectedDomainPackNamespace: null,
            selectedPaperId: null,
            selectedPaperImportId: null,
            selectedMetricsNamespace: null,
            selectedMetricsMode: 'registry',
            selectedMetricFullName: null,
            selectedSubdomain: null,
            allCellData: new Map<string, CellData>(),
            cellData: new Map<string, CellData>()
          });
          return;
        }

        const currentWorkspaceId = get().currentWorkspaceId;
        const activeWorkspace = workspaces.find(workspace => workspace.id === currentWorkspaceId) || workspaces[0];

        set({
          workspaces,
          currentWorkspaceId: activeWorkspace.id,
          workspace: activeWorkspace
        });

        await get().loadWorkspace(activeWorkspace.id);
      } catch (error) {
        console.warn('Failed to load workspaces from backend:', error);
        throw error;
      }
    },
    
    loadWorkspace: async (workspaceId: string) => {
      set({ isLoading: true });
      try {
        const ownerId = get().currentOwnerId;
        let workspaceInfo = get().workspaces.find(workspace => workspace.id === workspaceId) || null;

        try {
          const response = await sspClient.getWorkspace({ workspace_id: workspaceId, owner_id: ownerId });
          if (response?.workspace) {
            workspaceInfo = response.workspace;
          }
        } catch (error) {
          console.warn('Failed to fetch workspace metadata from backend:', error);
        }
        
        // Fetch papers from backend
        let papers: Paper[] = [];
        try {
          const response = await sspClient.getPapers({ workspace_id: workspaceId, owner_id: ownerId });
          if (response && response.papers) {
            papers = mergeWorkspacePapers(workspaceId, response.papers);
          }
        } catch (error) {
          console.warn('Failed to fetch papers from backend:', error);
          papers = mergeWorkspacePapers(workspaceId, []);
        }
        
        const paperImports = getWorkspacePaperImports(workspaceId);
        
        const { domainPacks, activeNamespaces, metrics } = deriveWorkspaceDomainPacks(papers, paperImports, workspaceId);
        
        console.time('[loadWorkspace] fetchCellDataForWorkspace');
        let cellData = new Map<string, CellData>();
        try {
          cellData = await fetchCellDataForWorkspace(workspaceId, ownerId);
        } catch (error) {
          console.warn('Failed to fetch assertions from backend:', error);
        }
        
        set({
          workspaces: workspaceInfo
            ? get().workspaces.map(item => item.id === workspaceInfo!.id ? workspaceInfo! : item)
            : get().workspaces,
          workspace: workspaceInfo || get().workspace || MOCK_WORKSPACE,
          currentWorkspaceId: workspaceId,
          domainPacks,
          activeDomainPackNamespaces: activeNamespaces,
          papers,
          paperImports,
          selectedWorkspaceViewId: get().selectedWorkspaceViewId === workspaceId ? get().selectedWorkspaceViewId : null,
          selectedDomainPackNamespace: domainPacks.some(pack => pack.namespace === get().selectedDomainPackNamespace)
            ? get().selectedDomainPackNamespace
            : null,
          selectedPaperId: papers.some(paper => paper.id === get().selectedPaperId) ? get().selectedPaperId : null,
          selectedPaperImportId: paperImports.some(entry => entry.id === get().selectedPaperImportId) ? get().selectedPaperImportId : null,
          selectedMetricsNamespace: domainPacks.some(pack => pack.namespace === get().selectedMetricsNamespace) ? get().selectedMetricsNamespace : null,
          selectedMetricFullName: metrics.some(metric => metric.full_name === get().selectedMetricFullName) ? get().selectedMetricFullName : null,
          selectedSubdomain: domainPacks.some(pack =>
            pack.namespace === get().selectedSubdomain?.namespace
          ) ? get().selectedSubdomain : null,
          metrics,
          allCellData: cellData,
          cellData: filterCellData(cellData, papers, metrics)
        });
      } finally {
        set({ isLoading: false });
      }
    },

    switchWorkspace: async (workspaceId: string) => {
      await get().loadWorkspace(workspaceId);
    },

    createWorkspace: async (input: CreateWorkspaceInput) => {
      const ownerId = get().currentOwnerId;
      try {
        const response = await sspClient.createWorkspace({
          name: input.name,
          description: input.description,
          root: input.root,
          owner_id: ownerId,
          metadata: { created_via: 'desktop-ui' }
        });

        const workspace: WorkspaceInfo = response.workspace;
        set({ workspaces: [...get().workspaces, workspace] });
        
        await get().loadWorkspace(workspace.id);
        return workspace;
      } catch (error) {
        console.error('[createWorkspace] Backend call failed:', error);
        throw error;
      }
    },

    deleteWorkspace: async (workspaceId: string) => {
      const ownerId = get().currentOwnerId;
      
      try {
        // Call backend to delete workspace
        await sspClient.deleteWorkspace({
          workspace_id: workspaceId,
          owner_id: ownerId
        });
        
        // Remove workspace from local state
        const updatedWorkspaces = get().workspaces.filter(ws => ws.id !== workspaceId);
        set({ workspaces: updatedWorkspaces });
        
        // If the deleted workspace was the current workspace, switch to another one or clear state
        if (get().currentWorkspaceId === workspaceId) {
          if (updatedWorkspaces.length > 0) {
            // Switch to the first available workspace
            await get().loadWorkspace(updatedWorkspaces[0].id);
          } else {
            // No workspaces left, clear the state
            set({
              workspace: null,
              currentWorkspaceId: '',
              domainPacks: [],
              activeDomainPackNamespaces: [],
              papers: [],
              paperImports: [],
              selectedRootView: true,
              selectedWorkspaceViewId: null,
              selectedDomainPackNamespace: null,
              selectedPaperId: null,
              selectedPaperImportId: null,
              selectedMetricsNamespace: null,
              selectedMetricsMode: 'registry',
              selectedMetricFullName: null,
              selectedSubdomain: null,
              metrics: [],
              allCellData: new Map(),
              cellData: new Map()
            });
          }
        }
        
        console.log('[deleteWorkspace] Workspace deleted successfully');
      } catch (error) {
        console.error('[deleteWorkspace] Failed to delete workspace:', error);
        throw error;
      }
    },
    
    refreshData: async () => {
      set({ isLoading: true });
      try {
        let papers: Paper[] = get().papers;
        try {
          const { currentWorkspaceId, currentOwnerId } = get();
          const response = await sspClient.getPapers({ workspace_id: currentWorkspaceId, owner_id: currentOwnerId });
          if (response && response.papers) {
            papers = mergeWorkspacePapers(currentWorkspaceId, response.papers);
            console.log(`✅ Refreshed ${papers.length} papers from database`);
          }
        } catch (error) {
          console.warn('Failed to refresh papers from backend:', error);
          papers = mergeWorkspacePapers(get().currentWorkspaceId, []);
        }
        
        const paperImports = getWorkspacePaperImports(get().currentWorkspaceId);
        
        // Derive domain packs from papers and imports
        const { domainPacks, activeNamespaces, metrics } = deriveWorkspaceDomainPacks(papers, paperImports, get().currentWorkspaceId);
        
        let cellData = new Map<string, CellData>();
        try {
          cellData = await fetchCellDataFromBackend();
        } catch (error) {
          console.warn('Failed to fetch assertions from backend:', error);
        }
        
        set({ 
          papers,
          paperImports,
          domainPacks,
          activeDomainPackNamespaces: activeNamespaces,
          metrics,
          selectedDomainPackNamespace: domainPacks.some(pack => pack.namespace === get().selectedDomainPackNamespace)
            ? get().selectedDomainPackNamespace
            : null,
          selectedPaperId: papers.some(paper => paper.id === get().selectedPaperId) ? get().selectedPaperId : null,
          selectedPaperImportId: paperImports.some(entry => entry.id === get().selectedPaperImportId) ? get().selectedPaperImportId : null,
          selectedMetricsNamespace: domainPacks.some(pack => pack.namespace === get().selectedMetricsNamespace) ? get().selectedMetricsNamespace : null,
          selectedMetricFullName: metrics.some(metric => metric.full_name === get().selectedMetricFullName) ? get().selectedMetricFullName : null,
          selectedSubdomain: domainPacks.some(pack =>
            pack.namespace === get().selectedSubdomain?.namespace
          ) ? get().selectedSubdomain : null,
          allCellData: cellData,
          cellData: filterCellData(cellData, papers, metrics)
        });
      } finally {
        set({ isLoading: false });
      }
    },

    enqueuePaperImports: (namespace: string, files: File[], source: 'drop' | 'file_picker') => {
      const { currentWorkspaceId } = get();
      if (!currentWorkspaceId || files.length === 0) {
        return;
      }

      const pdfFiles = files.filter(file => /\.pdf$/i.test(file.name));
      if (pdfFiles.length === 0) {
        return;
      }

      const newImports = pdfFiles.map((file, index) => createPaperImportEntry(currentWorkspaceId, namespace, file, source, index));
      const paperImports = [...get().paperImports, ...newImports];
      persistWorkspacePaperImports(currentWorkspaceId, paperImports);

      const { papers, allCellData } = get();
      const { domainPacks, activeNamespaces, metrics } = deriveWorkspaceDomainPacks(papers, paperImports, currentWorkspaceId);
      set({
        paperImports,
        domainPacks,
        activeDomainPackNamespaces: activeNamespaces,
        metrics,
        cellData: filterCellData(allCellData, papers, metrics)
      });

      void (async () => {
        for (const paperImport of newImports) {
          set(state => ({
            paperImports: state.paperImports.map(entry =>
              entry.id === paperImport.id
                ? { ...entry, status: 'validating', error_message: undefined, warning: undefined }
                : entry
            )
          }));

          try {
            const file = paperImport.local_file as File;
            const contentBase64 = await fileToBase64(file);
            const upload = await sspClient.uploadPdf({
              file_name: file.name,
              content_base64: contentBase64,
              content_type: file.type || 'application/pdf',
              workspace_id: currentWorkspaceId,
              owner_id: get().currentOwnerId,
            });
            const parseResult = await sspClient.parsePdfWithDomainPack({
              workspace_id: currentWorkspaceId,
              domain_pack_namespace: paperImport.domain_pack_namespace,
              upload_id: upload.upload_id,
              owner_id: get().currentOwnerId,
            });
            const preview = buildImportPreviewFromBackend(parseResult, file.name);
            const warning = Array.isArray(parseResult?.warnings) && parseResult.warnings.length > 0
              ? parseResult.warnings.join(' ')
              : undefined;

            set(state => ({
              paperImports: state.paperImports.map(entry =>
                entry.id === paperImport.id
                  ? {
                      ...entry,
                      status: 'preview_ready',
                      upload_id: upload.upload_id,
                      title: preview.title,
                      markdown_text: parseResult?.markdown_text || undefined,
                      preview,
                      warning,
                    }
                  : entry
              )
            }));
          } catch (error) {
            set(state => ({
              paperImports: state.paperImports.map(entry =>
                entry.id === paperImport.id
                  ? {
                      ...entry,
                      status: 'error',
                      error_message: error instanceof Error ? error.message : 'Failed to prepare preview.'
                    }
                  : entry
              )
            }));
          }

          persistWorkspacePaperImports(currentWorkspaceId, get().paperImports);
        }
      })();
    },

    retryPaperImport: (paperImportId: string) => {
      const paperImport = get().paperImports.find(entry => entry.id === paperImportId);
      if (!paperImport) {
        return;
      }

      set(state => ({
        paperImports: state.paperImports.map(entry =>
          entry.id === paperImportId
            ? { ...entry, status: 'queued', error_message: undefined }
            : entry
        )
      }));
      persistWorkspacePaperImports(get().currentWorkspaceId, get().paperImports);

      if (paperImport.local_file) {
        get().enqueuePaperImports(paperImport.domain_pack_namespace, [paperImport.local_file], paperImport.source);
        get().removePaperImport(paperImportId);
      }
    },

    commitPaperImport: async (paperImportId: string) => {
      const paperImport = get().paperImports.find(entry => entry.id === paperImportId);
      if (!paperImport) {
        return;
      }
      if (!paperImport.upload_id) {
        throw new Error('This paper import has no backend upload reference. Re-upload the file before committing.');
      }

      set(state => ({
        paperImports: state.paperImports.map(entry =>
          entry.id === paperImportId
            ? { ...entry, status: 'ingesting', error_message: undefined }
            : entry
        )
      }));
      persistWorkspacePaperImports(get().currentWorkspaceId, get().paperImports);

      try {
        const existingPaperIds = new Set(get().papers.map(p => p.id));
        const commitTimestamp = new Date().toISOString();
        
        await sspClient.commitParsedPdf({
          workspace_id: paperImport.workspace_id,
          domain_pack_namespace: paperImport.domain_pack_namespace,
          upload_id: paperImport.upload_id,
          owner_id: get().currentOwnerId,
        });

        const remainingImports = get().paperImports.filter(entry => entry.id !== paperImportId);
        persistWorkspacePaperImports(get().currentWorkspaceId, remainingImports);
        set({ paperImports: remainingImports });
        await get().refreshData();
        
        // Find newly added papers and assign ingestion timestamp
        const newPapers = get().papers.filter(p => !existingPaperIds.has(p.id));
        for (const paper of newPapers) {
          setPaperIngestionTimestamp(paper.id, commitTimestamp);
        }
        
        // Refresh again to apply the timestamps
        if (newPapers.length > 0) {
          await get().refreshData();
        }
      } catch (error) {
        set(state => ({
          paperImports: state.paperImports.map(entry =>
            entry.id === paperImportId
              ? {
                  ...entry,
                  status: 'error',
                  error_message: error instanceof Error ? error.message : 'Failed to commit parsed PDF.',
                }
              : entry
          )
        }));
        persistWorkspacePaperImports(get().currentWorkspaceId, get().paperImports);
        throw error;
      }
    },

    removePaperImport: (paperImportId: string) => {
      const { currentWorkspaceId, papers, allCellData } = get();
      const paperImports = get().paperImports.filter(entry => entry.id !== paperImportId);
      persistWorkspacePaperImports(currentWorkspaceId, paperImports);
      const { domainPacks, activeNamespaces, metrics } = deriveWorkspaceDomainPacks(papers, paperImports, currentWorkspaceId);
      set({
        paperImports,
        domainPacks,
        activeDomainPackNamespaces: activeNamespaces,
        metrics,
        cellData: filterCellData(allCellData, papers, metrics)
      });
    },

    removePaper: (paperId: string) => {
      const { currentWorkspaceId } = get();
      updatePaperRegistryState(current => {
        const removed = new Set(current.removedPaperIdsByWorkspace[currentWorkspaceId] || []);
        removed.add(paperId);

        return {
          paperImportsByWorkspace: current.paperImportsByWorkspace,
          removedPaperIdsByWorkspace: {
            ...current.removedPaperIdsByWorkspace,
            [currentWorkspaceId]: Array.from(removed)
          }
        };
      });

      const papers = get().papers.filter(paper => paper.id !== paperId);
      const { metrics, allCellData, selectedPaperId } = get();
      set({
        papers,
        selectedPaperId: selectedPaperId === paperId ? null : selectedPaperId,
        cellData: filterCellData(allCellData, papers, metrics)
      });
    },

    selectRoot: () => {
      set({
        selectedRootView: true,
        selectedWorkspaceViewId: null,
        selectedDomainPackNamespace: null,
        selectedPaperId: null,
        selectedPaperImportId: null,
        selectedMetricsNamespace: null,
        selectedMetricsMode: 'registry',
        selectedMetricFullName: null,
        selectedSubdomain: null
      });
    },

    selectWorkspaceView: (workspaceId: string | null) => {
      set({
        selectedRootView: false,
        selectedWorkspaceViewId: workspaceId,
        selectedDomainPackNamespace: null,
        selectedPaperId: null,
        selectedPaperImportId: null,
        selectedMetricsNamespace: null,
        selectedMetricsMode: 'registry',
        selectedMetricFullName: null,
        selectedSubdomain: null
      });
    },

    selectDomainPack: (namespace: string | null) => {
      set({
        selectedRootView: false,
        selectedWorkspaceViewId: null,
        selectedDomainPackNamespace: namespace,
        selectedPaperId: null,
        selectedPaperImportId: null,
        selectedMetricsNamespace: null,
        selectedMetricsMode: 'registry',
        selectedMetricFullName: null,
        selectedSubdomain: null
      });
    },

    selectPaper: (paperId: string | null) => {
      set({
        selectedRootView: false,
        selectedWorkspaceViewId: null,
        selectedDomainPackNamespace: null,
        selectedPaperId: paperId,
        selectedPaperImportId: null,
        selectedMetricsNamespace: null,
        selectedMetricsMode: 'registry',
        selectedMetricFullName: null,
        selectedSubdomain: null
      });
    },

    selectPaperImport: (paperImportId: string | null) => {
      set({
        selectedRootView: false,
        selectedWorkspaceViewId: null,
        selectedDomainPackNamespace: null,
        selectedPaperImportId: paperImportId,
        selectedPaperId: null,
        selectedMetricsNamespace: null,
        selectedMetricsMode: 'registry',
        selectedMetricFullName: null,
        selectedSubdomain: null
      });
    },

    selectMetrics: (namespace: string | null, mode: 'registry' | 'add' = 'registry') => {
      set({
        selectedRootView: false,
        selectedWorkspaceViewId: null,
        selectedDomainPackNamespace: null,
        selectedMetricsNamespace: namespace,
        selectedMetricsMode: mode,
        selectedPaperId: null,
        selectedPaperImportId: null,
        selectedMetricFullName: null,
        selectedSubdomain: null
      });
    },

    selectMetric: (metricFullName: string | null) => {
      set({
        selectedRootView: false,
        selectedWorkspaceViewId: null,
        selectedDomainPackNamespace: null,
        selectedMetricFullName: metricFullName,
        selectedPaperId: null,
        selectedPaperImportId: null,
        selectedMetricsNamespace: null,
        selectedMetricsMode: 'registry',
        selectedSubdomain: null
      });
    },

    selectSubdomain: (subdomain: SelectedSubdomain | null) => {
      set({
        selectedRootView: false,
        selectedWorkspaceViewId: null,
        selectedDomainPackNamespace: null,
        selectedSubdomain: subdomain,
        selectedPaperId: null,
        selectedPaperImportId: null,
        selectedMetricsNamespace: null,
        selectedMetricsMode: 'registry',
        selectedMetricFullName: null
      });
    },
    
    getCellData: (paperId: string, metricName: string) => {
      const key = `${paperId}:${metricName}`;
      return get().cellData.get(key) || null;
    },
    
    getEvidence: async (paperId: string, metricName: string) => {
      // TODO: Call SSP textDocument/sspRetrieveEvidence
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Get the actual cell data to show relevant evidence
      const cellData = get().getCellData(paperId, metricName);
      const paper = get().papers.find(p => p.id === paperId);
      
      if (!cellData) {
        return [];
      }
      
      // Generate cell-specific evidence matching the evidenceCount
      const metricDisplay = metricName.replace(/.*:/, '').replace(/_/g, ' ');
      const value = cellData.value || 'N/A';
      const unit = cellData.unit || '';
      const targetCount = cellData.evidenceCount;
      
      // Use hash of paperId + metricName to generate consistent but varied data
      const hash = (paperId + metricName).split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
      const seed = hash % 100;
      
      const mockEvidence: Evidence[] = [];
      
      // Generate chunks (at least 1, up to targetCount - 1 to leave room for formula if needed)
      const hasFormula = (metricDisplay.includes('delay') || metricDisplay.includes('latency') || 
                          metricDisplay.includes('throughput') || metricDisplay.includes('loss'));
      const chunkCount = hasFormula ? Math.max(1, targetCount - 1) : targetCount;
      
      // Chunk templates with more realistic content
      const chunkTemplates = [
        `In our experiments, we systematically measured the ${metricDisplay} across various operating conditions. The system consistently achieved ${value} ${unit}, which represents a significant improvement over the baseline configuration. These measurements were conducted using industry-standard test equipment with a measurement uncertainty of ±2%. The experimental setup followed IEEE 802.3 testing guidelines, ensuring reproducibility and comparability with previous studies in the field.`,
        
        `${paper?.title || 'The paper'} presents comprehensive analysis showing that ${metricDisplay} values of ${value} ${unit} were consistently achieved across multiple test runs spanning ${3 + (seed % 5)} weeks of continuous operation. The methodology is described in detail in Section ${2 + (seed % 3)}, where we outline the calibration procedures and validation against reference standards. Statistical analysis revealed a standard deviation of less than 5%, indicating high stability and reliability of the measured values.`,
        
        `The measured ${metricDisplay} of ${value} ${unit} represents a ${10 + (seed % 30)}% improvement over the baseline performance reported in prior work. These results were validated through independent verification by an external laboratory, which confirmed our findings within a ${2 + (seed % 3)}% margin. The improvement is attributed to our novel optimization algorithm described in Algorithm ${1 + (seed % 2)}, which dynamically adjusts system parameters based on real-time feedback. This approach has proven effective across diverse deployment scenarios.`,
        
        `Under peak load conditions with ${70 + (seed % 30)}% utilization, we recorded ${metricDisplay} at ${value} ${unit}, demonstrating the system's robustness and reliability even under stress. The test environment simulated real-world traffic patterns including bursty transmissions and variable packet sizes ranging from 64 to 1518 bytes. Performance remained stable throughout the ${24 + (seed % 48)}-hour test period, with no significant degradation observed. These findings validate our architectural design choices and confirm scalability to production deployments.`,
        
        `Table ${1 + (seed % 5)} in Section ${3 + (seed % 4)} summarizes the ${metricDisplay} measurements across different experimental configurations. The average value of ${value} ${unit} was observed, with individual measurements ranging from ${(parseFloat(value) * 0.95).toFixed(1)} to ${(parseFloat(value) * 1.05).toFixed(1)} ${unit}. The variance in measurements can be attributed to environmental factors such as temperature fluctuations (±3°C) and power supply variations. Statistical t-tests confirmed that our improvements are statistically significant at p < 0.01 confidence level compared to baseline methods.`
      ];
      
      // Add chunks
      for (let i = 0; i < chunkCount; i++) {
        mockEvidence.push({
          type: 'chunk',
          id: `${paperId}_${metricName}_chunk_${i + 1}`,
          text: chunkTemplates[i % chunkTemplates.length],
          confidence: 0.70 + ((seed + i * 7) % 25) / 100,
          boundingBox: { 
            page: 1 + ((seed + i) % 3), 
            x: 80 + ((seed + i * 13) % 50), 
            y: 150 + ((seed + i * 19) % 200), 
            width: 380, 
            height: 45 
          }
        });
      }
      
      // Add formula if appropriate and we haven't reached target count
      if (hasFormula && mockEvidence.length < targetCount) {
        mockEvidence.push({
          type: 'formula',
          id: `${paperId}_${metricName}_formula_1`,
          text: metricDisplay.includes('delay') || metricDisplay.includes('latency') 
            ? `τ_{${metricDisplay.split(' ')[0]}} = ${value}\\text{ ${unit}}`
            : metricDisplay.includes('loss')
            ? `L_{${metricDisplay.split(' ')[0]}} = ${value}\\text{ ${unit}}`
            : `R = ${value}\\text{ ${unit}}`,
          confidence: 0.88 + (seed % 10) / 100,
          boundingBox: { 
            page: 1 + (seed % 3), 
            x: 120 + (seed % 30), 
            y: 400 + (seed % 100), 
            width: 280, 
            height: 35 
          }
        });
      }
      
      return mockEvidence;
    },

    addMetric: (namespace: string, metric: MetricInput) => {
      const metricName = normalizeMetricName(metric.name);
      if (!metricName) {
        throw new Error('Metric name is required');
      }

      const packs = get().domainPacks;
      const pack = packs.find(item => item.namespace === namespace);
      if (!pack) {
        throw new Error(`Domain pack "${namespace}" was not found`);
      }

      if (pack.config.core_metrics.some(item => item.name === metricName)) {
        throw new Error(`Metric "${metricName}" already exists`);
      }

      const updatedPack = updateDomainPackMetricDefinitions(pack, [
        ...pack.config.core_metrics,
        { ...metric, name: metricName }
      ]);
      saveBootstrappedDomainPack(namespace, updatedPack.config);

      const nextPacks = packs.map(item => item.namespace === namespace ? updatedPack : item);
      const combinedMetrics = combineMetrics(nextPacks, get().activeDomainPackNamespaces);

      set({
        domainPacks: nextPacks,
        metrics: combinedMetrics,
        cellData: filterCellData(get().allCellData, get().papers, combinedMetrics),
        selectedMetricFullName: `${namespace}:${metricName}`,
        selectedMetricsNamespace: null,
        selectedMetricsMode: 'registry',
        selectedPaperId: null,
        selectedPaperImportId: null,
        selectedSubdomain: null
      });
    },

    updateMetric: (namespace: string, originalName: string, metric: MetricInput) => {
      const metricName = normalizeMetricName(metric.name);
      if (!metricName) {
        throw new Error('Metric name is required');
      }

      const packs = get().domainPacks;
      const pack = packs.find(item => item.namespace === namespace);
      if (!pack) {
        throw new Error(`Domain pack "${namespace}" was not found`);
      }

      if (
        metricName !== originalName &&
        pack.config.core_metrics.some(item => item.name === metricName)
      ) {
        throw new Error(`Metric "${metricName}" already exists`);
      }

      const oldFullName = `${namespace}:${originalName}`;
      const newFullName = `${namespace}:${metricName}`;
      const nextDefinitions = pack.config.core_metrics.map(item =>
        item.name === originalName
          ? { ...metric, name: metricName }
          : item
      );
      const updatedPack = updateDomainPackMetricDefinitions(pack, nextDefinitions);
      saveBootstrappedDomainPack(namespace, updatedPack.config);

      const nextPacks = packs.map(item => item.namespace === namespace ? updatedPack : item);
      const nextAllCellData = new Map<string, CellData>();
      get().allCellData.forEach((cell, key) => {
        if (cell.metricName === oldFullName) {
          nextAllCellData.set(`${cell.paperId}:${newFullName}`, {
            ...cell,
            metricName: newFullName,
            unit: metric.expected_unit
          });
        } else {
          nextAllCellData.set(key, cell);
        }
      });
      const combinedMetrics = combineMetrics(nextPacks, get().activeDomainPackNamespaces);

      set({
        domainPacks: nextPacks,
        metrics: combinedMetrics,
        allCellData: nextAllCellData,
        cellData: filterCellData(nextAllCellData, get().papers, combinedMetrics),
        selectedMetricFullName: newFullName
      });
    },

    deleteMetric: (namespace: string, metricName: string) => {
      const packs = get().domainPacks;
      const pack = packs.find(item => item.namespace === namespace);
      if (!pack) {
        throw new Error(`Domain pack "${namespace}" was not found`);
      }

      const deletedFullName = `${namespace}:${metricName}`;
      const updatedPack = updateDomainPackMetricDefinitions(
        pack,
        pack.config.core_metrics.filter(item => item.name !== metricName)
      );
      saveBootstrappedDomainPack(namespace, updatedPack.config);

      const nextPacks = packs.map(item => item.namespace === namespace ? updatedPack : item);
      const nextAllCellData = new Map<string, CellData>();
      get().allCellData.forEach((cell, key) => {
        if (cell.metricName !== deletedFullName) {
          nextAllCellData.set(key, cell);
        }
      });
      const combinedMetrics = combineMetrics(nextPacks, get().activeDomainPackNamespaces);

      set({
        domainPacks: nextPacks,
        metrics: combinedMetrics,
        allCellData: nextAllCellData,
        cellData: filterCellData(nextAllCellData, get().papers, combinedMetrics),
        selectedMetricFullName: get().selectedMetricFullName === deletedFullName ? null : get().selectedMetricFullName,
        selectedMetricsNamespace: namespace,
        selectedMetricsMode: 'registry'
      });
    },
    
    // Domain Pack Actions
    addDomainPack: async (namespace: string, config: DomainPackConfig | string) => {
      console.log(`Adding domain pack: ${namespace}`);
      
      try {
        // If config is a string, assume it's a path (legacy) - TODO: load from file
        const domainPackConfig: DomainPackConfig = typeof config === 'string' 
          ? await fetch(config).then(r => r.json())
          : config;
        
        // Save bootstrapped domain pack config to localStorage
        if (typeof config !== 'string') {
          saveBootstrappedDomainPack(namespace, domainPackConfig);
          console.log(`Bootstrapped domain pack ${namespace} saved to localStorage`);
        }
        
        // Convert metrics to namespaced format
        const metrics = domainPackConfig.core_metrics.map(m => ({
          name: m.name,
          full_name: `${namespace}:${m.name}`,
          namespace: namespace,
          unit: m.expected_unit,
          aliases: m.aliases || [],
          value_type: m.value_type
        }));
        
        // Create new domain pack
        const newPack: LoadedDomainPack = {
          namespace,
          config: domainPackConfig,
          enabled: true,
          metrics
        };
        
        // Add to existing packs
        const packs = [...get().domainPacks, newPack];
        const activeNamespaces = [...get().activeDomainPackNamespaces, namespace];
        const combinedMetrics = combineMetrics(packs, activeNamespaces);
        const { papers, allCellData, currentWorkspaceId } = get();
        
        // Persist domain pack to registry
        updateDomainPackRegistryState(current => {
          const workspacePacks = current.explicitDomainPacksByWorkspace[currentWorkspaceId] || [];
          if (!workspacePacks.includes(namespace)) {
            return {
              explicitDomainPacksByWorkspace: {
                ...current.explicitDomainPacksByWorkspace,
                [currentWorkspaceId]: [...workspacePacks, namespace]
              }
            };
          }
          return current;
        });
        
        set({
          domainPacks: packs,
          activeDomainPackNamespaces: activeNamespaces,
          metrics: combinedMetrics,
          cellData: filterCellData(allCellData, papers, combinedMetrics)
        });
        
        console.log(`Domain pack ${namespace} added successfully`);
      } catch (error) {
        console.error(`Failed to add domain pack ${namespace}:`, error);
        throw error;
      }
    },
    
    removeDomainPack: (namespace: string) => {
      // Remove from bootstrapped configs if it exists
      removeBootstrappedDomainPack(namespace);
      
      const packs = get().domainPacks.filter(p => p.namespace !== namespace);
      const activeNamespaces = get().activeDomainPackNamespaces.filter(n => n !== namespace);
      const metrics = combineMetrics(packs, activeNamespaces);
      const { papers, allCellData, currentWorkspaceId } = get();
      
      // Remove from persisted registry
      updateDomainPackRegistryState(current => {
        const workspacePacks = current.explicitDomainPacksByWorkspace[currentWorkspaceId] || [];
        return {
          explicitDomainPacksByWorkspace: {
            ...current.explicitDomainPacksByWorkspace,
            [currentWorkspaceId]: workspacePacks.filter(ns => ns !== namespace)
          }
        };
      });
      
      set({
        domainPacks: packs,
        activeDomainPackNamespaces: activeNamespaces,
        metrics,
        selectedDomainPackNamespace: get().selectedDomainPackNamespace === namespace
          ? null
          : get().selectedDomainPackNamespace,
        selectedMetricsNamespace: get().selectedMetricsNamespace === namespace ? null : get().selectedMetricsNamespace,
        selectedMetricsMode: get().selectedMetricsNamespace === namespace ? 'registry' : get().selectedMetricsMode,
        selectedMetricFullName: get().selectedMetricFullName?.startsWith(`${namespace}:`)
          ? null
          : get().selectedMetricFullName,
        selectedSubdomain: get().selectedSubdomain?.namespace === namespace ? null : get().selectedSubdomain,
        cellData: filterCellData(allCellData, papers, metrics)
      });
    },
    
    setActiveDomainPacks: (namespaces: string[]) => {
      const { domainPacks, papers, allCellData } = get();
      const metrics = combineMetrics(domainPacks, namespaces);
      
      set({
        activeDomainPackNamespaces: namespaces,
        metrics,
        cellData: filterCellData(allCellData, papers, metrics)
      });
    },
    
    getDomainPack: (namespace: string) => {
      return get().domainPacks.find(p => p.namespace === namespace) || null;
    },
    
    // Intent Actions
    setActiveIntentBranch: (branch: IntentBranch | null) => {
      set({ activeIntentBranch: branch });
    },
    
    setUserIntentProfile: (profile: UserIntentProfile) => {
      set({ 
        userIntentProfile: profile,
        learnedPatterns: profile.learned_patterns,
        confidenceThreshold: profile.confidence_threshold
      });
    },
    
    setLearnedPatterns: (patterns: IntentPattern[]) => {
      set({ learnedPatterns: patterns });
    },
    
    setConfidenceThreshold: (threshold: number) => {
      set({ confidenceThreshold: threshold });
    }
  };
});

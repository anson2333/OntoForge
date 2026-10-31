/**
 * SSP JSON-RPC Client
 * Communicates with the OntoForge backend server
 */

import { JSONRPC_URL } from './runtime_config';

interface JsonRpcRequest {
  jsonrpc: '2.0';
  method: string;
  params?: any;
  id: number | string;
}

interface JsonRpcResponse {
  jsonrpc: '2.0';
  result?: any;
  error?: {
    code: number;
    message: string;
    data?: any;
  };
  id: number | string;
}

export const AUTH_REQUIRED_CODE = -32001;
export const TOKEN_STORAGE_KEY = 'ontoforge-session-token';

export class SSPError extends Error {
  code?: number;

  constructor(message: string, code?: number) {
    super(message);
    this.name = 'SSPError';
    this.code = code;
  }
}

class SSPClient {
  private baseUrl: string;
  private requestId: number;
  private token: string | null;

  constructor(baseUrl: string = JSONRPC_URL) {
    this.baseUrl = baseUrl;
    this.requestId = 0;
    this.token = typeof window !== 'undefined'
      ? window.localStorage.getItem(TOKEN_STORAGE_KEY)
      : null;
  }

  private getNextId(): number {
    return ++this.requestId;
  }

  getToken(): string | null {
    return this.token;
  }

  setToken(token: string | null): void {
    this.token = token;
    if (typeof window === 'undefined') {
      return;
    }
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }

  async request(method: string, params?: any): Promise<any> {
    const request: JsonRpcRequest = {
      jsonrpc: '2.0',
      method,
      params,
      id: this.getNextId()
    };

    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(this.baseUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new SSPError(`HTTP ${response.status}: ${response.statusText}`);
      }

      const jsonResponse: JsonRpcResponse = await response.json();

      if (jsonResponse.error) {
        if (jsonResponse.error.code === AUTH_REQUIRED_CODE) {
          this.setToken(null);
        }
        throw new SSPError(
          jsonResponse.error.message || 'JSON-RPC request failed',
          jsonResponse.error.code
        );
      }

      return jsonResponse.result;
    } catch (error) {
      console.error('SSP request failed:', error);
      throw error;
    }
  }

  // Authentication

  async register(username: string, password: string, displayName?: string): Promise<any> {
    return this.request('authRegister', {
      username,
      password,
      display_name: displayName
    });
  }

  async login(username: string, password: string): Promise<any> {
    return this.request('authLogin', { username, password });
  }

  async logout(): Promise<any> {
    try {
      return await this.request('authLogout', {});
    } finally {
      this.setToken(null);
    }
  }

  async authStatus(): Promise<any> {
    return this.request('authStatus', {});
  }

  async listWorkspaceMembers(workspaceId: string): Promise<any> {
    return this.request('listWorkspaceMembers', { workspace_id: workspaceId });
  }

  async addWorkspaceMember(
    workspaceId: string,
    username: string,
    role: 'viewer' | 'editor'
  ): Promise<any> {
    return this.request('addWorkspaceMember', {
      workspace_id: workspaceId,
      username,
      role
    });
  }

  async removeWorkspaceMember(workspaceId: string, userId: string): Promise<any> {
    return this.request('removeWorkspaceMember', {
      workspace_id: workspaceId,
      user_id: userId
    });
  }

  // SSP Protocol Methods

  async initialize(workspaceRoot: string, config: any): Promise<any> {
    return this.request('textDocument/sspInitialize', {
      workspaceRoot,
      config,
      bootstrap_mode: 'config-first'
    });
  }

  async ingest(uri: string, options?: any): Promise<any> {
    return this.request('textDocument/sspIngest', {
      textDocument: { uri },
      options
    });
  }

  async retrieveEvidence(paperId: string, metricName: string): Promise<any> {
    return this.request('textDocument/sspRetrieveEvidence', {
      paperId,
      metricName
    });
  }

  async resolveConflict(conflictId: string, resolution: any): Promise<any> {
    return this.request('textDocument/sspResolveConflict', {
      conflictId,
      resolution
    });
  }

  async lockAssertion(assertionId: string, userId: string, notes: string): Promise<any> {
    return this.request('textDocument/sspLockAssertion', {
      assertionId,
      userId,
      arbitration_notes: notes,
      lock_type: 'permanent_human_lock'
    });
  }

  async queryMatrix(domainId: string): Promise<any> {
    return this.request('textDocument/sspQueryMatrix', {
      domainId
    });
  }

  async healthCheck(): Promise<boolean> {
    try {
      const result = await this.request('ping');
      return result === 'pong';
    } catch {
      return false;
    }
  }

  // Intent Framework Methods (Section 2.6)

  async call(method: string, params: any): Promise<any> {
    return this.request(method, params);
  }

  async declareIntent(params: {
    intent_type: string;
    intent_scope: string;
    description: string;
    constraints?: Record<string, any>;
    active_from: string;
    active_until?: string;
  }): Promise<any> {
    return this.request('sspDeclareIntent', params);
  }

  async createIntentBranch(params: {
    branch_name: string;
    description: string;
    inherit_from?: string;
    overrides?: Record<string, any>;
  }): Promise<any> {
    return this.request('sspCreateIntentBranch', params);
  }

  async switchIntentContext(params: { branch_id: string }): Promise<any> {
    return this.request('sspSwitchIntentContext', params);
  }

  async queryByIntent(params: { query: string; intent_context?: string }): Promise<any> {
    return this.request('sspQueryByIntent', params);
  }

  async suggestReviewQueue(params: {
    strategy?: string;
    limit?: number;
  }): Promise<any> {
    return this.request('sspSuggestReviewQueue', params);
  }

  async applyIntentPattern(params: {
    pattern_id: string;
    scope: Record<string, any>;
    dry_run?: boolean;
  }): Promise<any> {
    return this.request('sspApplyIntentPattern', params);
  }

  async queryIntentProfile(params: {
    user_id: string;
    detail_level?: 'summary' | 'full';
  }): Promise<any> {
    return this.request('sspQueryIntentProfile', params);
  }

  async parseUserIntent(params: {
    workspace_id: string;
    user_id: string;
    message: string;
    owner_id?: string;
    intent_context?: string;
  }): Promise<any> {
    return this.request('parseUserIntent', params);
  }

  // Evidence Verification Methods (Section 1.3 - Tier 3 HITL)

  /**
   * Verify evidence as correct without modifications
   */
  async verifyEvidence(params: {
    evidence_id: string;
    confidence_override?: number;
    intent_metadata: {
      intent_type: 'correction';
      intent_scope: 'local';
      tags?: string[];
    };
  }): Promise<any> {
    return this.request('sspVerifyNode', {
      params: {
        node_id: params.evidence_id,
        action: 'approve',
        verified_by: 'session'
      }
    });
  }

  /**
   * Move evidence into the review queue without approving it.
   */
  async requestEvidenceReview(params: {
    evidence_id: string;
    intent_metadata: {
      intent_type: 'correction';
      intent_scope: 'local';
      tags?: string[];
    };
  }): Promise<any> {
    return this.request('sspUpdateNode', {
      params: {
        node_id: params.evidence_id,
        updates: {},
        modified_by: 'session'
      }
    });
  }

  /**
   * Correct evidence with modifications
   */
  async correctEvidence(params: {
    evidence_id: string;
    modifications: {
      old_text: string;
      new_text: string;
      change_notes?: string;
    };
    new_status: 'pending_verification' | 'verified';
    evidence_type: 'chunk' | 'formula';
    intent_metadata: {
      intent_type: 'correction';
      intent_scope: 'local';
      confidence_override?: number;
      tags?: string[];
    };
  }): Promise<any> {
    const field = params.evidence_type === 'formula' ? 'latex_string' : 'raw_text';
    const updated = await this.request('sspUpdateNode', {
      params: {
        node_id: params.evidence_id,
        updates: { [field]: params.modifications.new_text },
        modified_by: 'session'
      }
    });
    if (params.new_status === 'verified') {
      return this.request('sspVerifyNode', {
        params: {
          node_id: params.evidence_id,
          action: 'approve',
          verified_by: 'session',
          notes: params.modifications.change_notes
        }
      });
    }
    return updated;
  }

  /**
   * Reject evidence as invalid
   */
  async rejectEvidence(params: {
    evidence_id: string;
    reason?: string;
    intent_metadata: {
      intent_type: 'correction';
      intent_scope: 'local';
      tags?: string[];
    };
  }): Promise<any> {
    return this.request('sspVerifyNode', {
      params: {
        node_id: params.evidence_id,
        action: 'reject',
        verified_by: 'session',
        notes: params.reason
      }
    });
  }

  /**
   * Batch verify multiple evidence items
   */
  async batchVerifyEvidence(params: {
    evidence_ids: string[];
    intent_metadata: {
      intent_type: 'correction';
      intent_scope: 'local';
      tags?: string[];
    };
  }): Promise<any> {
    return Promise.all(params.evidence_ids.map(evidenceId => this.verifyEvidence({
      evidence_id: evidenceId,
      intent_metadata: params.intent_metadata
    })));
  }

  /**
   * Batch reject multiple evidence items
   */
  async batchRejectEvidence(params: {
    evidence_ids: string[];
    reason?: string;
    intent_metadata: {
      intent_type: 'correction';
      intent_scope: 'local';
      tags?: string[];
    };
  }): Promise<any> {
    return Promise.all(params.evidence_ids.map(evidenceId => this.rejectEvidence({
      evidence_id: evidenceId,
      reason: params.reason,
      intent_metadata: params.intent_metadata
    })));
  }

  /**
   * Get evidence list for a paper or assertion
   */
  async getEvidenceList(params: {
    paper_id?: string;
    assertion_id?: string;
    filter?: {
      status?: string[];
      confidence_range?: [number, number];
    };
  }): Promise<any> {
    return this.request('textDocument/sspGetEvidenceList', params);
  }

  /**
   * Restore rejected evidence for re-correction
   */
  async restoreEvidence(params: {
    evidence_id: string;
    intent_metadata: {
      intent_type: 'correction';
      intent_scope: 'local';
      tags?: string[];
    };
  }): Promise<any> {
    return this.request('sspVerifyNode', {
      params: {
        node_id: params.evidence_id,
        action: 'request_changes',
        verified_by: 'session',
        notes: 'Restored for correction'
      }
    });
  }

  /**
   * List accessible workspaces
   */
  async listWorkspaces(params?: {
    owner_id?: string;
    include_archived?: boolean;
  }): Promise<any> {
    return this.request('listWorkspaces', params || {});
  }

  /**
   * Get workspace metadata
   */
  async getWorkspace(params: {
    workspace_id: string;
    owner_id?: string;
  }): Promise<any> {
    return this.request('getWorkspace', params);
  }

  /**
   * Create a new workspace
   */
  async createWorkspace(params: {
    name: string;
    description?: string;
    root?: string;
    owner_id?: string;
    metadata?: Record<string, any>;
  }): Promise<any> {
    return this.request('createWorkspace', params);
  }

  /**
   * Delete a workspace
   */
  async deleteWorkspace(params: {
    workspace_id: string;
    owner_id?: string;
  }): Promise<any> {
    return this.request('deleteWorkspace', params);
  }

  /**
   * Get papers from the database
   */
  async getPapers(params?: {
    workspace_id: string;
    domain_pack_namespace?: string;
    owner_id?: string;
  }): Promise<any> {
    return this.request('getPapers', params || {});
  }

  /**
   * Get assertions (cell data) from the database
   */
  async getAssertions(params?: {
    workspace_id: string;
    paper_id?: string;
    metric_name?: string;
    domain_pack_namespace?: string;
    owner_id?: string;
  }): Promise<any> {
    return this.request('getAssertions', params || {});
  }

  /**
   * Bootstrap domain pack from research proposal
   */
  async bootstrapDomainPack(params: {
    proposal_text: string;
  }): Promise<any> {
    return this.request('bootstrapDomainPack', params);
  }

  /**
   * List domain packs configured on the backend
   */
  async listDomainPacks(): Promise<any> {
    return this.request('listDomainPacks', {});
  }

  /**
   * Get the chunks/formulas supporting one paper-metric assertion
   */
  async getEvidence(params: {
    workspace_id: string;
    paper_id: string;
    metric_name: string;
    owner_id?: string;
  }): Promise<any> {
    return this.request('getEvidence', params);
  }

  /**
   * Method × scenario × metric coverage report with ranked gaps
   */
  async getCoverageAnalysis(params: {
    workspace_id: string;
    domain_pack_namespace?: string;
    methods?: string[];
    scenarios?: string[];
    metrics?: string[];
    gap_limit?: number;
    owner_id?: string;
  }): Promise<any> {
    return this.request('getCoverageAnalysis', params);
  }

  /**
   * Quality-filtered, path-explained ontology gap candidates
   */
  async analyzeResearchGaps(params: {
    workspace_id: string;
    include_machine_checked?: boolean;
    limit?: number;
  }): Promise<any> {
    return this.request('analyzeResearchGaps', params);
  }

  /**
   * Validate domain pack configuration
   */
  async validateDomainPack(params: {
    content: string;
    format: 'yaml' | 'json';
  }): Promise<any> {
    return this.request('validateDomainPack', params);
  }

  /**
   * Upload a PDF to backend-managed temporary storage
   */
  async uploadPdf(params: {
    file_name: string;
    content_base64: string;
    content_type?: string;
    workspace_id?: string;
    owner_id?: string;
  }): Promise<any> {
    return this.request('uploadPdf', params);
  }

  /**
   * Parse an uploaded PDF with domain-pack grounding
   */
  async parsePdfWithDomainPack(params: {
    workspace_id: string;
    domain_pack_namespace: string;
    upload_id?: string;
    paper_uri?: string;
    raw_text?: string;
    owner_id?: string;
    intent_context?: string;
    parse_options?: Record<string, any>;
  }): Promise<any> {
    return this.request('parsePdfWithDomainPack', params);
  }

  /**
   * Commit a previously uploaded and previewed PDF into the graph
   */
  async commitParsedPdf(params: {
    workspace_id: string;
    domain_pack_namespace: string;
    upload_id: string;
    preview_id: string;
    owner_id?: string;
    parse_options?: Record<string, any>;
  }): Promise<any> {
    return this.request('commitParsedPdf', params);
  }
}

// Singleton instance
export const sspClient = new SSPClient();

export default SSPClient;

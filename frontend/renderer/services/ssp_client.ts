/**
 * SSP JSON-RPC Client
 * Communicates with the OntoForge backend server
 */

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

class SSPClient {
  private baseUrl: string;
  private requestId: number;

  constructor(baseUrl: string = 'http://localhost:8765/jsonrpc') {
    this.baseUrl = baseUrl;
    this.requestId = 0;
  }

  private getNextId(): number {
    return ++this.requestId;
  }

  async request(method: string, params?: any): Promise<any> {
    const request: JsonRpcRequest = {
      jsonrpc: '2.0',
      method,
      params,
      id: this.getNextId()
    };

    try {
      const response = await fetch(this.baseUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const jsonResponse: JsonRpcResponse = await response.json();

      if (jsonResponse.error) {
        throw new Error(`JSON-RPC Error ${jsonResponse.error.code}: ${jsonResponse.error.message}`);
      }

      return jsonResponse.result;
    } catch (error) {
      console.error('SSP request failed:', error);
      throw error;
    }
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
    return this.request('textDocument/sspVerifyEvidence', params);
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
    intent_metadata: {
      intent_type: 'correction';
      intent_scope: 'local';
      confidence_override?: number;
      tags?: string[];
    };
  }): Promise<any> {
    return this.request('textDocument/sspCorrectEvidence', params);
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
    return this.request('textDocument/sspRejectEvidence', params);
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
    return this.request('textDocument/sspBatchVerifyEvidence', params);
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
    return this.request('textDocument/sspBatchRejectEvidence', params);
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
    return this.request('textDocument/sspRestoreEvidence', params);
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
    owner_id?: string;
    parse_options?: Record<string, any>;
  }): Promise<any> {
    return this.request('commitParsedPdf', params);
  }
}

// Singleton instance
export const sspClient = new SSPClient();

export default SSPClient;

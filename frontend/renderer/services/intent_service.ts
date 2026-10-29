/**
 * Intent Service
 * Manages user intent profiles, patterns, and branch contexts
 */

import { sspClient } from './ssp_client';

export interface IntentMetadata {
  intent_type: 'correction' | 'preference' | 'priority' | 'constraint' | 'goal';
  intent_scope: 'local' | 'pattern' | 'global';
  generalization_hint?: string;
  confidence_override?: number;
  tags?: string[];
}

export interface ParsedIntentResult {
  intent_type: IntentMetadata['intent_type'];
  intent_scope: IntentMetadata['intent_scope'];
  description: string;
  constraints: Record<string, any>;
  generalization_hint?: string;
  confidence: number;
  requires_confirmation: boolean;
}

export interface IntentPattern {
  pattern_id: string;
  confidence: number;
  applications: number;
  last_used: string;
  intent_type: string;
  description: string;
  matched_arbitrator_ids: string[];
}

export interface IntentGoal {
  goal_id: string;
  description: string;
  constraints: Record<string, any>;
  active_from: string;
  active_until?: string;
  status: 'active' | 'paused' | 'completed';
}

export interface IntentBranch {
  branch_id: string;
  branch_name: string;
  description: string;
  user_id: string;
  parent_branch_id?: string;
  created_at: string;
  active_until?: string;
  status: 'active' | 'archived' | 'completed';
  overrides: Record<string, any>;
}

export interface UserIntentProfile {
  user_id: string;
  learned_priorities: Record<string, number>;
  preferred_units: Record<string, string>;
  evidence_ranking: string[];
  active_goals: IntentGoal[];
  subdomain_focus: string[];
  temporal_preferences: Record<string, any>;
  confidence_threshold: number;
  total_intents_captured: number;
  learned_patterns: IntentPattern[];
}

export interface AISuggestion {
  recommended_assertion_id: string;
  confidence: number;
  reasoning: string;
  matched_intent_patterns: string[];
  user_can_override: boolean;
}

interface DeclaredIntentRecord {
  intent_id: string;
  intent_type: IntentMetadata['intent_type'];
  intent_scope: IntentMetadata['intent_scope'];
  description: string;
  constraints: Record<string, any>;
  active_from: string;
  active_until?: string;
  status: 'active' | 'paused';
  created_at: string;
}

const DECLARED_INTENTS_STORAGE_KEY = 'ontoforge-declared-intents';

class IntentService {
  private currentBranch: IntentBranch | null = null;
  private userProfile: UserIntentProfile | null = null;
  private declaredIntentsByUserId = this.loadDeclaredIntents();

  private loadDeclaredIntents(): Map<string, DeclaredIntentRecord[]> {
    if (typeof window === 'undefined') {
      return new Map<string, DeclaredIntentRecord[]>();
    }

    try {
      const raw = window.localStorage.getItem(DECLARED_INTENTS_STORAGE_KEY);
      if (!raw) {
        return new Map<string, DeclaredIntentRecord[]>();
      }

      const parsed = JSON.parse(raw) as Record<string, DeclaredIntentRecord[]>;
      return new Map(Object.entries(parsed));
    } catch (error) {
      console.warn('Failed to load persisted declared intents:', error);
      return new Map<string, DeclaredIntentRecord[]>();
    }
  }

  private persistDeclaredIntents(): void {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      const serialized = Object.fromEntries(this.declaredIntentsByUserId.entries());
      window.localStorage.setItem(DECLARED_INTENTS_STORAGE_KEY, JSON.stringify(serialized));
    } catch (error) {
      console.warn('Failed to persist declared intents:', error);
    }
  }

  private getDeclaredIntents(userId: string): DeclaredIntentRecord[] {
    return this.declaredIntentsByUserId.get(userId) || [];
  }

  private mergeDeclaredIntents(profile: UserIntentProfile): UserIntentProfile {
    const declaredIntents = this.getDeclaredIntents(profile.user_id);
    if (declaredIntents.length === 0) {
      return profile;
    }

    const goalIds = new Set(profile.active_goals.map(goal => goal.goal_id));
    const patternIds = new Set(profile.learned_patterns.map(pattern => pattern.pattern_id));

    const mergedGoals = [...profile.active_goals];
    const mergedPatterns = [...profile.learned_patterns];

    for (const declared of declaredIntents) {
      if (declared.intent_type === 'goal') {
        if (!goalIds.has(declared.intent_id)) {
          mergedGoals.unshift({
            goal_id: declared.intent_id,
            description: declared.description,
            constraints: declared.constraints,
            active_from: declared.active_from,
            active_until: declared.active_until,
            status: declared.status
          });
        }
        continue;
      }

      if (!patternIds.has(declared.intent_id)) {
        mergedPatterns.unshift({
          pattern_id: declared.intent_id,
          confidence: 1,
          applications: 1,
          last_used: declared.created_at,
          intent_type: declared.intent_type,
          description: declared.description,
          matched_arbitrator_ids: []
        });
      }
    }

    return {
      ...profile,
      active_goals: mergedGoals,
      learned_patterns: mergedPatterns,
      total_intents_captured: Math.max(profile.total_intents_captured, mergedGoals.length + mergedPatterns.length)
    };
  }

  /**
   * Declare explicit research intent
   */
  async declareIntent(params: {
    user_id?: string;
    intent_type: 'correction' | 'preference' | 'priority' | 'constraint' | 'goal';
    intent_scope: 'local' | 'pattern' | 'global';
    description: string;
    constraints?: Record<string, any>;
    active_from: string;
    active_until?: string;
  }): Promise<{ intent_id: string; status: string; affected_systems: string[]; recommendations: string[] }> {
    const { user_id = 'current_user', ...request } = params;
    const result = await sspClient.call('sspDeclareIntent', request);
    const existing = this.getDeclaredIntents(user_id);
    const nextRecord: DeclaredIntentRecord = {
      intent_id: result.intent_id,
      intent_type: request.intent_type,
      intent_scope: request.intent_scope,
      description: request.description,
      constraints: request.constraints || {},
      active_from: request.active_from,
      active_until: request.active_until,
      status: result.status,
      created_at: new Date().toISOString()
    };
    this.declaredIntentsByUserId.set(user_id, [nextRecord, ...existing]);
    this.persistDeclaredIntents();
    if (this.userProfile?.user_id === user_id) {
      this.userProfile = this.mergeDeclaredIntents(this.userProfile);
    }
    return result;
  }

  /**
   * Create intent branch for research context isolation
   */
  async createIntentBranch(params: {
    branch_name: string;
    description: string;
    inherit_from?: string;
    overrides?: Record<string, any>;
  }): Promise<{ branch_id: string; status: string; created_at: string }> {
    const result = await sspClient.call('sspCreateIntentBranch', params);
    if (result.branch_id) {
      await this.switchIntentContext(result.branch_id);
      this.currentBranch = {
        branch_id: result.branch_id,
        branch_name: params.branch_name,
        description: params.description,
        user_id: 'current_user',
        parent_branch_id: params.inherit_from,
        created_at: result.created_at,
        status: result.status,
        overrides: params.overrides || {}
      };
    }
    return result;
  }

  /**
   * Switch active intent context
   */
  async switchIntentContext(branch_id: string): Promise<{
    previous_branch_id?: string;
    current_branch_id: string;
    overrides_applied: Record<string, any>;
  }> {
    const result = await sspClient.call('sspSwitchIntentContext', { branch_id });
    this.currentBranch = {
      branch_id: result.current_branch_id,
      branch_name: '', // Would fetch full details separately
      description: '',
      user_id: 'current_user',
      created_at: new Date().toISOString(),
      status: 'active',
      overrides: result.overrides_applied
    };
    return result;
  }

  async clearIntentContext(): Promise<void> {
    await sspClient.call('sspSwitchIntentContext', { branch_id: '' });
    this.currentBranch = null;
  }

  /**
   * Query user intent profile
   */
  async queryIntentProfile(user_id: string, detail_level: 'summary' | 'full' = 'full'): Promise<UserIntentProfile> {
    const result = await sspClient.call('sspQueryIntentProfile', { user_id, detail_level });
    this.userProfile = this.mergeDeclaredIntents(result.profile);
    return this.userProfile;
  }

  /**
   * Parse freeform intent text into structured intent metadata.
   */
  async parseUserIntent(params: {
    workspace_id: string;
    user_id: string;
    message: string;
    owner_id?: string;
    intent_context?: string;
  }): Promise<ParsedIntentResult> {
    const result = await sspClient.parseUserIntent(params);
    return result.parsed_intent as ParsedIntentResult;
  }

  /**
   * Get smart review queue prioritized by intent
   */
  async getSuggestedReviewQueue(params: {
    workspace_id: string;
    strategy?: 'intent_aligned' | 'confidence_based' | 'temporal';
    limit?: number;
  }): Promise<{ review_items: any[]; total_pending: number; estimated_total_time: string }> {
    return sspClient.call('sspSuggestReviewQueue', {
      strategy: params.strategy || 'intent_aligned',
      limit: params.limit || 10,
      workspace_id: params.workspace_id
    });
  }

  /**
   * Apply learned intent pattern to batch resolve conflicts
   */
  async applyIntentPattern(params: {
    pattern_id: string;
    scope: Record<string, any>;
    dry_run?: boolean;
  }): Promise<{
    conflicts_resolved: number;
    assertions_locked: number;
    pattern_confidence: number;
    user_review_recommended: boolean;
  }> {
    return sspClient.call('sspApplyIntentPattern', { ...params, dry_run: params.dry_run ?? true });
  }

  /**
   * Intent-aware natural language query
   */
  async queryByIntent(params: {
    query: string;
    intent_context?: string;
    workspace_id?: string;
  }): Promise<{ papers: any[]; summary: string }> {
    return sspClient.call('sspQueryByIntent', {
      query: params.query,
      intent_context: params.intent_context || this.currentBranch?.branch_id,
      workspace_id: params.workspace_id
    });
  }

  /**
   * Get current active branch
   */
  getCurrentBranch(): IntentBranch | null {
    return this.currentBranch;
  }

  /**
   * Get cached user profile
   */
  getUserProfile(): UserIntentProfile | null {
    return this.userProfile;
  }

  /**
   * Set confidence threshold for AI suggestions
   */
  async setConfidenceThreshold(threshold: number): Promise<void> {
    // Would persist to backend user settings
    if (this.userProfile) {
      this.userProfile.confidence_threshold = threshold;
    }
  }

  /**
   * Delete learned intent pattern
   */
  async deletePattern(pattern_id: string): Promise<void> {
    let changed = false;
    for (const [userId, intents] of this.declaredIntentsByUserId.entries()) {
      const filtered = intents.filter(intent => intent.intent_id !== pattern_id);
      if (filtered.length !== intents.length) {
        this.declaredIntentsByUserId.set(userId, filtered);
        changed = true;
      }
    }
    if (changed) {
      this.persistDeclaredIntents();
    }
  }

  canDeletePattern(patternId: string): boolean {
    return Array.from(this.declaredIntentsByUserId.values())
      .some(intents => intents.some(intent => intent.intent_id === patternId));
  }
}

export const intentService = new IntentService();

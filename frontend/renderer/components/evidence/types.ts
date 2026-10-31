/**
 * Evidence Verification Types
 * Implements Tier 3 HITL correction workflow from Section 1.3
 */

export type VerificationStatus = 
  | 'raw'                    // Machine-extracted, never touched by human
  | 'under_correction'       // Human actively editing (locked by UI)
  | 'pending_verification'   // Edited, awaiting review by different arbitrator
  | 'verified'               // Approved as correct (can be reopened)
  | 'rejected';              // Marked as unusable (corrupted OCR, wrong extraction)

export type EvidenceAction = 'verify' | 'correct' | 'reject' | 'request_review' | 'restore';

export interface EvidenceModification {
  old_text: string;
  new_text: string;
  change_notes?: string;
}

export interface IntentMetadata {
  intent_type: 'correction';  // Always correction for Tier 3
  intent_scope: 'local';      // Local to this chunk
  confidence_override?: number; // User's confidence in correction (0.0-1.0)
  tags?: string[];            // e.g., ["ocr_error", "formula_fix"]
}

export interface EvidenceRevision {
  version: number;
  timestamp: string;
  user_id: string;
  status: VerificationStatus;
  modifications?: EvidenceModification;
  notes?: string;
}

export interface Evidence {
  id: string;
  type: 'chunk' | 'formula';
  paper_id: string;
  raw_text?: string;          // For ChunkNode
  latex_string?: string;      // For FormulaNode
  bounding_box: {
    page: number;
    coordinate_precision?: string;
    box: [number, number, number, number]; // [x1, y1, x2, y2]
  };
  verification_status: VerificationStatus;
  confidence_score: number;
  last_modified_by?: string;
  last_modified_at?: string;
  modification_count: number;
  supporting_assertion_id?: string;
  revisions?: EvidenceRevision[];
}

export interface EvidenceVerificationRequest {
  evidence_id: string;
  action: EvidenceAction;
  modifications?: EvidenceModification;
  new_status?: VerificationStatus;
  intent_metadata: IntentMetadata;
}

export interface EvidenceBatchOperation {
  evidence_ids: string[];
  action: 'verify' | 'reject';
  intent_metadata: IntentMetadata;
}

export interface EvidenceFilter {
  status?: VerificationStatus[];
  confidence_range?: [number, number];
  paper_id?: string;
  show_only_needs_review?: boolean;
}

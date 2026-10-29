/**
 * Evidence Module
 * Exports all evidence-related components and types
 */

export { default as EvidenceCard } from './EvidenceCard';
export { default as EvidenceInspector } from './EvidenceInspector';
export { default as EvidenceEditor } from './EvidenceEditor';
export { default as EvidenceHistory } from './EvidenceHistory';
export { default as EvidenceReviewQueue } from './EvidenceReviewQueue';

export type {
  Evidence,
  EvidenceAction,
  EvidenceModification,
  EvidenceRevision,
  EvidenceVerificationRequest,
  EvidenceBatchOperation,
  EvidenceFilter,
  IntentMetadata,
  VerificationStatus
} from './types';

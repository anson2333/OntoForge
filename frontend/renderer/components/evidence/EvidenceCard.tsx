/**
 * EvidenceCard Component
 * Displays individual evidence item with verification actions
 */

import { useState } from 'react';
import { Evidence, EvidenceAction, VerificationStatus } from './types';
import './EvidenceCard.css';

interface EvidenceCardProps {
  evidence: Evidence;
  onAction: (evidenceId: string, action: EvidenceAction) => void;
  onEdit: (evidenceId: string) => void;
  onViewHistory: (evidenceId: string) => void;
  isSelected?: boolean;
  onSelect?: (evidenceId: string, selected: boolean) => void;
}

export default function EvidenceCard({
  evidence,
  onAction,
  onEdit,
  onViewHistory,
  isSelected = false,
  onSelect
}: EvidenceCardProps) {
  const [showFullText, setShowFullText] = useState(false);

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.9) return 'high';
    if (confidence >= 0.7) return 'medium';
    return 'low';
  };

  const getStatusBadge = (status: VerificationStatus) => {
    const badges = {
      raw: { icon: '📥', label: 'Raw', color: 'gray' },
      under_correction: { icon: '✏️', label: 'Editing', color: 'blue' },
      pending_verification: { icon: '⏳', label: 'Pending Review', color: 'yellow' },
      verified: { icon: '✓', label: 'Verified', color: 'green' },
      rejected: { icon: '✗', label: 'Rejected', color: 'red' }
    };
    return badges[status];
  };

  const getActionButtons = () => {
    switch (evidence.verification_status) {
      case 'raw':
        return (
          <>
            <button className="action-btn verify" onClick={() => onAction(evidence.id, 'verify')}>
              ✓ Verify
            </button>
            <button className="action-btn correct" onClick={() => onEdit(evidence.id)}>
              ✏️ Correct
            </button>
            <button className="action-btn reject" onClick={() => onAction(evidence.id, 'reject')}>
              ✗ Reject
            </button>
          </>
        );
      case 'under_correction':
        return (
          <div className="editing-notice">
            <span className="lock-icon">🔒</span>
            <span>Currently being edited...</span>
          </div>
        );
      case 'pending_verification':
        return (
          <>
            <button className="action-btn verify" onClick={() => onAction(evidence.id, 'verify')}>
              ✓ Approve
            </button>
            <button className="action-btn correct" onClick={() => onEdit(evidence.id)}>
              ✏️ Changes
            </button>
            <button className="action-btn reject" onClick={() => onAction(evidence.id, 'reject')}>
              ✗ Reject
            </button>
          </>
        );
      case 'verified':
        return (
          <>
            <button className="action-btn secondary" onClick={() => onEdit(evidence.id)}>
              🔓 Reopen
            </button>
            <button className="action-btn secondary" onClick={() => onAction(evidence.id, 'request_review')}>
              Flag
            </button>
          </>
        );
      case 'rejected':
        return (
          <>
            <button className="action-btn restore" onClick={() => onAction(evidence.id, 'restore')}>
              ♻️ Restore
            </button>
          </>
        );
    }
  };

  const badge = getStatusBadge(evidence.verification_status);
  const confidenceColor = getConfidenceColor(evidence.confidence_score);
  const needsReview = evidence.confidence_score < 0.7;

  const displayText = evidence.type === 'chunk' 
    ? evidence.raw_text 
    : evidence.latex_string;
  
  const truncatedText = !showFullText && displayText && displayText.length > 150
    ? displayText.substring(0, 150) + '...'
    : displayText;

  return (
    <div className={`evidence-card confidence-${confidenceColor} ${isSelected ? 'selected' : ''}`}>
      <div className="evidence-card-layout">
        <div className="evidence-card-main">
          {/* Header */}
          <div className="evidence-card-header">
            <div className="evidence-card-title">
              {onSelect && (
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(e) => onSelect(evidence.id, e.target.checked)}
                  className="evidence-checkbox"
                />
              )}
              <span className="evidence-type-icon">
                {evidence.type === 'chunk' ? '📄' : '📐'}
              </span>
              <span className="evidence-id">
                {evidence.type === 'chunk' ? 'Chunk' : 'Formula'} #{evidence.id.split('_').pop() || evidence.id.split('#')[1] || 'N/A'}
              </span>
              <span className="evidence-location">
                Page {evidence.bounding_box.page}
              </span>
            </div>
            <div className="evidence-badges">
              <span className={`confidence-badge confidence-${confidenceColor}`}>
                {(evidence.confidence_score * 100).toFixed(0)}%
              </span>
              <span className={`status-badge status-${badge.color}`}>
                {badge.icon} {badge.label}
              </span>
              {needsReview && (
                <span className="warning-badge">Low confidence</span>
              )}
            </div>
          </div>

      {/* Content */}
      <div className="evidence-content">
        <div className="evidence-preview">
          <div className="text-content">
            <pre className={evidence.type === 'formula' ? 'formula-text' : 'chunk-text'}>
              {truncatedText || '(No text content available)'}
            </pre>
            {displayText && displayText.length > 150 && (
              <button 
                className="toggle-text-btn"
                onClick={() => setShowFullText(!showFullText)}
              >
                {showFullText ? '▲ Show Less' : '▼ Show More'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Metadata */}
      {evidence.supporting_assertion_id && (
        <div className="evidence-metadata">
          <span className="metadata-label">Supporting:</span>
          <span className="metadata-value">{evidence.supporting_assertion_id}</span>
        </div>
      )}
      
      {evidence.modification_count > 0 && (
        <div className="evidence-metadata">
          <span className="metadata-label">Modified:</span>
          <span className="metadata-value">
            {evidence.modification_count} time(s)
          </span>
          {evidence.last_modified_by && (
            <>
              <span className="metadata-separator">|</span>
              <span className="metadata-value">
                Last by: {evidence.last_modified_by} on {evidence.last_modified_at}
              </span>
            </>
          )}
          <button className="history-btn" onClick={() => onViewHistory(evidence.id)}>
            📜 View History
          </button>
        </div>
      )}
        </div>

        {/* Actions */}
        <div className="evidence-actions">
          {getActionButtons()}
        </div>
      </div>
    </div>
  );
}

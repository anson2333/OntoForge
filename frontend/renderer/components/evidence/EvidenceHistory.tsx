/**
 * EvidenceHistory Component
 * Displays revision history with diff view
 */

import { Evidence } from './types';
import './EvidenceHistory.css';

interface EvidenceHistoryProps {
  evidence: Evidence;
  onClose: () => void;
  onRestore: (version: number) => void;
}

export default function EvidenceHistory({ evidence, onClose, onRestore }: EvidenceHistoryProps) {
  const revisions = evidence.revisions || [];

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { icon: string; label: string; color: string }> = {
      raw: { icon: '📥', label: 'Raw', color: 'gray' },
      under_correction: { icon: '✏️', label: 'Editing', color: 'blue' },
      pending_verification: { icon: '⏳', label: 'Pending Review', color: 'yellow' },
      verified: { icon: '✓', label: 'Verified', color: 'green' },
      rejected: { icon: '✗', label: 'Rejected', color: 'red' }
    };
    return badges[status] || { icon: '?', label: status, color: 'gray' };
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div className="evidence-history-overlay">
      <div className="evidence-history-modal">
        {/* Header */}
        <div className="history-header">
          <h3>
            Revision History: {evidence.type === 'chunk' ? 'Chunk' : 'Formula'} #{evidence.id.split('#')[1]}
          </h3>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Content */}
        <div className="history-content">
          {revisions.length === 0 ? (
            <div className="empty-state">
              <p>No revision history available.</p>
              <p className="hint">History is recorded when evidence is modified.</p>
            </div>
          ) : (
            <div className="revision-list">
              {revisions.map((revision, index) => {
                const badge = getStatusBadge(revision.status);
                const isCurrent = index === 0;

                return (
                  <div key={revision.version} className={`revision-item ${isCurrent ? 'current' : ''}`}>
                    <div className="revision-header">
                      <div className="revision-info">
                        <span className="revision-version">
                          v{revision.version} {isCurrent && <span className="current-badge">(Current)</span>}
                        </span>
                        <span className="revision-timestamp">
                          {formatTimestamp(revision.timestamp)}
                        </span>
                        <span className="revision-user">
                          by {revision.user_id}
                        </span>
                      </div>
                      <div className="revision-status">
                        <span className={`status-badge status-${badge.color}`}>
                          {badge.icon} {badge.label}
                        </span>
                      </div>
                    </div>

                    {revision.modifications && (
                      <div className="revision-changes">
                        <div className="change-notes">
                          {revision.notes && (
                            <p className="notes">
                              <strong>Notes:</strong> {revision.notes}
                            </p>
                          )}
                          <p className="change-summary">
                            "{revision.modifications.change_notes || 'Manual correction'}"
                          </p>
                        </div>

                        <div className="diff-view">
                          <div className="diff-section diff-removed">
                            <strong>- Previous:</strong>
                            <pre>{revision.modifications.old_text}</pre>
                          </div>
                          <div className="diff-section diff-added">
                            <strong>+ Updated:</strong>
                            <pre>{revision.modifications.new_text}</pre>
                          </div>
                        </div>
                      </div>
                    )}

                    {revision.status === 'raw' && index === revisions.length - 1 && (
                      <div className="initial-extraction">
                        <p>📥 Initial extraction (machine-generated)</p>
                        <p className="confidence">
                          Confidence: {(evidence.confidence_score * 100).toFixed(0)}%
                        </p>
                      </div>
                    )}

                    {!isCurrent && (
                      <div className="revision-actions">
                        <button
                          className="restore-btn"
                          onClick={() => {
                            if (confirm(`Restore to version ${revision.version}?`)) {
                              onRestore(revision.version);
                            }
                          }}
                        >
                          ♻️ Restore to v{revision.version}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="history-footer">
          <div className="history-stats">
            <span>Total Revisions: {revisions.length}</span>
            <span>Total Modifications: {evidence.modification_count}</span>
          </div>
          <button className="close-footer-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

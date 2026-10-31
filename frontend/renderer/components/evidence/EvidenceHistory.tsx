import { t, getLocale } from '../../i18n';
/**
 * EvidenceHistory Component
 * Displays revision history with diff view
 */

import { useState } from 'react';
import { Evidence, EvidenceRevision } from './types';
import './EvidenceHistory.css';

interface EvidenceHistoryProps {
  evidence: Evidence;
  onClose: () => void;
  onRestore: (revision: EvidenceRevision, restoredText: string) => Promise<void>;
}

export default function EvidenceHistory({ evidence, onClose, onRestore }: EvidenceHistoryProps) {
  const revisions = evidence.revisions || [];
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null);

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { icon: string; label: string; color: string }> = {
      raw: { icon: '📥', label: t('Raw'), color: 'gray' },
      under_correction: { icon: '✏️', label: t("Editing"), color: 'blue' },
      pending_verification: { icon: '⏳', label: t("Pending Review"), color: 'yellow' },
      verified: { icon: '✓', label: t('Verified'), color: 'green' },
      rejected: { icon: '✗', label: t("Rejected"), color: 'red' }
    };
    return badges[status] || { icon: '?', label: status, color: 'gray' };
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString(getLocale());
  };

  return (
    <div className="evidence-history-overlay">
      <div className="evidence-history-modal">
        {/* Header */}
        <div className="history-header">
          <h3>
            {t("Revision History:")} {evidence.type === 'chunk' ? t("Chunk") : t("Formula")} #{evidence.id.split('#')[1]}
          </h3>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Content */}
        <div className="history-content">
          {revisions.length === 0 ? (
            <div className="empty-state">
              <p>{t("No revision history available.")}</p>
              <p className="hint">{t("History is recorded when evidence is modified.")}</p>
            </div>
          ) : (
            <div className="revision-list">
              {revisions.map((revision, index) => {
                const badge = getStatusBadge(revision.status);
                const isCurrent = index === 0;
                const restoredText = revision.modifications?.new_text
                  ?? revisions[index - 1]?.modifications?.old_text;

                return (
                  <div key={revision.version} className={`revision-item ${isCurrent ? 'current' : ''}`}>
                    <div className="revision-header">
                      <div className="revision-info">
                        <span className="revision-version">
                          v{revision.version} {isCurrent && <span className="current-badge">{t("(Current)")}</span>}
                        </span>
                        <span className="revision-timestamp">
                          {formatTimestamp(revision.timestamp)}
                        </span>
                        <span className="revision-user">
                          {t("by")} {revision.user_id}
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
                              <strong>{t("Notes:")}</strong> {revision.notes}
                            </p>
                          )}
                          <p className="change-summary">
                            "{revision.modifications.change_notes || t("Manual correction")}"
                          </p>
                        </div>

                        <div className="diff-view">
                          <div className="diff-section diff-removed">
                            <strong>{t("- Previous:")}</strong>
                            <pre>{revision.modifications.old_text}</pre>
                          </div>
                          <div className="diff-section diff-added">
                            <strong>{t("+ Updated:")}</strong>
                            <pre>{revision.modifications.new_text}</pre>
                          </div>
                        </div>
                      </div>
                    )}

                    {revision.status === 'raw' && index === revisions.length - 1 && (
                      <div className="initial-extraction">
                        <p>{t("📥 Initial extraction (machine-generated)")}</p>
                        <p className="confidence">
                          {t("Confidence:")} {(evidence.confidence_score * 100).toFixed(0)}%
                        </p>
                      </div>
                    )}

                    {!isCurrent && (
                      <div className="revision-actions">
                        <button
                          className="restore-btn"
                          disabled={!restoredText || restoringVersion !== null}
                          title={restoredText ? undefined : t("This revision does not contain restorable text")}
                          onClick={async () => {
                            if (!restoredText || !confirm(t('Restore to version {version}?', { version: revision.version }))) return;
                            setRestoringVersion(revision.version);
                            try {
                              await onRestore(revision, restoredText);
                            } finally {
                              setRestoringVersion(null);
                            }
                          }}
                        >
                          {restoringVersion === revision.version
                            ? t("Restoring...")
                            : t('Restore to v{version}', { version: revision.version })}
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
            <span>{t("Total Revisions:")} {revisions.length}</span>
            <span>{t("Total Modifications:")} {evidence.modification_count}</span>
          </div>
          <button className="close-footer-btn" onClick={onClose}>
            {t("Close")}
          </button>
        </div>
      </div>
    </div>
  );
}

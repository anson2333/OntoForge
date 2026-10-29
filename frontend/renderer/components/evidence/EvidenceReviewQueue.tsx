/**
 * EvidenceReviewQueue Component
 * Priority review queue for evidence needing attention
 */

import { useMemo } from 'react';
import { Evidence } from './types';
import './EvidenceReviewQueue.css';

interface EvidenceReviewQueueProps {
  evidenceList: Evidence[];
  onReview: (evidenceId: string) => void;
}

export interface QueueItem {
  evidence: Evidence;
  priority: 'high' | 'medium' | 'low';
  reason: string;
}

export function getReviewQueueItem(evidence: Evidence): QueueItem | null {
  // Low confidence items (highest priority)
  if (evidence.verification_status === 'raw' && evidence.confidence_score < 0.7) {
    return {
      evidence,
      priority: 'high',
      reason: `Low confidence: ${(evidence.confidence_score * 100).toFixed(0)}%`
    };
  }

  // Pending verification items
  if (evidence.verification_status === 'pending_verification') {
    return {
      evidence,
      priority: 'medium',
      reason: 'Edited, needs review'
    };
  }

  // Recently modified but unverified
  if (
    evidence.verification_status === 'under_correction' ||
    (evidence.modification_count > 0 && evidence.verification_status === 'raw')
  ) {
    return {
      evidence,
      priority: 'medium',
      reason: 'Modified, unverified'
    };
  }

  // Medium confidence items (lower priority)
  if (
    evidence.verification_status === 'raw' &&
    evidence.confidence_score >= 0.7 &&
    evidence.confidence_score < 0.85
  ) {
    return {
      evidence,
      priority: 'low',
      reason: `Medium confidence: ${(evidence.confidence_score * 100).toFixed(0)}%`
    };
  }

  return null;
}

export default function EvidenceReviewQueue({ evidenceList, onReview }: EvidenceReviewQueueProps) {
  const queueItems = useMemo(() => {
    const items: QueueItem[] = [];

    evidenceList.forEach(evidence => {
      const item = getReviewQueueItem(evidence);
      if (item) items.push(item);
    });

    // Sort by priority
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    items.sort((a, b) => {
      const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
      if (priorityDiff !== 0) return priorityDiff;
      // Within same priority, sort by confidence (lower first)
      return a.evidence.confidence_score - b.evidence.confidence_score;
    });

    return items;
  }, [evidenceList]);

  const stats = useMemo(() => {
    return {
      high: queueItems.filter(item => item.priority === 'high').length,
      medium: queueItems.filter(item => item.priority === 'medium').length,
      low: queueItems.filter(item => item.priority === 'low').length,
      total: queueItems.length
    };
  }, [queueItems]);

  const getPriorityIcon = (priority: string) => {
    switch (priority) {
      case 'high': return '🔴';
      case 'medium': return '🟡';
      case 'low': return '🟢';
      default: return '⚪';
    }
  };

  const getPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'high': return 'High Priority';
      case 'medium': return 'Medium Priority';
      case 'low': return 'Low Priority';
      default: return priority;
    }
  };

  return (
    <div className="evidence-review-queue">
      {/* Header */}
      <div className="queue-header">
        <h3>🔍 Review Queue</h3>
        <div className="queue-stats">
          <span className="stat high">
            🔴 High: <strong>{stats.high}</strong>
          </span>
          <span className="stat medium">
            🟡 Medium: <strong>{stats.medium}</strong>
          </span>
          <span className="stat low">
            🟢 Low: <strong>{stats.low}</strong>
          </span>
          <span className="stat total">
            Total: <strong>{stats.total}</strong>
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="queue-content">
        {queueItems.length === 0 ? (
          <div className="empty-queue">
            <div className="success-icon">✓</div>
            <h4>All Caught Up!</h4>
            <p>No evidence items need your attention right now.</p>
          </div>
        ) : (
          <div className="queue-list">
            {queueItems.map(item => (
              <div
                key={item.evidence.id}
                className={`queue-item priority-${item.priority}`}
              >
                <div className="queue-item-layout">
                  <div className="queue-item-main">
                    <div className="item-header">
                      <div className="item-info">
                        <span className="priority-badge">
                          {getPriorityIcon(item.priority)} {getPriorityLabel(item.priority)}
                        </span>
                        <span className="item-title">
                          {item.evidence.type === 'chunk' ? '📄' : '📐'}{' '}
                          {item.evidence.type === 'chunk' ? 'Chunk' : 'Formula'} #{item.evidence.id.split('#')[1]}
                        </span>
                        <span className="item-location">
                          Page {item.evidence.bounding_box.page}
                        </span>
                        <span className="reason-chip">
                          {item.reason}
                        </span>
                      </div>
                      <div className="item-confidence">
                        <span className={`confidence-indicator confidence-${
                          item.evidence.confidence_score >= 0.85 ? 'high' :
                          item.evidence.confidence_score >= 0.7 ? 'medium' : 'low'
                        }`}>
                          {(item.evidence.confidence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    {item.evidence.supporting_assertion_id && (
                      <div className="item-metadata">
                        <span className="metadata-label">Supporting:</span>
                        <span className="metadata-value">{item.evidence.supporting_assertion_id}</span>
                      </div>
                    )}

                    <div className="item-preview">
                      <pre>
                        {(item.evidence.type === 'chunk' 
                          ? item.evidence.raw_text 
                          : item.evidence.latex_string
                        )?.substring(0, 150)}...
                      </pre>
                    </div>
                  </div>

                  <div className="item-actions">
                    <button
                      className="review-btn"
                      onClick={() => onReview(item.evidence.id)}
                    >
                      Review Now →
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

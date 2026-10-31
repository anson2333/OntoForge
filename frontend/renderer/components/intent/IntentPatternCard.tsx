import { t, uiLabel, getLocale } from '../../i18n';
/**
 * Intent Pattern Card
 * Display individual learned pattern with metadata
 */

import React from 'react';
import { IntentPattern } from '../../services/intent_service';

interface IntentPatternCardProps {
  pattern: IntentPattern;
  onApply?: (patternId: string) => void;
  onDelete?: (patternId: string) => void;
  compact?: boolean;
}

export const IntentPatternCard: React.FC<IntentPatternCardProps> = ({
  pattern,
  onApply,
  onDelete,
  compact = false
}) => {
  const confidenceColor = pattern.confidence >= 0.8 ? '#4dff8a' : pattern.confidence >= 0.6 ? '#ffc04d' : '#ff6b6b';
  const confidenceLabel = pattern.confidence >= 0.8 ? t("High") : pattern.confidence >= 0.6 ? t("Medium") : t("Low");

  return (
    <div className={`intent-pattern-card ${compact ? 'compact' : ''}`}>
      <div className="pattern-header">
        <div className="pattern-meta">
          <span className="pattern-type-badge">{uiLabel(pattern.intent_type)}</span>
          <span className="pattern-id">{pattern.pattern_id}</span>
        </div>
        <div className="pattern-confidence-badge" style={{ color: confidenceColor }}>
          <span className="confidence-label">{confidenceLabel}</span>
          <span className="confidence-value">{(pattern.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>

      <div className="pattern-description">
        {pattern.description}
      </div>

      {!compact && (
        <>
          <div className="pattern-stats-grid">
            <div className="stat">
              <span className="stat-label">{t("Applications")}</span>
              <span className="stat-value">{pattern.applications}</span>
            </div>
            <div className="stat">
              <span className="stat-label">{t("Similar Arbitrations")}</span>
              <span className="stat-value">{pattern.matched_arbitrator_ids.length}</span>
            </div>
            <div className="stat">
              <span className="stat-label">{t("Last Used")}</span>
              <span className="stat-value">
                {new Date(pattern.last_used).toLocaleDateString(getLocale())}
              </span>
            </div>
          </div>

          {pattern.matched_arbitrator_ids.length > 0 && (
            <div className="matched-arbitrations">
              <span className="section-label">{t("Based on arbitrations:")}</span>
              <div className="arbitration-ids">
                {pattern.matched_arbitrator_ids.slice(0, 3).map((id) => (
                  <span key={id} className="arbitration-id" title={id}>
                    {id.substring(0, 8)}...
                  </span>
                ))}
                {pattern.matched_arbitrator_ids.length > 3 && (
                  <span className="more-count">+{pattern.matched_arbitrator_ids.length - 3} {t("more")}</span>
                )}
              </div>
            </div>
          )}
        </>
      )}

      <div className="pattern-actions">
        {onApply && (
          <button
            className="action-btn primary"
            onClick={() => onApply(pattern.pattern_id)}
            title={t("Apply this pattern to similar conflicts")}
          >
            {t("Apply Pattern")}
          </button>
        )}
        {onDelete && (
          <button
            className="action-btn secondary"
            onClick={() => onDelete(pattern.pattern_id)}
            title={t("Remove this learned pattern")}
          >
            {t("Delete")}
          </button>
        )}
      </div>

      <style>{`
        .intent-pattern-card {
          background: #1e1e1e;
          border: 1px solid #444;
          border-radius: 6px;
          padding: 16px;
          transition: all 0.2s;
        }

        .intent-pattern-card:hover {
          border-color: #007acc;
          box-shadow: 0 2px 8px rgba(0, 122, 204, 0.2);
        }

        .intent-pattern-card.compact {
          padding: 12px;
        }

        .pattern-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 12px;
        }

        .pattern-meta {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .pattern-type-badge {
          padding: 4px 10px;
          background: #1e3a5f;
          color: #4da6ff;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .pattern-id {
          font-family: monospace;
          font-size: 12px;
          color: #888;
        }

        .pattern-confidence-badge {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 2px;
        }

        .confidence-label {
          font-size: 11px;
          text-transform: uppercase;
          font-weight: 600;
          letter-spacing: 0.5px;
        }

        .confidence-value {
          font-size: 16px;
          font-weight: 700;
        }

        .pattern-description {
          color: #ddd;
          line-height: 1.5;
          margin-bottom: 16px;
          font-size: 14px;
        }

        .pattern-stats-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          margin-bottom: 16px;
          padding: 12px;
          background: #1a1a1a;
          border-radius: 4px;
        }

        .stat {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .stat-label {
          font-size: 11px;
          color: #888;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .stat-value {
          font-size: 16px;
          font-weight: 600;
          color: #fff;
        }

        .matched-arbitrations {
          margin-bottom: 16px;
        }

        .section-label {
          display: block;
          font-size: 12px;
          color: #888;
          margin-bottom: 8px;
        }

        .arbitration-ids {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .arbitration-id {
          padding: 4px 8px;
          background: #2a2a2a;
          border: 1px solid #444;
          border-radius: 3px;
          font-family: monospace;
          font-size: 11px;
          color: #888;
          cursor: help;
        }

        .more-count {
          padding: 4px 8px;
          color: #888;
          font-size: 11px;
          font-style: italic;
        }

        .pattern-actions {
          display: flex;
          gap: 8px;
        }

        .action-btn {
          flex: 1;
          padding: 10px 16px;
          border: none;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .action-btn.primary {
          background: #007acc;
          color: #fff;
        }

        .action-btn.primary:hover {
          background: #005a9e;
        }

        .action-btn.secondary {
          background: #444;
          color: #fff;
        }

        .action-btn.secondary:hover {
          background: #d73a49;
        }

        .compact .pattern-stats-grid,
        .compact .matched-arbitrations {
          display: none;
        }

        .compact .pattern-description {
          margin-bottom: 12px;
          font-size: 13px;
        }

        .compact .action-btn {
          padding: 8px 12px;
          font-size: 12px;
        }
      `}</style>
    </div>
  );
};

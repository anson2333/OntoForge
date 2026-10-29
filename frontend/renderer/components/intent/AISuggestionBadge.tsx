/**
 * AI Suggestion Badge
 * Visual indicator for AI-suggested conflict resolutions
 */

import React, { useState } from 'react';
import { AISuggestion } from '../../services/intent_service';

interface AISuggestionBadgeProps {
  suggestion: AISuggestion;
  onAccept?: () => void;
  onReject?: () => void;
  inline?: boolean;
}

export const AISuggestionBadge: React.FC<AISuggestionBadgeProps> = ({
  suggestion,
  onAccept,
  onReject,
  inline = false
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const confidenceColor = suggestion.confidence >= 0.8 ? '#4dff8a' : 
                         suggestion.confidence >= 0.6 ? '#ffc04d' : '#ff6b6b';
  
  const confidenceLevel = suggestion.confidence >= 0.8 ? 'High' : 
                          suggestion.confidence >= 0.6 ? 'Medium' : 'Low';

  const handleAccept = async () => {
    setIsProcessing(true);
    try {
      if (onAccept) {
        await onAccept();
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    setIsProcessing(true);
    try {
      if (onReject) {
        await onReject();
      }
    } finally {
      setIsProcessing(false);
    }
  };

  if (inline) {
    return (
      <span className="ai-suggestion-badge inline" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="badge-icon">🤖</span>
        <span className="badge-text">AI Suggested</span>
        <span className="confidence-indicator" style={{ color: confidenceColor }}>
          {(suggestion.confidence * 100).toFixed(0)}%
        </span>
      </span>
    );
  }

  return (
    <div className={`ai-suggestion-badge ${isExpanded ? 'expanded' : ''}`}>
      <div className="badge-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="badge-icon-large">🤖</div>
        <div className="badge-content">
          <div className="badge-title">
            <span>AI-Suggested Resolution</span>
            <span className="confidence-badge" style={{ backgroundColor: confidenceColor }}>
              {confidenceLevel} ({(suggestion.confidence * 100).toFixed(0)}%)
            </span>
          </div>
          <div className="badge-subtitle">
            Based on {suggestion.matched_intent_patterns.length} learned pattern(s)
          </div>
        </div>
        <button className="expand-btn" aria-label="Expand suggestion">
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      {isExpanded && (
        <div className="badge-details">
          <div className="detail-section">
            <h4>Reasoning</h4>
            <p className="reasoning-text">{suggestion.reasoning}</p>
          </div>

          {suggestion.matched_intent_patterns.length > 0 && (
            <div className="detail-section">
              <h4>Matched Patterns</h4>
              <div className="pattern-chips">
                {suggestion.matched_intent_patterns.map((patternId) => (
                  <span key={patternId} className="pattern-chip" title={patternId}>
                    {patternId.substring(0, 12)}...
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="detail-section">
            <h4>Recommended Assertion</h4>
            <div className="assertion-id">
              <code>{suggestion.recommended_assertion_id}</code>
            </div>
          </div>

          {suggestion.user_can_override && (
            <div className="action-section">
              <p className="override-notice">
                You can review and override this suggestion if needed.
              </p>
              <div className="action-buttons">
                <button
                  className="btn-accept"
                  onClick={handleAccept}
                  disabled={isProcessing}
                >
                  {isProcessing ? 'Applying...' : 'Accept Suggestion'}
                </button>
                <button
                  className="btn-reject"
                  onClick={handleReject}
                  disabled={isProcessing}
                >
                  {isProcessing ? 'Rejecting...' : 'Reject & Choose Manually'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <style>{`
        .ai-suggestion-badge {
          background: linear-gradient(135deg, #1e3a5f 0%, #2a2a2a 100%);
          border: 1px solid #007acc;
          border-radius: 8px;
          overflow: hidden;
          transition: all 0.3s;
        }

        .ai-suggestion-badge.expanded {
          box-shadow: 0 4px 16px rgba(0, 122, 204, 0.3);
        }

        .ai-suggestion-badge.inline {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          background: #1e3a5f;
          border: 1px solid #007acc;
          border-radius: 12px;
          font-size: 12px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .ai-suggestion-badge.inline:hover {
          background: #2a4a7f;
        }

        .badge-header {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px;
          cursor: pointer;
          transition: background 0.2s;
        }

        .badge-header:hover {
          background: rgba(255, 255, 255, 0.05);
        }

        .badge-icon {
          font-size: 14px;
        }

        .badge-icon-large {
          font-size: 32px;
          line-height: 1;
        }

        .badge-content {
          flex: 1;
        }

        .badge-title {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 4px;
          color: #fff;
          font-weight: 600;
          font-size: 14px;
        }

        .confidence-badge {
          padding: 3px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 700;
          color: #000;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .badge-subtitle {
          color: #888;
          font-size: 12px;
        }

        .badge-text {
          color: #fff;
          font-weight: 500;
        }

        .confidence-indicator {
          font-weight: 700;
          font-size: 13px;
        }

        .expand-btn {
          background: none;
          border: none;
          color: #888;
          font-size: 12px;
          cursor: pointer;
          padding: 4px 8px;
          transition: color 0.2s;
        }

        .expand-btn:hover {
          color: #fff;
        }

        .badge-details {
          padding: 0 16px 16px 16px;
          border-top: 1px solid #444;
        }

        .detail-section {
          margin-top: 16px;
        }

        .detail-section h4 {
          margin: 0 0 8px 0;
          color: #007acc;
          font-size: 13px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .reasoning-text {
          margin: 0;
          color: #ddd;
          line-height: 1.6;
          font-size: 14px;
        }

        .pattern-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .pattern-chip {
          padding: 4px 10px;
          background: #2a2a2a;
          border: 1px solid #444;
          border-radius: 4px;
          font-family: monospace;
          font-size: 11px;
          color: #888;
          cursor: help;
        }

        .assertion-id {
          padding: 12px;
          background: #1a1a1a;
          border: 1px solid #444;
          border-radius: 4px;
        }

        .assertion-id code {
          color: #4dff8a;
          font-family: monospace;
          font-size: 13px;
        }

        .action-section {
          margin-top: 20px;
          padding-top: 16px;
          border-top: 1px solid #444;
        }

        .override-notice {
          margin: 0 0 12px 0;
          color: #888;
          font-size: 12px;
          font-style: italic;
        }

        .action-buttons {
          display: flex;
          gap: 8px;
        }

        .btn-accept,
        .btn-reject {
          flex: 1;
          padding: 12px 16px;
          border: none;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-accept {
          background: #4dff8a;
          color: #000;
        }

        .btn-accept:hover:not(:disabled) {
          background: #3fe67a;
        }

        .btn-reject {
          background: #444;
          color: #fff;
        }

        .btn-reject:hover:not(:disabled) {
          background: #555;
        }

        .btn-accept:disabled,
        .btn-reject:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
};

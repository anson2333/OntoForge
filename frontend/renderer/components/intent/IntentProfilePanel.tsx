/**
 * Intent Profile Panel
 * Display learned patterns, preferences, and active goals
 */

import React, { useEffect, useState } from 'react';
import { intentService, UserIntentProfile, IntentPattern } from '../../services/intent_service';

interface IntentProfilePanelProps {
  userId: string;
  refreshToken?: number;
  onDeclareIntent?: () => void;
  onPatternClick?: (pattern: IntentPattern) => void;
}

export const IntentProfilePanel: React.FC<IntentProfilePanelProps> = ({
  userId,
  refreshToken = 0,
  onDeclareIntent,
  onPatternClick
}) => {
  const [profile, setProfile] = useState<UserIntentProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedTab, setSelectedTab] = useState<'patterns' | 'goals' | 'preferences'>('patterns');

  useEffect(() => {
    loadProfile();
  }, [userId, refreshToken]);

  const loadProfile = async () => {
    setIsLoading(true);
    try {
      const data = await intentService.queryIntentProfile(userId, 'full');
      setProfile(data);
    } catch (error) {
      console.error('Failed to load intent profile:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeletePattern = async (patternId: string) => {
    if (confirm('Delete this learned pattern?')) {
      await intentService.deletePattern(patternId);
      await loadProfile();
    }
  };

  if (isLoading) {
    return <div className="profile-panel loading">Loading profile...</div>;
  }

  if (!profile) {
    return <div className="profile-panel error">Failed to load profile</div>;
  }

  return (
    <div className="intent-profile-panel">
      <div className="panel-header">
        <div className="panel-title-row">
          <h3>Intents</h3>
          {onDeclareIntent && (
            <button
              className="declare-intent-btn"
              onClick={onDeclareIntent}
              title="Declare intent"
              aria-label="Declare intent"
            >
              +
            </button>
          )}
        </div>
        <div className="profile-stats">
          <span className="stat-item">
            <span className="stat-label">Total Intents:</span>
            <span className="stat-value">{profile.total_intents_captured}</span>
          </span>
          <span className="stat-item">
            <span className="stat-label">Patterns:</span>
            <span className="stat-value">{profile.learned_patterns.length}</span>
          </span>
          <span className="stat-item">
            <span className="stat-label">Active Goals:</span>
            <span className="stat-value">{profile.active_goals.length}</span>
          </span>
        </div>
      </div>

      <div className="panel-tabs">
        <button
          className={`tab-btn ${selectedTab === 'patterns' ? 'active' : ''}`}
          onClick={() => setSelectedTab('patterns')}
        >
          Learned Patterns ({profile.learned_patterns.length})
        </button>
        <button
          className={`tab-btn ${selectedTab === 'goals' ? 'active' : ''}`}
          onClick={() => setSelectedTab('goals')}
        >
          Active Goals ({profile.active_goals.length})
        </button>
        <button
          className={`tab-btn ${selectedTab === 'preferences' ? 'active' : ''}`}
          onClick={() => setSelectedTab('preferences')}
        >
          Preferences
        </button>
      </div>

      <div className="panel-content">
        {selectedTab === 'patterns' && (
          <div className="patterns-list">
            {profile.learned_patterns.length === 0 ? (
              <div className="empty-state">No learned patterns yet. Keep resolving conflicts to build patterns.</div>
            ) : (
              profile.learned_patterns.map((pattern) => (
                <div key={pattern.pattern_id} className="pattern-card">
                  <div className="pattern-header">
                    <span className="pattern-type">{pattern.intent_type}</span>
                    <span className="pattern-confidence">
                      {(pattern.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  <div className="pattern-description">{pattern.description}</div>
                  <div className="pattern-stats">
                    <span>Applied {pattern.applications} times</span>
                    <span>Last used: {new Date(pattern.last_used).toLocaleDateString()}</span>
                  </div>
                  <div className="pattern-actions">
                    <button
                      className="btn-apply"
                      onClick={() => onPatternClick && onPatternClick(pattern)}
                    >
                      Apply Pattern
                    </button>
                    {intentService.canDeletePattern(pattern.pattern_id) && (
                      <button
                        className="btn-delete"
                        onClick={() => handleDeletePattern(pattern.pattern_id)}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {selectedTab === 'goals' && (
          <div className="goals-list">
            {profile.active_goals.length === 0 ? (
              <div className="empty-state">No active goals. Declare an intent to create goals.</div>
            ) : (
              profile.active_goals.map((goal) => (
                <div key={goal.goal_id} className="goal-card">
                  <div className="goal-header">
                    <span className={`goal-status ${goal.status}`}>{goal.status}</span>
                    <span className="goal-dates">
                      {new Date(goal.active_from).toLocaleDateString()}
                      {goal.active_until && ` - ${new Date(goal.active_until).toLocaleDateString()}`}
                    </span>
                  </div>
                  <div className="goal-description">{goal.description}</div>
                  {Object.keys(goal.constraints).length > 0 && (
                    <div className="goal-constraints">
                      <strong>Constraints:</strong>
                      <pre>{JSON.stringify(goal.constraints, null, 2)}</pre>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {selectedTab === 'preferences' && (
          <div className="preferences-view">
            <div className="pref-section">
              <h4>Unit Preferences</h4>
              {Object.keys(profile.preferred_units).length === 0 ? (
                <div className="empty-state">No unit preferences learned yet</div>
              ) : (
                <ul className="pref-list">
                  {Object.entries(profile.preferred_units).map(([metric, unit]) => (
                    <li key={metric}>
                      <span className="pref-key">{metric}:</span>
                      <span className="pref-value">{unit}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="pref-section">
              <h4>Evidence Ranking</h4>
              {profile.evidence_ranking.length === 0 ? (
                <div className="empty-state">No evidence preferences</div>
              ) : (
                <ol className="ranking-list">
                  {profile.evidence_ranking.map((source, idx) => (
                    <li key={idx}>{source}</li>
                  ))}
                </ol>
              )}
            </div>

            <div className="pref-section">
              <h4>Subdomain Focus</h4>
              {profile.subdomain_focus.length === 0 ? (
                <div className="empty-state">No subdomain preferences</div>
              ) : (
                <div className="tag-list">
                  {profile.subdomain_focus.map((subdomain) => (
                    <span key={subdomain} className="subdomain-tag">{subdomain}</span>
                  ))}
                </div>
              )}
            </div>

            <div className="pref-section">
              <h4>AI Suggestion Threshold</h4>
              <div className="threshold-control">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={profile.confidence_threshold}
                  onChange={(e) => {
                    intentService.setConfidenceThreshold(parseFloat(e.target.value));
                  }}
                />
                <span className="threshold-value">{(profile.confidence_threshold * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        .intent-profile-panel {
          background: var(--panel-bg);
          border: 1px solid var(--border-color);
          border-radius: 8px;
          overflow: hidden;
          color: var(--text-primary);
        }

        .panel-header {
          padding: 16px;
          border-bottom: 1px solid var(--border-color);
          background: var(--panel-bg-elevated);
        }

        .panel-title-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 12px;
        }

        .panel-header h3 {
          margin: 0;
          color: var(--text-primary);
          font-size: 18px;
        }

        .declare-intent-btn {
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          background: var(--primary-color);
          color: var(--primary-text);
          border: 1px solid var(--primary-color);
          border-radius: 4px;
          cursor: pointer;
          font-size: 20px;
          font-weight: 700;
          line-height: 1;
        }

        .declare-intent-btn:hover {
          background: var(--primary-hover);
        }

        .profile-stats {
          display: flex;
          gap: 24px;
        }

        .stat-item {
          display: flex;
          gap: 8px;
          font-size: 14px;
        }

        .stat-label {
          color: var(--text-secondary);
        }

        .stat-value {
          color: var(--primary-color);
          font-weight: 600;
        }

        .panel-tabs {
          display: flex;
          border-bottom: 1px solid var(--border-color);
        }

        .tab-btn {
          flex: 1;
          padding: 12px;
          background: var(--panel-bg);
          border: none;
          border-bottom: 2px solid transparent;
          color: var(--text-secondary);
          font-size: 14px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .tab-btn:hover {
          color: var(--text-primary);
          background: var(--surface-bg-hover);
        }

        .tab-btn.active {
          color: var(--primary-color);
          border-bottom-color: var(--primary-color);
        }

        .panel-content {
          padding: 16px;
          max-height: 600px;
          overflow-y: auto;
        }

        .patterns-list,
        .goals-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .pattern-card,
        .goal-card {
          padding: 16px;
          background: var(--surface-bg);
          border: 1px solid var(--border-color);
          border-radius: 6px;
        }

        .pattern-header,
        .goal-header {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
        }

        .pattern-type,
        .goal-status {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
        }

        .pattern-type {
          background: var(--info-bg);
          color: var(--info-text);
        }

        .goal-status.active {
          background: var(--success-bg);
          color: var(--success-text);
        }

        .pattern-confidence {
          font-size: 12px;
          color: var(--text-secondary);
        }

        .pattern-description,
        .goal-description {
          color: var(--text-primary);
          margin-bottom: 8px;
          line-height: 1.5;
        }

        .pattern-stats {
          display: flex;
          gap: 16px;
          font-size: 12px;
          color: var(--text-secondary);
          margin-bottom: 12px;
        }

        .pattern-actions {
          display: flex;
          gap: 8px;
        }

        .btn-apply,
        .btn-delete {
          padding: 6px 12px;
          border-radius: 4px;
          font-size: 12px;
          border: none;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-apply {
          background: var(--primary-color);
          color: var(--primary-text);
        }

        .btn-apply:hover {
          background: var(--primary-hover);
        }

        .btn-delete {
          background: var(--surface-bg-hover);
          color: var(--text-primary);
        }

        .btn-delete:hover {
          background: var(--danger-color);
          color: white;
        }

        .goal-constraints {
          margin-top: 8px;
          padding: 8px;
          background: var(--panel-bg-muted);
          border-radius: 4px;
          font-size: 12px;
        }

        .goal-constraints pre {
          margin: 4px 0 0 0;
          color: var(--text-secondary);
          white-space: pre-wrap;
        }

        .empty-state {
          text-align: center;
          padding: 40px;
          color: var(--text-secondary);
          font-style: italic;
        }

        .preferences-view {
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        .pref-section h4 {
          margin: 0 0 12px 0;
          color: var(--text-primary);
          font-size: 14px;
        }

        .pref-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .pref-list li {
          padding: 8px 0;
          display: flex;
          justify-content: space-between;
          border-bottom: 1px solid var(--border-color);
        }

        .pref-key {
          color: var(--text-secondary);
        }

        .pref-value {
          color: var(--text-primary);
          font-weight: 500;
        }

        .ranking-list {
          padding-left: 24px;
          color: var(--text-primary);
        }

        .ranking-list li {
          padding: 4px 0;
        }

        .tag-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .subdomain-tag {
          padding: 6px 12px;
          background: var(--info-bg);
          color: var(--info-text);
          border-radius: 4px;
          font-size: 12px;
        }

        .threshold-control {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .threshold-control input[type="range"] {
          flex: 1;
        }

        .threshold-value {
          color: var(--primary-color);
          font-weight: 600;
          min-width: 50px;
          text-align: right;
        }
      `}</style>
    </div>
  );
};

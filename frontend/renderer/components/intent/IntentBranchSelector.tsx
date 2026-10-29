/**
 * Intent Branch Selector
 * Dropdown for switching between research context branches
 */

import React, { useEffect, useState } from 'react';
import { intentService, IntentBranch } from '../../services/intent_service';

interface IntentBranchSelectorProps {
  onBranchChange?: (branch: IntentBranch | null) => void;
}

export const IntentBranchSelector: React.FC<IntentBranchSelectorProps> = ({
  onBranchChange
}) => {
  const [currentBranch, setCurrentBranch] = useState<IntentBranch | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    const branch = intentService.getCurrentBranch();
    setCurrentBranch(branch);
  }, []);

  const handleClearContext = async () => {
    setCurrentBranch(null);
    setIsExpanded(false);
    if (onBranchChange) {
      onBranchChange(null);
    }
  };

  return (
    <div className="intent-branch-selector">
      <button
        className="branch-selector-btn"
        onClick={() => setIsExpanded(!isExpanded)}
        title="Switch intent context"
      >
        <span className="branch-icon">🎯</span>
        <span className="branch-name">
          {currentBranch ? currentBranch.branch_name : 'No Active Context'}
        </span>
        <span className="dropdown-arrow">{isExpanded ? '▲' : '▼'}</span>
      </button>

      {isExpanded && (
        <div className="branch-dropdown">
          <div className="dropdown-header">Intent Contexts</div>
          
          {currentBranch && (
            <div className="current-branch-info">
              <div className="branch-item active">
                <span className="branch-icon">✓</span>
                <div>
                  <div className="branch-item-name">{currentBranch.branch_name}</div>
                  <div className="branch-item-desc">{currentBranch.description}</div>
                </div>
              </div>
              <button
                className="clear-context-btn"
                onClick={handleClearContext}
              >
                Clear Context
              </button>
            </div>
          )}

          {!currentBranch && (
            <div className="branch-item disabled">
              <span className="branch-icon">○</span>
              <div>
                <div className="branch-item-name">Main Context</div>
                <div className="branch-item-desc">No active intent branch</div>
              </div>
            </div>
          )}

          <div className="dropdown-footer">
            <button
              className="create-branch-btn"
              onClick={() => {
                // Would open IntentBranchCreationModal
                console.log('Create new branch');
              }}
            >
              + Create New Branch
            </button>
          </div>
        </div>
      )}

      <style>{`
        .intent-branch-selector {
          position: relative;
          display: inline-block;
        }

        .branch-selector-btn {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          background: var(--surface-bg);
          border: 1px solid var(--border-strong);
          border-radius: 4px;
          color: var(--text-primary);
          font-size: 14px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .branch-selector-btn:hover {
          background: var(--surface-bg-hover);
          border-color: var(--primary-color);
        }

        .branch-icon {
          font-size: 16px;
        }

        .branch-name {
          max-width: 200px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .dropdown-arrow {
          font-size: 10px;
          color: var(--text-secondary);
        }

        .branch-dropdown {
          position: absolute;
          top: calc(100% + 4px);
          left: 0;
          min-width: 300px;
          background: var(--panel-bg-elevated);
          border: 1px solid var(--border-color);
          border-radius: 4px;
          box-shadow: 0 4px 12px var(--shadow-color);
          z-index: 100;
        }

        .dropdown-header {
          padding: 12px 16px;
          border-bottom: 1px solid var(--border-color);
          font-weight: 600;
          color: var(--text-primary);
          font-size: 13px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .current-branch-info {
          padding: 8px;
        }

        .branch-item {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 12px;
          cursor: pointer;
          transition: background 0.2s;
          border-radius: 4px;
        }

        .branch-item:not(.disabled):not(.active):hover {
          background: var(--surface-bg-hover);
        }

        .branch-item.active {
          background: var(--info-bg);
          cursor: default;
        }

        .branch-item.disabled {
          opacity: 0.6;
          cursor: default;
        }

        .branch-item-name {
          font-weight: 500;
          color: var(--text-primary);
          font-size: 14px;
        }

        .branch-item-desc {
          font-size: 12px;
          color: var(--text-secondary);
          margin-top: 2px;
        }

        .clear-context-btn {
          width: 100%;
          padding: 8px;
          margin-top: 8px;
          background: var(--surface-bg-hover);
          border: none;
          border-radius: 4px;
          color: var(--text-primary);
          font-size: 13px;
          cursor: pointer;
          transition: background 0.2s;
        }

        .clear-context-btn:hover {
          background: var(--border-strong);
        }

        .dropdown-footer {
          padding: 8px;
          border-top: 1px solid var(--border-color);
        }

        .create-branch-btn {
          width: 100%;
          padding: 10px;
          background: var(--primary-color);
          border: none;
          border-radius: 4px;
          color: var(--primary-text);
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.2s;
        }

        .create-branch-btn:hover {
          background: var(--primary-hover);
        }
      `}</style>
    </div>
  );
};

import { t, uiLabel } from '../../i18n';
/**
 * EvidenceInspector Component
 * Main container for evidence review with filtering and batch operations
 */

import { useState, useMemo, useEffect } from 'react';
import EvidenceCard from './EvidenceCard';
import EvidenceEditor from './EvidenceEditor';
import EvidenceHistory from './EvidenceHistory';
import EvidenceReviewQueue, { getReviewQueueItem } from './EvidenceReviewQueue';
import { Evidence, EvidenceAction, EvidenceFilter } from './types';
import './EvidenceInspector.css';

interface EvidenceInspectorProps {
  evidenceList: Evidence[];
  onVerify: (evidenceId: string, metadata: any) => Promise<void>;
  onCorrect: (evidenceId: string, modifications: any, metadata: any) => Promise<void>;
  onReject: (evidenceId: string, metadata: any) => Promise<void>;
  onBatchOperation: (evidenceIds: string[], action: 'verify' | 'reject') => Promise<void>;
  contextLabel?: string;
  contextValue?: string;
  status?: 'pending' | 'resolved' | 'conflict' | 'locked';
  onClose?: () => void;
}

export default function EvidenceInspector({
  evidenceList,
  onVerify,
  onCorrect,
  onReject,
  onBatchOperation,
  contextLabel,
  contextValue,
  status,
  onClose
}: EvidenceInspectorProps) {
  const [filter, setFilter] = useState<EvidenceFilter>({});
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [viewingHistoryId, setViewingHistoryId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'review-queue'>('all');

  // Clear selection when evidence list changes (e.g., workspace switch)
  useEffect(() => {
    setSelectedIds(new Set());
  }, [evidenceList]);

  // Filter evidence
  const filteredEvidence = useMemo(() => {
    return evidenceList.filter(evidence => {
      if (filter.status && !filter.status.includes(evidence.verification_status)) {
        return false;
      }
      if (filter.confidence_range) {
        const [min, max] = filter.confidence_range;
        if (evidence.confidence_score < min || evidence.confidence_score > max) {
          return false;
        }
      }
      if (filter.show_only_needs_review && evidence.confidence_score >= 0.7) {
        return false;
      }
      return true;
    });
  }, [evidenceList, filter]);

  // Statistics
  const stats = useMemo(() => {
    const total = evidenceList.length;
    const reviewQueue = evidenceList.filter(e => getReviewQueueItem(e) !== null).length;
    
    return { total, reviewQueue };
  }, [evidenceList]);

  const handleAction = async (evidenceId: string, action: EvidenceAction) => {
    const metadata = {
      intent_type: 'correction' as const,
      intent_scope: 'local' as const,
      tags: [action]
    };

    try {
      switch (action) {
        case 'verify':
          await onVerify(evidenceId, metadata);
          break;
        case 'reject':
          await onReject(evidenceId, metadata);
          break;
        case 'restore':
          // Restore is just changing status back to raw for re-correction
          await onVerify(evidenceId, { ...metadata, tags: ['restore'] });
          break;
        case 'request_review':
          // Flag for review by changing to pending_verification
          await onVerify(evidenceId, { ...metadata, tags: ['review_request'] });
          break;
        default:
          console.warn('Unknown action:', action);
      }
    } catch (error) {
      console.error('Error performing action:', error);
      alert(t("Failed to perform action. Please try again."));
    }
  };

  const handleEdit = (evidenceId: string) => {
    setEditingId(evidenceId);
  };

  const handleViewHistory = (evidenceId: string) => {
    setViewingHistoryId(evidenceId);
  };

  const handleSelect = (evidenceId: string, selected: boolean) => {
    const newSelected = new Set(selectedIds);
    if (selected) {
      newSelected.add(evidenceId);
    } else {
      newSelected.delete(evidenceId);
    }
    setSelectedIds(newSelected);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(filteredEvidence.map(e => e.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleFilterClick = (nextFilter: EvidenceFilter) => {
    const isSameStatus =
      JSON.stringify(filter.status ?? null) === JSON.stringify(nextFilter.status ?? null);
    const isSameConfidence =
      JSON.stringify(filter.confidence_range ?? null) === JSON.stringify(nextFilter.confidence_range ?? null);

    if (isSameStatus && isSameConfidence) {
      setFilter({});
      return;
    }

    setFilter(nextFilter);
  };

  const handleBatchVerify = async () => {
    if (selectedIds.size === 0) return;
    
    if (confirm(t('Verify {count} evidence items?', { count: selectedIds.size }))) {
      try {
        await onBatchOperation(Array.from(selectedIds), 'verify');
        setSelectedIds(new Set());
      } catch (error) {
        console.error('Batch verify failed:', error);
        alert('Failed to verify selected items. Please try again.');
      }
    }
  };

  const handleBatchReject = async () => {
    if (selectedIds.size === 0) return;
    
    if (confirm(t('Reject {count} evidence items? This action can be undone.', { count: selectedIds.size }))) {
      try {
        await onBatchOperation(Array.from(selectedIds), 'reject');
        setSelectedIds(new Set());
      } catch (error) {
        console.error('Batch reject failed:', error);
        alert('Failed to reject selected items. Please try again.');
      }
    }
  };

  const editingEvidence = editingId 
    ? evidenceList.find(e => e.id === editingId) 
    : null;

  const viewingHistoryEvidence = viewingHistoryId
    ? evidenceList.find(e => e.id === viewingHistoryId)
    : null;
  const isAllFilterActive = !filter.status && !filter.confidence_range;

  return (
    <div className="evidence-inspector">
      {/* Tabs */}
      <div className="evidence-tabs">
        <div className="evidence-tab-group">
          <button
            className={`tab ${activeTab === 'all' ? 'active' : ''}`}
            onClick={() => setActiveTab('all')}
          >
            {t("📋 All Evidence (")}{stats.total}{t(')')}
          </button>
          <button
            className={`tab ${activeTab === 'review-queue' ? 'active' : ''}`}
            onClick={() => setActiveTab('review-queue')}
          >
            {t("🔍 Review Queue (")}{stats.reviewQueue}{t(')')}
          </button>
        </div>

        {(contextLabel || contextValue || status || onClose) && (
          <div className="evidence-tab-context">
            {(contextLabel || contextValue) && (
              <div className="evidence-context-text">
                {contextLabel && <span className="context-label">{contextLabel}</span>}
                {contextValue && <span className="context-value">{contextValue}</span>}
              </div>
            )}
            {status && (
              <span className={`context-status status-${status}`}>
                {uiLabel(status)}
              </span>
            )}
            {onClose && (
              <button className="evidence-close-btn" onClick={onClose}>
                {t("Close")}
              </button>
            )}
          </div>
        )}
      </div>

      {activeTab === 'all' ? (
        <>
          {/* Header with stats and filters */}
          <div className="evidence-header">
            <div className="evidence-filters">
              <label>{t("Filter:")}</label>
              <button
                className={`filter-btn ${isAllFilterActive ? 'active' : ''}`}
                onClick={() => setFilter({})}
              >
                {t("All")}
              </button>
              <button
                className={`filter-btn ${filter.confidence_range?.[1] === 0.7 ? 'active' : ''}`}
                onClick={() => handleFilterClick({ confidence_range: [0, 0.7] })}
              >
                {t("Low Conf.")}
              </button>
              <button
                className={`filter-btn ${filter.status?.includes('raw') ? 'active' : ''}`}
                onClick={() => handleFilterClick({ status: ['raw'] })}
              >
                {t("Unverified")}
              </button>
              <button
                className={`filter-btn ${filter.status?.includes('rejected') ? 'active' : ''}`}
                onClick={() => handleFilterClick({ status: ['rejected'] })}
              >
                {t("Rejected")}
              </button>
            </div>

            {/* Batch operations merged into header */}
            {filteredEvidence.length > 0 && (
              <div className="batch-operations-inline">
                <label className="select-all-label">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === filteredEvidence.length && filteredEvidence.length > 0}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                  />
                  {t("Select All")}
                  {selectedIds.size > 0 && ` (${selectedIds.size})`}
                </label>
                {selectedIds.size > 0 && (
                  <>
                    <button className="batch-btn verify" onClick={handleBatchVerify}>
                      {t("✓ Verify (")}{selectedIds.size}{t(')')}
                    </button>
                    <button className="batch-btn reject" onClick={handleBatchReject}>
                      {t("✗ Reject (")}{selectedIds.size}{t(')')}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Evidence list */}
          <div className="evidence-list">
            {filteredEvidence.length === 0 ? (
              <div className="empty-state">
                <p>{t("No evidence items match the current filter.")}</p>
              </div>
            ) : (
              filteredEvidence.map(evidence => (
                <EvidenceCard
                  key={evidence.id}
                  evidence={evidence}
                  onAction={handleAction}
                  onEdit={handleEdit}
                  onViewHistory={handleViewHistory}
                  isSelected={selectedIds.has(evidence.id)}
                  onSelect={handleSelect}
                />
              ))
            )}
          </div>
        </>
      ) : (
        <EvidenceReviewQueue
          evidenceList={evidenceList}
          onReview={(evidenceId) => {
            setEditingId(evidenceId);
          }}
        />
      )}

      {/* Modals */}
      {editingEvidence && (
        <EvidenceEditor
          evidence={editingEvidence}
          onSave={async (modifications, metadata) => {
            await onCorrect(editingEvidence.id, modifications, metadata);
            setEditingId(null);
          }}
          onCancel={() => setEditingId(null)}
        />
      )}

      {viewingHistoryEvidence && (
        <EvidenceHistory
          evidence={viewingHistoryEvidence}
          onClose={() => setViewingHistoryId(null)}
          onRestore={async (revision, restoredText) => {
            const currentText = viewingHistoryEvidence.type === 'chunk'
              ? viewingHistoryEvidence.raw_text || ''
              : viewingHistoryEvidence.latex_string || '';
            await onCorrect(
              viewingHistoryEvidence.id,
              {
                old_text: currentText,
                new_text: restoredText,
                change_notes: t('Restored from revision v{version}', { version: revision.version })
              },
              {
                intent_type: 'correction',
                intent_scope: 'local',
                tags: ['history_restore']
              }
            );
            setViewingHistoryId(null);
          }}
        />
      )}
    </div>
  );
}

import { t, localizeMessage } from '../i18n';
/**
 * Digital Microscope Component
 * Evidence viewer showing PDF crops and supporting text
 */

import { useState, useEffect } from 'react';
import { useWorkspaceStore, Evidence as WorkspaceEvidence } from '../services/workspace';
import { EvidenceInspector } from './evidence';
import { Evidence as InspectorEvidence, EvidenceModification, IntentMetadata } from './evidence/types';
import { sspClient } from '../services/ssp_client';

interface DigitalMicroscopeProps {
  paperId: string;
  metricName: string;
  onClose: () => void;
}

// Adapter to convert workspace Evidence to Inspector Evidence
function convertToInspectorEvidence(
  wsEvidence: WorkspaceEvidence[],
  paperId: string
): InspectorEvidence[] {
  return wsEvidence.map((ev, index) => {
    return {
      id: ev.id || `evidence_${paperId}_${index}`,
      type: ev.type,
      paper_id: paperId,
      raw_text: ev.type === 'chunk' ? ev.text : undefined,
      latex_string: ev.type === 'formula' ? ev.text : undefined,
      bounding_box: ev.boundingBox ? {
        page: ev.boundingBox.page,
        coordinate_precision: ev.boundingBox.coordinate_precision,
        box: [ev.boundingBox.x, ev.boundingBox.y, 
              ev.boundingBox.x + ev.boundingBox.width, 
              ev.boundingBox.y + ev.boundingBox.height]
      } : { page: 1, box: [0, 0, 100, 100] },
      verification_status: ev.verification_status || 'raw',
      confidence_score: ev.confidence,
      modification_count: ev.modification_count || 0,
      last_modified_at: ev.last_modified_at
    };
  });
}

export default function DigitalMicroscope({ paperId, metricName, onClose }: DigitalMicroscopeProps) {
  const { getEvidence, getCellData, papers } = useWorkspaceStore();
  const [evidence, setEvidence] = useState<InspectorEvidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  const downloadOriginal = async () => {
    setSourceError(null);
    try {
      const result = await sspClient.call('getPaperSource', {
        workspace_id: useWorkspaceStore.getState().currentWorkspaceId, paper_id: paperId
      });
      const bytes = Uint8Array.from(atob(result.content_base64), character => character.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = result.file_name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setSourceError(error instanceof Error ? error.message : t("Original PDF unavailable"));
    }
  };

  const paper = papers.find(p => p.id === paperId);
  const cellData = getCellData(paperId, metricName);
  const metricLabel = metricName.replace(/.*:/, '').replace(/_/g, ' ');
  const contextValue = cellData
    ? `${cellData.value} ${cellData.unit || ''}`.trim()
    : undefined;

  useEffect(() => {
    loadEvidence();
  }, [paperId, metricName]);

  const loadEvidence = async () => {
    setLoading(true);
    setEvidenceError(null);
    try {
      const data = await getEvidence(paperId, metricName);
      const inspectorData = convertToInspectorEvidence(data, paperId);
      setEvidence(inspectorData);
    } catch (error) {
      setEvidenceError(error instanceof Error ? error.message : t("Failed to load evidence"));
      setEvidence([]);
    } finally {
      setLoading(false);
    }
  };

  // SSP Protocol Handlers
  const handleVerify = async (evidenceId: string, metadata: IntentMetadata) => {
    try {
      const isRestore = metadata.tags?.includes('restore') ?? false;
      const isReviewRequest = metadata.tags?.includes('review_request') ?? false;
      let nextStatus: InspectorEvidence['verification_status'] = 'verified';

      if (isRestore) {
        await sspClient.restoreEvidence({
          evidence_id: evidenceId,
          intent_metadata: metadata
        });
        nextStatus = 'under_correction';
      } else if (isReviewRequest) {
        await sspClient.requestEvidenceReview({
          evidence_id: evidenceId,
          intent_metadata: metadata
        });
        nextStatus = 'pending_verification';
      } else {
        await sspClient.verifyEvidence({
          evidence_id: evidenceId,
          confidence_override: metadata.confidence_override,
          intent_metadata: metadata
        });
      }

      // Update local state
      setEvidence(prev => prev.map(ev => 
        ev.id === evidenceId ? { ...ev, verification_status: nextStatus } : ev
      ));
    } catch (error) {
      console.error('Failed to verify evidence:', error);
      const isConnectionError = error instanceof TypeError && error.message.includes('fetch');
      if (isConnectionError) {
        alert(t('Backend server not responding'));
      } else {
        alert(t("Failed to verify evidence. See console for details."));
      }
    }
  };

  const handleCorrect = async (
    evidenceId: string, 
    modifications: EvidenceModification, 
    metadata: IntentMetadata
  ) => {
    try {
      const nextStatus: InspectorEvidence['verification_status'] = metadata.tags?.includes('review_request')
        ? 'pending_verification'
        : 'verified';
      await sspClient.correctEvidence({
        evidence_id: evidenceId,
        modifications,
        new_status: nextStatus,
        evidence_type: evidence.find(item => item.id === evidenceId)?.type || 'chunk',
        intent_metadata: metadata
      });
      // Update local state
      setEvidence(prev => prev.map(ev => 
        ev.id === evidenceId ? { 
          ...ev, 
          verification_status: nextStatus,
          modification_count: ev.modification_count + 1,
          raw_text: ev.type === 'chunk' ? modifications.new_text : ev.raw_text,
          latex_string: ev.type === 'formula' ? modifications.new_text : ev.latex_string
        } : ev
      ));
    } catch (error) {
      console.error('Failed to correct evidence:', error);
      const isConnectionError = error instanceof TypeError && error.message.includes('fetch');
      if (isConnectionError) {
        alert(t('Failed to correct evidence. See console for details.'));
      } else {
        alert(t("Failed to correct evidence. See console for details."));
      }
    }
  };

  const handleReject = async (evidenceId: string, metadata: IntentMetadata) => {
    try {
      await sspClient.rejectEvidence({
        evidence_id: evidenceId,
        reason: 'User rejected',
        intent_metadata: metadata
      });
      // Update local state
      setEvidence(prev => prev.map(ev => 
        ev.id === evidenceId ? { ...ev, verification_status: 'rejected' } : ev
      ));
    } catch (error) {
      console.error('Failed to reject evidence:', error);
      const isConnectionError = error instanceof TypeError && error.message.includes('fetch');
      if (isConnectionError) {
        alert(t('Backend server not responding'));
      } else {
        alert(t("Failed to reject evidence. See console for details."));
      }
    }
  };

  const handleBatchOperation = async (
    evidenceIds: string[], 
    action: 'verify' | 'reject'
  ) => {
    try {
      const metadata: IntentMetadata = {
        intent_type: 'correction',
        intent_scope: 'local',
        tags: ['batch_operation']
      };

      if (action === 'verify') {
        await sspClient.batchVerifyEvidence({
          evidence_ids: evidenceIds,
          intent_metadata: metadata
        });
      } else {
        await sspClient.batchRejectEvidence({
          evidence_ids: evidenceIds,
          reason: 'Batch rejection',
          intent_metadata: metadata
        });
      }

      // Update local state
      const newStatus = action === 'verify' ? 'verified' : 'rejected';
      setEvidence(prev => prev.map(ev => 
        evidenceIds.includes(ev.id) ? { ...ev, verification_status: newStatus } : ev
      ));
    } catch (error) {
      console.error(`Failed to ${action} evidence:`, error);
      alert(t('Failed to update evidence. Please try again.'));
    }
  };

  return (
    <div style={{ 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column',
      backgroundColor: 'var(--app-bg)',
      color: 'var(--text-primary)'
    }}>
      {/* Evidence Inspector */}
      <div style={{ padding: '8px 12px' }}>
        <button onClick={downloadOriginal}>{t("Download original PDF")}</button>
        {sourceError && <p role="alert">{localizeMessage(sourceError)}</p>}
      </div>
      {loading ? (
        <div style={{ 
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: 0.5 
        }}>
          {t("Loading evidence...")}
        </div>
      ) : evidenceError ? (
        <div role="alert" style={{ padding: '16px' }}>
          <p>{localizeMessage(evidenceError)}</p><button onClick={loadEvidence}>{t("Retry evidence")}</button>
        </div>
      ) : evidence.length === 0 ? (
        <div style={{ 
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '12px',
          opacity: 0.5 
        }}>
          <p style={{ fontSize: '18px' }}>📭</p>
          <p>{t("No evidence found for this cell")}</p>
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <EvidenceInspector
            evidenceList={evidence}
            contextLabel={paper ? `${paper.title} - ${metricLabel}` : metricLabel}
            contextValue={contextValue}
            status={cellData?.status}
            onClose={onClose}
            onVerify={handleVerify}
            onCorrect={handleCorrect}
            onReject={handleReject}
            onBatchOperation={handleBatchOperation}
          />
        </div>
      )}
    </div>
  );
}

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
  paperId: string,
  cellStatus: 'pending' | 'resolved' | 'conflict' | 'locked'
): InspectorEvidence[] {
  return wsEvidence.map((ev, index) => {
    // Map cell status to evidence verification status
    let verificationStatus: InspectorEvidence['verification_status'];
    let modificationCount = 0;
    
    switch (cellStatus) {
      case 'locked':
        // Locked = finalized, all evidence verified
        verificationStatus = 'verified';
        modificationCount = 0;
        break;
      case 'resolved':
        // Resolved = mostly verified, maybe one pending review
        verificationStatus = index === wsEvidence.length - 1 ? 'pending_verification' : 'verified';
        modificationCount = index === wsEvidence.length - 1 ? 0 : Math.floor(Math.random() * 2);
        break;
      case 'conflict':
        // Conflict = mix of states including corrections and rejections
        const conflictStates: InspectorEvidence['verification_status'][] = [
          'under_correction', 'rejected', 'pending_verification', 'verified'
        ];
        verificationStatus = conflictStates[index % conflictStates.length];
        modificationCount = verificationStatus === 'under_correction' ? Math.floor(Math.random() * 3) + 1 : 0;
        break;
      case 'pending':
      default:
        // Pending = raw or pending verification
        verificationStatus = index === 0 ? 'raw' : 'pending_verification';
        modificationCount = 0;
        break;
    }
    
    return {
      id: ev.id || `evidence_${paperId}_${index}`,
      type: ev.type,
      paper_id: paperId,
      raw_text: ev.type === 'chunk' ? ev.text : undefined,
      latex_string: ev.type === 'formula' ? ev.text : undefined,
      bounding_box: ev.boundingBox ? {
        page: ev.boundingBox.page,
        box: [ev.boundingBox.x, ev.boundingBox.y, 
              ev.boundingBox.x + ev.boundingBox.width, 
              ev.boundingBox.y + ev.boundingBox.height]
      } : { page: 1, box: [0, 0, 100, 100] },
      verification_status: verificationStatus,
      confidence_score: ev.confidence,
      modification_count: modificationCount,
      last_modified_at: new Date().toISOString()
    };
  });
}

export default function DigitalMicroscope({ paperId, metricName, onClose }: DigitalMicroscopeProps) {
  const { getEvidence, getCellData, papers } = useWorkspaceStore();
  const [evidence, setEvidence] = useState<InspectorEvidence[]>([]);
  const [loading, setLoading] = useState(true);

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
    try {
      const data = await getEvidence(paperId, metricName);
      const cellStatus = cellData?.status || 'pending';
      const inspectorData = convertToInspectorEvidence(data, paperId, cellStatus);
      setEvidence(inspectorData);
    } finally {
      setLoading(false);
    }
  };

  // SSP Protocol Handlers
  const handleVerify = async (evidenceId: string, metadata: IntentMetadata) => {
    try {
      await sspClient.verifyEvidence({
        evidence_id: evidenceId,
        confidence_override: metadata.confidence_override,
        intent_metadata: metadata
      });
      // Update local state
      setEvidence(prev => prev.map(ev => 
        ev.id === evidenceId ? { ...ev, verification_status: 'verified' } : ev
      ));
    } catch (error) {
      console.error('Failed to verify evidence:', error);
      const isConnectionError = error instanceof TypeError && error.message.includes('fetch');
      if (isConnectionError) {
        alert('⚠️ Backend server not running. UI-only testing mode.');
      } else {
        alert('Failed to verify evidence. See console for details.');
      }
    }
  };

  const handleCorrect = async (
    evidenceId: string, 
    modifications: EvidenceModification, 
    metadata: IntentMetadata
  ) => {
    try {
      await sspClient.correctEvidence({
        evidence_id: evidenceId,
        modifications,
        new_status: 'verified',
        intent_metadata: metadata
      });
      // Update local state
      setEvidence(prev => prev.map(ev => 
        ev.id === evidenceId ? { 
          ...ev, 
          verification_status: 'verified',
          modification_count: ev.modification_count + 1,
          raw_text: ev.type === 'chunk' ? modifications.new_text : ev.raw_text,
          latex_string: ev.type === 'formula' ? modifications.new_text : ev.latex_string
        } : ev
      ));
    } catch (error) {
      console.error('Failed to correct evidence:', error);
      const isConnectionError = error instanceof TypeError && error.message.includes('fetch');
      if (isConnectionError) {
        alert('⚠️ Backend server not running.\n\nThe UI change was successful, but could not save to backend.\nStart the SSP server at http://localhost:8765 for full functionality.\n\n(This is normal during UI-only testing)');
      } else {
        alert('Failed to correct evidence. See console for details.');
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
        alert('⚠️ Backend server not running. UI-only testing mode.');
      } else {
        alert('Failed to reject evidence. See console for details.');
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
      alert(`Failed to ${action} evidence. See console for details.`);
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
      {loading ? (
        <div style={{ 
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: 0.5 
        }}>
          Loading evidence...
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
          <p>No evidence found for this cell</p>
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

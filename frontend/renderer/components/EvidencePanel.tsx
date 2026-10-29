/**
 * Evidence Panel Component
 * Lists all supporting evidence with confidence scores
 */

import { Evidence } from '../services/workspace';
import ConfidenceIndicator from './ConfidenceIndicator';

interface EvidencePanelProps {
  evidence: Evidence[];
  selectedEvidence: Evidence | null;
  onSelectEvidence: (evidence: Evidence) => void;
}

export default function EvidencePanel({ evidence, selectedEvidence, onSelectEvidence }: EvidencePanelProps) {
  if (evidence.length === 0) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: 0.5
      }}>
        <p>No evidence found</p>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', paddingRight: '8px' }}>
      <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', opacity: 0.8 }}>
        Supporting Evidence ({evidence.length})
      </h4>
      {evidence.map((item, index) => (
        <div
          key={item.id}
          className="evidence-item"
          onClick={() => onSelectEvidence(item)}
          style={{
            cursor: 'pointer',
            borderLeftColor: selectedEvidence?.id === item.id ? '#646cff' : '#404040',
            backgroundColor: selectedEvidence?.id === item.id ? '#2d2d2d' : '#2a2a2a'
          }}
        >
          {/* Evidence Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '8px'
          }}>
            <span style={{
              fontSize: '12px',
              padding: '2px 8px',
              borderRadius: '3px',
              backgroundColor: item.type === 'formula' ? '#3a3a7a' : '#3a3a3a',
              color: item.type === 'formula' ? '#9999ff' : '#999999'
            }}>
              {item.type === 'formula' ? '∫ Formula' : '📝 Chunk'}
            </span>
            <span style={{ fontSize: '12px', opacity: 0.6 }}>
              #{index + 1}
            </span>
          </div>

          {/* Evidence Text */}
          <div style={{
            fontSize: '13px',
            lineHeight: '1.5',
            marginBottom: '8px',
            fontFamily: item.type === 'formula' ? 'monospace' : 'inherit'
          }}>
            {item.text}
          </div>

          {/* Bounding Box Info */}
          {item.boundingBox && (
            <div style={{ fontSize: '11px', opacity: 0.5, marginBottom: '8px' }}>
              Page {item.boundingBox.page} · ({item.boundingBox.x}, {item.boundingBox.y})
            </div>
          )}

          {/* Confidence Indicator */}
          <ConfidenceIndicator confidence={item.confidence} />
        </div>
      ))}
    </div>
  );
}

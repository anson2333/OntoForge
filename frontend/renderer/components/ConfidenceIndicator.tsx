/**
 * Confidence Indicator Component
 * Visual bar showing confidence score
 */

interface ConfidenceIndicatorProps {
  confidence: number; // 0.0 to 1.0
}

export default function ConfidenceIndicator({ confidence }: ConfidenceIndicatorProps) {
  const percentage = Math.round(confidence * 100);
  
  let color = '#f44336'; // Red for low confidence
  if (confidence > 0.7) {
    color = '#4caf50'; // Green for high confidence
  } else if (confidence > 0.5) {
    color = '#ffa500'; // Orange for medium confidence
  }

  return (
    <div>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: '11px',
        marginBottom: '4px',
        opacity: 0.7
      }}>
        <span>Confidence</span>
        <span style={{ fontWeight: 500 }}>{percentage}%</span>
      </div>
      <div className="confidence-bar">
        <div
          className="confidence-fill"
          style={{
            width: `${percentage}%`,
            background: color
          }}
        />
      </div>
    </div>
  );
}

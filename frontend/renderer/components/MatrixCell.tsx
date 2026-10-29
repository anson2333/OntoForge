/**
 * Matrix Cell Component
 * Individual cell showing value, status, and confidence
 */

import { CellData } from '../services/workspace';

interface MatrixCellProps {
  cellData: CellData | null;
  onClick: () => void;
  isSelected?: boolean;
}

export default function MatrixCell({ cellData, onClick, isSelected }: MatrixCellProps) {
  if (!cellData) {
    return (
      <td className="matrix-cell" style={{ opacity: 0.3, textAlign: 'center' }}>
        —
      </td>
    );
  }

  const statusColors = {
    pending: '#ffa500',
    resolved: '#4caf50',
    conflict: '#f44336',
    locked: '#9c27b0'
  };

  const statusLabels = {
    pending: 'Pending',
    resolved: 'Verified',
    conflict: 'Conflict!',
    locked: 'Locked'
  };

  return (
    <td
      className="matrix-cell"
      onClick={onClick}
      style={{
        cursor: 'pointer',
        borderLeft: `3px solid ${statusColors[cellData.status]}`,
        backgroundColor: isSelected ? 'var(--surface-bg-selected)' : undefined,
        boxShadow: isSelected ? '0 0 0 2px var(--primary-color) inset' : undefined,
        position: 'relative'
      }}
    >
      <div className="cell-value">
        {cellData.value} {cellData.unit}
      </div>
      <div className="cell-status" style={{ color: statusColors[cellData.status] }}>
        {statusLabels[cellData.status]}
      </div>
      <div style={{ fontSize: '0.75em', opacity: 0.6, marginTop: '4px' }}>
        {cellData.evidenceCount} evidence · {(cellData.confidence * 100).toFixed(0)}% conf.
      </div>
      {isSelected && (
        <div style={{
          position: 'absolute',
          top: 4,
          right: 4,
          fontSize: '16px'
        }}>
          📍
        </div>
      )}
    </td>
  );
}

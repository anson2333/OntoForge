/**
 * Matrix Grid Component
 * Displays papers (rows) × metrics (columns) data grid
 */

import { useState } from 'react';
import { useWorkspaceStore } from '../services/workspace';
import MatrixCell from './MatrixCell';
import { Metric, Paper } from '../services/workspace';

interface MatrixGridProps {
  onCellClick: (paperId: string, metricName: string) => void;
  selectedCell?: { paperId: string; metricName: string } | null;
}

type SortDirection = 'asc' | 'desc';

type SortState =
  | { type: 'paper'; mode: 'domain' | 'alphabetic' | 'year'; direction: SortDirection }
  | { type: 'metric'; metricName: string; direction: SortDirection }
  | null;

function compareText(left: string, right: string): number {
  return left.localeCompare(right, undefined, { sensitivity: 'base' });
}

function parseSortableValue(value: string | null | undefined): number | string | null {
  if (!value) {
    return null;
  }

  const numericValue = Number.parseFloat(value);
  if (!Number.isNaN(numericValue) && Number.isFinite(numericValue)) {
    return numericValue;
  }

  return value.toLowerCase();
}

function compareMetricValues(
  leftPaper: Paper,
  rightPaper: Paper,
  metric: Metric,
  getCellData: (paperId: string, metricName: string) => ReturnType<typeof useWorkspaceStore.getState>['getCellData'] extends (...args: any[]) => infer TResult ? TResult : never,
  direction: SortDirection
): number {
  const leftValue = parseSortableValue(getCellData(leftPaper.id, metric.full_name)?.value);
  const rightValue = parseSortableValue(getCellData(rightPaper.id, metric.full_name)?.value);

  if (leftValue === null && rightValue === null) {
    return compareText(leftPaper.title, rightPaper.title);
  }

  if (leftValue === null) {
    return 1;
  }

  if (rightValue === null) {
    return -1;
  }

  let comparison = 0;

  if (typeof leftValue === 'number' && typeof rightValue === 'number') {
    comparison = leftValue - rightValue;
  } else {
    comparison = compareText(String(leftValue), String(rightValue));
  }

  if (comparison === 0) {
    comparison = compareText(leftPaper.title, rightPaper.title);
  }

  return direction === 'asc' ? comparison : -comparison;
}

function comparePaperRows(
  leftPaper: Paper,
  rightPaper: Paper,
  mode: 'domain' | 'alphabetic' | 'year',
  direction: SortDirection
): number {
  let comparison = 0;

  if (mode === 'domain') {
    const leftNamespace = leftPaper.domain_pack_namespace || '';
    const rightNamespace = rightPaper.domain_pack_namespace || '';

    comparison = compareText(leftNamespace, rightNamespace);
    if (comparison === 0) {
      comparison = compareText(leftPaper.title, rightPaper.title);
    }
  } else if (mode === 'year') {
    comparison = leftPaper.year - rightPaper.year;
    if (comparison === 0) {
      comparison = compareText(leftPaper.title, rightPaper.title);
    }
  } else {
    comparison = compareText(leftPaper.title, rightPaper.title);
  }

  return direction === 'asc' ? comparison : -comparison;
}

function nextSortDirection(currentSort: SortState, nextType: SortState): SortDirection {
  if (!currentSort || !nextType) {
    return 'asc';
  }

  if (currentSort.type !== nextType.type) {
    return 'asc';
  }

  if (currentSort.type === 'paper' && nextType.type === 'paper' && currentSort.mode !== nextType.mode) {
    return 'asc';
  }

  if (currentSort.type === 'metric' && nextType.type === 'metric' && currentSort.metricName !== nextType.metricName) {
    return 'asc';
  }

  return currentSort.direction === 'asc' ? 'desc' : 'asc';
}

function getSortIndicator(sortState: SortState, header: 'paper-domain' | 'paper-alphabetic' | 'paper-year' | string): string {
  if (!sortState) {
    return '↕';
  }

  if (header === 'paper-domain' && sortState.type === 'paper' && sortState.mode === 'domain') {
    return sortState.direction === 'asc' ? '↑' : '↓';
  }

  if (header === 'paper-alphabetic' && sortState.type === 'paper' && sortState.mode === 'alphabetic') {
    return sortState.direction === 'asc' ? '↑' : '↓';
  }

  if (header === 'paper-year' && sortState.type === 'paper' && sortState.mode === 'year') {
    return sortState.direction === 'asc' ? '↑' : '↓';
  }

  if (header !== 'paper' && sortState.type === 'metric' && sortState.metricName === header) {
    return sortState.direction === 'asc' ? '↑' : '↓';
  }

  return '↕';
}

export default function MatrixGrid({ onCellClick, selectedCell }: MatrixGridProps) {
  const [sortState, setSortState] = useState<SortState>(null);
  const { papers, metrics, getCellData, workspace, activeDomainPackNamespaces, selectedPaperId, selectPaper } = useWorkspaceStore();
  const visiblePapers = papers.filter(
    paper => !paper.domain_pack_namespace || activeDomainPackNamespaces.includes(paper.domain_pack_namespace)
  );
  const sortedPapers = [...visiblePapers].sort((leftPaper, rightPaper) => {
    if (!sortState) {
      return 0;
    }

    if (sortState.type === 'paper') {
      return comparePaperRows(leftPaper, rightPaper, sortState.mode, sortState.direction);
    }

    const metric = metrics.find(item => item.full_name === sortState.metricName);
    if (!metric) {
      return 0;
    }

    return compareMetricValues(leftPaper, rightPaper, metric, getCellData, sortState.direction);
  });

  const handlePaperSort = (mode: 'domain' | 'alphabetic' | 'year') => {
    const nextDirection = nextSortDirection(sortState, { type: 'paper', mode, direction: 'asc' });
    setSortState({ type: 'paper', mode, direction: nextDirection });
  };

  const handleMetricSort = (metricName: string) => {
    const nextDirection = nextSortDirection(sortState, { type: 'metric', metricName, direction: 'asc' });
    setSortState({ type: 'metric', metricName, direction: nextDirection });
  };

  if (visiblePapers.length === 0) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        opacity: 0.5
      }}>
        <p>No papers loaded. Click "Load Workspace" to begin.</p>
      </div>
    );
  }

  return (
    <div className="matrix-container">
      <table className="matrix-table">
        <thead>
          <tr>
            <th style={{ minWidth: '250px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>Paper</span>
                  {workspace && (
                    <span 
                      style={{ 
                        fontSize: '10px', 
                        opacity: 0.5,
                        padding: '2px 4px',
                        backgroundColor: 'var(--chip-bg)',
                        borderRadius: '2px'
                      }}
                      title={`Workspace: ${workspace.name} • ${activeDomainPackNamespaces.length} active domain packs`}
                    >
                      📦
                    </span>
                  )}
                </div>
                <div className="matrix-paper-sort-controls">
                  <button
                    type="button"
                    className="matrix-paper-sort-chip"
                    onClick={() => handlePaperSort('domain')}
                    title="Sort papers by domain pack label"
                  >
                    <span>Domain</span>
                    <span className="matrix-sort-indicator">{getSortIndicator(sortState, 'paper-domain')}</span>
                  </button>
                  <button
                    type="button"
                    className="matrix-paper-sort-chip"
                    onClick={() => handlePaperSort('alphabetic')}
                    title="Sort papers alphabetically"
                  >
                    <span>A-Z</span>
                    <span className="matrix-sort-indicator">{getSortIndicator(sortState, 'paper-alphabetic')}</span>
                  </button>
                  <button
                    type="button"
                    className="matrix-paper-sort-chip"
                    onClick={() => handlePaperSort('year')}
                    title="Sort papers by publication year"
                  >
                    <span>Year</span>
                    <span className="matrix-sort-indicator">{getSortIndicator(sortState, 'paper-year')}</span>
                  </button>
                </div>
              </div>
            </th>
            {metrics.map(metric => (
              <th 
                key={metric.full_name} 
                style={{ minWidth: '120px' }}
                title={metric.aliases.length > 0 ? `Aliases: ${metric.aliases.join(', ')}` : undefined}
              >
                <button
                  type="button"
                  className="matrix-sort-button"
                  onClick={() => handleMetricSort(metric.full_name)}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>
                        {metric.name.replace(/_/g, ' ')}
                        <span style={{ fontSize: '0.7em', opacity: 0.5, marginLeft: '4px' }}>({metric.namespace})</span>
                      </div>
                      <div style={{ fontSize: '0.85em', opacity: 0.6, fontWeight: 'normal' }}>
                        [{metric.unit}]
                      </div>
                      {metric.aliases.length > 0 && (
                        <div style={{ 
                          fontSize: '0.7em', 
                          opacity: 0.4, 
                          fontWeight: 'normal',
                          fontStyle: 'italic',
                          marginTop: '2px'
                        }}>
                          aka: {metric.aliases[0]}
                        </div>
                      )}
                    </div>
                    <span className="matrix-sort-indicator">{getSortIndicator(sortState, metric.full_name)}</span>
                  </div>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedPapers.map(paper => (
            <tr
              key={paper.id}
              style={selectedPaperId === paper.id ? { backgroundColor: 'var(--surface-bg-selected, #e7f2ff)' } : undefined}
            >
              <td style={{ background: selectedPaperId === paper.id ? 'var(--surface-bg-selected, #e7f2ff)' : 'var(--panel-bg)' }}>
                <div style={{ fontWeight: 500 }}>{paper.title}</div>
                <div style={{ fontSize: '0.85em', opacity: 0.7, marginTop: '4px' }}>
                  {paper.authors.join(', ')} ({paper.year})
                </div>
                <div style={{ fontSize: '0.8em', opacity: 0.5, marginTop: '2px' }}>
                  {paper.venue}
                </div>
                <div style={{ fontSize: '0.75em', opacity: 0.55, marginTop: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {paper.domain_pack_namespace || 'unscoped'}
                </div>
              </td>
              {metrics.map(metric => {
                const cellData = getCellData(paper.id, metric.full_name);
                const isSelected = selectedCell?.paperId === paper.id && selectedCell?.metricName === metric.full_name;
                return (
                  <MatrixCell
                    key={`${paper.id}-${metric.full_name}`}
                    cellData={cellData}
                    onClick={() => {
                      selectPaper(paper.id);
                      onCellClick(paper.id, metric.full_name);
                    }}
                    isSelected={isSelected}
                  />
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Paper Preview View
 * Displays paper import details across preview and ingestion lifecycle states.
 */

import React from 'react';
import { PaperImportEntry } from '../../services/workspace';
import { HierarchyNav, HierarchyNavItem } from './HierarchyNav';
import './PaperPreviewView.css';

interface PaperPreviewViewProps {
  paperImport: PaperImportEntry;
  hierarchyItems: HierarchyNavItem[];
  onCommit: (paperImportId: string) => Promise<void>;
  onRetry?: (paperImportId: string) => void;
  onCancel: () => void;
}

export const PaperPreviewView: React.FC<PaperPreviewViewProps> = ({
  paperImport,
  hierarchyItems,
  onCommit,
  onRetry,
  onCancel
}) => {
  const { preview, warning, file_name, file_size, title, status, error_message, upload_id } = paperImport;
  const [isCommitting, setIsCommitting] = React.useState(false);

  React.useEffect(() => {
    if (status !== 'ingesting') {
      setIsCommitting(false);
    }
  }, [paperImport.id, status]);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDateTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const statusContent: Record<PaperImportEntry['status'], { label: string; title: string; message: string }> = {
    queued: {
      label: 'Queued',
      title: 'Queued for preview',
      message: 'This PDF has been added to the domain pack and is waiting for preview preparation.'
    },
    validating: {
      label: 'Preparing Preview',
      title: 'Preparing paper preview',
      message: 'OntoForge is uploading the PDF, extracting text, and matching the paper against this domain pack.'
    },
    preview_ready: {
      label: 'Preview Ready',
      title: 'Preview ready',
      message: 'Review the extracted metadata and evidence summary, then commit the paper to the workspace.'
    },
    ingesting: {
      label: 'Committing',
      title: 'Committing paper',
      message: 'OntoForge is writing the parsed paper, assertions, and evidence links into the workspace.'
    },
    error: {
      label: 'Needs Attention',
      title: 'Import failed',
      message: 'The paper could not finish the current import step. Review the error details below.'
    }
  };

  const handleCommit = async () => {
    if (status !== 'preview_ready' || !upload_id) {
      return;
    }

    setIsCommitting(true);
    try {
      await onCommit(paperImport.id);
    } catch (error) {
      console.error('Failed to commit paper:', error);
      setIsCommitting(false);
    }
  };

  const canCommit = status === 'preview_ready' && Boolean(upload_id);
  const canRetry = status === 'error' && Boolean(onRetry);
  const previewTitle = preview?.title || title || file_name;
  const isBusy = status === 'queued' || status === 'validating' || status === 'ingesting' || isCommitting;
  const statusDetails = statusContent[status];

  return (
    <div className="paper-preview-view">
      <div className="preview-header">
        <HierarchyNav items={hierarchyItems} />
        <div className="preview-status-badge" data-status={status}>
          {statusDetails.label}
        </div>
      </div>

      <div className="preview-content">
        <h1 className="preview-title">{previewTitle}</h1>

        <section className="preview-lifecycle-section" data-status={status}>
          <div className="preview-lifecycle-copy">
            <h2>{statusDetails.title}</h2>
            <p>{statusDetails.message}</p>
          </div>
          {isBusy && (
            <div className="preview-progress-indicator" aria-label={statusDetails.label} />
          )}
        </section>

        {/* Stats Section */}
        {preview && (
          <div className="preview-stats-section">
            <h2 className="section-title">📊 Extraction Summary</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{preview.chunk_count}</div>
                <div className="stat-label">Text Chunks</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{preview.formula_count}</div>
                <div className="stat-label">Formulas</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{preview.assertion_count}</div>
                <div className="stat-label">Assertions</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{preview.evidence_count}</div>
                <div className="stat-label">Evidence Links</div>
              </div>
            </div>
          </div>
        )}

        {/* Metadata Section */}
        <div className="preview-metadata-section">
          <h2 className="section-title">📄 Paper Metadata</h2>
          <div className="metadata-grid">
            {preview && (
              <>
                <div className="metadata-row">
                  <span className="metadata-label">Title:</span>
                  <span className="metadata-value">{preview.title}</span>
                </div>
                {preview.authors && preview.authors.length > 0 && (
                  <div className="metadata-row">
                    <span className="metadata-label">Authors:</span>
                    <span className="metadata-value">{preview.authors.join(', ')}</span>
                  </div>
                )}
                {preview.year && (
                  <div className="metadata-row">
                    <span className="metadata-label">Year:</span>
                    <span className="metadata-value">{preview.year}</span>
                  </div>
                )}
                {preview.venue && (
                  <div className="metadata-row">
                    <span className="metadata-label">Venue:</span>
                    <span className="metadata-value">{preview.venue}</span>
                  </div>
                )}
              </>
            )}
            {!preview && (
              <div className="metadata-row">
                <span className="metadata-label">Title:</span>
                <span className="metadata-value">{title || file_name}</span>
              </div>
            )}
            <div className="metadata-row">
              <span className="metadata-label">File:</span>
              <span className="metadata-value">{file_name} ({formatFileSize(file_size)})</span>
            </div>
            <div className="metadata-row">
              <span className="metadata-label">Added:</span>
              <span className="metadata-value">{formatDateTime(paperImport.created_at)}</span>
            </div>
            <div className="metadata-row">
              <span className="metadata-label">Source:</span>
              <span className="metadata-value">{paperImport.source === 'drop' ? 'Drag and drop' : 'File picker'}</span>
            </div>
          </div>
        </div>

        {error_message && (
          <div className="preview-error-section">
            <div className="error-content">
              <h3 className="error-title">Import Error</h3>
              <p className="error-message">{error_message}</p>
            </div>
          </div>
        )}

        {!upload_id && status === 'preview_ready' && (
          <div className="preview-warning-section">
            <div className="warning-icon">⚠️</div>
            <div className="warning-content">
              <h3 className="warning-title">Upload Reference Missing</h3>
              <p className="warning-message">This preview no longer has a backend upload reference. Retry the import before committing it.</p>
            </div>
          </div>
        )}

        {/* Warning Section */}
        {warning && (
          <div className="preview-warning-section">
            <div className="warning-icon">⚠️</div>
            <div className="warning-content">
              <h3 className="warning-title">Extraction Warning</h3>
              <p className="warning-message">{warning}</p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="preview-actions">
          {status === 'preview_ready' && (
            <button
              className="preview-action-btn primary"
              onClick={handleCommit}
              disabled={!canCommit || isCommitting}
            >
              {isCommitting ? 'Committing...' : 'Commit to Workspace'}
            </button>
          )}
          {canRetry && (
            <button
              className="preview-action-btn primary"
              onClick={() => onRetry?.(paperImport.id)}
            >
              Retry Preview
            </button>
          )}
          {(status === 'queued' || status === 'validating' || status === 'ingesting') && (
            <button
              className="preview-action-btn primary"
              disabled
            >
              {statusDetails.label}
            </button>
          )}
          <button
            className="preview-action-btn secondary"
            onClick={onCancel}
            disabled={isCommitting && status === 'ingesting'}
          >
            Back to Papers
          </button>
        </div>
      </div>
    </div>
  );
};

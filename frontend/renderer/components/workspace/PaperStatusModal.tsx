/**
 * Paper Status Modal
 * Displays different UI based on paper state:
 * - queued/validating: Show upload status
 * - preview_ready: Show preview with assertions and option to commit
 * - ingesting: Show ingestion progress
 * - error: Show detailed error message with retry option
 * - persisted paper: Show paper metadata
 */

import React from 'react';
import { Paper, PaperImportEntry } from '../../services/workspace';
import './PaperStatusModal.css';

interface PaperStatusModalProps {
  paper?: Paper;
  paperImport?: PaperImportEntry;
  onClose: () => void;
  onRetry?: (importId: string) => void;
  onCommit?: (importId: string) => void;
  onOpenPDF?: (paperId: string) => void;
  onDismiss?: (importId: string) => void;
}

export const PaperStatusModal: React.FC<PaperStatusModalProps> = ({
  paper,
  paperImport,
  onClose,
  onRetry,
  onCommit,
  onOpenPDF,
  onDismiss
}) => {
  // Determine what to show
  const isPaper = !!paper;
  const isImport = !!paperImport;

  if (!isPaper && !isImport) {
    return null;
  }

  const renderPaperView = () => {
    if (!paper) return null;

    return (
      <div className="paper-status-content">
        <div className="status-section">
          <h3>Paper Information</h3>
          <div className="paper-meta">
            <div className="meta-row">
              <span className="meta-label">Title:</span>
              <span className="meta-value">{paper.title}</span>
            </div>
            {paper.authors.length > 0 && (
              <div className="meta-row">
                <span className="meta-label">Authors:</span>
                <span className="meta-value">{paper.authors.join(', ')}</span>
              </div>
            )}
            {paper.venue && (
              <div className="meta-row">
                <span className="meta-label">Venue:</span>
                <span className="meta-value">{paper.venue}</span>
              </div>
            )}
            {paper.year && (
              <div className="meta-row">
                <span className="meta-label">Year:</span>
                <span className="meta-value">{paper.year}</span>
              </div>
            )}
            <div className="meta-row">
              <span className="meta-label">Status:</span>
              <span className="meta-value status-badge" data-status={paper.ingestion_status}>
                {paper.ingestion_status.replace(/_/g, ' ')}
              </span>
            </div>
          </div>
        </div>

        <div className="modal-actions">
          {onOpenPDF && (
            <button
              className="btn-primary"
              onClick={() => onOpenPDF(paper.id)}
            >
              Open PDF
            </button>
          )}
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    );
  };

  const renderImportView = () => {
    if (!paperImport) return null;

    const { status, error_message, warning, preview, file_name, file_size } = paperImport;

    // Queued or Validating state
    if (status === 'queued' || status === 'validating') {
      const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
      };

      return (
        <div className="paper-status-content">
          <div className="status-section">
            <div className="status-icon-large" style={{ fontSize: '48px' }}>
              {status === 'queued' ? '⏳' : '⏱️'}
            </div>
            <h3 style={{ marginTop: '16px', marginBottom: '8px' }}>
              {status === 'queued' ? 'Queued for Processing' : 'Validating PDF'}
            </h3>
            <p className="status-message" style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
              {status === 'queued'
                ? 'Your PDF is in the queue and will be processed shortly.'
                : 'Extracting text, formulas, and metadata from PDF...'}
            </p>
            
            <div className="file-info" style={{
              background: 'var(--background-secondary)',
              padding: '16px',
              borderRadius: '6px',
              border: '1px solid var(--border-color)'
            }}>
              <div className="meta-row" style={{ marginBottom: '12px' }}>
                <span className="meta-label" style={{ fontWeight: 600, minWidth: '60px' }}>File:</span>
                <span className="meta-value" style={{ 
                  wordBreak: 'break-word',
                  fontFamily: 'monospace',
                  fontSize: '13px'
                }}>{file_name || 'Unknown'}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label" style={{ fontWeight: 600, minWidth: '60px' }}>Size:</span>
                <span className="meta-value">{formatFileSize(file_size)}</span>
              </div>
            </div>

            {status === 'validating' && (
              <div style={{ marginTop: '20px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                <div style={{ 
                  display: 'inline-block',
                  width: '12px',
                  height: '12px',
                  border: '2px solid var(--border-color)',
                  borderTopColor: 'var(--primary-color)',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  marginRight: '8px',
                  verticalAlign: 'middle'
                }} />
                This may take a few moments depending on PDF size and complexity
              </div>
            )}
          </div>
          <div className="modal-actions">
            <button className="btn-secondary" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      );
    }

    // Error state
    if (status === 'error') {
      const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
      };

      return (
        <div className="paper-status-content">
          <div className="status-section error-section">
            <div className="status-icon-large error" style={{ fontSize: '48px' }}>❌</div>
            <h3 style={{ marginTop: '16px', marginBottom: '8px', color: 'var(--error-color)' }}>
              Import Failed
            </h3>
            <p className="status-message" style={{ marginBottom: '24px' }}>
              The PDF could not be processed. Please review the details below.
            </p>
            
            {error_message && (
              <div className="error-details" style={{ marginBottom: '20px' }}>
                <h4>Error Details</h4>
                <pre className="error-message-box" style={{
                  background: 'var(--background-secondary)',
                  padding: '12px',
                  borderRadius: '4px',
                  border: '1px solid var(--error-color)',
                  fontSize: '13px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: '150px',
                  overflow: 'auto'
                }}>{error_message}</pre>
              </div>
            )}

            <div className="file-info" style={{
              background: 'var(--background-secondary)',
              padding: '16px',
              borderRadius: '6px',
              border: '1px solid var(--border-color)',
              marginBottom: '20px'
            }}>
              <div className="meta-row" style={{ marginBottom: '12px' }}>
                <span className="meta-label" style={{ fontWeight: 600, minWidth: '60px' }}>File:</span>
                <span className="meta-value" style={{ 
                  wordBreak: 'break-word',
                  fontFamily: 'monospace',
                  fontSize: '13px'
                }}>{file_name || 'Unknown'}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label" style={{ fontWeight: 600, minWidth: '60px' }}>Size:</span>
                <span className="meta-value">{formatFileSize(file_size)}</span>
              </div>
            </div>

            <div className="error-hints" style={{
              background: 'rgba(255, 183, 77, 0.1)',
              border: '1px solid rgba(255, 183, 77, 0.3)',
              borderRadius: '6px',
              padding: '16px'
            }}>
              {error_message?.includes('File reference lost') ? (
                <>
                  <h4 style={{ marginTop: 0, marginBottom: '12px', fontSize: '14px' }}>What to do</h4>
                  <ul style={{ margin: 0, paddingLeft: '20px' }}>
                    <li style={{ marginBottom: '8px' }}>Close this dialog and click "Dismiss" to clear this failed import</li>
                    <li style={{ marginBottom: '8px' }}>Drop the PDF file into the workspace sidebar again</li>
                    <li>The import will restart from the beginning</li>
                  </ul>
                </>
              ) : (
                <>
                  <h4 style={{ marginTop: 0, marginBottom: '12px', fontSize: '14px' }}>Common Issues</h4>
                  <ul style={{ margin: 0, paddingLeft: '20px' }}>
                    <li style={{ marginBottom: '8px' }}>PDF may be corrupted or password-protected</li>
                    <li style={{ marginBottom: '8px' }}>PDF may not contain extractable text (scanned images)</li>
                    <li style={{ marginBottom: '8px' }}>Backend service may be experiencing issues</li>
                    <li>Domain pack configuration may be invalid</li>
                  </ul>
                </>
              )}
            </div>
          </div>

          <div className="modal-actions">
            {error_message?.includes('File reference lost') ? (
              onDismiss && (
                <button
                  className="btn-primary"
                  onClick={() => {
                    onDismiss(paperImport.id);
                    onClose();
                  }}
                >
                  Dismiss
                </button>
              )
            ) : (
              onRetry && (
                <button
                  className="btn-primary"
                  onClick={() => {
                    onRetry(paperImport.id);
                    onClose();
                  }}
                >
                  Retry Import
                </button>
              )
            )}
            <button className="btn-secondary" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      );
    }

    // Ingesting state
    if (status === 'ingesting') {
      return (
        <div className="paper-status-content">
          <div className="status-section">
            <div className="status-icon-large" style={{ fontSize: '48px' }}>⚙️</div>
            <h3 style={{ marginTop: '16px', marginBottom: '8px' }}>Committing to Workspace</h3>
            <p className="status-message" style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
              Building knowledge graph and creating assertion nodes...
            </p>
            
            {preview && (
              <div className="preview-stats" style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
                gap: '16px',
                padding: '20px',
                background: 'var(--background-secondary)',
                borderRadius: '6px',
                border: '1px solid var(--border-color)'
              }}>
                <div className="stat-item" style={{ textAlign: 'center' }}>
                  <span className="stat-value" style={{
                    display: 'block',
                    fontSize: '24px',
                    fontWeight: 600,
                    color: 'var(--primary-color)',
                    marginBottom: '4px'
                  }}>{preview.chunk_count}</span>
                  <span className="stat-label" style={{
                    display: 'block',
                    fontSize: '12px',
                    color: 'var(--text-secondary)'
                  }}>Text Chunks</span>
                </div>
                <div className="stat-item" style={{ textAlign: 'center' }}>
                  <span className="stat-value" style={{
                    display: 'block',
                    fontSize: '24px',
                    fontWeight: 600,
                    color: 'var(--primary-color)',
                    marginBottom: '4px'
                  }}>{preview.formula_count}</span>
                  <span className="stat-label" style={{
                    display: 'block',
                    fontSize: '12px',
                    color: 'var(--text-secondary)'
                  }}>Formulas</span>
                </div>
                <div className="stat-item" style={{ textAlign: 'center' }}>
                  <span className="stat-value" style={{
                    display: 'block',
                    fontSize: '24px',
                    fontWeight: 600,
                    color: 'var(--primary-color)',
                    marginBottom: '4px'
                  }}>{preview.assertion_count}</span>
                  <span className="stat-label" style={{
                    display: 'block',
                    fontSize: '12px',
                    color: 'var(--text-secondary)'
                  }}>Assertions</span>
                </div>
              </div>
            )}

            <div style={{ marginTop: '20px', fontSize: '13px', color: 'var(--text-secondary)', textAlign: 'center' }}>
              <div style={{ 
                display: 'inline-block',
                width: '12px',
                height: '12px',
                border: '2px solid var(--border-color)',
                borderTopColor: 'var(--primary-color)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
                marginRight: '8px',
                verticalAlign: 'middle'
              }} />
              Please wait while the paper is being committed...
            </div>
          </div>
          <div className="modal-actions">
            <button className="btn-secondary" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      );
    }

    // Preview Ready state
    if (status === 'preview_ready' && preview) {
      return (
        <div className="paper-status-content">
          <div className="status-section">
            <div className="status-icon-large" style={{ fontSize: '48px', color: 'var(--success-color)' }}>✓</div>
            <h3 style={{ marginTop: '16px', marginBottom: '8px', color: 'var(--success-color)' }}>
              Preview Ready
            </h3>
            <p className="status-message" style={{ marginBottom: '24px', color: 'var(--text-secondary)' }}>
              PDF has been successfully parsed and analyzed. Review the extracted content below.
            </p>

            {warning && (
              <div className="warning-box" style={{
                background: 'rgba(255, 183, 77, 0.1)',
                border: '1px solid rgba(255, 183, 77, 0.3)',
                borderRadius: '6px',
                padding: '12px',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <span className="warning-icon" style={{ fontSize: '20px' }}>⚠️</span>
                <span style={{ fontSize: '13px', flex: 1 }}>{warning}</span>
              </div>
            )}

            <div className="preview-details">
              <h4 style={{ marginTop: 0, marginBottom: '16px', fontSize: '14px' }}>Extracted Content</h4>
              <div className="preview-stats" style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '16px',
                padding: '20px',
                background: 'var(--background-secondary)',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                marginBottom: '16px'
              }}>
                <div className="stat-item" style={{ textAlign: 'center' }}>
                  <span className="stat-value" style={{
                    display: 'block',
                    fontSize: '32px',
                    fontWeight: 600,
                    color: 'var(--primary-color)',
                    marginBottom: '4px'
                  }}>{preview.chunk_count}</span>
                  <span className="stat-label" style={{
                    display: 'block',
                    fontSize: '12px',
                    color: 'var(--text-secondary)'
                  }}>Text Chunks</span>
                </div>
                <div className="stat-item" style={{ textAlign: 'center' }}>
                  <span className="stat-value" style={{
                    display: 'block',
                    fontSize: '32px',
                    fontWeight: 600,
                    color: 'var(--primary-color)',
                    marginBottom: '4px'
                  }}>{preview.formula_count}</span>
                  <span className="stat-label" style={{
                    display: 'block',
                    fontSize: '12px',
                    color: 'var(--text-secondary)'
                  }}>Formulas</span>
                </div>
                <div className="stat-item" style={{ textAlign: 'center' }}>
                  <span className="stat-value" style={{
                    display: 'block',
                    fontSize: '32px',
                    fontWeight: 600,
                    color: 'var(--primary-color)',
                    marginBottom: '4px'
                  }}>{preview.assertion_count}</span>
                  <span className="stat-label" style={{
                    display: 'block',
                    fontSize: '12px',
                    color: 'var(--text-secondary)'
                  }}>Assertions</span>
                </div>
                <div className="stat-item" style={{ textAlign: 'center' }}>
                  <span className="stat-value" style={{
                    display: 'block',
                    fontSize: '32px',
                    fontWeight: 600,
                    color: 'var(--primary-color)',
                    marginBottom: '4px'
                  }}>{preview.evidence_count}</span>
                  <span className="stat-label" style={{
                    display: 'block',
                    fontSize: '12px',
                    color: 'var(--text-secondary)'
                  }}>Evidence Links</span>
                </div>
              </div>

              <div style={{
                background: 'var(--background-secondary)',
                padding: '16px',
                borderRadius: '6px',
                border: '1px solid var(--border-color)'
              }}>
                <div className="meta-row" style={{ marginBottom: preview.venue ? '12px' : '0' }}>
                  <span className="meta-label" style={{ fontWeight: 600, minWidth: '80px' }}>Title:</span>
                  <span className="meta-value">{preview.title}</span>
                </div>
                {preview.authors && preview.authors.length > 0 && (
                  <div className="meta-row" style={{ marginBottom: preview.venue ? '12px' : '0' }}>
                    <span className="meta-label" style={{ fontWeight: 600, minWidth: '80px' }}>Authors:</span>
                    <span className="meta-value">{preview.authors.join(', ')}</span>
                  </div>
                )}
                {preview.venue && (
                  <div className="meta-row" style={{ marginBottom: '12px' }}>
                    <span className="meta-label" style={{ fontWeight: 600, minWidth: '80px' }}>Venue:</span>
                    <span className="meta-value">{preview.venue}</span>
                  </div>
                )}
                {preview.year && (
                  <div className="meta-row">
                    <span className="meta-label" style={{ fontWeight: 600, minWidth: '80px' }}>Year:</span>
                    <span className="meta-value">{preview.year}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="commit-prompt" style={{
              marginTop: '20px',
              padding: '16px',
              background: 'rgba(var(--primary-color-rgb), 0.1)',
              border: '1px solid rgba(var(--primary-color-rgb), 0.3)',
              borderRadius: '6px',
              fontSize: '14px',
              textAlign: 'center'
            }}>
              <p style={{ margin: 0 }}>
                Click <strong>"Commit to Workspace"</strong> to add this paper to your knowledge graph.
              </p>
            </div>
          </div>

          <div className="modal-actions">
            {onCommit && (
              <button
                className="btn-primary"
                onClick={() => {
                  onCommit(paperImport.id);
                  onClose();
                }}
              >
                Commit to Workspace
              </button>
            )}
            <button className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
          </div>
        </div>
      );
    }

    return null;
  };

  const getModalTitle = () => {
    if (isPaper && paper) {
      return paper.title;
    }
    if (isImport && paperImport) {
      // Use title if available, otherwise use file_name, never use ID
      return paperImport.title || paperImport.file_name || 'Paper Import';
    }
    return 'Paper Details';
  };

  const getModalSubtitle = () => {
    if (isImport && paperImport) {
      const statusLabels = {
        queued: 'Queued for processing',
        validating: 'Validating and extracting preview',
        preview_ready: 'Ready to commit',
        ingesting: 'Committing to workspace',
        error: 'Import failed'
      };
      return statusLabels[paperImport.status] || paperImport.status;
    }
    if (isPaper && paper) {
      return paper.ingestion_status === 'ingested' ? 'Ingested' : 'Error';
    }
    return '';
  };

  return (
    <div className="modal-overlay paper-status-modal-overlay" onClick={onClose}>
      <div className="paper-status-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-content">
            <h2 className="modal-title">{getModalTitle()}</h2>
            {getModalSubtitle() && (
              <p className="modal-subtitle">{getModalSubtitle()}</p>
            )}
          </div>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {isPaper ? renderPaperView() : renderImportView()}
        </div>
      </div>
    </div>
  );
};

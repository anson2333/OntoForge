import { t, getLocale, localizeMessage } from '../../i18n';
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
  onConfigureModel: () => void;
}

export const PaperPreviewView: React.FC<PaperPreviewViewProps> = ({
  paperImport,
  hierarchyItems,
  onCommit,
  onRetry,
  onCancel,
  onConfigureModel
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
    return date.toLocaleString(getLocale(), {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const statusContent: Record<PaperImportEntry['status'], { label: string; title: string; message: string }> = {
    queued: {
      label: t('Queued'),
      title: t('Queued for preview'),
      message: t('This PDF has been added to the domain pack and is waiting for preview preparation.')
    },
    validating: {
      label: t('Preparing Preview'),
      title: t('Preparing paper preview'),
      message: t('OntoForge is uploading the PDF, extracting text, and matching the paper against this domain pack.')
    },
    preview_ready: {
      label: t('Preview Ready'),
      title: t('Preview ready'),
      message: t('Review the extracted metadata and evidence summary, then commit the paper to the workspace.')
    },
    ingesting: {
      label: t('Committing'),
      title: t('Committing paper'),
      message: t('OntoForge is writing the parsed paper, assertions, and evidence links into the workspace.')
    },
    error: {
      label: t('Needs Attention'),
      title: t('Import failed'),
      message: t('The paper could not finish the current import step. Review the error details below.')
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

  const canCommit = status === 'preview_ready' && Boolean(upload_id && paperImport.preview_id);
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

        {error_message && (
          <div className="preview-error-section">
            <div className="error-content">
              <h3 className="error-title">{t("Import Error")}</h3>
              <p className="error-message">{localizeMessage(error_message)}</p>
            </div>
          </div>
        )}

        {/* Stats Section */}
        {preview && (
          <div className="preview-stats-section">
            <h2 className="section-title">{t("📊 Extraction Summary")}</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{preview.chunk_count}</div>
                <div className="stat-label">{t("Text Chunks")}</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{preview.formula_count}</div>
                <div className="stat-label">{t("Formulas")}</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{preview.assertion_count}</div>
                <div className="stat-label">{t("Assertions")}</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{preview.evidence_count}</div>
                <div className="stat-label">{t("Evidence Links")}</div>
              </div>
            </div>
          </div>
        )}

        {/* Metadata Section */}
        <div className="preview-metadata-section">
          <h2 className="section-title">{t("📄 Paper Metadata")}</h2>
          <div className="metadata-grid">
            {preview && (
              <>
                <div className="metadata-row">
                  <span className="metadata-label">{t("Title:")}</span>
                  <span className="metadata-value">{preview.title}</span>
                </div>
                {preview.authors && preview.authors.length > 0 && (
                  <div className="metadata-row">
                    <span className="metadata-label">{t("Authors:")}</span>
                    <span className="metadata-value">{preview.authors.join(', ')}</span>
                  </div>
                )}
                {preview.year && (
                  <div className="metadata-row">
                    <span className="metadata-label">{t("Year:")}</span>
                    <span className="metadata-value">{preview.year}</span>
                  </div>
                )}
                {preview.venue && (
                  <div className="metadata-row">
                    <span className="metadata-label">{t("Venue:")}</span>
                    <span className="metadata-value">{preview.venue}</span>
                  </div>
                )}
              </>
            )}
            {!preview && (
              <div className="metadata-row">
                <span className="metadata-label">{t("Title:")}</span>
                <span className="metadata-value">{title || file_name}</span>
              </div>
            )}
            <div className="metadata-row">
              <span className="metadata-label">{t("File:")}</span>
              <span className="metadata-value">{file_name} ({formatFileSize(file_size)}{t(')')}</span>
            </div>
            <div className="metadata-row">
              <span className="metadata-label">{t("Added:")}</span>
              <span className="metadata-value">{formatDateTime(paperImport.created_at)}</span>
            </div>
            <div className="metadata-row">
              <span className="metadata-label">{t("Source:")}</span>
              <span className="metadata-value">{paperImport.source === 'drop' ? t('Drag and drop') : t('File picker')}</span>
            </div>
          </div>
        </div>

        {!upload_id && status === 'preview_ready' && (
          <div className="preview-warning-section">
            <div className="warning-icon">⚠️</div>
            <div className="warning-content">
              <h3 className="warning-title">{t("Upload Reference Missing")}</h3>
              <p className="warning-message">{t("This preview no longer has a backend upload reference. Retry the import before committing it.")}</p>
            </div>
          </div>
        )}

        {/* Warning Section */}
        {warning && !error_message && (
          <div className="preview-warning-section">
            <div className="warning-icon">⚠️</div>
            <div className="warning-content">
              <h3 className="warning-title">{t("Extraction Warning")}</h3>
              <p className="warning-message">{localizeMessage(warning)}</p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="preview-actions">
          {canRetry && <button type="button" className="preview-action-btn secondary" onClick={onConfigureModel}>{t("检查模型接口")}</button>}
          {status === 'preview_ready' && (
            <button
              className="preview-action-btn primary"
              onClick={handleCommit}
              disabled={!canCommit || isCommitting}
            >
              {isCommitting ? t('Committing...') : t('Commit to Workspace')}
            </button>
          )}
          {canRetry && (
            <button
              className="preview-action-btn primary"
              onClick={() => onRetry?.(paperImport.id)}
            >
              {t("Retry Preview")}
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
            {t("Back to Papers")}
          </button>
        </div>
      </div>
    </div>
  );
};

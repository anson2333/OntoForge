import { t, uiLabel, getLocale, localizeMessage, domainTitle } from '../../i18n';
/**
 * Domain Pack Node Component
 * Collapsible tree node showing domain pack details, papers, metrics, and subdomains
 */

import React, { useEffect, useRef, useState } from 'react';
import { LoadedDomainPack, Paper, PaperImportEntry, useWorkspaceStore } from '../../services/workspace';
import { useServiceStatus } from '../../services/service_status';
import './DomainPackNode.css';

interface DomainPackNodeProps {
  domainPack: LoadedDomainPack;
  paperCount: number;
  papers: Paper[];
  paperImports: PaperImportEntry[];
}

type SidebarPaperEntry =
  | { kind: 'paper'; value: Paper }
  | { kind: 'import'; value: PaperImportEntry };

export const DomainPackNode: React.FC<DomainPackNodeProps> = ({
  domainPack,
  paperCount,
  papers,
  paperImports
}) => {
  const [expanded, setExpanded] = useState(true);
  const [showPapers, setShowPapers] = useState(false);
  const [showMetrics, setShowMetrics] = useState(false);
  const [showSubdomains, setShowSubdomains] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [isDraggingOverPapers, setIsDraggingOverPapers] = useState(false);
  const [paperPendingDeletion, setPaperPendingDeletion] = useState<SidebarPaperEntry | null>(null);
  const [hoveredEntry, setHoveredEntry] = useState<SidebarPaperEntry | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{ x: number; y: number } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const activeDomainPacks = useWorkspaceStore(state => state.activeDomainPackNamespaces);
  const allCellData = useWorkspaceStore(state => state.allCellData);
  const selectedPaperId = useWorkspaceStore(state => state.selectedPaperId);
  const selectedPaperImportId = useWorkspaceStore(state => state.selectedPaperImportId);
  const selectedMetricsNamespace = useWorkspaceStore(state => state.selectedMetricsNamespace);
  const selectedMetricFullName = useWorkspaceStore(state => state.selectedMetricFullName);
  const selectedSubdomain = useWorkspaceStore(state => state.selectedSubdomain);
  const setActiveDomainPacks = useWorkspaceStore(state => state.setActiveDomainPacks);
  const removeDomainPack = useWorkspaceStore(state => state.removeDomainPack);
  const selectDomainPack = useWorkspaceStore(state => state.selectDomainPack);
  const enqueuePaperImports = useWorkspaceStore(state => state.enqueuePaperImports);
  const retryPaperImport = useWorkspaceStore(state => state.retryPaperImport);
  const removePaperImport = useWorkspaceStore(state => state.removePaperImport);
  const removePaper = useWorkspaceStore(state => state.removePaper);
  const selectPaper = useWorkspaceStore(state => state.selectPaper);
  const selectPaperImport = useWorkspaceStore(state => state.selectPaperImport);
  const selectMetrics = useWorkspaceStore(state => state.selectMetrics);
  const selectMetric = useWorkspaceStore(state => state.selectMetric);
  const selectSubdomain = useWorkspaceStore(state => state.selectSubdomain);

  const { llmStatus } = useServiceStatus();
  const isActive = activeDomainPacks.includes(domainPack.namespace);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen]);

  const handleToggleActive = () => {
    if (isActive) {
      setActiveDomainPacks(activeDomainPacks.filter(namespace => namespace !== domainPack.namespace));
    } else {
      setActiveDomainPacks([...activeDomainPacks, domainPack.namespace]);
    }
    setMenuOpen(false);
  };

  const handleRemoveDomainPack = () => {
    if (confirm(t('Remove domain pack "{name}"?', { name: domainPack.config.domain.name }))) {
      removeDomainPack(domainPack.namespace);
    }
    setMenuOpen(false);
  };

  const handleFileSelection = (fileList: FileList | null, source: 'drop' | 'file_picker') => {
    if (!fileList) {
      return;
    }

    const files = Array.from(fileList).filter(file => /\.pdf$/i.test(file.name));
    if (files.length === 0) {
      return;
    }

    setShowPapers(true);
    enqueuePaperImports(domainPack.namespace, files, source);
  };

  const handlePapersHeaderClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest('.section-action-btn')) {
      return;
    }
    setShowPapers(current => !current);
  };

  const getPaperEvidenceCount = (paperId: string) => {
    let total = 0;
    allCellData.forEach(cell => {
      if (cell.paperId === paperId) {
        total += cell.evidenceCount;
      }
    });
    return total;
  };

  const getEntryEvidenceCount = (entry: SidebarPaperEntry) => {
    if (entry.kind === 'paper') {
      return getPaperEvidenceCount(entry.value.id);
    }
    return entry.value.preview?.evidence_count ?? 0;
  };

  const getSubdomains = () => {
    const subdomains: string[] = [];
    const taxonomyTree = domainPack.config.domain.taxonomy_tree || [];
    taxonomyTree.forEach(dimension => {
      if (typeof dimension === 'string' || !dimension.subdomain_map) {
        return;
      }
      Object.values(dimension.subdomain_map).forEach(subdomainId => {
        if (typeof subdomainId === 'string' && !subdomains.includes(subdomainId)) {
          subdomains.push(subdomainId);
        }
      });
    });
    return subdomains;
  };

  const sidebarEntries: SidebarPaperEntry[] = [
    ...paperImports
      .slice()
      .sort((left, right) => left.created_at.localeCompare(right.created_at))
      .map(value => ({ kind: 'import' as const, value })),
    ...papers
      .slice()
      .sort((left, right) => left.title.localeCompare(right.title, undefined, { sensitivity: 'base' }))
      .map(value => ({ kind: 'paper' as const, value }))
  ];

  const subdomains = getSubdomains();

  return (
    <div className={`domain-pack-node ${isActive ? 'active' : 'inactive'}`}>
      <div
        className="domain-pack-header"
        onClick={() => {
          selectDomainPack(domainPack.namespace);
          setExpanded(!expanded);
        }}
      >
        <div className="header-content">
          <span className="expand-icon">{expanded ? '▼' : '▶'}</span>
          <div className="pack-info">
            <div className="pack-name-row">
              <span className="pack-icon">📦</span>
              <span className="pack-name">{domainTitle(domainPack.config.domain.name)}</span>
              <span className="pack-namespace">{domainPack.namespace}</span>
            </div>
          </div>
        </div>

        <div className="pack-actions" onClick={event => event.stopPropagation()} ref={menuRef}>
          <button
            className={`btn-icon btn-menu ${menuOpen ? 'active' : ''}`}
            onClick={() => setMenuOpen(!menuOpen)}
            title={t("Domain pack actions")}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            ⋯
          </button>

          {menuOpen && (
            <div className="pack-menu" role="menu">
              <button className="pack-menu-item" onClick={handleToggleActive} role="menuitem">
                <span className="menu-item-icon">{isActive ? '◌' : '●'}</span>
                <span>{isActive ? t("Hide from matrix") : t("Show in matrix")}</span>
              </button>
              <button className="pack-menu-item danger" onClick={handleRemoveDomainPack} role="menuitem">
                <span className="menu-item-icon">×</span>
                <span>{t("Remove domain pack")}</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {expanded && (
        <div className="domain-pack-details">
          <div className="detail-section">
            <div className="section-header-small" onClick={handlePapersHeaderClick}>
              <div className="section-header-title">
                <span className="expand-icon-small">{showPapers ? '▼' : '▶'}</span>
                <span className="section-icon">📄</span>
                <span className="section-label">{t("Papers")}</span>
              </div>
              <span className="section-count">{paperCount}</span>
              <div
                className="section-header-actions"
                onMouseDown={event => event.stopPropagation()}
                onClick={event => event.stopPropagation()}
              >
                <button
                  type="button"
                  className="section-action-btn"
                  title={t("Add PDF to this domain")}
                  onMouseDown={event => event.stopPropagation()}
                  onClick={event => {
                    event.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                >
                  +
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  multiple
                  hidden
                  onChange={event => {
                    handleFileSelection(event.target.files, 'file_picker');
                    event.target.value = '';
                  }}
                />
              </div>
            </div>

            {showPapers && (
              <>
                {!llmStatus.enabled && (
                  <div className="llm-warning-banner" style={{
                    padding: '8px 12px',
                    margin: '8px 12px 0',
                    background: 'rgba(255, 183, 77, 0.1)',
                    border: '1px solid rgba(255, 183, 77, 0.3)',
                    borderRadius: '4px',
                    fontSize: '12px',
                    color: '#ffb74d'
                  }}>
                    {t("⚠️ LLM service disabled: Papers will be ingested with basic rule-based classification. For AI-powered subdomain classification, configure LLM in .env file.")}
                  </div>
                )}
                <div
                  className={`section-content papers-drop-zone ${isDraggingOverPapers ? 'drag-over' : ''}`}
                  onDragEnter={event => {
                    event.preventDefault();
                    setIsDraggingOverPapers(true);
                  }}
                  onDragOver={event => {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = 'copy';
                  }}
                  onDragLeave={event => {
                    event.preventDefault();
                    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                      setIsDraggingOverPapers(false);
                    }
                  }}
                  onDrop={event => {
                    event.preventDefault();
                    setIsDraggingOverPapers(false);
                    handleFileSelection(event.dataTransfer.files, 'drop');
                  }}
                >
                {sidebarEntries.length > 0 ? (
                  <ul className="papers-list">
                    {sidebarEntries.map(entry => {
                      const isPersistedPaper = entry.kind === 'paper';
                      const paperStatus = isPersistedPaper ? entry.value.ingestion_status : entry.value.status;
                      const paperYear = isPersistedPaper ? entry.value.year : entry.value.preview?.year;
                      const isSelected = isPersistedPaper 
                        ? selectedPaperId === entry.value.id 
                        : selectedPaperImportId === entry.value.id;
                      const subtitle = isPersistedPaper
                        ? [entry.value.authors.join(', '), entry.value.venue].filter(Boolean).join(' · ')
                        : entry.value.preview
                          ? [entry.value.preview.authors.join(', '), entry.value.preview.venue].filter(Boolean).join(' · ')
                          : entry.value.file_name;

                      return (
                        <li
                          key={entry.value.id}
                          className={`paper-item ${isSelected ? 'selected' : ''}`}
                        >
                          <button
                            type="button"
                            className="paper-row-button"
                            onClick={() => {
                              if (isPersistedPaper) {
                                selectPaper(entry.value.id);
                              } else {
                                selectPaperImport(entry.value.id);
                              }
                            }}
                            onMouseEnter={(e) => {
                              const rect = e.currentTarget.getBoundingClientRect();
                              setHoveredEntry(entry);
                              setHoverPosition({ x: rect.right + 10, y: rect.top });
                            }}
                            onMouseLeave={() => {
                              setHoveredEntry(null);
                              setHoverPosition(null);
                            }}
                          >
                            <span className="paper-main">
                              <span className="paper-title">{entry.value.title}</span>
                              <span className="paper-subtitle">{subtitle || t("Awaiting preview metadata")}</span>
                            </span>
                            <span className="paper-status" data-status={paperStatus}>{uiLabel(paperStatus)}</span>
                            {typeof paperYear === 'number' && <span className="paper-year">{paperYear}</span>}
                          </button>
                          {!isPersistedPaper && entry.value.status === 'error' && (
                            <button
                              type="button"
                              className="paper-retry-btn"
                              title={t("Retry import preview")}
                              onClick={event => {
                                event.stopPropagation();
                                retryPaperImport(entry.value.id);
                              }}
                            >
                              ↻
                            </button>
                          )}
                          <button
                            type="button"
                            className="paper-remove-btn"
                            title={t("Remove paper from sidebar")}
                            onClick={event => {
                              event.stopPropagation();
                              setPaperPendingDeletion(entry);
                            }}
                          >
                            ×
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="empty-message">{t("Drop PDF files here or use + to add a paper to this domain")}</p>
                )}
                </div>
              </>
            )}
          </div>

          <div className="detail-section">
            <div
              className={`section-header-small ${selectedMetricsNamespace === domainPack.namespace ? 'selected' : ''}`}
              onClick={() => {
                setShowMetrics(true);
                selectMetrics(domainPack.namespace, 'registry');
              }}
            >
              <div className="section-header-title">
                <span className="expand-icon-small">{showMetrics ? '▼' : '▶'}</span>
                <span className="section-icon">📊</span>
                <span className="section-label">{t("Metrics")}</span>
              </div>
              <span className="section-count">{domainPack.metrics.length}</span>
              <div
                className="section-header-actions"
                onMouseDown={event => event.stopPropagation()}
                onClick={event => event.stopPropagation()}
              >
                <button
                  type="button"
                  className="section-action-btn"
                  title={t("Add metric to this domain")}
                  onClick={() => {
                    setShowMetrics(true);
                    selectMetrics(domainPack.namespace, 'add');
                  }}
                >
                  +
                </button>
              </div>
            </div>

            {showMetrics && (
              <div className="section-content">
                <ul className="metrics-list">
                  {domainPack.metrics.map(metric => (
                    <li
                      key={metric.full_name}
                      className={`metric-item ${selectedMetricFullName === metric.full_name ? 'selected' : ''}`}
                    >
                      <button
                        type="button"
                        className="metric-row-button"
                        onClick={() => selectMetric(metric.full_name)}
                      >
                        <span className="metric-name">{metric.name}</span>
                        <span className="metric-unit">[{metric.unit}]</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {subdomains.length > 0 && (
            <div className="detail-section">
              <div className="section-header-small" onClick={() => setShowSubdomains(!showSubdomains)}>
                <div className="section-header-title">
                  <span className="expand-icon-small">{showSubdomains ? '▼' : '▶'}</span>
                  <span className="section-icon">🏷️</span>
                  <span className="section-label">{t("Subdomains")}</span>
                </div>
                <span className="section-count">{subdomains.length}</span>
              </div>

              {showSubdomains && (
                <div className="section-content">
                  <ul className="subdomains-list">
                    {subdomains.map(subdomain => (
                      <li
                        key={subdomain}
                        className={`subdomain-item ${
                          selectedSubdomain?.namespace === domainPack.namespace && selectedSubdomain.id === subdomain
                            ? 'selected'
                            : ''
                        }`}
                      >
                        <button
                          type="button"
                          className="subdomain-row-button"
                          onClick={() => selectSubdomain({ namespace: domainPack.namespace, id: subdomain })}
                        >
                          {subdomain.split('.').pop()}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {paperPendingDeletion && (
        <div className="paper-delete-overlay" onClick={() => setPaperPendingDeletion(null)}>
          <div className="paper-delete-dialog" onClick={event => event.stopPropagation()}>
            <div className="paper-delete-titlebar">
              <span>{t("Delete Paper")}</span>
              <button
                type="button"
                className="paper-delete-close"
                onClick={() => setPaperPendingDeletion(null)}
                aria-label={t("Close delete dialog")}
              >
                ×
              </button>
            </div>
            <div className="paper-delete-body">
              <div className="paper-delete-row">
                <span className="paper-delete-label">{t("Title:")}</span>
                <span className="paper-delete-value">{paperPendingDeletion.value.title}</span>
              </div>
              <div className="paper-delete-row">
                <span className="paper-delete-label">{t("Number of evidences:")}</span>
                <span className="paper-delete-value">{getEntryEvidenceCount(paperPendingDeletion)}</span>
              </div>
              <div className="paper-delete-warning">{t("Deletion is not recoverable. Proceed?")}</div>
            </div>
            <div className="paper-delete-actions">
              <button
                type="button"
                className="paper-delete-btn secondary"
                onClick={() => setPaperPendingDeletion(null)}
              >
                {t("Cancel")}
              </button>
              <button
                type="button"
                className="paper-delete-btn danger"
                onClick={() => {
                  if (paperPendingDeletion.kind === 'paper') {
                    removePaper(paperPendingDeletion.value.id);
                  } else {
                    removePaperImport(paperPendingDeletion.value.id);
                  }
                  setPaperPendingDeletion(null);
                }}
              >
                {t("Delete")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hover Tooltip for Papers and Imports */}
      {hoveredEntry && hoverPosition && (
        <div
          className="paper-hover-tooltip"
          style={{
            position: 'fixed',
            left: `${hoverPosition.x}px`,
            top: `${hoverPosition.y}px`,
            zIndex: 10000,
          }}
          onMouseEnter={() => {
            // Keep tooltip visible when hovering over it
            setHoveredEntry(hoveredEntry);
          }}
          onMouseLeave={() => {
            setHoveredEntry(null);
            setHoverPosition(null);
          }}
        >
          {(() => {
            const isPaper = hoveredEntry.kind === 'paper';
            const paper = isPaper ? (hoveredEntry.value as Paper) : undefined;
            const paperImport = !isPaper ? (hoveredEntry.value as PaperImportEntry) : undefined;
            
            const formatFileSize = (bytes: number) => {
              if (bytes < 1024) return `${bytes} B`;
              if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
              return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
            };

            const formatDate = (isoString: string) => {
              const date = new Date(isoString);
              return date.toLocaleDateString(getLocale(), { year: 'numeric', month: 'short', day: 'numeric' });
            };

            // For successfully ingested papers
            if (isPaper && paper) {
              return (
                <>
                  <div className="tooltip-body">
                    <div className="tooltip-info">
                      {paper.ingested_at && (
                        <div className="tooltip-meta" style={{ fontSize: '13px', textAlign: 'center', padding: '8px' }}>
                          <strong>{t("Ingested:")}</strong> {formatDate(paper.ingested_at)}
                        </div>
                      )}
                      {!paper.ingested_at && (
                        <div className="tooltip-meta" style={{ fontSize: '12px', textAlign: 'center', padding: '8px', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                          {t("Import date not available")}
                        </div>
                      )}
                    </div>
                  </div>
                </>
              );
            }

            // For imports in progress or with errors
            if (!paperImport) return null;

            const statusLabels: Record<string, string> = {
              queued: t("Queued for processing"),
              validating: t("Validating and extracting preview"),
              preview_ready: t("Ready to commit"),
              ingesting: t("Committing to workspace"),
              error: t('Import failed')
            };

            return (
              <>
                <div className="tooltip-header">
                  <div className="tooltip-status" data-status={paperImport.status}>
                    {statusLabels[paperImport.status] || paperImport.status}
                  </div>
                </div>

                <div className="tooltip-body">
                  {paperImport.status === 'error' && paperImport.error_message && (
                    <div className="tooltip-error">
                      <div className="tooltip-section-title">{t("Error:")}</div>
                      <div className="tooltip-error-message">{localizeMessage(paperImport.error_message)}</div>
                    </div>
                  )}

                  {paperImport.status === 'preview_ready' && paperImport.preview && (
                    <div className="tooltip-preview">
                      <div className="tooltip-stats">
                        <div className="stat">
                          <span className="stat-value">{paperImport.preview.chunk_count}</span>
                          <span className="stat-label">{t("Chunks")}</span>
                        </div>
                        <div className="stat">
                          <span className="stat-value">{paperImport.preview.formula_count}</span>
                          <span className="stat-label">{t("Formulas")}</span>
                        </div>
                        <div className="stat">
                          <span className="stat-value">{paperImport.preview.assertion_count}</span>
                          <span className="stat-label">{t("Assertions")}</span>
                        </div>
                      </div>
                      {paperImport.preview.authors && paperImport.preview.authors.length > 0 && (
                        <div className="tooltip-meta">
                          <strong>{t("Authors:")}</strong> {paperImport.preview.authors.join(', ')}
                        </div>
                      )}
                      {paperImport.preview.year && (
                        <div className="tooltip-meta">
                          <strong>{t("Year:")}</strong> {paperImport.preview.year}
                        </div>
                      )}
                    </div>
                  )}

                  {(paperImport.status === 'queued' || paperImport.status === 'validating' || paperImport.status === 'ingesting') && (
                    <div className="tooltip-info">
                      <div className="tooltip-file-info">
                        <div><strong>{t("File:")}</strong> {paperImport.file_name}</div>
                        <div><strong>{t("Size:")}</strong> {formatFileSize(paperImport.file_size)}</div>
                      </div>
                      {paperImport.status === 'validating' && (
                        <div className="tooltip-message">{t("⏳ Extracting text and analyzing content...")}</div>
                      )}
                      {paperImport.status === 'ingesting' && paperImport.preview && (
                        <div className="tooltip-stats">
                          <div className="stat">
                            <span className="stat-value">{paperImport.preview.assertion_count}</span>
                            <span className="stat-label">{t("Assertions")}</span>
                          </div>
                          <div className="tooltip-message">{t("⚙️ Building knowledge graph...")}</div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
};

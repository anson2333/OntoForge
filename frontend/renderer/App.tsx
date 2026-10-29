import { useState, useEffect } from 'react';
import MatrixGrid from './components/MatrixGrid';
import DigitalMicroscope from './components/DigitalMicroscope';
import GraphView from './components/GraphView';
import TabBar, { TabId } from './components/TabBar';
import { IntentBranchSelector, IntentDeclarationModal, IntentProfilePanel } from './components/intent';
import { WorkspaceSidebar } from './components/workspace/WorkspaceSidebar';
import { RootView } from './components/workspace/RootView';
import { WorkspaceView } from './components/workspace/WorkspaceView';
import { DomainPackView } from './components/workspace/DomainPackView';
import { PaperPreviewView } from './components/workspace/PaperPreviewView';
import { MetricsView } from './components/workspace/MetricsView';
import { MetricView } from './components/workspace/MetricView';
import { SubdomainView } from './components/workspace/SubdomainView';
import { StatusIndicator } from './components/StatusIndicator';
import { useWorkspaceStore } from './services/workspace';
import { intentService } from './services/intent_service';
import { useServiceStatus } from './services/service_status';

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('matrix');
  const [selectedCell, setSelectedCell] = useState<{paperId: string, metricName: string} | null>(null);
  const [showIntentModal, setShowIntentModal] = useState(false);
  const [showProfilePanel, setShowProfilePanel] = useState(false);
  const [intentProfileRefreshToken, setIntentProfileRefreshToken] = useState(0);
  const [showSidebar, setShowSidebar] = useState(true);
  const [evidencePanelHeight, setEvidencePanelHeight] = useState(350);
  const [isResizingEvidence, setIsResizingEvidence] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const savedTheme = localStorage.getItem('ontoforge-theme');
    return savedTheme === 'light' ? 'light' : 'dark';
  });
  const workspace = useWorkspaceStore();
  const windowTitle = 'OntoForge';
  const { backendStatus, llmStatus } = useServiceStatus();

  // Calculate ingestion progress
  const ingestingPapers = workspace.paperImports.filter(p => 
    p.status === 'validating' || p.status === 'ingesting'
  );
  const queuedPapers = workspace.paperImports.filter(p => p.status === 'queued');
  
  const getStatusMessage = () => {
    if (workspace.isLoading) return 'Loading...';
    if (ingestingPapers.length > 0) {
      const paper = ingestingPapers[0];
      const action = paper.status === 'validating' ? 'Validating' : 'Parsing';
      const truncated = paper.title.length > 30 ? paper.title.slice(0, 30) + '...' : paper.title;
      const more = ingestingPapers.length > 1 ? ` (+${ingestingPapers.length - 1} more)` : '';
      return `${action} "${truncated}"${more}`;
    }
    if (queuedPapers.length > 0) {
      return `${queuedPapers.length} paper${queuedPapers.length > 1 ? 's' : ''} queued`;
    }
    return 'Ready';
  };

  // Load user intent profile on mount
  useEffect(() => {
    loadIntentProfile();
  }, []);

  useEffect(() => {
    workspace.loadWorkspaces().catch(error => {
      console.error('Failed to load workspaces from backend:', error);
    });
  }, []);

  // Clear evidence selection when workspace changes
  useEffect(() => {
    setSelectedCell(null);
  }, [workspace.currentWorkspaceId]);

  useEffect(() => {
    if (selectedCell && !workspace.papers.some(paper => paper.id === selectedCell.paperId)) {
      setSelectedCell(null);
    }
  }, [workspace.papers, selectedCell]);

  useEffect(() => {
    if (
      activeTab !== 'matrix' &&
      (
        workspace.selectedPaperId ||
        workspace.selectedPaperImportId ||
        workspace.selectedRootView ||
        workspace.selectedWorkspaceViewId ||
        workspace.selectedDomainPackNamespace ||
        workspace.selectedMetricsNamespace ||
        workspace.selectedMetricFullName ||
        workspace.selectedSubdomain
      )
    ) {
      setActiveTab('matrix');
    }
  }, [
    activeTab,
    workspace.selectedPaperId,
    workspace.selectedPaperImportId,
    workspace.selectedRootView,
    workspace.selectedWorkspaceViewId,
    workspace.selectedDomainPackNamespace,
    workspace.selectedMetricsNamespace,
    workspace.selectedMetricFullName,
    workspace.selectedSubdomain
  ]);

  useEffect(() => {
    localStorage.setItem('ontoforge-theme', theme);
  }, [theme]);

  useEffect(() => {
    document.title = windowTitle;
    window.electronAPI?.setWindowTitle(windowTitle).catch(error => {
      console.error('Failed to update window title:', error);
    });
  }, [windowTitle]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || showIntentModal) return;

      const target = event.target as HTMLElement | null;
      const isEditingText =
        target?.tagName === 'INPUT' ||
        target?.tagName === 'TEXTAREA' ||
        target?.tagName === 'SELECT' ||
        target?.isContentEditable;
      const isInsideDialog = Boolean(
        target?.closest('.evidence-editor-overlay, .evidence-history-overlay, .modal-overlay')
      );

      if (selectedCell && !isEditingText && !isInsideDialog) {
        setSelectedCell(null);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedCell, showIntentModal]);

  // Handle evidence panel resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingEvidence) return;
      
      // Calculate height from mouse position to bottom of window minus footer
      const footer = document.querySelector('footer');
      const footerHeight = footer?.clientHeight || 24;
      const newHeight = window.innerHeight - e.clientY - footerHeight;
      
      if (newHeight >= 200 && newHeight <= window.innerHeight - 250) {
        setEvidencePanelHeight(newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsResizingEvidence(false);
    };

    if (isResizingEvidence) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'row-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizingEvidence]);

  const loadIntentProfile = async () => {
    try {
      const profile = await intentService.queryIntentProfile('current_user', 'full');
      workspace.setUserIntentProfile(profile);
    } catch (error) {
      console.error('Failed to load intent profile:', error);
    }
  };

  const handleCellClick = (paperId: string, metricName: string) => {
    setSelectedCell({ paperId, metricName });
  };

  const handleCloseEvidence = () => {
    setSelectedCell(null);
  };

  const handleBranchChange = (branch: any) => {
    workspace.setActiveIntentBranch(branch);
  };

  const handleTabChange = (tabId: TabId) => {
    setActiveTab(tabId);
    // Close evidence panel when switching tabs
    if (tabId !== 'matrix') {
      setSelectedCell(null);
    }
  };

  const handlePaperClickFromGraph = (paperId: string) => {
    // Switch to matrix view and highlight the paper
    setActiveTab('matrix');
    workspace.selectPaper(paperId);
  };

  const toolButtonStyle = {
    padding: '7px 12px',
    backgroundColor: 'var(--surface-bg)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '13px'
  };

  const iconButtonStyle = {
    ...toolButtonStyle,
    width: '30px',
    height: '24px',
    padding: '0',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'stretch',
    fontSize: '14px',
    lineHeight: 1,
    overflow: 'hidden'
  };

  const toggleTheme = () => {
    setTheme(current => current === 'dark' ? 'light' : 'dark');
  };

  const selectedPaperImport = workspace.selectedPaperImportId
    ? workspace.paperImports.find(p => p.id === workspace.selectedPaperImportId)
    : undefined;
  const selectedPaper = workspace.selectedPaperId && activeTab === 'matrix'
    ? workspace.papers.find(p => p.id === workspace.selectedPaperId)
    : undefined;
  const selectedMetric = workspace.selectedMetricFullName
    ? workspace.domainPacks.flatMap(pack => pack.metrics).find(metric => metric.full_name === workspace.selectedMetricFullName)
    : undefined;
  const selectedMetricDomainPack = selectedMetric
    ? workspace.domainPacks.find(pack => pack.namespace === selectedMetric.namespace)
    : undefined;
  const selectedMetricsDomainPack = workspace.selectedMetricsNamespace
    ? workspace.domainPacks.find(pack => pack.namespace === workspace.selectedMetricsNamespace)
    : undefined;
  const selectedSubdomainDomainPack = workspace.selectedSubdomain
    ? workspace.domainPacks.find(pack => pack.namespace === workspace.selectedSubdomain?.namespace)
    : undefined;
  const selectedWorkspaceView = workspace.selectedWorkspaceViewId
    ? workspace.workspaces.find(item => item.id === workspace.selectedWorkspaceViewId)
    : undefined;
  const selectedDomainPackView = workspace.selectedDomainPackNamespace
    ? workspace.domainPacks.find(pack => pack.namespace === workspace.selectedDomainPackNamespace)
    : undefined;
  const isDetailContext = Boolean(
    workspace.selectedRootView ||
    selectedWorkspaceView ||
    selectedDomainPackView ||
    selectedPaperImport ||
    selectedPaper ||
    selectedMetricsDomainPack ||
    selectedMetric ||
    workspace.selectedSubdomain
  );
  const rootLabel = 'Home';
  const workspaceNavLabel = workspace.workspace?.name || 'Workspace';
  const selectWorkspaceContext = () => {
    if (workspace.currentWorkspaceId) {
      workspace.selectWorkspaceView(workspace.currentWorkspaceId);
    } else {
      workspace.selectRoot();
    }
    setSelectedCell(null);
  };
  const getDomainPackSubdomains = (domainPack: { config: { domain: { taxonomy_tree: unknown[] | string[] } } }) => {
    const subdomains: string[] = [];
    const taxonomyTree = domainPack.config.domain.taxonomy_tree || [];
    taxonomyTree.forEach(dimension => {
      if (typeof dimension === 'string' || !dimension || typeof dimension !== 'object' || !('subdomain_map' in dimension)) {
        return;
      }
      Object.values((dimension as { subdomain_map?: Record<string, string> }).subdomain_map || {}).forEach(subdomainId => {
        if (typeof subdomainId === 'string' && !subdomains.includes(subdomainId)) {
          subdomains.push(subdomainId);
        }
      });
    });
    return subdomains;
  };
  const buildDomainHierarchy = (
    domainPack: { namespace: string; config: { domain: { name: string } } },
    section?: { label: string; onClick?: () => void },
    leaf?: string
  ) => [
    { label: rootLabel, onClick: workspace.selectRoot },
    { label: workspaceNavLabel, onClick: selectWorkspaceContext },
    { label: domainPack.config.domain.name, onClick: () => workspace.selectDomainPack(domainPack.namespace) },
    ...(section ? [section] : []),
    ...(leaf ? [{ label: leaf }] : [])
  ];

  const renderToolbarTools = () => {
    if (isDetailContext) {
      return (
        <>
          <button style={toolButtonStyle} onClick={toggleTheme} title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}>
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </>
      );
    }

    return (
      <>
        <IntentBranchSelector onBranchChange={handleBranchChange} />
        <button style={toolButtonStyle} onClick={() => setShowProfilePanel(!showProfilePanel)}>
          Intents
        </button>
        <button style={toolButtonStyle} onClick={() => workspace.refreshData()}>
          Refresh
        </button>
        <button style={toolButtonStyle} onClick={toggleTheme} title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}>
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
      </>
    );
  };

  return (
    <div
      data-theme={theme}
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        backgroundColor: 'var(--app-bg)',
        color: 'var(--text-primary)'
      }}
    >
      <TabBar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        title="OntoForge"
        rightContent={renderToolbarTools()}
      />

      {/* Main Content - 3 Column Layout */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left Sidebar - Workspace Navigation */}
        {showSidebar && <WorkspaceSidebar onClose={() => setShowSidebar(false)} />}
        
        {/* Center - Content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', backgroundColor: 'var(--app-bg)' }}>
          {/* Content Area */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', backgroundColor: 'var(--app-bg)' }}>
          {/* Matrix View */}
          {activeTab === 'matrix' && (
            workspace.selectedRootView ? (
              <RootView
                workspaces={workspace.workspaces}
                currentWorkspaceId={workspace.currentWorkspaceId}
                hierarchyItems={[{ label: rootLabel }]}
                onOpenWorkspace={async (workspaceId) => {
                  if (workspaceId !== workspace.currentWorkspaceId) {
                    await workspace.switchWorkspace(workspaceId);
                  }
                  workspace.selectWorkspaceView(workspaceId);
                }}
              />
            ) : selectedWorkspaceView ? (
              <WorkspaceView
                workspace={selectedWorkspaceView}
                domainPacks={workspace.domainPacks}
                papers={workspace.papers}
                paperImports={workspace.paperImports}
                hierarchyItems={[
                  { label: rootLabel, onClick: workspace.selectRoot },
                  { label: selectedWorkspaceView.name }
                ]}
                onOpenDomainPack={(namespace) => workspace.selectDomainPack(namespace)}
              />
            ) : selectedDomainPackView ? (
              <DomainPackView
                domainPack={selectedDomainPackView}
                papers={workspace.papers.filter(paper => paper.domain_pack_namespace === selectedDomainPackView.namespace)}
                paperImports={workspace.paperImports.filter(entry => entry.domain_pack_namespace === selectedDomainPackView.namespace)}
                subdomains={getDomainPackSubdomains(selectedDomainPackView)}
                hierarchyItems={[
                  { label: rootLabel, onClick: workspace.selectRoot },
                  { label: workspaceNavLabel, onClick: selectWorkspaceContext },
                  { label: selectedDomainPackView.config.domain.name }
                ]}
                onOpenMetrics={() => workspace.selectMetrics(selectedDomainPackView.namespace, 'registry')}
                onOpenSubdomain={(subdomainId) => workspace.selectSubdomain({ namespace: selectedDomainPackView.namespace, id: subdomainId })}
                onOpenPaper={(paperId) => workspace.selectPaper(paperId)}
                onOpenPaperImport={(paperImportId) => workspace.selectPaperImport(paperImportId)}
              />
            ) : selectedPaperImport ? (
              <PaperPreviewView
                paperImport={selectedPaperImport}
                hierarchyItems={buildDomainHierarchy(
                  workspace.domainPacks.find(pack => pack.namespace === selectedPaperImport.domain_pack_namespace) || {
                    namespace: selectedPaperImport.domain_pack_namespace,
                    config: { domain: { name: selectedPaperImport.domain_pack_namespace } }
                  },
                  {
                    label: 'Papers',
                    onClick: () => workspace.selectPaperImport(null)
                  },
                  selectedPaperImport.title || selectedPaperImport.file_name
                )}
                onCommit={async (id) => {
                  await workspace.commitPaperImport(id);
                  workspace.selectPaperImport(null);
                }}
                onRetry={(id) => workspace.retryPaperImport(id)}
                onCancel={() => workspace.selectPaperImport(null)}
              />
            ) : selectedMetric && selectedMetricDomainPack ? (
              <MetricView
                metric={selectedMetric}
                domainPack={selectedMetricDomainPack}
                papers={workspace.papers}
                cellData={workspace.allCellData}
                hierarchyItems={buildDomainHierarchy(
                  selectedMetricDomainPack,
                  {
                    label: 'Metrics',
                    onClick: () => workspace.selectMetrics(selectedMetric.namespace, 'registry')
                  },
                  selectedMetric.name
                )}
                onSave={(originalName, metric) => workspace.updateMetric(selectedMetric.namespace, originalName, metric)}
                onDelete={(metric) => workspace.deleteMetric(metric.namespace, metric.name)}
              />
            ) : selectedMetricsDomainPack ? (
              <MetricsView
                domainPack={selectedMetricsDomainPack}
                mode={workspace.selectedMetricsMode}
                hierarchyItems={buildDomainHierarchy(
                  selectedMetricsDomainPack,
                  {
                    label: 'Metrics',
                    onClick: () => workspace.selectMetrics(selectedMetricsDomainPack.namespace, 'registry')
                  },
                  workspace.selectedMetricsMode === 'add' ? 'Add Metric' : undefined
                )}
                onOpenAdd={() => workspace.selectMetrics(selectedMetricsDomainPack.namespace, 'add')}
                onAddMetric={(metric) => workspace.addMetric(selectedMetricsDomainPack.namespace, metric)}
                onEditMetric={(metric) => workspace.selectMetric(metric.full_name)}
                onDeleteMetric={(metric) => workspace.deleteMetric(metric.namespace, metric.name)}
              />
            ) : workspace.selectedSubdomain && selectedSubdomainDomainPack ? (
              <SubdomainView
                subdomainId={workspace.selectedSubdomain.id}
                domainPack={selectedSubdomainDomainPack}
                papers={workspace.papers}
                metrics={selectedSubdomainDomainPack.metrics}
                hierarchyItems={buildDomainHierarchy(
                  selectedSubdomainDomainPack,
                  {
                    label: 'Subdomains',
                    onClick: () => workspace.selectSubdomain(null)
                  },
                  workspace.selectedSubdomain.id.split('.').pop() || workspace.selectedSubdomain.id
                )}
              />
            ) : (
              <>
                {/* Matrix Grid */}
                <div style={{ 
                  height: selectedCell ? `calc(100% - ${evidencePanelHeight}px - 5px)` : '100%',
                  flexShrink: 0,
                  overflow: 'auto'
                }}>
                  <MatrixGrid onCellClick={handleCellClick} selectedCell={selectedCell} />
                </div>

              {/* Digital Microscope (Evidence Viewer) */}
              {selectedCell && (
                <>
                  {/* Resize Handle */}
                  <div 
                    style={{
                      height: '5px',
                      backgroundColor: isResizingEvidence ? 'var(--primary-color)' : 'var(--border-color)',
                      cursor: 'row-resize',
                      flexShrink: 0,
                      zIndex: 10,
                      transition: isResizingEvidence ? 'none' : 'background-color 0.2s'
                    }}
                    onMouseDown={() => setIsResizingEvidence(true)}
                    onMouseEnter={(e) => {
                      if (!isResizingEvidence) {
                        e.currentTarget.style.backgroundColor = 'var(--primary-color)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isResizingEvidence) {
                        e.currentTarget.style.backgroundColor = 'var(--border-color)';
                      }
                    }}
                  />
                  
                  <div style={{ 
                    flex: 1,
                    minHeight: 0,
                    overflow: 'auto',
                    display: 'flex',
                    flexDirection: 'column'
                  }}>
                    <DigitalMicroscope
                      paperId={selectedCell.paperId}
                      metricName={selectedCell.metricName}
                      onClose={handleCloseEvidence}
                    />
                  </div>
                </>
              )}
              </>
            )
          )}

          {/* Graph View */}
          {activeTab === 'graph' && (
            <GraphView onPaperClick={handlePaperClickFromGraph} />
          )}

          {/* Timeline View (Placeholder) */}
          {activeTab === 'timeline' && (
            <div style={{ 
              flex: 1, 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              flexDirection: 'column',
              gap: '16px'
            }}>
              <h2 style={{ color: '#999999' }}>📅 Timeline View</h2>
              <p style={{ color: 'var(--text-secondary)' }}>Coming soon...</p>
            </div>
          )}
          </div>
        </div>

        {/* Right Panel - Intent Profile (Optional) */}
        {showProfilePanel && (
          <div style={{ 
            width: '400px', 
            borderLeft: '1px solid var(--border-color)',
            backgroundColor: 'var(--panel-bg)',
            overflow: 'auto'
          }}>
            <IntentProfilePanel 
              userId="current_user"
              refreshToken={intentProfileRefreshToken}
              onDeclareIntent={() => setShowIntentModal(true)}
              onPatternClick={(pattern) => {
                console.log('Apply pattern:', pattern);
              }}
            />
          </div>
        )}
      </div>

      {/* Status Bar */}
      <footer style={{
        padding: '8px 16px',
        backgroundColor: 'var(--chrome-bg)',
        borderTop: '1px solid var(--border-color)',
        fontSize: '12px',
        display: 'flex',
        justifyContent: 'space-between',
        gap: '16px',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
          <button
            style={{
              ...iconButtonStyle,
              fontSize: '13px'
            }}
            onClick={() => setShowSidebar(current => !current)}
            title={showSidebar ? 'Hide workspace sidebar' : 'Show workspace sidebar'}
            aria-label={showSidebar ? 'Hide workspace sidebar' : 'Show workspace sidebar'}
          >
            <span
              style={{
                width: '40%',
                height: '100%',
                backgroundColor: showSidebar ? 'var(--text-primary)' : 'transparent',
                borderRight: '1px solid var(--border-strong)'
              }}
            />
            <span
              style={{
                width: '60%',
                height: '100%',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-primary)',
                backgroundColor: 'transparent',
                fontSize: '11px',
                fontWeight: 700
              }}
            />
          </button>
          <span style={{ 
            display: 'flex', 
            alignItems: 'center',
            gap: '8px'
          }}>
            <span style={{ fontWeight: 600 }}>
              {getStatusMessage()}
            </span>
            {ingestingPapers.length > 0 && (
              <span className="ingestion-spinner" style={{
                display: 'inline-block',
                width: '12px',
                height: '12px',
                border: '2px solid var(--border-color)',
                borderTopColor: 'var(--primary-color)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
              }} />
            )}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <StatusIndicator
            status={backendStatus.status}
            label="Backend"
            tooltip={backendStatus.message}
          />
          <StatusIndicator
            status={llmStatus.status}
            label="LLM"
            tooltip={
              llmStatus.enabled 
                ? `Backend → LLM Server: ${llmStatus.provider || 'Unknown'}${llmStatus.model ? ` (${llmStatus.model})` : ''} - ${llmStatus.message}` 
                : 'Backend → LLM Server: Disabled (paper ingestion will use fallback classification)'
            }
          />
          {workspace.userIntentProfile && (
            <>
              <span style={{ marginLeft: '4px', opacity: 0.5 }}>|</span>
              <span style={{ opacity: 0.7, fontSize: '11px' }}>
                {workspace.learnedPatterns.length} patterns learned
              </span>
            </>
          )}
          <button
            style={{
              ...toolButtonStyle,
              padding: '3px 8px',
              fontSize: '14px',
              marginLeft: '4px'
            }}
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </footer>

      {/* Intent Declaration Modal */}
      <IntentDeclarationModal
        isOpen={showIntentModal}
        onClose={() => setShowIntentModal(false)}
        onSuccess={(intentId) => {
          console.log('Intent declared:', intentId);
          loadIntentProfile();
          setIntentProfileRefreshToken(current => current + 1);
        }}
      />
    </div>
  );
}

export default App;

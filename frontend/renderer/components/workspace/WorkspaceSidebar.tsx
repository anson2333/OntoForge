import { t, uiLabel } from '../../i18n';
/**
 * Workspace Sidebar Component
 * Tree-based navigation showing workspace → domain packs → papers/subdomains
 * Section 2.0 and Phase C multi-domain-pack architecture
 */

import React, { useState, useRef, useEffect } from 'react';
import { useWorkspaceStore } from '../../services/workspace';
import { DomainPackNode } from './DomainPackNode';
import { AddDomainPackModal } from './AddDomainPackModal';
import { CreateWorkspaceModal } from './CreateWorkspaceModal';
import { WorkspaceMembersModal } from './WorkspaceMembersModal';
import { useAuthStore } from '../../services/auth';
import { TaxonomyDimension } from '../domain/DomainPackPanel';
import './WorkspaceSidebar.css';

interface WorkspaceSidebarProps {
  onClose?: () => void;
}

const getWorkspaceTag = (status: string, isSelected: boolean) => {
  if (isSelected) {
    return { label: t("Active"), tone: 'active' };
  }

  if (status === 'archived' || status === 'readonly') {
    return { label: status, tone: status };
  }

  return null;
};

export const WorkspaceSidebar: React.FC<WorkspaceSidebarProps> = ({ onClose }) => {
  const workspaces = useWorkspaceStore(state => state.workspaces);
  const workspace = useWorkspaceStore(state => state.workspace);
  const currentWorkspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const domainPacks = useWorkspaceStore(state => state.domainPacks);
  const activeDomainPackNamespaces = useWorkspaceStore(state => state.activeDomainPackNamespaces);
  const papers = useWorkspaceStore(state => state.papers);
  const paperImports = useWorkspaceStore(state => state.paperImports);
  const addDomainPack = useWorkspaceStore(state => state.addDomainPack);
  const switchWorkspace = useWorkspaceStore(state => state.switchWorkspace);
  const createWorkspace = useWorkspaceStore(state => state.createWorkspace);
  const deleteWorkspace = useWorkspaceStore(state => state.deleteWorkspace);
  const selectRoot = useWorkspaceStore(state => state.selectRoot);
  const selectWorkspaceView = useWorkspaceStore(state => state.selectWorkspaceView);
  const [expandedWorkspaceId, setExpandedWorkspaceId] = useState<string | null>(currentWorkspaceId);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState<string | null>(null);
  const [taxonomyExpanded, setTaxonomyExpanded] = useState(false);
  const [taxonomyFiltersByWorkspace, setTaxonomyFiltersByWorkspace] = useState<Record<string, Record<string, string[]>>>({});
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const [isResizing, setIsResizing] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showCreateWorkspaceModal, setShowCreateWorkspaceModal] = useState(false);
  const [membersWorkspaceId, setMembersWorkspaceId] = useState<string | null>(null);
  const currentUserId = useAuthStore(state => state.user?.user_id);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const workspaceMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      
      const newWidth = e.clientX;
      if (newWidth >= 240 && newWidth <= 600) {
        setSidebarWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  useEffect(() => {
    setExpandedWorkspaceId(currentWorkspaceId);
  }, [currentWorkspaceId]);

  // Close workspace menu when clicking outside
  useEffect(() => {
    if (!workspaceMenuOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (workspaceMenuRef.current && !workspaceMenuRef.current.contains(event.target as Node)) {
        setWorkspaceMenuOpen(null);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setWorkspaceMenuOpen(null);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [workspaceMenuOpen]);

  if (!workspace) {
    return (
      <div className="workspace-sidebar" ref={sidebarRef} style={{ width: sidebarWidth }}>
        {/* Workspace Header with Create Button */}
        <div className="workspace-header">
          <div className="workspace-details">
            <h3 className="workspace-name">{t("Workspace")}</h3>
          </div>
          <div className="workspace-header-actions">
            <button
              className="workspace-create-btn"
              onClick={() => setShowCreateWorkspaceModal(true)}
              title={t("Create workspace")}
              aria-label={t("Create workspace")}
            >
              +
            </button>
            {onClose && (
              <button
                className="workspace-close-btn"
                onClick={onClose}
                title={t("Hide workspace sidebar")}
                aria-label={t("Hide workspace sidebar")}
              >
                ×
              </button>
            )}
          </div>
        </div>

        <div className="no-workspace">
          <p>{t("Click + to create workspace")}</p>
        </div>
        {showCreateWorkspaceModal && (
          <CreateWorkspaceModal
            onClose={() => setShowCreateWorkspaceModal(false)}
            onCreateWorkspace={createWorkspace}
          />
        )}
        <div 
          className="resize-handle"
          onMouseDown={() => setIsResizing(true)}
        />
      </div>
    );
  }

  const handleWorkspaceNodeClick = async (workspaceId: string) => {
    if (workspaceId !== currentWorkspaceId) {
      setExpandedWorkspaceId(workspaceId);
      setTaxonomyExpanded(false);
      await switchWorkspace(workspaceId);
      selectWorkspaceView(workspaceId);
      return;
    }

    selectWorkspaceView(workspaceId);
    setExpandedWorkspaceId(current => current === workspaceId ? null : workspaceId);
  };

  const handleDeleteWorkspace = async (workspaceId: string, workspaceName: string) => {
    if (confirm(t('Delete workspace "{name}"? This removes all its domains, papers and assertions and cannot be undone.', { name: workspaceName }))) {
      try {
        await deleteWorkspace(workspaceId);
        setWorkspaceMenuOpen(null);
      } catch (error) {
        console.error('Failed to delete workspace:', error);
        alert(t("Failed to delete workspace. See console for details."));
      }
    }
    setWorkspaceMenuOpen(null);
  };

  // Get taxonomy dimensions from active domain packs
  const taxonomyDimensions: TaxonomyDimension[] = [];
  domainPacks.forEach(pack => {
    if (activeDomainPackNamespaces.includes(pack.namespace)) {
      const dims = pack.config.domain.taxonomy_tree || [];
      dims.forEach(dim => {
        if (typeof dim !== 'string') {
          taxonomyDimensions.push(dim as TaxonomyDimension);
        }
      });
    }
  });

  const taxonomyFilters = taxonomyFiltersByWorkspace[workspace.id] || {};
  const hasActiveFilters = Object.values(taxonomyFilters).some(values => values.length > 0);

  const handleFilterChange = (dimension: string, values: string[]) => {
    setTaxonomyFiltersByWorkspace(prev => ({
      ...prev,
      [workspace.id]: {
        ...(prev[workspace.id] || {}),
        [dimension]: values
      }
    }));
  };

  const handleClearAllFilters = () => {
    setTaxonomyFiltersByWorkspace(prev => ({
      ...prev,
      [workspace.id]: {}
    }));
  };

  const handleAddDomainPack = async (domainPackData: any, source: 'file' | 'bootstrap') => {
    try {
      // Extract namespace from domain pack data
      const namespace = domainPackData.domain?.id?.split('.').pop() || 'unknown';
      
      // Add to store (this will update the UI)
      await addDomainPack(namespace, domainPackData);
      
      console.log(`Domain pack added from ${source}:`, namespace);
    } catch (error) {
      console.error('Failed to add domain pack:', error);
      throw error;
    }
  };

  return (
    <div className="workspace-sidebar" ref={sidebarRef} style={{ width: sidebarWidth }}>
      {/* Workspace Header */}
      <div className="workspace-header">
        <div className="workspace-details" onClick={selectRoot}>
          <h3 className="workspace-name">{t("Workspace")}</h3>
        </div>
        <div className="workspace-header-actions">
          <button
            className="workspace-create-btn"
            onClick={() => setShowCreateWorkspaceModal(true)}
            title={t("Create workspace")}
            aria-label={t("Create workspace")}
          >
            +
          </button>
        {onClose && (
          <button
            className="workspace-close-btn"
            onClick={onClose}
            title={t("Hide workspace sidebar")}
            aria-label={t("Hide workspace sidebar")}
          >
            ×
          </button>
        )}
        </div>
      </div>

      {workspaces.map(item => {
        const isSelectedWorkspace = item.id === currentWorkspaceId;
        const isExpandedWorkspace = expandedWorkspaceId === item.id;
        const workspaceTag = getWorkspaceTag(item.status, isSelectedWorkspace);
        const isMenuOpen = workspaceMenuOpen === item.id;

        return (
          <div key={item.id} className={`workspace-node ${isSelectedWorkspace ? 'active' : ''}`}>
            <div className="workspace-root-node">
              <div className="workspace-info" onClick={() => { void handleWorkspaceNodeClick(item.id); }}>
                <span className="expand-icon">{isExpandedWorkspace ? '▼' : '▶'}</span>
                <div className="workspace-details">
                  <div className="workspace-title-row">
                    <div className="workspace-root-name">{item.name}</div>
                    {workspaceTag && (
                      <span className="workspace-status" data-status={workspaceTag.tone}>{workspaceTag.label}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Workspace actions menu */}
              <div 
                className="workspace-actions" 
                onClick={event => event.stopPropagation()} 
                ref={isMenuOpen ? workspaceMenuRef : null}
              >
                <button
                  className={`btn-icon btn-workspace-menu ${isMenuOpen ? 'active' : ''}`}
                  onClick={() => setWorkspaceMenuOpen(isMenuOpen ? null : item.id)}
                  title={t("Workspace actions")}
                  aria-haspopup="menu"
                  aria-expanded={isMenuOpen}
                >
                  ⋯
                </button>

                {isMenuOpen && (
                  <div className="workspace-menu" role="menu">
                    <button
                      className="workspace-menu-item"
                      onClick={() => {
                        setMembersWorkspaceId(item.id);
                        setWorkspaceMenuOpen(null);
                      }}
                      role="menuitem"
                    >
                      <span className="menu-item-icon">◎</span>
                      <span>{t("Manage access")}</span>
                    </button>
                    <button 
                      className="workspace-menu-item danger" 
                      onClick={() => handleDeleteWorkspace(item.id, item.name)} 
                      role="menuitem"
                    >
                      <span className="menu-item-icon">×</span>
                      <span>{t("Delete workspace")}</span>
                    </button>
                  </div>
                )}
              </div>
            </div>

            {isSelectedWorkspace && isExpandedWorkspace && (
              <div className="workspace-children">
                <div className="tree-group domain-packs-tree">
                  <div className="tree-node branch-node domain-pack-branch">
                    <div className="tree-node-main">
                      <span className="expand-icon">▼</span>
                      <span className="tree-node-label">{t("Domain Packs")}</span>
                      <span className="tree-node-count">{domainPacks.length}</span>
                    </div>
                    <button 
                      className="btn-add-domain-pack" 
                      title={t("Add Domain Pack")}
                      onClick={() => setShowAddModal(true)}
                    >
                      +
                    </button>
                  </div>

                  <div className="tree-children domain-packs-list">
                    {domainPacks.map(pack => {
                      const packPapers = papers.filter(p => p.domain_pack_namespace === pack.namespace);
                      const packPaperImports = paperImports.filter(entry => entry.domain_pack_namespace === pack.namespace);
                      return (
                        <DomainPackNode
                          key={pack.namespace}
                          domainPack={pack}
                          paperCount={packPapers.length + packPaperImports.length}
                          papers={packPapers}
                          paperImports={packPaperImports}
                        />
                      );
                    })}
                  </div>

                  {domainPacks.length === 0 && (
                    <div className="tree-empty-state">
                      <p>{t("No domain packs loaded")}</p>
                    </div>
                  )}
                </div>

                {taxonomyDimensions.length > 0 && (
                  <div className="tree-group taxonomy-tree">
                    <div className="tree-node branch-node" onClick={() => setTaxonomyExpanded(!taxonomyExpanded)}>
                      <div className="tree-node-main">
                        <span className="expand-icon">{taxonomyExpanded ? '▼' : '▶'}</span>
                        <span className="tree-node-label">{t("Taxonomy Filters")}</span>
                      </div>
                      {hasActiveFilters && (
                        <button 
                          className="btn-clear-filters"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleClearAllFilters();
                          }}
                          title={t("Clear all filters")}
                        >
                          {t("Clear")}
                        </button>
                      )}
                    </div>
                    
                    {taxonomyExpanded && (
                      <div className="tree-children taxonomy-filters-content">
                        {taxonomyDimensions.map(dimension => {
                          const selected = taxonomyFilters[dimension.name] || [];
                          
                          return (
                            <div key={dimension.name} className="taxonomy-dimension tree-node-leaf-group">
                              <div className="tree-node leaf-node taxonomy-dimension-label">
                                <span className="tree-node-label">{uiLabel(dimension.name)}</span>
                              </div>
                              <div className="dimension-values tree-children">
                                {dimension.values.map(value => {
                                  const isSelected = selected.includes(value);
                                  const hasSubdomain = dimension.subdomain_map?.[value];
                                  
                                  return (
                                    <button
                                      key={value}
                                      onClick={() => {
                                        const newSelected = isSelected
                                          ? selected.filter(v => v !== value)
                                          : [...selected, value];
                                        handleFilterChange(dimension.name, newSelected);
                                      }}
                                      className={`taxonomy-value-btn ${isSelected ? 'selected' : ''}`}
                                      title={hasSubdomain 
                                        ? t('Subdomain: {name}', { name: hasSubdomain })
                                        : t("No subdomain mapping")}
                                    >
                                      {value}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* Resize Handle */}
      <div 
        className="resize-handle"
        onMouseDown={() => setIsResizing(true)}
      />

      {/* Add Domain Pack Modal */}
      {showAddModal && (
        <AddDomainPackModal
          onClose={() => setShowAddModal(false)}
          onAddDomainPack={handleAddDomainPack}
        />
      )}

      {showCreateWorkspaceModal && (
        <CreateWorkspaceModal
          onClose={() => setShowCreateWorkspaceModal(false)}
          onCreateWorkspace={createWorkspace}
        />
      )}

      {membersWorkspaceId && (() => {
        const selected = workspaces.find(item => item.id === membersWorkspaceId);
        return selected ? (
          <WorkspaceMembersModal
            workspaceId={selected.id}
            workspaceName={selected.name}
            canManage={selected.owner_id === currentUserId}
            onClose={() => setMembersWorkspaceId(null)}
          />
        ) : null;
      })()}
    </div>
  );
};

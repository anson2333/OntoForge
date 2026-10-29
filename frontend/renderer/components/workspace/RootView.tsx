/**
 * Root View
 * Collection surface for all workspaces.
 */

import React from 'react';
import { WorkspaceInfo } from '../../services/workspace';
import { HierarchyNav, HierarchyNavItem } from './HierarchyNav';
import './RootView.css';

interface RootViewProps {
  workspaces: WorkspaceInfo[];
  currentWorkspaceId: string;
  hierarchyItems: HierarchyNavItem[];
  onOpenWorkspace: (workspaceId: string) => void;
}

export const RootView: React.FC<RootViewProps> = ({
  workspaces,
  currentWorkspaceId,
  hierarchyItems,
  onOpenWorkspace
}) => {
  return (
    <div className="root-view">
      <div className="root-view-header">
        <HierarchyNav items={hierarchyItems} />
        <div className="root-context-pill">{workspaces.length} workspaces</div>
      </div>

      <div className="root-view-content">
        <section className="root-panel">
          <div className="root-panel-header">
            <h2>Workspaces</h2>
          </div>
          {workspaces.length > 0 ? (
            <div className="root-workspace-grid">
              {workspaces.map(workspace => (
                <button
                  type="button"
                  className={`root-workspace-card ${workspace.id === currentWorkspaceId ? 'active' : ''}`}
                  key={workspace.id}
                  onClick={() => onOpenWorkspace(workspace.id)}
                >
                  <span className="root-workspace-name">{workspace.name}</span>
                  <span className="root-workspace-meta">{workspace.status}</span>
                  {workspace.description && (
                    <span className="root-workspace-description">{workspace.description}</span>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <div className="root-empty-state">No workspaces have been created yet.</div>
          )}
        </section>
      </div>
    </div>
  );
};

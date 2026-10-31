import { t, uiLabel, domainTitle } from '../../i18n';
/**
 * Workspace View
 * Detail surface for a selected workspace.
 */

import React from 'react';
import { LoadedDomainPack, Paper, PaperImportEntry, WorkspaceInfo } from '../../services/workspace';
import { HierarchyNav, HierarchyNavItem } from './HierarchyNav';
import './WorkspaceView.css';

interface WorkspaceViewProps {
  workspace: WorkspaceInfo;
  domainPacks: LoadedDomainPack[];
  papers: Paper[];
  paperImports: PaperImportEntry[];
  hierarchyItems: HierarchyNavItem[];
  onOpenDomainPack: (namespace: string) => void;
}

export const WorkspaceView: React.FC<WorkspaceViewProps> = ({
  workspace,
  domainPacks,
  papers,
  paperImports,
  hierarchyItems,
  onOpenDomainPack
}) => {
  return (
    <div className="workspace-view">
      <div className="workspace-view-header">
        <HierarchyNav items={hierarchyItems} />
        <div className="workspace-context-pill">{uiLabel(workspace.status)}</div>
      </div>

      <div className="workspace-view-content">
        <div className="workspace-title-block">
          <h1>{workspace.name}</h1>
          {workspace.description && <p>{workspace.description}</p>}
        </div>

        <div className="workspace-summary-grid">
          <div className="workspace-summary-item">
            <span>{domainPacks.length}</span>
            <label>{t("Domain Packs")}</label>
          </div>
          <div className="workspace-summary-item">
            <span>{papers.length}</span>
            <label>{t("Papers")}</label>
          </div>
          <div className="workspace-summary-item">
            <span>{paperImports.length}</span>
            <label>{t("Pending Imports")}</label>
          </div>
        </div>

        <section className="workspace-panel">
          <div className="workspace-panel-header">
            <h2>{t("Domain Packs")}</h2>
          </div>
          {domainPacks.length > 0 ? (
            <div className="workspace-domain-list">
              {domainPacks.map(pack => {
                const packPaperCount = papers.filter(paper => paper.domain_pack_namespace === pack.namespace).length;
                const packImportCount = paperImports.filter(entry => entry.domain_pack_namespace === pack.namespace).length;
                return (
                  <button
                    type="button"
                    className="workspace-domain-row"
                    key={pack.namespace}
                    onClick={() => onOpenDomainPack(pack.namespace)}
                  >
                    <span>
                      <strong>{domainTitle(pack.config.domain.name)}</strong>
                      <small>{pack.namespace}</small>
                    </span>
                    <span>{pack.metrics.length} {t("metrics")}</span>
                    <span>{packPaperCount + packImportCount} {t("papers")}</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="workspace-empty-state">{t("No domain packs are attached to this workspace.")}</div>
          )}
        </section>
      </div>
    </div>
  );
};

/**
 * Domain Pack View
 * Detail surface for a selected domain pack.
 */

import React from 'react';
import { LoadedDomainPack, Paper, PaperImportEntry } from '../../services/workspace';
import { HierarchyNav, HierarchyNavItem } from './HierarchyNav';
import './DomainPackView.css';

interface DomainPackViewProps {
  domainPack: LoadedDomainPack;
  papers: Paper[];
  paperImports: PaperImportEntry[];
  subdomains: string[];
  hierarchyItems: HierarchyNavItem[];
  onOpenMetrics: () => void;
  onOpenSubdomain: (subdomainId: string) => void;
  onOpenPaper: (paperId: string) => void;
  onOpenPaperImport: (paperImportId: string) => void;
}

export const DomainPackView: React.FC<DomainPackViewProps> = ({
  domainPack,
  papers,
  paperImports,
  subdomains,
  hierarchyItems,
  onOpenMetrics,
  onOpenSubdomain,
  onOpenPaper,
  onOpenPaperImport
}) => {
  return (
    <div className="domain-pack-view">
      <div className="domain-pack-view-header">
        <HierarchyNav items={hierarchyItems} />
        <div className="domain-pack-context-pill">{domainPack.namespace}</div>
      </div>

      <div className="domain-pack-view-content">
        <div className="domain-pack-title-block">
          <h1>{domainPack.config.domain.name}</h1>
          <p>{domainPack.config.domain.id}</p>
        </div>

        <div className="domain-pack-summary-grid">
          <button type="button" className="domain-pack-summary-item" onClick={onOpenMetrics}>
            <span>{domainPack.metrics.length}</span>
            <label>Metrics</label>
          </button>
          <div className="domain-pack-summary-item">
            <span>{papers.length + paperImports.length}</span>
            <label>Papers</label>
          </div>
          <div className="domain-pack-summary-item">
            <span>{subdomains.length}</span>
            <label>Subdomains</label>
          </div>
        </div>

        <div className="domain-pack-section-grid">
          <section className="domain-pack-panel">
            <div className="domain-pack-panel-header">
              <h2>Papers</h2>
            </div>
            {[...paperImports, ...papers].length > 0 ? (
              <div className="domain-pack-list">
                {paperImports.map(entry => (
                  <button
                    type="button"
                    className="domain-pack-list-row"
                    key={entry.id}
                    onClick={() => onOpenPaperImport(entry.id)}
                  >
                    <span>{entry.title}</span>
                    <small>{entry.status.replace(/_/g, ' ')}</small>
                  </button>
                ))}
                {papers.map(paper => (
                  <button
                    type="button"
                    className="domain-pack-list-row"
                    key={paper.id}
                    onClick={() => onOpenPaper(paper.id)}
                  >
                    <span>{paper.title}</span>
                    <small>{paper.year}</small>
                  </button>
                ))}
              </div>
            ) : (
              <div className="domain-pack-empty-state">No papers are attached to this domain pack.</div>
            )}
          </section>

          <section className="domain-pack-panel">
            <div className="domain-pack-panel-header">
              <h2>Metrics</h2>
              <button type="button" onClick={onOpenMetrics}>Open</button>
            </div>
            <div className="domain-pack-list">
              {domainPack.metrics.map(metric => (
                <div className="domain-pack-list-row passive" key={metric.full_name}>
                  <span>{metric.name.replace(/_/g, ' ')}</span>
                  <small>{metric.unit || 'unitless'}</small>
                </div>
              ))}
            </div>
          </section>

          <section className="domain-pack-panel">
            <div className="domain-pack-panel-header">
              <h2>Subdomains</h2>
            </div>
            {subdomains.length > 0 ? (
              <div className="domain-pack-list">
                {subdomains.map(subdomain => (
                  <button
                    type="button"
                    className="domain-pack-list-row"
                    key={subdomain}
                    onClick={() => onOpenSubdomain(subdomain)}
                  >
                    <span>{subdomain.split('.').pop()?.replace(/_/g, ' ') || subdomain}</span>
                    <small>{subdomain}</small>
                  </button>
                ))}
              </div>
            ) : (
              <div className="domain-pack-empty-state">No subdomains are mapped in this domain pack.</div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

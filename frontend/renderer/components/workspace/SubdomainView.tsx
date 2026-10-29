/**
 * Subdomain View
 * Focused detail surface for a taxonomy subdomain selected from the sidebar.
 */

import React from 'react';
import { TaxonomyDimension } from '../domain';
import { LoadedDomainPack, Metric, Paper } from '../../services/workspace';
import { HierarchyNav, HierarchyNavItem } from './HierarchyNav';
import './SubdomainView.css';

interface SubdomainViewProps {
  subdomainId: string;
  domainPack: LoadedDomainPack;
  papers: Paper[];
  metrics: Metric[];
  hierarchyItems: HierarchyNavItem[];
}

function getMappedValues(domainPack: LoadedDomainPack, subdomainId: string) {
  const taxonomyTree = domainPack.config.domain.taxonomy_tree || [];
  const rows: Array<{ dimension: string; value: string }> = [];

  taxonomyTree.forEach(dimension => {
    if (typeof dimension === 'string') {
      return;
    }

    const structuredDimension = dimension as TaxonomyDimension;
    Object.entries(structuredDimension.subdomain_map || {}).forEach(([value, mappedSubdomain]) => {
      if (mappedSubdomain === subdomainId) {
        rows.push({ dimension: structuredDimension.name, value });
      }
    });
  });

  return rows;
}

export const SubdomainView: React.FC<SubdomainViewProps> = ({
  subdomainId,
  domainPack,
  papers,
  metrics,
  hierarchyItems
}) => {
  const mappedValues = getMappedValues(domainPack, subdomainId);
  const domainPapers = papers.filter(paper => paper.domain_pack_namespace === domainPack.namespace);
  const domainMetrics = metrics.filter(metric => metric.namespace === domainPack.namespace);
  const displayName = subdomainId.split('.').pop()?.replace(/_/g, ' ') || subdomainId;

  return (
    <div className="subdomain-view">
      <div className="subdomain-view-header">
        <HierarchyNav items={hierarchyItems} />
        <div className="subdomain-context-pill">{domainPack.config.domain.name}</div>
      </div>

      <div className="subdomain-view-content">
        <div className="subdomain-title-block">
          <div className="subdomain-kicker">Subdomain</div>
          <h1>{displayName}</h1>
          <div className="subdomain-full-name">{subdomainId}</div>
        </div>

        <div className="subdomain-summary-grid">
          <div className="subdomain-summary-item">
            <span className="subdomain-summary-value">{mappedValues.length}</span>
            <span className="subdomain-summary-label">Mapped Taxonomy Values</span>
          </div>
          <div className="subdomain-summary-item">
            <span className="subdomain-summary-value">{domainPapers.length}</span>
            <span className="subdomain-summary-label">Domain Papers</span>
          </div>
          <div className="subdomain-summary-item">
            <span className="subdomain-summary-value">{domainMetrics.length}</span>
            <span className="subdomain-summary-label">Available Metrics</span>
          </div>
        </div>

        <div className="subdomain-section">
          <h2>Taxonomy Mapping</h2>
          {mappedValues.length > 0 ? (
            <div className="subdomain-mapping-table">
              <div className="subdomain-mapping-row header">
                <span>Dimension</span>
                <span>Value</span>
              </div>
              {mappedValues.map(row => (
                <div className="subdomain-mapping-row" key={`${row.dimension}:${row.value}`}>
                  <span>{row.dimension}</span>
                  <span>{row.value}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="subdomain-empty-state">No taxonomy values are explicitly mapped to this subdomain.</div>
          )}
        </div>

        <div className="subdomain-section">
          <h2>Metrics In Scope</h2>
          {domainMetrics.length > 0 ? (
            <div className="subdomain-metric-list">
              {domainMetrics.map(metric => (
                <div className="subdomain-metric-row" key={metric.full_name}>
                  <span>{metric.name.replace(/_/g, ' ')}</span>
                  <span>{metric.unit || 'unitless'}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="subdomain-empty-state">No metrics are currently available for this domain pack.</div>
          )}
        </div>

        <div className="subdomain-section">
          <h2>Domain Papers</h2>
          {domainPapers.length > 0 ? (
            <div className="subdomain-paper-list">
              {domainPapers.map(paper => (
                <div className="subdomain-paper-row" key={paper.id}>
                  <span>{paper.title}</span>
                  <span>{paper.year || 'Unknown year'}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="subdomain-empty-state">No ingested papers are attached to this domain pack yet.</div>
          )}
        </div>
      </div>
    </div>
  );
};

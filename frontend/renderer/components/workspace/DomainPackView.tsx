import { t, uiLabel, domainTitle } from '../../i18n';
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
  onUploadPapers: (files: File[]) => void;
  onConfigureModel: () => void;
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
  onOpenPaperImport,
  onUploadPapers,
  onConfigureModel
}) => {
  const fileInput = React.useRef<HTMLInputElement>(null);
  return (
    <div className="domain-pack-view">
      <div className="domain-pack-view-header">
        <HierarchyNav items={hierarchyItems} />
        <div className="domain-pack-context-pill">{domainPack.namespace}</div>
      </div>

      <div className="domain-pack-view-content">
        <div className="domain-pack-title-block">
          <h1>{domainTitle(domainPack.config.domain.name)}</h1>
          <p>{domainPack.config.domain.id}</p>
        </div>

        <section className="domain-pack-import-guide" aria-label={t("论文导入")}>
          <div>
            <h2>{t("上传论文 PDF")}</h2>
            <p>{t("先配置模型接口，再上传 PDF；检查提取结果后确认入库。")}</p>
            <p>{t("领域包是指标和分类规则（YAML / JSON），论文请在这里上传。支持一次选择多篇。")}</p>
          </div>
          <div className="domain-pack-import-actions">
            <button type="button" onClick={onConfigureModel}>{t("配置模型接口")}</button>
            <button type="button" className="upload-primary" onClick={() => fileInput.current?.click()}>{t("上传论文 PDF")}</button>
            <input ref={fileInput} type="file" accept=".pdf,application/pdf" multiple hidden aria-label={t("选择论文 PDF")}
              onChange={event => {
                const files = Array.from(event.target.files || []);
                if (files.length) onUploadPapers(files);
                event.target.value = '';
              }} />
          </div>
        </section>

        <div className="domain-pack-summary-grid">
          <button type="button" className="domain-pack-summary-item" onClick={onOpenMetrics}>
            <span>{domainPack.metrics.length}</span>
            <label>{t("Metrics")}</label>
          </button>
          <div className="domain-pack-summary-item">
            <span>{papers.length + paperImports.length}</span>
            <label>{t("Papers")}</label>
          </div>
          <div className="domain-pack-summary-item">
            <span>{subdomains.length}</span>
            <label>{t("Subdomains")}</label>
          </div>
        </div>

        <div className="domain-pack-section-grid">
          <section className="domain-pack-panel">
            <div className="domain-pack-panel-header">
              <h2>{t("Papers")}</h2>
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
                    <small>{uiLabel(entry.status)}</small>
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
              <div className="domain-pack-empty-state">{t("No papers are attached to this domain pack.")}</div>
            )}
          </section>

          <section className="domain-pack-panel">
            <div className="domain-pack-panel-header">
              <h2>{t("Metrics")}</h2>
              <button type="button" onClick={onOpenMetrics}>{t("Open")}</button>
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
              <h2>{t("Subdomains")}</h2>
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
              <div className="domain-pack-empty-state">{t("No subdomains are mapped in this domain pack.")}</div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

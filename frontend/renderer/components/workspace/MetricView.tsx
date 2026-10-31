import { t, uiLabel, localizeMessage, domainTitle } from '../../i18n';
/**
 * Metric View
 * Focused detail surface for a metric selected from the workspace sidebar.
 */

import React from 'react';
import { CellData, LoadedDomainPack, Metric, MetricInput, Paper } from '../../services/workspace';
import { HierarchyNav, HierarchyNavItem } from './HierarchyNav';
import './MetricView.css';

interface MetricViewProps {
  metric: Metric;
  domainPack: LoadedDomainPack;
  papers: Paper[];
  cellData: Map<string, CellData>;
  hierarchyItems: HierarchyNavItem[];
  onSave: (originalName: string, metric: MetricInput) => void;
  onDelete: (metric: Metric) => void;
}

export const MetricView: React.FC<MetricViewProps> = ({
  metric,
  domainPack,
  papers,
  cellData,
  hierarchyItems,
  onSave,
  onDelete
}) => {
  const metricDefinition = domainPack.config.core_metrics.find(item => item.name === metric.name);
  const [draft, setDraft] = React.useState<MetricInput>({
    name: metric.name,
    expected_unit: metric.unit,
    aliases: metric.aliases,
    value_type: metric.value_type || metricDefinition?.value_type || 'float'
  });
  const [aliasText, setAliasText] = React.useState(metric.aliases.join(', '));
  const [error, setError] = React.useState<string | null>(null);
  const domainPapers = papers.filter(paper => paper.domain_pack_namespace === metric.namespace);
  const observations = domainPapers
    .map(paper => ({
      paper,
      cell: cellData.get(`${paper.id}:${metric.full_name}`) || null
    }))
    .filter(row => row.cell);

  const resolvedCount = observations.filter(row => row.cell?.status === 'resolved' || row.cell?.status === 'locked').length;
  const evidenceCount = observations.reduce((total, row) => total + (row.cell?.evidenceCount || 0), 0);
  const averageConfidence = observations.length > 0
    ? observations.reduce((total, row) => total + (row.cell?.confidence || 0), 0) / observations.length
    : 0;

  React.useEffect(() => {
    setDraft({
      name: metric.name,
      expected_unit: metric.unit,
      aliases: metric.aliases,
      value_type: metric.value_type || metricDefinition?.value_type || 'float'
    });
    setAliasText(metric.aliases.join(', '));
    setError(null);
  }, [metric.full_name]);

  const handleSave = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    try {
      onSave(metric.name, {
        ...draft,
        aliases: aliasText
          .split(',')
          .map(alias => alias.trim())
          .filter(Boolean)
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : t("Failed to update metric"));
    }
  };

  return (
    <div className="metric-view">
      <div className="metric-view-header">
        <HierarchyNav items={hierarchyItems} />
        <div className="metric-context-pill">{domainTitle(domainPack.config.domain.name)}</div>
      </div>

      <div className="metric-view-content">
        <div className="metric-title-block">
          <div className="metric-kicker">{t("Metric")}</div>
          <h1>{metric.name.replace(/_/g, ' ')}</h1>
          <div className="metric-full-name">{metric.full_name}</div>
        </div>

        <div className="metric-summary-grid">
          <div className="metric-summary-item">
            <span className="metric-summary-value">{metric.unit || t('Unitless')}</span>
            <span className="metric-summary-label">{t("Expected Unit")}</span>
          </div>
          <div className="metric-summary-item">
            <span className="metric-summary-value">{uiLabel(metric.value_type || metricDefinition?.value_type || 'Value')}</span>
            <span className="metric-summary-label">{t("Value Type")}</span>
          </div>
          <div className="metric-summary-item">
            <span className="metric-summary-value">{observations.length}</span>
            <span className="metric-summary-label">{t("Observed Papers")}</span>
          </div>
          <div className="metric-summary-item">
            <span className="metric-summary-value">{evidenceCount}</span>
            <span className="metric-summary-label">{t("Evidence Links")}</span>
          </div>
        </div>

        <div className="metric-section">
          <h2>{t("Edit Metric")}</h2>
          <form className="metric-editor-form" onSubmit={handleSave}>
            <label>
              <span>{t("Name")}</span>
              <input
                value={draft.name}
                onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}
              />
            </label>

            <label>
              <span>{t("Expected Unit")}</span>
              <input
                value={draft.expected_unit}
                onChange={event => setDraft(current => ({ ...current, expected_unit: event.target.value }))}
              />
            </label>

            <label>
              <span>{t("Value Type")}</span>
              <select
                value={draft.value_type}
                onChange={event => setDraft(current => ({ ...current, value_type: event.target.value as MetricInput['value_type'] }))}
              >
                <option value="float">{t("Float")}</option>
                <option value="int">{t("Integer")}</option>
                <option value="string">{t("String")}</option>
                <option value="bool">{t("Boolean")}</option>
              </select>
            </label>

            <label>
              <span>{t("Aliases")}</span>
              <input
                value={aliasText}
                onChange={event => setAliasText(event.target.value)}
                placeholder={t("comma-separated aliases")}
              />
            </label>

            {error && <div className="metric-editor-error">{localizeMessage(error)}</div>}

            <div className="metric-editor-actions">
              <button type="submit">{t("Save Changes")}</button>
              <button
                type="button"
                className="danger"
                onClick={() => {
                  if (confirm(t('Delete metric "{name}"? Existing extracted values for this metric will be removed from the current local view.', { name: metric.name }))) {
                    onDelete(metric);
                  }
                }}
              >
                {t("Delete Metric")}
              </button>
            </div>
          </form>
        </div>

        <div className="metric-section">
          <h2>{t("Definition")}</h2>
          <dl className="metric-definition-list">
            <div>
              <dt>{t("Aliases")}</dt>
              <dd>{metric.aliases.length > 0 ? metric.aliases.join(', ') : t("None")}</dd>
            </div>
            <div>
              <dt>{t("Namespace")}</dt>
              <dd>{metric.namespace}</dd>
            </div>
            <div>
              <dt>{t("Resolved Values")}</dt>
              <dd>{resolvedCount} {t("of")} {observations.length}</dd>
            </div>
            <div>
              <dt>{t("Average Confidence")}</dt>
              <dd>{observations.length > 0 ? `${Math.round(averageConfidence * 100)}%` : t("No observations")}</dd>
            </div>
          </dl>
        </div>

        <div className="metric-section">
          <h2>{t("Observed Values")}</h2>
          {observations.length > 0 ? (
            <div className="metric-observation-table">
              <div className="metric-observation-row header">
                <span>{t("Paper")}</span>
                <span>{t("Value")}</span>
                <span>{t("Status")}</span>
                <span>{t("Confidence")}</span>
              </div>
              {observations.map(({ paper, cell }) => (
                <div className="metric-observation-row" key={paper.id}>
                  <span className="metric-paper-title">{paper.title}</span>
                  <span>{cell?.value ?? 'N/A'} {cell?.unit || metric.unit || ''}</span>
                  <span>{cell ? uiLabel(cell.status) : ''}</span>
                  <span>{cell ? `${Math.round(cell.confidence * 100)}%` : 'N/A'}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="metric-empty-state">{t("No extracted values for this metric yet.")}</div>
          )}
        </div>
      </div>
    </div>
  );
};

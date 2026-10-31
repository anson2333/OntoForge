import { t, uiLabel, localizeMessage } from '../../i18n';
/**
 * Metrics View
 * Collection-level surface for adding, editing, and deleting domain-pack metrics.
 */

import React from 'react';
import { LoadedDomainPack, Metric, MetricInput } from '../../services/workspace';
import { HierarchyNav, HierarchyNavItem } from './HierarchyNav';
import './MetricsView.css';

interface MetricsViewProps {
  domainPack: LoadedDomainPack;
  mode: 'registry' | 'add';
  hierarchyItems: HierarchyNavItem[];
  onOpenAdd: () => void;
  onAddMetric: (metric: MetricInput) => void;
  onEditMetric: (metric: Metric) => void;
  onDeleteMetric: (metric: Metric) => void;
}

const EMPTY_METRIC: MetricInput = {
  name: '',
  expected_unit: '',
  aliases: [],
  value_type: 'float'
};

export const MetricsView: React.FC<MetricsViewProps> = ({
  domainPack,
  mode,
  hierarchyItems,
  onOpenAdd,
  onAddMetric,
  onEditMetric,
  onDeleteMetric
}) => {
  const [draft, setDraft] = React.useState<MetricInput>(EMPTY_METRIC);
  const [aliasText, setAliasText] = React.useState('');
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    try {
      onAddMetric({
        ...draft,
        aliases: aliasText
          .split(',')
          .map(alias => alias.trim())
          .filter(Boolean)
      });
      setDraft(EMPTY_METRIC);
      setAliasText('');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : t("Failed to add metric"));
    }
  };

  return (
    <div className="metrics-view">
      <div className="metrics-view-header">
        <HierarchyNav items={hierarchyItems} />
        <div className="metrics-context-pill">{domainPack.namespace}</div>
      </div>

      <div className="metrics-view-content">
        {mode === 'registry' ? (
          <section className="metrics-panel metrics-registry-panel">
            <div className="metrics-panel-header">
              <h2>{t("Metric Registry")}</h2>
              <div className="metrics-panel-actions">
                <span>{domainPack.metrics.length} {t("metrics")}</span>
                <button type="button" className="metrics-add-button" onClick={onOpenAdd} title={t("Add metric")}>
                  +
                </button>
              </div>
            </div>

            <div className="metrics-table">
              <div className="metrics-row header">
                <span>{t("Name")}</span>
                <span>{t("Unit")}</span>
                <span>{t("Type")}</span>
                <span>{t("Aliases")}</span>
                <span>{t("Actions")}</span>
              </div>
              {domainPack.metrics.map(metric => (
                <div className="metrics-row" key={metric.full_name}>
                  <span className="metrics-name">{metric.name.replace(/_/g, ' ')}</span>
                  <span>{metric.unit || t('Unitless')}</span>
                  <span>{uiLabel(metric.value_type || 'Value')}</span>
                  <span>{metric.aliases.length > 0 ? metric.aliases.join(', ') : t("None")}</span>
                  <span className="metrics-actions">
                    <button type="button" onClick={() => onEditMetric(metric)}>{t("Edit")}</button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        if (confirm(t('Delete metric "{name}"? Existing extracted values for this metric will be removed from the current local view.', { name: metric.name }))) {
                          onDeleteMetric(metric);
                        }
                      }}
                    >
                      {t("Delete")}
                    </button>
                  </span>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <section className="metrics-panel metrics-add-panel">
            <div className="metrics-panel-header">
              <h2>{t("Add Metric")}</h2>
            </div>

            <form className="metric-form" onSubmit={handleSubmit}>
              <label>
                <span>{t("Name")}</span>
                <input
                  value={draft.name}
                  onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}
                placeholder={t('Metric identifier example')}
                />
              </label>

              <label>
                <span>{t("Expected Unit")}</span>
                <input
                  value={draft.expected_unit}
                  onChange={event => setDraft(current => ({ ...current, expected_unit: event.target.value }))}
                placeholder={t('Unit example')}
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

              {error && <div className="metric-form-error">{localizeMessage(error)}</div>}

              <div className="metric-form-actions">
                <button type="submit">{t("Add Metric")}</button>
              </div>
            </form>
          </section>
        )}
      </div>
    </div>
  );
};

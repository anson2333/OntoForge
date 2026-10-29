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
      setError(nextError instanceof Error ? nextError.message : 'Failed to add metric');
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
              <h2>Metric Registry</h2>
              <div className="metrics-panel-actions">
                <span>{domainPack.metrics.length} metrics</span>
                <button type="button" className="metrics-add-button" onClick={onOpenAdd} title="Add metric">
                  +
                </button>
              </div>
            </div>

            <div className="metrics-table">
              <div className="metrics-row header">
                <span>Name</span>
                <span>Unit</span>
                <span>Type</span>
                <span>Aliases</span>
                <span>Actions</span>
              </div>
              {domainPack.metrics.map(metric => (
                <div className="metrics-row" key={metric.full_name}>
                  <span className="metrics-name">{metric.name.replace(/_/g, ' ')}</span>
                  <span>{metric.unit || 'unitless'}</span>
                  <span>{metric.value_type || 'value'}</span>
                  <span>{metric.aliases.length > 0 ? metric.aliases.join(', ') : 'None'}</span>
                  <span className="metrics-actions">
                    <button type="button" onClick={() => onEditMetric(metric)}>Edit</button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        if (confirm(`Delete metric "${metric.name}"? Existing extracted values for this metric will be removed from the current local view.`)) {
                          onDeleteMetric(metric);
                        }
                      }}
                    >
                      Delete
                    </button>
                  </span>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <section className="metrics-panel metrics-add-panel">
            <div className="metrics-panel-header">
              <h2>Add Metric</h2>
            </div>

            <form className="metric-form" onSubmit={handleSubmit}>
              <label>
                <span>Name</span>
                <input
                  value={draft.name}
                  onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}
                  placeholder="e.g. reconfiguration_delay"
                />
              </label>

              <label>
                <span>Expected Unit</span>
                <input
                  value={draft.expected_unit}
                  onChange={event => setDraft(current => ({ ...current, expected_unit: event.target.value }))}
                  placeholder="e.g. ms"
                />
              </label>

              <label>
                <span>Value Type</span>
                <select
                  value={draft.value_type}
                  onChange={event => setDraft(current => ({ ...current, value_type: event.target.value as MetricInput['value_type'] }))}
                >
                  <option value="float">Float</option>
                  <option value="int">Integer</option>
                  <option value="string">String</option>
                  <option value="bool">Boolean</option>
                </select>
              </label>

              <label>
                <span>Aliases</span>
                <input
                  value={aliasText}
                  onChange={event => setAliasText(event.target.value)}
                  placeholder="comma-separated aliases"
                />
              </label>

              {error && <div className="metric-form-error">{error}</div>}

              <div className="metric-form-actions">
                <button type="submit">Add Metric</button>
              </div>
            </form>
          </section>
        )}
      </div>
    </div>
  );
};

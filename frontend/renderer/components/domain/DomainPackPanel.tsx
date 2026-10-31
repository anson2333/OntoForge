import { t, uiLabel } from '../../i18n';
/**
 * Domain Pack Panel
 * View and edit domain pack configuration (metrics, taxonomy, validation rules)
 */

import React, { useEffect, useState } from 'react';
import { sspClient } from '../../services/ssp_client';

export interface MetricDefinition {
  name: string;
  expected_unit: string;
  aliases: string[];
  value_type: 'float' | 'int' | 'string' | 'bool';
  description?: string;
  minimum?: number | null;
  maximum?: number | null;
  unit_conversions?: Record<string, number>;
}

export interface TaxonomyDimension {
  name: string;
  values: string[];
  subdomain_map?: Record<string, string>;
  description?: string;
}

export interface DomainInfo {
  id: string;
  name: string;
  taxonomy_tree: string[] | TaxonomyDimension[];
  parent_domain_id?: string;
}

export interface ValidationRules {
  required_context_keys: string[];
  unit_normalization: Record<string, string[]>;
  extraction_instructions?: string[];
  require_numeric_evidence?: boolean;
  mark_missing_context?: boolean;
  require_condition_evidence?: boolean;
  document_families?: Record<string, string[]>;
  excluded_result_roles?: string[];
  excluded_result_terms?: string[];
  max_batch_characters?: number | null;
}

export interface DomainPackConfig {
  schema_version: string;
  domain: DomainInfo;
  core_metrics: MetricDefinition[];
  validation: ValidationRules;
}

interface DomainPackPanelProps {
  onClose?: () => void;
  onSave?: (config: DomainPackConfig) => void;
}

export const DomainPackPanel: React.FC<DomainPackPanelProps> = ({ onClose, onSave }) => {
  const [config, setConfig] = useState<DomainPackConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [selectedTab, setSelectedTab] = useState<'metrics' | 'taxonomy' | 'validation' | 'raw'>('metrics');
  const [editedConfig, setEditedConfig] = useState<string>('');

  useEffect(() => {
    loadDomainPack();
  }, []);

  const loadDomainPack = async () => {
    setIsLoading(true);
    try {
      const result = await sspClient.listDomainPacks();
      const firstPack = result?.domain_packs?.[0];
      setConfig(firstPack?.config ?? null);
    } catch (error) {
      console.error('Failed to load domain pack from backend:', error);
      setConfig(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEdit = () => {
    if (config) {
      setEditedConfig(JSON.stringify(config, null, 2));
      setIsEditing(true);
    }
  };

  const handleSave = () => {
    try {
      const parsed = JSON.parse(editedConfig);
      setConfig(parsed);
      setIsEditing(false);
      onSave?.(parsed);
    } catch (error) {
      alert(t("Invalid JSON format"));
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditedConfig('');
  };

  if (isLoading) {
    return (
      <div style={{
        padding: '20px',
        backgroundColor: '#1e1e1e',
        color: '#cccccc',
        height: '100%'
      }}>
        {t("Loading domain pack...")}
      </div>
    );
  }

  if (!config) {
    return (
      <div style={{
        padding: '20px',
        backgroundColor: '#1e1e1e',
        color: '#cccccc',
        height: '100%'
      }}>
        {t("Failed to load domain pack")}
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: '#1e1e1e',
      color: '#cccccc'
    }}>
      {/* Header */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #404040',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>{t("Domain Pack Configuration")}</h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', opacity: 0.7 }}>
            {config.domain.name} {t("(v")}{config.schema_version}{t(')')}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {isEditing ? (
            <>
              <button
                onClick={handleSave}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#0e639c',
                  border: 'none',
                  borderRadius: '3px',
                  color: 'white',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                {t("Save")}
              </button>
              <button
                onClick={handleCancel}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#3e3e3e',
                  border: 'none',
                  borderRadius: '3px',
                  color: 'white',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                {t("Cancel")}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleEdit}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#0e639c',
                  border: 'none',
                  borderRadius: '3px',
                  color: 'white',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                {t("Edit JSON")}
              </button>
              <button
                onClick={loadDomainPack}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#3e3e3e',
                  border: 'none',
                  borderRadius: '3px',
                  color: 'white',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                {t("Reload")}
              </button>
            </>
          )}
          {onClose && (
            <button
              onClick={onClose}
              style={{
                padding: '6px 12px',
                backgroundColor: '#3e3e3e',
                border: 'none',
                borderRadius: '3px',
                color: 'white',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              {t("Close")}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      {!isEditing && (
        <div style={{
          display: 'flex',
          borderBottom: '1px solid #404040',
          padding: '0 16px',
          backgroundColor: '#252525'
        }}>
          {(['metrics', 'taxonomy', 'validation', 'raw'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setSelectedTab(tab)}
              style={{
                padding: '12px 16px',
                backgroundColor: selectedTab === tab ? '#1e1e1e' : 'transparent',
                border: 'none',
                borderBottom: selectedTab === tab ? '2px solid #0e639c' : '2px solid transparent',
                color: selectedTab === tab ? '#ffffff' : '#cccccc',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: selectedTab === tab ? 600 : 400
              }}
            >
              {tab === 'raw' ? t('Raw Configuration') : uiLabel(tab)}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {isEditing ? (
          <textarea
            value={editedConfig}
            onChange={(e) => setEditedConfig(e.target.value)}
            style={{
              width: '100%',
              height: '100%',
              backgroundColor: '#1e1e1e',
              color: '#cccccc',
              border: '1px solid #404040',
              borderRadius: '4px',
              padding: '12px',
              fontFamily: 'Monaco, Menlo, Consolas, monospace',
              fontSize: '12px',
              resize: 'none'
            }}
          />
        ) : selectedTab === 'metrics' ? (
          <div>
            <h4 style={{ marginTop: 0 }}>{t("Core Metrics (")}{config.core_metrics.length}{t(')')}</h4>
            {config.core_metrics.map((metric) => (
              <div
                key={metric.name}
                style={{
                  padding: '12px',
                  backgroundColor: '#252525',
                  borderRadius: '4px',
                  marginBottom: '8px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px' }}>{metric.name}</span>
                  <span style={{
                    padding: '2px 8px',
                    backgroundColor: '#0e639c',
                    borderRadius: '3px',
                    fontSize: '11px'
                  }}>
                    {metric.expected_unit}
                  </span>
                </div>
                <div style={{ fontSize: '12px', opacity: 0.7, marginBottom: '4px' }}>
                  {t("Type:")} <code style={{ backgroundColor: '#1e1e1e', padding: '2px 6px', borderRadius: '2px' }}>
                    {uiLabel(metric.value_type || 'float')}
                  </code>
                </div>
                {metric.aliases.length > 0 && (
                  <div style={{ fontSize: '12px', opacity: 0.7 }}>
                    {t("Aliases:")} {metric.aliases.map((alias, i) => (
                      <code
                        key={i}
                        style={{
                          backgroundColor: '#1e1e1e',
                          padding: '2px 6px',
                          borderRadius: '2px',
                          marginRight: '4px'
                        }}
                      >
                        {alias}
                      </code>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : selectedTab === 'taxonomy' ? (
          <div>
            <h4 style={{ marginTop: 0 }}>{t("Domain Taxonomy")}</h4>
            <div style={{
              padding: '12px',
              backgroundColor: '#252525',
              borderRadius: '4px',
              marginBottom: '12px'
            }}>
              <div style={{ fontSize: '12px', opacity: 0.7, marginBottom: '4px' }}>{t("Domain ID:")}</div>
              <code style={{ fontSize: '13px' }}>{config.domain.id}</code>
            </div>
            {Array.isArray(config.domain.taxonomy_tree) && config.domain.taxonomy_tree.length > 0 ? (
              typeof config.domain.taxonomy_tree[0] === 'string' ? (
                <div>
                  <h5>{t("Simple Taxonomy:")}</h5>
                  {(config.domain.taxonomy_tree as string[]).map((item, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '8px 12px',
                        backgroundColor: '#252525',
                        borderRadius: '4px',
                        marginBottom: '4px'
                      }}
                    >
                      {item}
                    </div>
                  ))}
                </div>
              ) : (
                <div>
                  <h5>{t("Structured Taxonomy:")}</h5>
                  {(config.domain.taxonomy_tree as TaxonomyDimension[]).map((dim, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '12px',
                        backgroundColor: '#252525',
                        borderRadius: '4px',
                        marginBottom: '12px'
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '8px' }}>
                        {dim.name}
                      </div>
                      {dim.description && (
                        <div style={{ fontSize: '12px', opacity: 0.7, marginBottom: '8px' }}>
                          {dim.description}
                        </div>
                      )}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {dim.values.map((val, j) => (
                          <span
                            key={j}
                            style={{
                              padding: '4px 10px',
                              backgroundColor: dim.subdomain_map?.[val] ? '#0e639c' : '#3e3e3e',
                              borderRadius: '3px',
                              fontSize: '11px'
                            }}
                            title={dim.subdomain_map?.[val] || undefined}
                          >
                            {val}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )
            ) : null}
          </div>
        ) : selectedTab === 'validation' ? (
          <div>
            <h4 style={{ marginTop: 0 }}>{t("Validation Rules")}</h4>
            <div style={{ marginBottom: '20px' }}>
              <h5>{t("Required Context Keys:")}</h5>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {config.validation.required_context_keys.map((key, i) => (
                  <span
                    key={i}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: '#0e639c',
                      borderRadius: '3px',
                      fontSize: '12px'
                    }}
                  >
                    {key}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <h5>{t("Unit Normalization:")}</h5>
              {Object.entries(config.validation.unit_normalization).map(([unit, synonyms]) => (
                <div
                  key={unit}
                  style={{
                    padding: '12px',
                    backgroundColor: '#252525',
                    borderRadius: '4px',
                    marginBottom: '8px'
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: '6px' }}>
                    {unit}
                  </div>
                  <div style={{ fontSize: '12px', opacity: 0.7 }}>
                    {synonyms.map((syn, i) => (
                      <code
                        key={i}
                        style={{
                          backgroundColor: '#1e1e1e',
                          padding: '2px 6px',
                          borderRadius: '2px',
                          marginRight: '4px'
                        }}
                      >
                        {syn}
                      </code>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div>
            <h4 style={{ marginTop: 0 }}>{t("Raw Configuration")}</h4>
            <pre style={{
              backgroundColor: '#252525',
              padding: '12px',
              borderRadius: '4px',
              overflow: 'auto',
              fontSize: '12px',
              fontFamily: 'Monaco, Menlo, Consolas, monospace'
            }}>
              {JSON.stringify(config, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

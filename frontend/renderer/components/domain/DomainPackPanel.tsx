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
      // Try to fetch from backend
      const result = await sspClient.call('textDocument/sspGetDomainPack', {});
      setConfig(result.config);
    } catch (error) {
      console.warn('Backend not available, using mock domain pack');
      // Mock domain pack for development
      const mockConfig: DomainPackConfig = {
        schema_version: '1.0',
        domain: {
          id: 'domain.networking.optical',
          name: 'Optical Access Networks',
          taxonomy_tree: [
            {
              name: 'topology',
              values: ['mesh', 'ring', 'star', 'free_space'],
              subdomain_map: {
                'free_space': 'domain.networking.optical.fso',
                'mesh': 'domain.networking.optical.access'
              },
              description: 'Network topology types'
            },
            {
              name: 'switching_mechanism',
              values: ['wdm', 'optical_packet', 'burst_switching', 'circuit_switching'],
              subdomain_map: {
                'wdm': 'domain.networking.optical.wdm',
                'optical_packet': 'domain.networking.optical.ops'
              },
              description: 'Switching technologies'
            },
            {
              name: 'performance_metrics',
              values: ['latency', 'throughput', 'reliability', 'scalability'],
              description: 'Performance characteristics'
            }
          ]
        },
        core_metrics: [
          {
            name: 'reconfiguration_delay',
            expected_unit: 'ms',
            aliases: ['switching_delay', 'matrix_latency', 'reconfiguration_time'],
            value_type: 'float'
          },
          {
            name: 'cross_talk',
            expected_unit: 'dB',
            aliases: ['crosstalk', 'channel_isolation'],
            value_type: 'float'
          },
          {
            name: 'insertion_loss',
            expected_unit: 'dB',
            aliases: ['optical_loss', 'path_loss'],
            value_type: 'float'
          },
          {
            name: 'extinction_ratio',
            expected_unit: 'dB',
            aliases: ['ER', 'on_off_ratio'],
            value_type: 'float'
          },
          {
            name: 'bit_error_rate',
            expected_unit: 'unitless',
            aliases: ['BER', 'error_rate'],
            value_type: 'float'
          },
          {
            name: 'power_consumption',
            expected_unit: 'W',
            aliases: ['energy_consumption', 'power_draw'],
            value_type: 'float'
          },
          {
            name: 'port_count',
            expected_unit: 'ports',
            aliases: ['num_ports', 'switch_size'],
            value_type: 'int'
          },
          {
            name: 'wavelength_range',
            expected_unit: 'nm',
            aliases: ['spectral_range', 'operating_wavelength'],
            value_type: 'string'
          }
        ],
        validation: {
          required_context_keys: ['network_load', 'topology', 'temperature'],
          unit_normalization: {
            'ms': ['ms', 'millisecond', 'milliseconds', 'msec'],
            'dB': ['dB', 'db', 'decibel', 'decibels'],
            'W': ['W', 'watt', 'watts', 'w'],
            'ports': ['ports', 'port', 'channels', 'channel']
          }
        }
      };
      setConfig(mockConfig);
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
      alert('Invalid JSON format');
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
        Loading domain pack...
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
        Failed to load domain pack
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
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>Domain Pack Configuration</h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', opacity: 0.7 }}>
            {config.domain.name} (v{config.schema_version})
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
                Save
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
                Cancel
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
                Edit JSON
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
                Reload
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
              Close
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
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
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
            <h4 style={{ marginTop: 0 }}>Core Metrics ({config.core_metrics.length})</h4>
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
                  Type: <code style={{ backgroundColor: '#1e1e1e', padding: '2px 6px', borderRadius: '2px' }}>
                    {metric.value_type}
                  </code>
                </div>
                {metric.aliases.length > 0 && (
                  <div style={{ fontSize: '12px', opacity: 0.7 }}>
                    Aliases: {metric.aliases.map((alias, i) => (
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
            <h4 style={{ marginTop: 0 }}>Domain Taxonomy</h4>
            <div style={{
              padding: '12px',
              backgroundColor: '#252525',
              borderRadius: '4px',
              marginBottom: '12px'
            }}>
              <div style={{ fontSize: '12px', opacity: 0.7, marginBottom: '4px' }}>Domain ID:</div>
              <code style={{ fontSize: '13px' }}>{config.domain.id}</code>
            </div>
            {Array.isArray(config.domain.taxonomy_tree) && config.domain.taxonomy_tree.length > 0 ? (
              typeof config.domain.taxonomy_tree[0] === 'string' ? (
                <div>
                  <h5>Simple Taxonomy:</h5>
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
                  <h5>Structured Taxonomy:</h5>
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
            <h4 style={{ marginTop: 0 }}>Validation Rules</h4>
            <div style={{ marginBottom: '20px' }}>
              <h5>Required Context Keys:</h5>
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
              <h5>Unit Normalization:</h5>
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
            <h4 style={{ marginTop: 0 }}>Raw Configuration</h4>
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

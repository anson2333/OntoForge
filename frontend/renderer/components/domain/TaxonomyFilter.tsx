/**
 * Taxonomy Filter Component
 * Allows filtering papers by taxonomy dimensions from domain pack
 */

import React from 'react';
import { TaxonomyDimension } from './DomainPackPanel';

interface TaxonomyFilterProps {
  dimensions: TaxonomyDimension[];
  selectedFilters: Record<string, string[]>;
  onFilterChange: (dimension: string, values: string[]) => void;
  onClearAll: () => void;
}

export const TaxonomyFilter: React.FC<TaxonomyFilterProps> = ({
  dimensions,
  selectedFilters,
  onFilterChange,
  onClearAll
}) => {
  const hasActiveFilters = Object.values(selectedFilters).some(values => values.length > 0);

  return (
    <div style={{
      padding: '12px',
      backgroundColor: '#252525',
      borderBottom: '1px solid #404040'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '8px'
      }}>
        <span style={{ fontSize: '13px', fontWeight: 600 }}>Filter by Taxonomy</span>
        {hasActiveFilters && (
          <button
            onClick={onClearAll}
            style={{
              padding: '4px 8px',
              backgroundColor: 'transparent',
              border: '1px solid #404040',
              borderRadius: '3px',
              color: '#cccccc',
              cursor: 'pointer',
              fontSize: '11px'
            }}
          >
            Clear All
          </button>
        )}
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {dimensions.map(dimension => {
          const selected = selectedFilters[dimension.name] || [];
          
          return (
            <div key={dimension.name}>
              <div style={{ 
                fontSize: '11px', 
                opacity: 0.7, 
                marginBottom: '4px',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                {dimension.name.replace(/_/g, ' ')}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                {dimension.values.map(value => {
                  const isSelected = selected.includes(value);
                  const hasSubdomain = dimension.subdomain_map?.[value];
                  
                  return (
                    <button
                      key={value}
                      onClick={() => {
                        const newSelected = isSelected
                          ? selected.filter(v => v !== value)
                          : [...selected, value];
                        onFilterChange(dimension.name, newSelected);
                      }}
                      style={{
                        padding: '4px 8px',
                        backgroundColor: isSelected 
                          ? hasSubdomain ? '#0e639c' : '#3e3e3e'
                          : 'transparent',
                        border: `1px solid ${isSelected ? 'transparent' : '#404040'}`,
                        borderRadius: '3px',
                        color: isSelected ? '#ffffff' : '#cccccc',
                        cursor: 'pointer',
                        fontSize: '11px',
                        transition: 'all 0.15s ease'
                      }}
                      title={hasSubdomain 
                        ? `Subdomain: ${hasSubdomain}` 
                        : 'No subdomain mapping'}
                    >
                      {value}
                      {hasSubdomain && ' 🎯'}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      
      {hasActiveFilters && (
        <div style={{
          marginTop: '8px',
          padding: '6px',
          backgroundColor: '#1e1e1e',
          borderRadius: '3px',
          fontSize: '11px',
          opacity: 0.8
        }}>
          Active filters: {Object.entries(selectedFilters)
            .filter(([, values]) => values.length > 0)
            .map(([dim, values]) => `${dim}: ${values.join(', ')}`)
            .join(' | ')}
        </div>
      )}
    </div>
  );
};

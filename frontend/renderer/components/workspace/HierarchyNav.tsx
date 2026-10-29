/**
 * Hierarchy Nav
 * Breadcrumb control for moving across the workspace hierarchy.
 */

import React from 'react';
import './HierarchyNav.css';

export interface HierarchyNavItem {
  label: string;
  onClick?: () => void;
}

interface HierarchyNavProps {
  items: HierarchyNavItem[];
}

export const HierarchyNav: React.FC<HierarchyNavProps> = ({ items }) => {
  return (
    <nav className="hierarchy-nav" aria-label="Workspace hierarchy">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <React.Fragment key={`${item.label}-${index}`}>
            {index > 0 && <span className="hierarchy-separator">/</span>}
            {item.onClick && !isLast ? (
              <button type="button" className="hierarchy-item" onClick={item.onClick}>
                {item.label}
              </button>
            ) : (
              <span className={`hierarchy-item ${isLast ? 'current' : ''}`}>{item.label}</span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
};

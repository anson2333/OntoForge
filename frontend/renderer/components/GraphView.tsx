import { t, uiLabel, useLanguage } from '../i18n';
/**
 * GraphView Component
 * Interactive knowledge graph visualization using force-directed layout
 * Shows: Workspace → Domain Packs → Papers → Assertions
 */

import { useState, useEffect, useRef } from 'react';
import { useWorkspaceStore } from '../services/workspace';
import './GraphView.css';

interface GraphNode {
  id: string;
  label: string;
  type: 'workspace' | 'domain' | 'paper' | 'assertion' | 'subdomain';
  namespace?: string;
  color?: string;
  size?: number;
}

interface GraphLink {
  source: string;
  target: string;
  label?: string;
  type: 'contains' | 'belongs_to' | 'cites' | 'evidenced_by';
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface GraphViewProps {
  onPaperClick?: (paperId: string) => void;
}

export default function GraphView({ onPaperClick }: GraphViewProps) {
  const language = useLanguage();
  const { workspace, domainPacks, papers, activeDomainPackNamespaces, cellData } = useWorkspaceStore();
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [filterNodeType, setFilterNodeType] = useState<string>('all');
  const [layoutType, setLayoutType] = useState<'force' | 'hierarchical'>('hierarchical');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hoveredNode: string | null = null;

  // Build graph data from workspace state
  useEffect(() => {
    buildGraphData();
  }, [workspace, domainPacks, papers, activeDomainPackNamespaces, cellData]);

  const buildGraphData = () => {
    const nodes: GraphNode[] = [];
    const links: GraphLink[] = [];

    if (!workspace) {
      setGraphData({ nodes, links });
      return;
    }

    // Add workspace node
    nodes.push({
      id: workspace.id,
      label: workspace.name,
      type: 'workspace',
      color: '#007bff',
      size: 20
    });

    // Add domain pack nodes
    domainPacks.forEach(pack => {
      if (!pack || !pack.config || !pack.config.domain) return;
      
      const domainId = `domain_${pack.namespace}`;
      nodes.push({
        id: domainId,
        label: pack.config.domain.name || pack.namespace,
        type: 'domain',
        namespace: pack.namespace,
        color: activeDomainPackNamespaces.includes(pack.namespace) ? '#28a745' : '#6c757d',
        size: 15
      });

      // Link workspace to domain
      links.push({
        source: workspace.id,
        target: domainId,
        type: 'contains',
        label: 'contains'
      });

      // Add subdomain nodes (only if active)
      if (activeDomainPackNamespaces.includes(pack.namespace)) {
        const subdomains = getSubdomainsFromPack(pack);
        subdomains.forEach(subdomain => {
          const subdomainId = `subdomain_${subdomain}`;
          nodes.push({
            id: subdomainId,
            label: subdomain.split('.').pop() || subdomain,
            type: 'subdomain',
            color: '#17a2b8',
            size: 10
          });

          links.push({
            source: domainId,
            target: subdomainId,
            type: 'contains',
            label: 'has'
          });
        });
      }
    });

    // Add paper nodes (filtered by active domain packs)
    const filteredPapers = papers.filter(paper => {
      if (!paper || !paper.domain_pack_namespace) return false;
      // Show papers that belong to active domain packs
      return activeDomainPackNamespaces.includes(paper.domain_pack_namespace);
    });

    filteredPapers.forEach(paper => {
      if (!paper || !paper.id || !paper.title) return;
      
      nodes.push({
        id: paper.id,
        label: paper.title.length > 40 ? paper.title.substring(0, 37) + '...' : paper.title,
        type: 'paper',
        color: '#ffc107',
        size: 12
      });

      // Link papers to workspace
      links.push({
        source: workspace.id,
        target: paper.id,
        type: 'contains'
      });

      // Link papers to their domain pack
      if (paper.domain_pack_namespace) {
        const domainId = `domain_${paper.domain_pack_namespace}`;
        if (nodes.find(n => n.id === domainId)) {
          links.push({
            source: paper.id,
            target: domainId,
            type: 'belongs_to',
            label: 'in'
          });
        }
      }
    });

    // Add assertion nodes for metric values actually recorded in the matrix
    const seenAssertions = new Set<string>();
    cellData.forEach(cell => {
      if (!cell.value || seenAssertions.has(cell.metricName)) return;
      const paper = filteredPapers.find(candidate => candidate.id === cell.paperId);
      if (!paper) return;
      seenAssertions.add(cell.metricName);

      const assertionId = `assertion_${cell.metricName}`;
      nodes.push({
        id: assertionId,
        label: cell.metricName.replace(/.*:/, ''),
        type: 'assertion',
        namespace: cell.metricName.split(':')[0],
        color: '#dc3545',
        size: 8
      });

      links.push({
        source: paper.id,
        target: assertionId,
        type: 'evidenced_by',
        label: 'claims'
      });
    });

    setGraphData({ nodes, links });
  };

  const getSubdomainsFromPack = (pack: any): string[] => {
    const subdomains: string[] = [];
    if (!pack || !pack.config || !pack.config.domain || !pack.config.domain.taxonomy_tree) {
      return subdomains;
    }
    const taxonomyTree = pack.config.domain.taxonomy_tree || [];
    taxonomyTree.forEach((dimension: any) => {
      if (typeof dimension !== 'string' && dimension.subdomain_map) {
        Object.values(dimension.subdomain_map).forEach((subdomainId: any) => {
          if (typeof subdomainId === 'string' && !subdomains.includes(subdomainId)) {
            subdomains.push(subdomainId);
          }
        });
      }
    });
    return subdomains;
  };

  // Simple canvas-based graph rendering
  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Simple hierarchical layout
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const levelSpacing = 150;
    const nodeSpacing = 80;

    // Position nodes by type
    const nodePositions = new Map<string, { x: number; y: number }>();
    
    graphData.nodes.forEach(node => {
      let level = 0;
      let offset = 0;

      switch (node.type) {
        case 'workspace':
          level = 0;
          offset = 0;
          break;
        case 'domain':
          level = 1;
          offset = graphData.nodes.filter(n => n.type === 'domain').indexOf(node) * nodeSpacing - (graphData.nodes.filter(n => n.type === 'domain').length * nodeSpacing) / 2;
          break;
        case 'subdomain':
          level = 2;
          offset = graphData.nodes.filter(n => n.type === 'subdomain').indexOf(node) * nodeSpacing - (graphData.nodes.filter(n => n.type === 'subdomain').length * nodeSpacing) / 2;
          break;
        case 'paper':
          level = 2.5;
          offset = graphData.nodes.filter(n => n.type === 'paper').indexOf(node) * (nodeSpacing * 0.8) - (graphData.nodes.filter(n => n.type === 'paper').length * nodeSpacing * 0.8) / 2;
          break;
        case 'assertion':
          level = 3.5;
          offset = graphData.nodes.filter(n => n.type === 'assertion').indexOf(node) * (nodeSpacing * 0.6) - (graphData.nodes.filter(n => n.type === 'assertion').length * nodeSpacing * 0.6) / 2;
          break;
      }

      nodePositions.set(node.id, {
        x: centerX + offset,
        y: centerY - (2 * levelSpacing) + level * levelSpacing
      });
    });

    // Draw links
    ctx.strokeStyle = '#404040';
    ctx.lineWidth = 1;
    graphData.links.forEach(link => {
      const source = nodePositions.get(link.source);
      const target = nodePositions.get(link.target);
      if (source && target) {
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
      }
    });

    // Draw nodes
    graphData.nodes.forEach(node => {
      const pos = nodePositions.get(node.id);
      if (!pos) return;

      const isHovered = hoveredNode === node.id;
      const isSelected = selectedNode?.id === node.id;

      // Draw node circle
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, (node.size || 10) * (isHovered ? 1.3 : 1), 0, 2 * Math.PI);
      ctx.fillStyle = node.color || '#cccccc';
      ctx.fill();

      if (isSelected) {
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 3;
        ctx.stroke();
      }
    });

    // Draw labels separately to avoid overlaps
    const labelBounds: Array<{ x: number; y: number; width: number; height: number }> = [];
    graphData.nodes.forEach(node => {
      const pos = nodePositions.get(node.id);
      if (!pos) return;

      const isHovered = hoveredNode === node.id;
      ctx.font = isHovered ? 'bold 12px sans-serif' : '11px sans-serif';
      
      // Measure text
      const label = node.type === 'domain' ? t(node.label) : node.label;
      const metrics = ctx.measureText(label);
      const textWidth = metrics.width;
      const textHeight = 14;
      const padding = 4;
      
      // Calculate initial label position (below node)
      let labelX = pos.x;
      let labelY = pos.y + (node.size || 10) + 8;
      
      // Check for collisions with existing labels and adjust position
      let collisionDetected = true;
      let attempts = 0;
      const maxAttempts = 8;
      const offsets = [
        { dx: 0, dy: 0 },      // Below (default)
        { dx: 0, dy: -30 },    // Above
        { dx: 20, dy: 0 },     // Right
        { dx: -20, dy: 0 },    // Left
        { dx: 15, dy: -15 },   // Top-right
        { dx: -15, dy: -15 },  // Top-left
        { dx: 15, dy: 15 },    // Bottom-right
        { dx: -15, dy: 15 }    // Bottom-left
      ];
      
      while (collisionDetected && attempts < maxAttempts) {
        const offset = offsets[attempts];
        labelX = pos.x + offset.dx;
        labelY = pos.y + (node.size || 10) + 8 + offset.dy;
        
        const bounds = {
          x: labelX - textWidth / 2 - padding,
          y: labelY - padding,
          width: textWidth + padding * 2,
          height: textHeight + padding * 2
        };
        
        // Check collision with existing labels
        collisionDetected = labelBounds.some(existing => 
          !(bounds.x + bounds.width < existing.x ||
            bounds.x > existing.x + existing.width ||
            bounds.y + bounds.height < existing.y ||
            bounds.y > existing.y + existing.height)
        );
        
        if (!collisionDetected) {
          labelBounds.push(bounds);
          
          // Draw label background
          ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
          ctx.fillRect(bounds.x, bounds.y, bounds.width, bounds.height);
          
          // Draw label border for hovered nodes
          if (isHovered) {
            ctx.strokeStyle = node.color || '#ffffff';
            ctx.lineWidth = 1;
            ctx.strokeRect(bounds.x, bounds.y, bounds.width, bounds.height);
          }
          
          // Draw label text
          ctx.fillStyle = '#ffffff';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillText(label, labelX, labelY);
        }
        
        attempts++;
      }
      
      // If still colliding after all attempts, draw anyway with semi-transparent background
      if (collisionDetected) {
        const bounds = {
          x: labelX - textWidth / 2 - padding,
          y: labelY - padding,
          width: textWidth + padding * 2,
          height: textHeight + padding * 2
        };
        
        ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
        ctx.fillRect(bounds.x, bounds.y, bounds.width, bounds.height);
        
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(label, labelX, labelY);
      }
    });
  }, [graphData, hoveredNode, selectedNode, language]);

  const applyFilter = (type: string) => {
    setFilterNodeType(type);
    // Re-build graph with filter
    buildGraphData();
  };

  return (
    <div className="graph-view">
      {/* Graph Controls */}
      <div className="graph-controls">
        <div className="control-group">
          <label>{t("Layout:")}</label>
          <select value={layoutType} onChange={(e) => setLayoutType(e.target.value as any)}>
            <option value="hierarchical">{t("Hierarchical")}</option>
            <option value="force">{t("Force-Directed (Coming Soon)")}</option>
          </select>
        </div>

        <div className="control-group">
          <label>{t("Filter:")}</label>
          <select value={filterNodeType} onChange={(e) => applyFilter(e.target.value)}>
            <option value="all">{t("All Nodes")}</option>
            <option value="workspace">{t("Workspace Only")}</option>
            <option value="domain">{t("Domains")}</option>
            <option value="paper">{t("Papers")}</option>
            <option value="assertion">{t("Assertions")}</option>
          </select>
        </div>

        <div className="control-group">
          <label>{t("Active Domain Packs:")}</label>
          <div className="domain-badges">
            {domainPacks.filter(p => activeDomainPackNamespaces.includes(p.namespace)).map(pack => (
              <span key={pack.namespace} className="domain-badge" style={{ backgroundColor: '#28a745' }}>
                {pack.namespace}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="graph-canvas-container">
        <canvas ref={canvasRef} className="graph-canvas" />
      </div>

      {/* Node Details Panel */}
      {selectedNode && (
        <div className="node-details">
          <div className="node-details-header">
            <h3>{selectedNode.type === 'domain' ? t(selectedNode.label) : selectedNode.label}</h3>
            <button onClick={() => setSelectedNode(null)}>×</button>
          </div>
          <div className="node-details-content">
            <div className="detail-row">
              <span className="detail-label">{t("Type:")}</span>
              <span className="detail-value">{uiLabel(selectedNode.type)}</span>
            </div>
            {selectedNode.namespace && (
              <div className="detail-row">
                <span className="detail-label">{t("Namespace:")}</span>
                <span className="detail-value">{selectedNode.namespace}</span>
              </div>
            )}
            <div className="detail-row">
              <span className="detail-label">{t("ID:")}</span>
              <span className="detail-value">{selectedNode.id}</span>
            </div>
            {selectedNode.type === 'paper' && (
              <button 
                className="view-in-matrix-btn"
                onClick={() => onPaperClick && onPaperClick(selectedNode.id)}
              >
                {t("View in Matrix")}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="graph-legend">
        <h4>{t("Legend")}</h4>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#007bff' }}></span>
          <span>{t("Workspace")}</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#28a745' }}></span>
          <span>{t("Domain Pack (Active)")}</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#17a2b8' }}></span>
          <span>{t("Subdomain")}</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#ffc107' }}></span>
          <span>{t("Paper")}</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#dc3545' }}></span>
          <span>{t("Assertion")}</span>
        </div>
      </div>

      {/* Stats */}
      <div className="graph-stats">
        <span>{graphData.nodes.length} {t("nodes")}</span>
        <span>{graphData.links.length} {t("edges")}</span>
      </div>
    </div>
  );
}

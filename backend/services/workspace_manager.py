"""
Workspace Manager Service
Manages workspace lifecycle and coordinates multiple domain pack loading.
Implements Section 2.0 and 2.1 of the specification.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from ..schemas.nodes import WorkspaceNode, DomainNode
from ..schemas.protocol import (
    WorkspaceInfo,
    DomainPackConfig,
    LoadedDomainPackInfo,
    SSPInitializeResponse
)
from ..config.loader import DomainPackLoader
from ..config.registries import MetricRegistry, AliasRegistry, UnitRegistry


class DomainPackInstance:
    """Container for a loaded domain pack with its registries."""
    
    def __init__(
        self,
        namespace: str,
        domain_node: DomainNode,
        metric_registry: MetricRegistry,
        alias_registry: AliasRegistry,
        unit_registry: UnitRegistry,
        config_path: str
    ):
        self.namespace = namespace
        self.domain_node = domain_node
        self.metric_registry = metric_registry
        self.alias_registry = alias_registry
        self.unit_registry = unit_registry
        self.config_path = config_path
        self.enabled = True
    
    def get_namespaced_metrics(self) -> List[str]:
        """Get all metrics with namespace prefix."""
        return [f"{self.namespace}:{metric}" for metric in self.metric_registry.list_all()]
    
    def resolve_metric(self, metric_name: str) -> Optional[str]:
        """
        Resolve a metric name (with or without namespace) to fully qualified name.
        
        Args:
            metric_name: Either "reconfiguration_delay" or "optical:reconfiguration_delay"
        
        Returns:
            Fully qualified metric name or None if not found
        """
        # Already namespaced?
        if ":" in metric_name:
            ns, base_name = metric_name.split(":", 1)
            if ns == self.namespace and self.metric_registry.get(base_name):
                return metric_name
            return None
        
        # Try as base name
        if self.metric_registry.get(metric_name):
            return f"{self.namespace}:{metric_name}"
        
        # Try aliases
        canonical = self.alias_registry.resolve(metric_name)
        if canonical and self.metric_registry.get(canonical):
            return f"{self.namespace}:{canonical}"
        
        return None


class WorkspaceManager:
    """
    Manages workspace state and multiple domain pack instances.
    Provides namespace isolation and cross-domain-pack queries.
    """
    
    def __init__(self, node_repository=None):
        """
        Initialize workspace manager.
        
        Args:
            node_repository: Optional database repository for persistence
        """
        self.node_repository = node_repository
        self.current_workspace: Optional[WorkspaceNode] = None
        self.domain_packs: Dict[str, DomainPackInstance] = {}
        self.loader = DomainPackLoader()
    
    async def initialize_workspace(
        self,
        workspace_info: WorkspaceInfo,
        domain_pack_configs: List[DomainPackConfig]
    ) -> SSPInitializeResponse:
        """
        Initialize or load a workspace with multiple domain packs.
        
        Args:
            workspace_info: Workspace identification and metadata
            domain_pack_configs: List of domain packs to load
        
        Returns:
            SSPInitializeResponse with loaded domain pack information
        """
        # Create or load workspace node
        workspace_node = WorkspaceNode(
            id=workspace_info.id,
            name=workspace_info.name,
            description=workspace_info.description,
            root_path=workspace_info.root,
            created_at=datetime.now(),
            last_modified_at=datetime.now(),
            status="active"
        )
        
        self.current_workspace = workspace_node
        
        # Persist workspace node if repository available
        if self.node_repository:
            await self.node_repository.create_node(workspace_node)
        
        # Load each domain pack
        loaded_packs: List[LoadedDomainPackInfo] = []
        
        for pack_config in domain_pack_configs:
            try:
                pack_instance = await self._load_domain_pack(pack_config)
                self.domain_packs[pack_config.namespace] = pack_instance
                
                # Create info response
                loaded_packs.append(LoadedDomainPackInfo(
                    namespace=pack_config.namespace,
                    domain_id=pack_instance.domain_node.id,
                    name=pack_instance.domain_node.name,
                    version=pack_instance.domain_node.domain_pack_version,
                    metrics_count=len(pack_instance.metric_registry.list_all()),
                    subdomains_count=0  # TODO: count subdomains from taxonomy_tree
                ))
                
                # Create workspace -> domain pack edge if repository available
                if self.node_repository:
                    await self.node_repository.create_edge(
                        from_node_id=workspace_node.id,
                        to_node_id=pack_instance.domain_node.id,
                        edge_type="CONTAINS_DOMAIN_PACK",
                        properties={"namespace": pack_config.namespace}
                    )
                
            except Exception as e:
                print(f"Warning: Failed to load domain pack '{pack_config.namespace}': {e}")
                continue
        
        # Count total papers (from database if available)
        total_papers = 0
        if self.node_repository:
            # TODO: query paper count from database
            pass
        
        return SSPInitializeResponse(
            workspace_id=workspace_info.id,
            status="initialized" if loaded_packs else "error",
            loaded_domain_packs=loaded_packs,
            total_papers=total_papers,
            ready=len(loaded_packs) > 0,
            message=f"Loaded {len(loaded_packs)} domain pack(s)" if loaded_packs 
                    else "Failed to load any domain packs"
        )
    
    async def _load_domain_pack(self, pack_config: DomainPackConfig) -> DomainPackInstance:
        """
        Load a single domain pack from config file.
        
        Args:
            pack_config: Domain pack configuration with namespace
        
        Returns:
            DomainPackInstance with loaded registries
        """
        # Resolve config path
        config_path = Path(pack_config.config_ref.path)
        if not config_path.is_absolute():
            # Make relative to workspace root if available
            if self.current_workspace:
                workspace_root = Path(self.current_workspace.root_path.replace("file://", ""))
                config_path = workspace_root / config_path
        
        # Load config using domain pack loader
        domain_pack = self.loader.load_config(str(config_path))
        
        # Build registries
        metric_registry = MetricRegistry()
        alias_registry = AliasRegistry()
        unit_registry = UnitRegistry()
        
        for metric in domain_pack.core_metrics:
            metric_registry.register(metric.name, metric.expected_unit)
            
            if hasattr(metric, 'aliases') and metric.aliases:
                for alias in metric.aliases:
                    alias_registry.register_alias(alias, metric.name)
        
        # Build unit normalization registry
        if hasattr(domain_pack, 'validation') and domain_pack.validation:
            if hasattr(domain_pack.validation, 'unit_normalization'):
                for canonical_unit, variants in domain_pack.validation.unit_normalization.items():
                    for variant in variants:
                        unit_registry.register_unit(variant, canonical_unit)
        
        # Create domain node with namespace
        domain_node = DomainNode(
            id=domain_pack.domain.id,
            name=domain_pack.domain.name,
            namespace=pack_config.namespace,
            domain_pack_id=domain_pack.domain.id,
            domain_pack_version=str(domain_pack.schema_version),
            taxonomy_tree=domain_pack.domain.model_dump().get('taxonomy_tree', {}),
            core_metrics=[f"{pack_config.namespace}:{m.name}" for m in domain_pack.core_metrics],
            parent_domain_id=domain_pack.domain.parent_domain_id,
            classification_hints=domain_pack.domain.classification_hints,
            approval_status="approved"
        )
        
        # Persist domain node if repository available
        if self.node_repository:
            await self.node_repository.create_node(domain_node)
        
        return DomainPackInstance(
            namespace=pack_config.namespace,
            domain_node=domain_node,
            metric_registry=metric_registry,
            alias_registry=alias_registry,
            unit_registry=unit_registry,
            config_path=str(config_path)
        )
    
    def get_domain_pack(self, namespace: str) -> Optional[DomainPackInstance]:
        """Get domain pack by namespace."""
        return self.domain_packs.get(namespace)
    
    def list_domain_packs(self) -> List[str]:
        """List all loaded domain pack namespaces."""
        return list(self.domain_packs.keys())
    
    def resolve_metric_globally(self, metric_name: str) -> Optional[tuple[str, DomainPackInstance]]:
        """
        Resolve a metric name across all loaded domain packs.
        
        Args:
            metric_name: Metric name (with or without namespace)
        
        Returns:
            Tuple of (fully_qualified_name, domain_pack_instance) or None
        """
        # If already fully qualified, try direct lookup
        if ":" in metric_name:
            namespace = metric_name.split(":", 1)[0]
            pack = self.domain_packs.get(namespace)
            if pack:
                resolved = pack.resolve_metric(metric_name)
                if resolved:
                    return (resolved, pack)
            return None
        
        # Try each domain pack
        for namespace, pack in self.domain_packs.items():
            resolved = pack.resolve_metric(metric_name)
            if resolved:
                return (resolved, pack)
        
        return None
    
    def get_all_metrics(self, namespace: Optional[str] = None) -> List[str]:
        """
        Get all metrics, optionally filtered by namespace.
        
        Args:
            namespace: Optional namespace filter
        
        Returns:
            List of fully qualified metric names
        """
        if namespace:
            pack = self.domain_packs.get(namespace)
            return pack.get_namespaced_metrics() if pack else []
        
        # All metrics from all packs
        all_metrics = []
        for pack in self.domain_packs.values():
            all_metrics.extend(pack.get_namespaced_metrics())
        return all_metrics
    
    def validate_assertion_subject(self, subject: str, namespace: str) -> bool:
        """
        Validate that an assertion subject is a valid metric in the given namespace.
        
        Args:
            subject: Metric name (e.g., "optical:reconfiguration_delay")
            namespace: Expected namespace
        
        Returns:
            True if valid, False otherwise
        """
        pack = self.domain_packs.get(namespace)
        if not pack:
            return False
        
        return pack.resolve_metric(subject) is not None

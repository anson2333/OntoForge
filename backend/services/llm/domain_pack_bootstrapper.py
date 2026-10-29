"""
LLM-based Domain Pack Bootstrapper

This module uses LLM to extract domain concepts, metrics, and taxonomy
from research proposals or domain descriptions.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from backend.services.llm.base import LLMProvider, get_default_provider
from backend.schemas.domain_pack import DomainPackConfig, DomainInfo, MetricDefinition, ValidationRules


class TaxonomyDimension(BaseModel):
    """A dimension of the domain taxonomy"""
    name: str = Field(description="Name of the taxonomy dimension (e.g., 'network_type', 'topology')")
    values: List[str] = Field(description="Possible values for this dimension")
    subdomain_map: Dict[str, str] = Field(default_factory=dict, description="Mapping from values to subdomain IDs")
    description: str = Field(description="Description of what this dimension represents")


class BootstrappedDomainPack(BaseModel):
    """Domain pack structure extracted by LLM"""
    domain_id: str = Field(description="Unique domain identifier (e.g., 'domain.networking.optical')")
    domain_name: str = Field(description="Human-readable domain name")
    taxonomy_dimensions: List[TaxonomyDimension] = Field(description="Taxonomy dimensions defining subdomains")
    core_metrics: List[Dict[str, Any]] = Field(description="Core metrics with name, unit, aliases, value_type")
    validation_rules: Dict[str, Any] = Field(description="Validation configuration")


class DomainPackBootstrapper:
    """Bootstraps domain pack configurations from text using LLM"""
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or get_default_provider()
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for domain pack extraction"""
        return """You are an expert research domain analyzer. Extract domain pack configuration from research proposals.

A domain pack defines:
1. **Domain Identity**: Unique ID and name for the research area
2. **Taxonomy Dimensions**: Categorical variables that define subdomains (e.g., network_type, topology, frequency_band)
3. **Core Metrics**: Quantitative measurements researchers track (with units, aliases, data types)
4. **Validation Rules**: Required context keys and unit normalizations

Guidelines:
- Domain ID format: domain.<category>.<subdomain> (e.g., domain.networking.optical, domain.computing.quantum)
- Taxonomy dimensions should capture the main categorical variables in the domain
- Metrics must have expected_unit (e.g., 'ms', 'dB', 'Gbps', 'ratio')
- Include common aliases for metrics (e.g., 'latency' → ['delay', 'response_time'])
- value_type must be 'float', 'int', 'string', or 'boolean'
- Subdomain mapping: map specific taxonomy values to subdomain IDs (e.g., 'mmWave' → 'domain.networking.wireless.mmwave')

Extract 5-8 core metrics that are most frequently measured in this domain.
Create 2-4 taxonomy dimensions that meaningfully partition the domain.
"""
    
    def _build_user_prompt(self, proposal_text: str) -> str:
        """Build user prompt with the proposal text"""
        return f"""Research Proposal/Domain Description:

{proposal_text}

Extract the domain pack configuration from this text.
"""
    
    async def bootstrap_async(self, proposal_text: str) -> DomainPackConfig:
        """
        Bootstrap a domain pack from proposal text using LLM
        
        Args:
            proposal_text: Research proposal or domain description
            
        Returns:
            Complete DomainPackConfig
            
        Raises:
            ValueError: If LLM fails or returns invalid structure
        """
        if not proposal_text or not proposal_text.strip():
            raise ValueError("proposal_text cannot be empty")
        
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(proposal_text)
        
        try:
            result = await self.provider.invoke_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=BootstrappedDomainPack,
                temperature=0.3,  # Low temperature for consistency
                max_tokens=2000
            )
            
            if not result.success or not result.data:
                raise ValueError(f"LLM failed to bootstrap domain pack: {result.error}")
            
            bootstrapped = result.data
            
            # Convert to DomainPackConfig
            domain_pack = DomainPackConfig(
                schema_version="1.0",
                domain=DomainInfo(
                    id=bootstrapped.domain_id,
                    name=bootstrapped.domain_name,
                    taxonomy_tree=[
                        {
                            "name": dim.name,
                            "values": dim.values,
                            "subdomain_map": dim.subdomain_map,
                            "description": dim.description
                        }
                        for dim in bootstrapped.taxonomy_dimensions
                    ]
                ),
                core_metrics=[
                    MetricDefinition(**metric)
                    for metric in bootstrapped.core_metrics
                ],
                validation=ValidationRules(
                    required_context_keys=bootstrapped.validation_rules.get("required_context_keys", []),
                    unit_normalization=bootstrapped.validation_rules.get("unit_normalization", {})
                )
            )
            
            return domain_pack
            
        except Exception as e:
            raise ValueError(f"Failed to bootstrap domain pack: {str(e)}")
    
    def bootstrap(self, proposal_text: str) -> DomainPackConfig:
        """
        Synchronous wrapper for bootstrap_async
        
        Args:
            proposal_text: Research proposal or domain description
            
        Returns:
            Complete DomainPackConfig
        """
        import asyncio
        return asyncio.run(self.bootstrap_async(proposal_text))


def create_domain_pack_bootstrapper(provider: Optional[LLMProvider] = None) -> DomainPackBootstrapper:
    """Factory function to create a domain pack bootstrapper"""
    return DomainPackBootstrapper(provider)

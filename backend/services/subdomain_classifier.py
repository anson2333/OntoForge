"""
Subdomain Classification Service
Automatically classifies papers into subdomains based on taxonomy dimensions.
"""

import json
from typing import Any, Dict, List, Tuple
from backend.schemas.domain_pack import DomainPackConfig, TaxonomyDimension
from backend.schemas.nodes import PaperNode, ChunkNode


class SubdomainClassifier:
    """
    Classifies papers into subdomains using taxonomy-based rules and LLM reasoning.
    """

    def __init__(self, domain_config: DomainPackConfig):
        """
        Initialize classifier with domain configuration.
        
        Args:
            domain_config: Loaded domain pack configuration
        """
        self.domain_config = domain_config
        self.taxonomy_dimensions = self._parse_taxonomy_dimensions()

    def _parse_taxonomy_dimensions(self) -> List[TaxonomyDimension]:
        """
        Extract structured taxonomy dimensions from domain config.
        
        Returns:
            List of TaxonomyDimension objects
        """
        dimensions = []
        taxonomy_tree = self.domain_config.domain.taxonomy_tree

        # Handle both old format (List[str]) and new format (List[TaxonomyDimension])
        if isinstance(taxonomy_tree, list):
            for item in taxonomy_tree:
                if isinstance(item, str):
                    # Old format: just dimension name
                    dimensions.append(
                        TaxonomyDimension(
                            name=item,
                            values=[],
                            subdomain_map={},
                            description=f"Legacy dimension: {item}"
                        )
                    )
                elif isinstance(item, dict):
                    # New format: structured dimension
                    dimensions.append(TaxonomyDimension(**item))
                elif hasattr(item, 'name'):
                    # Already a TaxonomyDimension object
                    dimensions.append(item)

        return dimensions

    async def classify_paper(
        self,
        paper: PaperNode,
        extracted_chunks: List[ChunkNode],
        llm_client=None
    ) -> List[Tuple[str, float, str]]:
        """
        Classify a paper into subdomains based on content and taxonomy.
        
        Args:
            paper: Paper metadata
            extracted_chunks: Text chunks extracted from paper
            llm_client: Optional LLM client for AI-based classification
        
        Returns:
            List of (subdomain_id, confidence, dimension_name) tuples
        """
        subdomain_assignments = []

        # If no structured taxonomy, return parent domain only
        if not self.taxonomy_dimensions or all(not dim.subdomain_map for dim in self.taxonomy_dimensions):
            return [(
                self.domain_config.domain.id,
                1.0,
                "default"
            )]

        # Use LLM-based classification if available
        if llm_client:
            classification = await self._llm_classify(paper, extracted_chunks, llm_client)
        else:
            # Fallback to rule-based classification
            classification = self._rule_based_classify(paper, extracted_chunks)

        # Map dimension values to subdomain IDs
        for dimension in self.taxonomy_dimensions:
            if dimension.name in classification and dimension.subdomain_map:
                value = classification[dimension.name]['value']
                confidence = classification[dimension.name].get('confidence', 0.8)

                if value in dimension.subdomain_map:
                    subdomain_id = dimension.subdomain_map[value]
                    subdomain_assignments.append((subdomain_id, confidence, dimension.name))

        # If no subdomains matched, assign to parent domain
        if not subdomain_assignments:
            subdomain_assignments.append((
                self.domain_config.domain.id,
                1.0,
                "parent_default"
            ))

        return subdomain_assignments

    async def _llm_classify(
        self,
        paper: PaperNode,
        chunks: List[ChunkNode],
        llm_client
    ) -> Dict[str, Dict[str, Any]]:
        """
        Use LLM to classify paper based on taxonomy dimensions.
        
        Args:
            paper: Paper metadata
            chunks: Text chunks from paper
            llm_client: LLM client (e.g., OpenAI, Anthropic)
        
        Returns:
            Dict mapping dimension names to {value, confidence}
        """
        # Build taxonomy description for LLM prompt
        taxonomy_desc = []
        for dim in self.taxonomy_dimensions:
            if dim.subdomain_map:
                taxonomy_desc.append(
                    f"- **{dim.name}**: Choose from {dim.values}\n  ({dim.description})"
                )

        taxonomy_str = "\n".join(taxonomy_desc)

        # Get sample chunks (first 5 or first 1000 chars total)
        sample_text = ""
        for chunk in chunks[:5]:
            sample_text += chunk.raw_text + "\n\n"
            if len(sample_text) > 1000:
                break
        sample_text = sample_text[:1000]

        # Build classification prompt
        prompt = f"""You are classifying a scientific paper into research subdomains.

**Paper Information:**
- Title: {paper.title}
- Authors: {', '.join(paper.authors)}
- Year: {paper.year}
- Venue: {paper.venue}

**Sample Content:**
{sample_text}

**Taxonomy Dimensions:**
{taxonomy_str}

For each dimension, select the most appropriate value from the available options.
Return your classification as JSON with this structure:

{{
    "dimension_name": {{
        "value": "selected_value",
        "confidence": 0.85,
        "reasoning": "brief explanation"
    }}
}}

Only include dimensions where you can make a confident classification (>0.6 confidence).
"""

        try:
            # Call LLM (adapt to your LLM client interface)
            response = await llm_client.generate(
                prompt=prompt,
                response_format="json",
                temperature=0.3
            )

            # Parse JSON response
            classification = json.loads(response)
            return classification

        except Exception as e:
            print(f"LLM classification failed: {e}")
            # Fallback to rule-based
            return self._rule_based_classify(paper, chunks)

    def _rule_based_classify(
        self,
        paper: PaperNode,
        chunks: List[ChunkNode]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Simple keyword-based classification as fallback.
        
        Args:
            paper: Paper metadata
            chunks: Text chunks from paper
        
        Returns:
            Dict mapping dimension names to {value, confidence}
        """
        classification = {}

        # Combine title and sample chunks for keyword matching
        text_content = paper.title.lower()
        for chunk in chunks[:10]:  # Use first 10 chunks
            text_content += " " + chunk.raw_text.lower()

        # For each dimension, find keywords matching values
        for dimension in self.taxonomy_dimensions:
            if not dimension.subdomain_map:
                continue

            best_match = None
            best_score = 0.0

            for value in dimension.values:
                # Simple keyword matching
                value_keywords = value.lower().replace("_", " ").split()
                score = sum(1 for kw in value_keywords if kw in text_content)
                
                # Normalize by keyword count
                if value_keywords:
                    score = score / len(value_keywords)

                if score > best_score:
                    best_score = score
                    best_match = value

            # Only add if we found a reasonable match
            if best_match and best_score > 0.3:
                classification[dimension.name] = {
                    'value': best_match,
                    'confidence': min(best_score, 0.85),  # Cap at 0.85 for rule-based
                    'reasoning': f'Keyword match in content'
                }

        return classification

    def get_subdomain_hierarchy(self) -> Dict[str, List[str]]:
        """
        Get mapping of parent domains to their subdomains.
        
        Returns:
            Dict mapping parent domain IDs to list of subdomain IDs
        """
        hierarchy = {self.domain_config.domain.id: []}

        for dimension in self.taxonomy_dimensions:
            for subdomain_id in dimension.subdomain_map.values():
                if subdomain_id not in hierarchy[self.domain_config.domain.id]:
                    hierarchy[self.domain_config.domain.id].append(subdomain_id)

        return hierarchy

    def ensure_subdomains_exist(self, node_repository) -> List[str]:
        """
        Ensure all subdomains defined in taxonomy exist as DomainNodes.
        Creates missing subdomain nodes.
        
        Args:
            node_repository: NodeRepository instance for database operations
        
        Returns:
            List of created subdomain IDs
        """
        from backend.schemas.nodes import DomainNode

        created = []
        parent_domain = self.domain_config.domain

        for dimension in self.taxonomy_dimensions:
            for value, subdomain_id in dimension.subdomain_map.items():
                # Check if subdomain node already exists
                try:
                    existing = node_repository.get_node_by_id(subdomain_id, "DomainNode")
                    if existing:
                        continue  # Already exists
                except:
                    pass  # Doesn't exist, create it

                # Generate subdomain name
                subdomain_name = f"{parent_domain.name} - {value.replace('_', ' ').title()}"

                # Create subdomain node
                subdomain_node = DomainNode(
                    id=subdomain_id,
                    name=subdomain_name,
                    domain_pack_id=parent_domain.id,
                    domain_pack_version=self.domain_config.schema_version,
                    taxonomy_tree={dimension.name: [value]},  # Inherit subset of parent taxonomy
                    core_metrics=self.domain_config.core_metrics,
                    approval_status="draft"
                )

                node_repository.create_domain_node(subdomain_node)
                created.append(subdomain_id)

        return created

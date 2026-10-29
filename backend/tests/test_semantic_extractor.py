"""Tests for LLM-based semantic extraction."""

import pytest

from backend.schemas.domain_pack import DomainInfo, DomainPackConfig, MetricDefinition, ValidationRules
from backend.schemas.protocol import ExtractedChunk, ExtractedFormula
from backend.services.llm.base import LLMProviderConfig, MockLLMProvider
from backend.services.llm.semantic_extractor import (
    AssertionExtractionResult,
    ExtractedAssertionCandidate,
    SemanticExtractor,
    _build_extraction_context,
    _build_response_schema,
    _build_system_prompt,
    _build_user_prompt,
)


@pytest.fixture
def sample_domain_pack_config():
    """Create a sample domain pack config for testing."""
    return DomainPackConfig(
        schema_version="1.0",
        domain=DomainInfo(
            id="domain.networking.optical",
            name="Optical Networking",
            taxonomy_tree=[],
        ),
        core_metrics=[
            MetricDefinition(
                name="reconfiguration_delay",
                aliases=["switching_time", "reconfiguration_time"],
                expected_unit="ms",
            ),
            MetricDefinition(
                name="insertion_loss",
                aliases=["optical_loss"],
                expected_unit="dB",
            ),
        ],
        validation=ValidationRules(
            required_context_keys=["network_load", "topology"],
            unit_normalization={
                "ms": ["milliseconds", "msec"],
                "dB": ["decibels", "db"],
            },
        ),
    )


@pytest.fixture
def sample_chunks():
    """Create sample extracted chunks."""
    return [
        ExtractedChunk(
            chunk_id="chunk_0",
            raw_text="The reconfiguration delay is 12.5 ms under high network load.",
            bounding_box={"page": 1, "x": 100, "y": 200, "width": 400, "height": 50},
        ),
        ExtractedChunk(
            chunk_id="chunk_1",
            raw_text="We measured an insertion loss of 3.2 dB in the ring resonator.",
            bounding_box={"page": 1, "x": 100, "y": 300, "width": 400, "height": 50},
        ),
        ExtractedChunk(
            chunk_id="chunk_2",
            raw_text="Figure 1 shows the experimental setup used in our study.",
            bounding_box={"page": 2, "x": 100, "y": 100, "width": 400, "height": 30},
        ),
    ]


@pytest.fixture
def sample_formulas():
    """Create sample extracted formulas."""
    return [
        ExtractedFormula(
            formula_id="formula_0",
            latex_string=r"T_{reconfig} = 12.5 \text{ ms}",
            variables_map={"T_reconfig": "reconfiguration_delay"},
            bounding_box={"page": 1, "x": 100, "y": 400, "width": 200, "height": 30},
        ),
    ]


def test_build_extraction_context(sample_domain_pack_config):
    """Test building extraction context from domain pack config."""
    context = _build_extraction_context(sample_domain_pack_config)

    assert context.domain_id == "domain.networking.optical"
    assert context.namespace == "optical"
    assert len(context.metrics) == 2
    assert context.metrics[0]["name"] == "reconfiguration_delay"
    assert context.metrics[0]["expected_unit"] == "ms"
    assert "switching_time" in context.metrics[0]["aliases"]
    assert "equals" in context.predicates
    assert "network_load" in context.context_keys


def test_build_system_prompt(sample_domain_pack_config):
    """Test building system prompt for LLM."""
    context = _build_extraction_context(sample_domain_pack_config)
    prompt = _build_system_prompt(context)

    assert "domain.networking.optical" in prompt
    assert "reconfiguration_delay" in prompt
    assert "ms" in prompt
    assert "confidence" in prompt.lower()
    assert "metric_name" in prompt


def test_build_user_prompt(sample_chunks, sample_formulas):
    """Test building user prompt with chunks and formulas."""
    prompt = _build_user_prompt(sample_chunks, sample_formulas)

    assert "chunk_0" in prompt
    assert "12.5 ms" in prompt
    assert "formula_0" in prompt
    assert "T_{reconfig}" in prompt


def test_build_response_schema():
    """Test JSON schema generation for structured output."""
    schema = _build_response_schema()

    assert schema["type"] == "object"
    assert "assertions" in schema["properties"]
    assert schema["properties"]["assertions"]["type"] == "array"
    assert "metric_name" in schema["properties"]["assertions"]["items"]["properties"]


def test_semantic_extractor_initialization():
    """Test semantic extractor initialization."""
    config = LLMProviderConfig(provider="mock", model="test-model", enabled=True)
    provider = MockLLMProvider(config)
    extractor = SemanticExtractor(llm_provider=provider)

    assert extractor.is_available()


def test_semantic_extractor_unavailable_when_provider_disabled():
    """Test semantic extractor reports unavailable when provider disabled."""
    config = LLMProviderConfig(provider="disabled", enabled=False)
    provider = MockLLMProvider(config)
    extractor = SemanticExtractor(llm_provider=provider)

    assert not extractor.is_available()


def test_semantic_extractor_unavailable_when_no_provider():
    """Test semantic extractor reports unavailable with no provider."""
    extractor = SemanticExtractor(llm_provider=None)

    assert not extractor.is_available()


@pytest.mark.asyncio
async def test_extract_assertions_with_mock_provider(
    sample_domain_pack_config, sample_chunks, sample_formulas
):
    """Test assertion extraction with mock LLM provider."""
    # Create a mock provider that returns realistic structured output
    config = LLMProviderConfig(provider="mock", model="test-model", enabled=True)
    
    class RealisticMockProvider(MockLLMProvider):
        async def invoke_structured(self, request):
            # Return a realistic extraction result
            return type('Result', (), {
                'structured_output': {
                    'assertions': [
                        {
                            'metric_name': 'reconfiguration_delay',
                            'predicate': 'equals',
                            'value': '12.5',
                            'unit': 'ms',
                            'context_conditions': {'network_load': 'high'},
                            'confidence': 0.95,
                            'reasoning': 'Direct statement in text',
                            'source_chunk_ids': ['chunk_0'],
                            'source_formula_ids': ['formula_0'],
                        }
                    ],
                    'warnings': [],
                }
            })()
    
    provider = RealisticMockProvider(config)
    extractor = SemanticExtractor(llm_provider=provider)

    assertions = await extractor.extract_assertions(
        chunks=sample_chunks,
        formulas=sample_formulas,
        config=sample_domain_pack_config,
        domain_pack_namespace="optical",
    )

    assert len(assertions) == 1
    assert assertions[0].subject == "optical:reconfiguration_delay"
    assert assertions[0].object == "12.5"
    assert assertions[0].unit == "ms"
    assert len(assertions[0].evidence_links) == 2  # chunk + formula


def test_extract_assertions_sync_wrapper(
    sample_domain_pack_config, sample_chunks, sample_formulas
):
    """Test synchronous wrapper for assertion extraction."""
    config = LLMProviderConfig(provider="mock", model="test-model", enabled=True)
    
    class RealisticMockProvider(MockLLMProvider):
        async def invoke_structured(self, request):
            return type('Result', (), {
                'structured_output': {
                    'assertions': [
                        {
                            'metric_name': 'insertion_loss',
                            'predicate': 'equals',
                            'value': '3.2',
                            'unit': 'dB',
                            'context_conditions': {},
                            'confidence': 0.9,
                            'reasoning': 'Measured value in text',
                            'source_chunk_ids': ['chunk_1'],
                            'source_formula_ids': [],
                        }
                    ],
                    'warnings': [],
                }
            })()
    
    provider = RealisticMockProvider(config)
    extractor = SemanticExtractor(llm_provider=provider)

    # Test synchronous wrapper
    assertions = extractor.extract_assertions_sync(
        chunks=sample_chunks,
        formulas=sample_formulas,
        config=sample_domain_pack_config,
        domain_pack_namespace="optical",
    )

    assert len(assertions) == 1
    assert assertions[0].subject == "optical:insertion_loss"
    assert assertions[0].object == "3.2"
    assert assertions[0].unit == "dB"


@pytest.mark.asyncio
async def test_extract_assertions_filters_invalid_metrics(
    sample_domain_pack_config, sample_chunks, sample_formulas
):
    """Test that assertions with invalid metric names are filtered out."""
    config = LLMProviderConfig(provider="mock", model="test-model", enabled=True)
    
    class MockProviderWithInvalidMetric(MockLLMProvider):
        async def invoke_structured(self, request):
            return type('Result', (), {
                'structured_output': {
                    'assertions': [
                        {
                            'metric_name': 'invalid_metric_not_in_domain',
                            'predicate': 'equals',
                            'value': '100',
                            'unit': 'units',
                            'context_conditions': {},
                            'confidence': 0.8,
                            'reasoning': 'Should be filtered out',
                            'source_chunk_ids': ['chunk_0'],
                            'source_formula_ids': [],
                        },
                        {
                            'metric_name': 'reconfiguration_delay',
                            'predicate': 'equals',
                            'value': '12.5',
                            'unit': 'ms',
                            'context_conditions': {},
                            'confidence': 0.95,
                            'reasoning': 'Valid metric',
                            'source_chunk_ids': ['chunk_0'],
                            'source_formula_ids': [],
                        }
                    ],
                    'warnings': [],
                }
            })()
    
    provider = MockProviderWithInvalidMetric(config)
    extractor = SemanticExtractor(llm_provider=provider)

    assertions = await extractor.extract_assertions(
        chunks=sample_chunks,
        formulas=sample_formulas,
        config=sample_domain_pack_config,
        domain_pack_namespace="optical",
    )

    # Only the valid metric should be included
    assert len(assertions) == 1
    assert assertions[0].subject == "optical:reconfiguration_delay"


@pytest.mark.asyncio
async def test_extract_assertions_normalizes_aliases_and_units(
    sample_domain_pack_config, sample_chunks, sample_formulas
):
    """Alias metric names and unit synonyms are normalized to the domain pack form."""
    config = LLMProviderConfig(provider="mock", model="test-model", enabled=True)

    class AliasMockProvider(MockLLMProvider):
        async def invoke_structured(self, request):
            return type('Result', (), {
                'structured_output': {
                    'assertions': [
                        {
                            'metric_name': 'switching_time',
                            'predicate': 'equals',
                            'value': '12.5',
                            'unit': 'milliseconds',
                            'context_conditions': {},
                            'confidence': 0.9,
                            'reasoning': 'Alias of reconfiguration_delay',
                            'source_chunk_ids': ['chunk_0'],
                            'source_formula_ids': [],
                        }
                    ],
                    'warnings': [],
                }
            })()

    extractor = SemanticExtractor(llm_provider=AliasMockProvider(config))

    assertions = await extractor.extract_assertions(
        chunks=sample_chunks,
        formulas=sample_formulas,
        config=sample_domain_pack_config,
        domain_pack_namespace="optical",
    )

    assert len(assertions) == 1
    assert assertions[0].subject == "optical:reconfiguration_delay"
    assert assertions[0].unit == "ms"


@pytest.mark.asyncio
async def test_extract_assertions_handles_llm_failure(
    sample_domain_pack_config, sample_chunks, sample_formulas
):
    """Test that extraction gracefully handles LLM failures."""
    config = LLMProviderConfig(provider="mock", model="test-model", enabled=True)
    
    class FailingMockProvider(MockLLMProvider):
        async def invoke_structured(self, request):
            raise RuntimeError("Simulated LLM failure")
    
    provider = FailingMockProvider(config)
    extractor = SemanticExtractor(llm_provider=provider)

    assertions = await extractor.extract_assertions(
        chunks=sample_chunks,
        formulas=sample_formulas,
        config=sample_domain_pack_config,
        domain_pack_namespace="optical",
    )

    # Should return empty list on failure, not crash
    assert assertions == []

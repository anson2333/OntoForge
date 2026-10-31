"""Executable domain guidance, conversions, and source-grounded CV extraction."""
import pytest
from backend.config.loader import DomainPackLoader
from backend.schemas.protocol import ExtractedChunk
from backend.services.llm.base import LLMProviderConfig, MockLLMProvider, StructuredOutputResult
from backend.services.llm.semantic_extractor import SemanticExtractor, _build_extraction_context, _build_system_prompt


def config():
    return DomainPackLoader().load('backend/configs/domain-pack-cv-detection.yaml')


def test_cv_prompt_includes_definitions_context_taxonomy_and_exclusions():
    prompt = _build_system_prompt(_build_extraction_context(config()))
    for text in ['timing_scope', 'training_data', 'voc2007_test', 'VOC 2007', 'percentage-point', 'baseline']:
        assert text in prompt
    assert 'network_load, topology, temperature' not in prompt
    assert 'model_variant' in prompt


@pytest.mark.asyncio
async def test_cv_converts_seconds_keeps_provenance_and_marks_missing_context():
    rows = [dict(metric_name='inference_latency', value='0.32', unit='seconds', confidence=0.9,
                 source_chunk_ids=['c1'], context_conditions={'detector_family': 'Fast R-CNN', 'model_variant': 'Fast R-CNN VGG16', 'method': 'region_based'})]
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            return StructuredOutputResult(provider='mock', structured_output={'assertions': rows})
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider='mock', enabled=True)))
    result = await extractor.extract_assertions([ExtractedChunk(chunk_id='c1', raw_text='Fast R-CNN test time is 0.32 seconds per image.', bounding_box={'page': 6})], [], config(), 'cv_detection')
    assert len(result) == 1
    assert float(result[0].object) == 320
    assert result[0].unit == 'ms'
    assert result[0].context_conditions['reported_value'] == '0.32'
    assert result[0].context_conditions['reported_unit'] == 'seconds'
    assert result[0].context_conditions['scenario'] == 'unknown'
    assert result[0].context_conditions['review_required'] is True


@pytest.mark.asyncio
async def test_cv_rejects_out_of_range_and_absent_json_numbers():
    rows = [dict(metric_name='voc_map50', value=value, unit='percent', confidence=0.9, source_chunk_ids=['c1']) for value in ['120', '73.2', '66.9']]
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            return StructuredOutputResult(provider='mock', structured_output={'assertions': rows})
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider='mock', enabled=True)))
    result = await extractor.extract_assertions([ExtractedChunk(chunk_id='c1', raw_text='The mAP is 66.9 percent, not 120.', bounding_box={'page': 1})], [], config(), 'cv_detection')
    assert [r.object for r in result] == ['66.9']
    assert any('range' in w for w in extractor.diagnostics['warnings'])
    assert any('absent' in w for w in extractor.diagnostics['warnings'])


def test_cv_percentage_points_are_not_absolute_accuracy_units():
    from backend.services.normalization import normalize_unit
    assert normalize_unit('percentage_points', config()) != 'percent'


def test_metadata_prefers_document_arxiv_year_over_benchmark():
    from backend.services.pdf_ingestion_service import _build_metadata
    metadata = _build_metadata('paper.pdf', b'pdf', 'Fast R-CNN\nEvaluated on VOC 2012.\narXiv:1504.08083v1 [cs.CV] 30 Apr 2015', None)
    assert metadata.year == 2015


@pytest.mark.asyncio
async def test_document_family_and_excluded_roles_are_executable():
    rows = [
        dict(metric_name='inference_fps', value='45', unit='fps', context_conditions={'detector_family': 'YOLO', 'result_role': 'primary'}),
        dict(metric_name='inference_fps', value='0.02', unit='fps', context_conditions={'detector_family': 'R-CNN', 'result_role': 'primary'}),
        dict(metric_name='voc_map50', value='74.7', unit='percent', context_conditions={'detector_family': 'YOLO', 'source_table': 'Model combination experiments'}),
        dict(metric_name='voc_map50', value='54.5', unit='percent', context_conditions={'detector_family': 'YOLO', 'result_role': 'baseline'}),
    ]
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            assert 'complete detector family of THIS paper is yolo' in request.user_prompt
            return StructuredOutputResult(provider='mock', structured_output={'assertions': [dict(r, confidence=0.9, source_chunk_ids=['c1']) for r in rows]})
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider='mock', enabled=True)))
    result = await extractor.extract_assertions([ExtractedChunk(chunk_id='c1', raw_text='You Only Look Once\nAbstract\nYOLO is 45 fps, R-CNN is 0.02 fps; combination 74.7 and baseline 54.5 percent.', bounding_box={'page': 1})], [], config(), 'cv_detection')
    assert [r.object for r in result] == ['45']
    assert len(extractor.diagnostics['warnings']) == 3


@pytest.mark.asyncio
async def test_output_limit_is_failed_batch_even_if_adapter_could_salvage_a_row():
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            return StructuredOutputResult(provider='mock', structured_output={'assertions': [{'metric_name': 'voc_map50', 'value': '54.5', 'unit': 'percent', 'source_chunk_ids': ['c1']}]}, finish_reason='length')
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider='mock', enabled=True)))
    result = await extractor.extract_assertions([ExtractedChunk(chunk_id='c1', raw_text='YOLO\nAbstract\n54.5 percent.', bounding_box={'page': 1})], [], config(), 'cv_detection')
    assert result == []
    assert extractor.diagnostics['failed_batches'] == [0]
    assert extractor.diagnostics['finish_reasons'] == ['length']


def test_cv_batch_budget_is_used():
    extractor = SemanticExtractor()
    chunks = [ExtractedChunk(chunk_id=f'c{i}', raw_text='a' * 10000, bounding_box={'page': i + 1}) for i in range(2)]
    assert len(extractor._chunk_batches(chunks, config())) == 2


@pytest.mark.asyncio
async def test_svd_variant_is_not_misclassified_as_a_multi_detector_ensemble():
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            return StructuredOutputResult(provider='mock', structured_output={'assertions': [{'metric_name': 'voc_map50', 'value': '66.6', 'unit': 'percent', 'confidence': .9, 'source_chunk_ids': ['c1'], 'context_conditions': {'detector_family': 'Fast R-CNN + SVD', 'result_role': 'ablation'}}]})
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider='mock', enabled=True)))
    result = await extractor.extract_assertions([ExtractedChunk(chunk_id='c1', raw_text='Fast R-CNN\nAbstract\nWith SVD we report 66.6 percent.', bounding_box={'page': 1})], [], config(), 'cv_detection')
    assert len(result) == 1


def test_invalid_conversion_and_range_are_rejected_by_schema():
    from pydantic import ValidationError
    from backend.schemas.domain_pack import MetricDefinition
    with pytest.raises(ValidationError):
        MetricDefinition(name='x', expected_unit='ms', unit_conversions={'s': -1000})
    with pytest.raises(ValidationError):
        MetricDefinition(name='x', expected_unit='ms', minimum=10, maximum=1)


@pytest.mark.asyncio
async def test_single_detector_feature_fusion_is_not_an_ensemble():
    class Provider(MockLLMProvider):
        async def invoke_structured(self, request):
            return StructuredOutputResult(provider='mock', structured_output={'assertions': [{'metric_name': 'voc_map50', 'value': '54.5', 'unit': 'percent', 'confidence': .9, 'source_chunk_ids': ['c1'], 'context_conditions': {'detector_family': 'YOLO', 'model_variant': 'feature fusion variant', 'result_role': 'ablation'}, 'reasoning': 'Single network with learned feature fusion.'}]})
    extractor = SemanticExtractor(Provider(LLMProviderConfig(provider='mock', enabled=True)))
    result = await extractor.extract_assertions([ExtractedChunk(chunk_id='c1', raw_text='YOLO\nAbstract\nThe feature fusion variant has 54.5 percent mAP.', bounding_box={'page': 1})], [], config(), 'cv_detection')
    assert len(result) == 1

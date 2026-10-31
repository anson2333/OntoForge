"""Replay frozen model candidates through the final CV policy, with no API calls."""
import asyncio
import json
import os
from pathlib import Path

from backend.config.loader import DomainPackLoader
from backend.schemas.protocol import ExtractedChunk, ExtractedFormula
from backend.services.llm.base import LLMProviderConfig, MockLLMProvider, StructuredOutputResult
from backend.services.llm.semantic_extractor import SemanticExtractor


def main():
    root = Path(__file__).resolve().parents[1]
    config = DomainPackLoader().load(root / 'backend/configs/domain-pack-cv-detection.yaml')
    # This is candidate-validation replay, not another model extraction run.
    # Keep all cited evidence together regardless of the final batching policy.
    config = config.model_copy(update={'validation': config.validation.model_copy(update={'max_batch_characters': None})})
    os.environ['ONTOFORGE_LLM_BATCH_CHARACTERS'] = '1000000'
    report = {'method': 'Frozen round1 candidates replayed locally against final policy; zero model calls. Batching disabled only for replay. Does not establish completeness of the potentially truncated round1 Faster R-CNN output.', 'papers': {}}
    for stem in ['fast_rcnn', 'faster_rcnn', 'yolo']:
        preview = json.loads((root / f'data/cv-validation/rule-review/{stem}-preview.json').read_text(encoding='utf-8'))
        candidates = []
        for assertion in preview['assertions']:
            context = dict(assertion['context_conditions'])
            candidates.append({'metric_name': assertion['subject'].split(':')[-1],
                'value': context.get('reported_value', assertion['object']),
                'unit': context.get('reported_unit', assertion['unit']),
                'source_chunk_ids': [link['source_id'] for link in assertion['evidence_links'] if link['source_id'].startswith('chunk')],
                'source_formula_ids': [link['source_id'] for link in assertion['evidence_links'] if not link['source_id'].startswith('chunk')],
                'context_conditions': context, 'confidence': context.get('confidence', .7), 'reasoning': context.get('reasoning', '')})

        class Replay(MockLLMProvider):
            async def invoke_structured(self, request):
                return StructuredOutputResult(provider='mock', structured_output={'assertions': candidates}, finish_reason='stop')

        extractor = SemanticExtractor(Replay(LLMProviderConfig(provider='mock', enabled=True, model='offline-replay')))
        accepted = asyncio.run(extractor.extract_assertions(
            [ExtractedChunk.model_validate(chunk) for chunk in preview['chunks']],
            [ExtractedFormula.model_validate(formula) for formula in preview['formulas']], config, 'cv_detection'))
        report['papers'][stem] = {'input_candidates': len(candidates), 'remaining_candidates': len(accepted),
                                 'filtered_candidates': len(candidates) - len(accepted), 'warnings': extractor.diagnostics['warnings']}
    target = root / 'docs/cv-validation/rule-review/policy-replay.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

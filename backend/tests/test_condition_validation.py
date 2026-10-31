import pytest
from backend.schemas.protocol import ExtractedChunk
from backend.services.llm.condition_validation import validate_conditions

def run(context, text, metric='inference_latency'):
 return validate_conditions(context,metric,[ExtractedChunk(chunk_id='c1',raw_text=text,bounding_box={'page':1})],['c1'])

def evidence(quote):return {'source_chunk_id':'c1','quote':quote}

def test_missing_or_forged_evidence_cannot_claim_end_to_end():
 for ctx in [{'timing_scope':'end_to_end'}, {'timing_scope':'end_to_end','timing_scope_evidence':evidence('including all steps on a GPU')}]:
  result,_=run(ctx,'The test rate is 5 fps.')
  assert result['timing_scope']=='unknown'
  assert result['reported_experiment_conditions']['timing_scope']=='end_to_end'

def test_exclusion_quote_cannot_support_end_to_end():
 quote='Test time excludes proposal generation.'
 result,_=run({'timing_scope':'end_to_end','timing_scope_evidence':evidence(quote)},quote)
 assert result['timing_scope']=='unknown'
 result,_=run({'timing_scope':'detector_only_excludes_proposals','timing_scope_evidence':evidence(quote)},quote)
 assert result['timing_scope']=='detector_only_excludes_proposals'

def test_explicit_inclusion_and_component_scope():
 quote='The detector runs at 5 fps including all steps.'
 result,excluded=run({'timing_scope':'end_to_end','timing_scope_evidence':evidence(quote)},quote)
 assert result['timing_scope']=='end_to_end' and not excluded
 quote='RPN proposal generation costs 10 ms.'
 result,excluded=run({'timing_scope':'proposal_only','timing_scope_evidence':evidence(quote)},quote)
 assert excluded

def test_proposal_backbone_cannot_become_detector_backbone():
 quote='The RPN proposal network uses VGG16.'
 result,_=run({'backbone':'VGG16','detector_backbone':'VGG16','proposal_backbone':'VGG16','detector_backbone_evidence':evidence(quote),'proposal_backbone_evidence':evidence(quote)},quote,'voc_map50')
 assert result['backbone']=='unknown' and result['proposal_backbone']=='VGG16'
 quote='The detector backbone is ZF; RPN proposal backbone is VGG16.'
 result,_=run({'detector_backbone':'ZF','proposal_backbone':'VGG16','detector_backbone_evidence':evidence('The detector backbone is ZF;'),'proposal_backbone_evidence':evidence('RPN proposal backbone is VGG16.')},quote,'voc_map50')
 assert result['backbone']=='ZF' and result['proposal_backbone']=='VGG16'
@pytest.mark.asyncio
async def test_component_is_filtered_and_condition_issues_force_review():
 from backend.config.loader import DomainPackLoader
 from backend.services.llm.base import LLMProviderConfig, MockLLMProvider, StructuredOutputResult
 from backend.services.llm.semantic_extractor import SemanticExtractor
 config=DomainPackLoader().load('backend/configs/domain-pack-cv-detection.yaml')
 quote='RPN proposal generation costs 10 ms.'
 rows=[{'metric_name':'inference_latency','value':'10','unit':'ms','confidence':.9,'source_chunk_ids':['c1'],'context_conditions':{'timing_scope':'proposal_only','timing_scope_evidence':evidence(quote)}},
       {'metric_name':'inference_latency','value':'196','unit':'ms','confidence':.9,'source_chunk_ids':['c1'],'context_conditions':{k:'reported' for k in config.validation.required_context_keys}}]
 class Provider(MockLLMProvider):
  async def invoke_structured(self,request):
   return StructuredOutputResult(provider='mock',structured_output={'assertions':rows})
 extractor=SemanticExtractor(Provider(LLMProviderConfig(provider='mock',enabled=True)))
 result=await extractor.extract_assertions([ExtractedChunk(chunk_id='c1',raw_text=quote+' Total detection time is 196 ms.',bounding_box={'page':1})],[],config,'cv_detection')
 assert len(result)==1 and result[0].object=='196'
 assert result[0].context_conditions['review_required']
 assert result[0].context_conditions['timing_scope']=='unknown'
 assert any('组件耗时' in w for w in extractor.diagnostics['warnings'])

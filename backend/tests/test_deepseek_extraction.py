"""Provider-specific extraction budgets must leave room for answer tokens."""
import httpx
import pytest
from backend.services.llm.base import OpenAICompatibleProvider, LLMProviderConfig, StructuredOutputRequest

@pytest.mark.asyncio
@pytest.mark.parametrize('vendor,flexible,expected', [('deepseek',True,{'type':'disabled'}),('deepseek',False,None),('custom',True,None)])
async def test_deepseek_extraction_thinking(monkeypatch,vendor,flexible,expected):
    captured={}
    async def post(self,url,**kwargs):
        captured.update(kwargs['json'])
        return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]})
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    provider=OpenAICompatibleProvider(LLMProviderConfig(provider='openai_compatible',vendor=vendor,model='deepseek-flash',api_key='test',enabled=True,max_output_tokens=4096))
    await provider.invoke_structured(StructuredOutputRequest(system_prompt='Extract JSON',user_prompt='Paper',response_schema_name='test',metadata={'flexible_output':flexible}))
    assert captured.get('thinking')==expected
    assert captured['max_tokens']==4096

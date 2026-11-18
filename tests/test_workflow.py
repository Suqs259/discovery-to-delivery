import pytest
from fastapi.testclient import TestClient
from app.main import app, ROOT
from app.workflow import workflow, validate


@pytest.fixture(autouse=True)
def demo(monkeypatch):
    monkeypatch.setenv('MODEL_MODE', 'demo')


def test_evidence_and_traceability():
    source = (ROOT / 'data/sample.txt').read_text(encoding='utf-8')
    report = workflow.invoke({'transcript': source})
    assert len(report['requirements']) >= 5
    assert {r['category'] for r in report['requirements']} == {'integration','security','quality','delivery','workflow'}
    for r in report['requirements']:
        assert r['quote'] in source.splitlines()[r['source_line']-1]
    assert {r['id'] for r in report['requirements']} == {p['requirement_id'] for p in report['plan']}
    assert all(p['status'] == 'proposal_requires_customer_review' for p in report['plan'])


def test_fabricated_evidence_is_removed():
    r = validate({'transcript':'客户要求保留原文', 'requirements':[
        {'category':'security','statement':'虚构需求','quote':'不存在的证据','source_line':1},
        {'category':'security','statement':'越界行号','quote':'证据','source_line':999}]})
    assert r['requirements'] == []
    assert r['rejected'] == 2


def test_empty_extraction_produces_questions():
    r = workflow.invoke({'transcript':'今天晴天，我们刚刚结束会议。'})
    assert r['requirements'] == []
    assert len(r['questions']) == 5
    assert len(r['risks']) == 3


def test_api_validation_and_export():
    client = TestClient(app)
    assert client.post('/api/analyze',json={'transcript':'短'}).status_code == 422
    assert client.post('/api/analyze',json={'transcript':' '*20}).status_code == 422
    assert client.post('/api/analyze',json={'transcript':'x'*16001}).status_code == 422
    data = client.post('/api/analyze',json={'transcript':'客户表示需要接入 CRM，并进行权限隔离。'}).json()
    assert 'transcript' not in data
    assert '待客户审核' in data['markdown']
    assert data['mode'] == 'rule-demo'
    assert client.get('/').status_code == 200


def test_input_bounded_to_40_requirements():
    r = workflow.invoke({'transcript':'接入 API 权限隔离 准确率评估 月底交付 人工审批\n'*100})
    assert len(r['requirements']) <= 40


def test_live_extraction_with_mock(monkeypatch):
    import langchain_openai
    from app.workflow import Extraction, Requirement
    monkeypatch.setenv('MODEL_MODE', 'live')
    class FakeModel:
        def __init__(self, **kwargs): pass
        def with_structured_output(self, schema): return self
        def invoke(self, messages):
            return Extraction(requirements=[Requirement(category='security',statement='需要隔离客户资料',quote='权限隔离',source_line=1)])
    monkeypatch.setattr(langchain_openai,'ChatOpenAI',FakeModel)
    result = workflow.invoke({'transcript':'客户要求权限隔离，具体规则待确认。'})
    assert result['mode'] == 'live'
    assert len(result['requirements']) == 1

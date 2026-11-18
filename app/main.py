import time
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.workflow import workflow, markdown

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title='Discovery to Delivery', version='1.0.0')


class AnalyzeRequest(BaseModel):
    transcript: str = Field(min_length=10, max_length=16000)


@app.get('/')
def home():
    return FileResponse(ROOT / 'static/index.html')


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/api/sample')
def sample():
    return {'transcript': (ROOT / 'data/sample.txt').read_text(encoding='utf-8')}


@app.post('/api/analyze')
def analyze(body: AnalyzeRequest):
    transcript = body.transcript.strip()
    if len(transcript) < 10:
        raise HTTPException(422, '请输入至少 10 个有效字符')
    started = time.perf_counter()
    try:
        result = workflow.invoke({'transcript': transcript})
    except Exception:
        raise HTTPException(502, '分析失败，请检查模型配置或使用 demo 模式')
    result.pop('transcript', None)
    return {**result, 'markdown': markdown(result),
            'latency_ms': round((time.perf_counter() - started) * 1000)}

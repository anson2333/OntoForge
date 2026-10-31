"""Exercise the normal JSON-RPC handlers with a saved local user's active model.

Runs in-process HTTP transport so no password or session token is written to disk.
Creates a new workspace; never clears existing data. Outputs only redacted results.
"""
import base64
import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
from backend.server.app import app
from backend.database import init_db
from backend.services.auth_service import create_session
from backend.tests.conftest import SyncASGIClient


def main():
    report_path = Path('docs/live-validation-2026-10-30.json')
    profiles = json.loads(Path('backend/data/llm-profiles.json').read_text())
    active = [(uid, data) for uid, data in profiles['users'].items() if data.get('active_id')]
    if len(active) != 1:
        raise RuntimeError('Expected exactly one user with an active saved model')
    uid, config = active[0]
    profile = next(p for p in config['profiles'] if p['id'] == config['active_id'])
    # Resolve the existing local account without altering its password or saved API.
    users = json.loads(Path('backend/data/users.json').read_text())
    rows = users['users']
    if isinstance(rows, dict):
        rows = list(rows.values())
    user = next(u for u in rows if u['user_id'] == uid)
    session = create_session(user)
    client = SyncASGIClient(app)
    init_db(os.environ['NEO4J_URI'], os.environ['NEO4J_USER'], os.environ['NEO4J_PASSWORD'])
    report = {'date': '2026-10-30', 'transport': 'HTTPX ASGI against normal JSON-RPC handlers; local account session',
              'model': profile['model'], 'provider': profile['provider'], 'steps': []}

    def save():
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

    def rpc(method, params):
        started = time.monotonic()
        response = client.post('/jsonrpc', json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params},
                               headers={'Authorization': 'Bearer ' + session['token']}).json()
        step = {'method': method, 'seconds': round(time.monotonic() - started, 3), 'ok': 'error' not in response}
        report['steps'].append(step)
        if 'error' in response:
            step['error'] = response['error']['message']
            save()
            raise RuntimeError(step['error'])
        save()
        print(json.dumps(step), flush=True)
        return response['result']

    try:
        workspace = rpc('createWorkspace', {'name': '真实模型全流程验收 2026-10-30', 'root': 'live-validation',
                                           'description': '使用现有智谱接口与真实论文进行验收，保留提取结果供人工核对。'})['workspace']
        wid = workspace['id']
        report['workspace_id'] = wid
        pdf = Path('data/cv-validation/historical/fast_rcnn.pdf')
        raw = pdf.read_bytes()
        report['paper_file'] = pdf.name
        report['source_sha256'] = hashlib.sha256(raw).hexdigest()
        upload = rpc('uploadPdf', {'workspace_id': wid, 'file_name': pdf.name,
                                  'content_base64': base64.b64encode(raw).decode()})
        params = {'workspace_id': wid, 'domain_pack_namespace': 'cv_detection', 'upload_id': upload['upload_id']}
        preview = rpc('parsePdfWithDomainPack', params)
        report['preview'] = {k: v for k, v in preview.items() if k not in {'chunks', 'formulas', 'assertions', 'evidence', 'markdown_text'}}
        report['assertion_sample'] = preview.get('assertions', [])[:5]
        save()
        failures = preview.get('diagnostics', {}).get('errors', [])
        assert not failures, failures[0]['message'] if failures else ''
        assert preview.get('assertion_extraction_method') == 'llm', 'Extraction did not use the real LLM'
        assert preview.get('assertions'), 'Model returned no valid assertions'
        committed = rpc('commitParsedPdf', {**params, 'preview_id': preview['preview_id']})
        report['commit'] = committed
        report['papers'] = rpc('getPapers', {'workspace_id': wid})
        assertions = rpc('getAssertions', {'workspace_id': wid, 'paper_id': committed['paper_id']})
        report['assertions'] = assertions
        report['coverage'] = rpc('getCoverageAnalysis', {'workspace_id': wid, 'domain_pack_namespace': 'cv_detection'})
        rows = assertions.get('assertions', [])
        assert rows, 'No persisted assertions'
        report['evidence'] = rpc('getEvidence', {'workspace_id': wid, 'paper_id': committed['paper_id'],
                                               'metric_name': rows[0]['metricName']})
        assert report['evidence'].get('evidence'), 'No source evidence returned'
        preserved = rpc('getPaperSource', {'workspace_id': wid, 'paper_id': committed['paper_id']})
        assert base64.b64decode(preserved['content_base64']) == raw
        report['source_bytes_preserved'] = True
        report['complete'] = True
    except Exception as exc:
        report['complete'] = False
        report['failure'] = str(exc)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()

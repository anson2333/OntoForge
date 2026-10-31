"""Resumable, sequential CV rule pilot using the existing active local model.

Raw previews stay under ignored data/. No credentials or session tokens are saved.
--commit saves the immutable original previews as unreviewed literature records.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
from backend.server.app import app
from backend.database import init_db, close_db
from backend.services.auth_service import create_session
from backend.config.loader import DomainPackLoader
from backend.config.validator import DomainPackValidator

FILES = ['fast_rcnn', 'faster_rcnn', 'yolo']


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', action='store_true')
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--zhipu-interval', type=float, default=65, help='Conservative pilot-only cooldown; does not change saved API settings')
    parser.add_argument('--papers', nargs='+', choices=FILES, default=FILES)
    parser.add_argument('--run-dir', default='data/cv-validation/rule-review')
    parser.add_argument('--output-dir', default='docs/cv-validation/rule-review')
    parser.add_argument('--workspace-id')
    parser.add_argument('--workspace-name', default='CV目标检测：规则与原文核验')
    parser.add_argument('--workspace-root', default='cv-rule-review')
    parser.add_argument('--expect-vendor', help='Fail before making requests if the selected vendor differs')
    args = parser.parse_args()
    run_dir = ROOT / args.run_dir
    summary_path = ROOT / args.output_dir / 'run-summary.json'
    config_path = ROOT / 'backend/configs/domain-pack-cv-detection.yaml'
    config = DomainPackLoader().load(config_path)
    DomainPackValidator.validate_or_raise(config)
    config_hash = hashlib.sha256(config.model_dump_json().encode()).hexdigest()
    profile_store = json.loads((ROOT / 'backend/data/llm-profiles.json').read_text())
    active = [(uid, record) for uid, record in profile_store['users'].items() if record.get('active_id')]
    if len(active) != 1:
        raise RuntimeError('Expected one existing user with an active model profile')
    uid, record = active[0]
    profile = next(p for p in record['profiles'] if p['id'] == record['active_id'])
    if args.expect_vendor and profile.get('vendor') != args.expect_vendor:
        raise RuntimeError('The active saved model does not match the requested vendor')
    profile_fingerprint = hashlib.sha256(json.dumps({key: value for key, value in profile.items() if key != 'connection'}, sort_keys=True).encode()).hexdigest()
    from backend.services import pdf_ingestion_service
    from backend.services.llm_profiles import profile_configuration
    from backend.services.llm.base import provider_from_config
    frozen_model = profile_configuration(uid, profile['id'])
    # Pin the existing profile in this process only so a UI switch cannot mix
    # providers across papers/batches. Credentials never enter saved artifacts.
    pdf_ingestion_service.get_default_provider = lambda: provider_from_config(frozen_model)
    source_hashes = {file: hashlib.sha256((ROOT / file).read_bytes()).hexdigest() for file in [
        'backend/schemas/domain_pack.py', 'backend/services/llm/semantic_extractor.py',
        'backend/services/pdf_ingestion_service.py', 'backend/configs/domain-pack-cv-detection.yaml']}
    if profile.get('vendor') == 'zhipu':
        from backend.services.llm import zhipu_requests
        zhipu_requests.MIN_INTERVAL_SECONDS = max(1, args.zhipu_interval)
    users = json.loads((ROOT / 'backend/data/users.json').read_text())['users']
    user = next(u for u in (users.values() if isinstance(users, dict) else users) if u['user_id'] == uid)
    token = create_session(user)['token']
    init_db(os.environ['NEO4J_URI'], os.environ['NEO4J_USER'], os.environ['NEO4J_PASSWORD'])

    def rpc(method, params):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://local') as client:
                response = await client.post('/jsonrpc', json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params},
                                             headers={'Authorization': 'Bearer ' + token})
                body = response.json()
                if 'error' in body:
                    raise RuntimeError(body['error']['message'])
                return body['result']
        return asyncio.run(send())

    state_path = run_dir / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    if state and state['config_sha256'] != config_hash:
        raise RuntimeError('Rule configuration changed. Preserve the old run and start a new checkpoint explicitly.')
    if state and state.get('profile_fingerprint', profile_fingerprint) != profile_fingerprint:
        raise RuntimeError('Model settings changed. Preserve this run and use a separate checkpoint.')
    if state and state.get('source_sha256', source_hashes) != source_hashes:
        raise RuntimeError('Extraction code changed. Preserve this run and use a separate checkpoint.')
    if not state:
        workspace = rpc('getWorkspace', {'workspace_id': args.workspace_id})['workspace'] if args.workspace_id else rpc('createWorkspace', {'name': args.workspace_name, 'root': args.workspace_root,
            'description': f'Fast R-CNN、Faster R-CNN、YOLO · {profile["name"]} · 优化规则验证。原始模型结果保留为待核对；判别报告见 {args.output_dir}/REPORT.md。'})['workspace']
        state = {'workspace_id': workspace['id'], 'owner_id': uid, 'config_sha256': config_hash,
                 'model': profile['model'], 'provider': profile['provider'], 'vendor': profile.get('vendor'),
                 'profile_name': profile['name'], 'profile_fingerprint': profile_fingerprint, 'source_sha256': source_hashes,
                 'max_output_tokens': profile.get('max_output_tokens'), 'timeout_seconds': profile.get('timeout_seconds'), 'papers': {}}
        save(state_path, state)
    summary = {k: v for k, v in state.items() if k != 'owner_id'}
    summary['pilot_zhipu_interval_seconds'] = args.zhipu_interval
    for stem in args.papers:
        path = ROOT / f'data/cv-validation/historical/{stem}.pdf'
        raw = path.read_bytes()
        entry = state['papers'].setdefault(stem, {'file_sha256': hashlib.sha256(raw).hexdigest()})
        assert entry['file_sha256'] == hashlib.sha256(raw).hexdigest()
        if not entry.get('upload_id'):
            entry.update(rpc('uploadPdf', {'workspace_id': state['workspace_id'], 'file_name': path.name,
                                        'content_base64': base64.b64encode(raw).decode()}))
            save(state_path, state)
        params = {'workspace_id': state['workspace_id'], 'domain_pack_namespace': 'cv_detection', 'upload_id': entry['upload_id']}
        preview_path = run_dir / f'{stem}-preview.json'
        if args.retry_failed and preview_path.exists():
            old = json.loads(preview_path.read_text(encoding='utf-8'))
            if old['diagnostics'].get('failed_batches'):
                history = preview_path.with_name(f'{stem}-partial-{int(time.time())}.json')
                preview_path.rename(history)
        if not preview_path.exists():
            print(f'Extracting {stem} sequentially with {profile["model"]}...', flush=True)
            started = time.monotonic()
            preview = rpc('parsePdfWithDomainPack', params)
            save(preview_path, preview)
            entry['seconds'] = round(time.monotonic() - started, 3)
        else:
            preview = json.loads(preview_path.read_text(encoding='utf-8'))
        entry.update(preview_id=preview['preview_id'], status=preview['status'], diagnostics=preview['diagnostics'],
                     assertion_count=len(preview['assertions']), extraction_method=preview['assertion_extraction_method'])
        save(state_path, state)
        summary['papers'] = state['papers']
        save(summary_path, summary)
        assert preview['assertion_extraction_method'] == 'llm', 'No real model assertions'
        assert not preview['diagnostics']['failed_batches'], 'Model batch failed; inspect saved diagnostics before retrying'
        print(f'{stem}: {len(preview["assertions"])} assertions, {entry.get("seconds")} seconds', flush=True)
        # Export model assertions and evidence locations without copying article full text.
        save(summary_path.parent / f'{stem}-model-results.json', {
            'paper': stem, 'paper_metadata': preview['paper_metadata'], 'source_sha256': entry['file_sha256'],
            'diagnostics': preview['diagnostics'], 'assertions': preview['assertions'],
            'chunk_pages': {chunk['chunk_id']: chunk['bounding_box'].get('page') for chunk in preview['chunks']}})
        if args.commit and not entry.get('commit'):
            entry['commit'] = rpc('commitParsedPdf', {**params, 'preview_id': preview['preview_id']})
            assert entry['commit']['status'] == 'committed'
            save(state_path, state)
    if args.commit:
        summary['coverage'] = rpc('getCoverageAnalysis', {'workspace_id': state['workspace_id'], 'domain_pack_namespace': 'cv_detection'})
    summary['papers'] = state['papers']
    summary['complete'] = True
    save(summary_path, summary)
    close_db()


if __name__ == '__main__':
    main()

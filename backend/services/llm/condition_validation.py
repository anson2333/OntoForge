"""Conservative condition grounding; quote presence is not semantic verification."""
import re


def validate_conditions(context, metric_name, chunks, cited_ids):
    context = dict(context)
    context['reported_experiment_conditions'] = {
        key: context.get(key, 'unknown') for key in
        ('timing_scope', 'backbone', 'detector_backbone', 'proposal_backbone')}
    issues = []
    sources = {c.chunk_id: c.raw_text for c in chunks if c.chunk_id in cited_ids}

    def normalized(value):
        return re.sub(r'\s+', ' ', str(value)).strip().lower()

    def quote_for(key):
        evidence = context.get(key + '_evidence', {})
        if not isinstance(evidence, dict):
            return ''
        quote = normalized(evidence.get('quote', ''))
        source = normalized(sources.get(evidence.get('source_chunk_id'), ''))
        return quote if len(quote) >= 12 and quote in source else ''

    speed = metric_name in {'inference_latency', 'inference_fps'}
    scope = context.get('timing_scope', 'unknown')
    if speed:
        quote = quote_for('timing_scope')
        exclusion = bool(re.search(r'exclud|without|not includ|不包含|不包括', quote))
        inclusion = bool(re.search(r'including all|all steps|end.to.end|complete pipeline|包含所有|完整流程', quote))
        valid = (scope == 'end_to_end' and inclusion and not exclusion
                 or scope == 'detector_only_excludes_proposals' and exclusion and bool(re.search(r'proposal|候选', quote))
                 or scope in {'proposal_only', 'component_only'} and bool(re.search(r'proposal|rpn|component|候选|组件', quote)))
        if not valid:
            context['timing_scope'] = 'unknown'
            issues.append('timing_scope_evidence_missing_or_inconsistent')
    else:
        context['timing_scope'] = 'not_applicable'
    for key, role in [('detector_backbone', r'detector|detection|检测'),
                      ('proposal_backbone', r'proposal|rpn|候选')]:
        value = context.get(key, 'unknown')
        quote = quote_for(key)
        token = re.sub(r'[^a-z0-9]', '', str(value).lower())
        supported = (token and token != 'unknown' and token in re.sub(r'[^a-z0-9]', '', quote)
                     and re.search(role, quote))
        if not supported:
            context[key] = 'unknown'
            if value != 'unknown' or key == 'detector_backbone':
                issues.append(key + '_evidence_missing_or_inconsistent')
    # Legacy consumers read backbone as the detector backbone, never the RPN's.
    context['backbone'] = context['detector_backbone']
    context['condition_validation_issues'] = issues
    context['condition_validation'] = 'needs_review' if issues else 'quote_grounded_not_human_verified'
    return context, speed and context['timing_scope'] in {'proposal_only', 'component_only'}

"""Translate observed native search evidence, never model-authored sources."""
from datetime import datetime
import ipaddress
from urllib.parse import urlsplit
from .config import DeskError
from .models import ResearchResult, validate_analysis
from .sources import record


def public_url(value):
    from .models import safe_url
    value=safe_url(value)
    host=urlsplit(value).hostname.lower().rstrip('.')
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')) or '.' not in host:
        raise DeskError('Private source address is unavailable.')
    try:
        if not ipaddress.ip_address(host).is_global:raise DeskError('Private source address is unavailable.')
    except ValueError:pass
    return value


def registry(envelope):
    """Keep every URL-bearing text result; attempted opens are diagnostics only."""
    rows=[]
    for event in envelope.get('observed',[]):
        if event.get('type')!='webSearch':continue
        for hit in event.get('results') or []:
            if not isinstance(hit,dict) or hit.get('type')!='text_result':continue
            try:url=public_url(hit.get('url',''))
            except (DeskError,ValueError,AttributeError):continue
            text=hit.get('snippet')
            if not isinstance(text,str):text=''
            published=None
            # Only explicitly named provider publication metadata is accepted.
            for field in ('published_at','datePublished','publication_date'):
                raw=hit.get(field)
                if not isinstance(raw,str):continue
                try:
                    parsed=datetime.fromisoformat(raw.replace('Z','+00:00'))
                    if parsed.tzinfo:published=parsed.isoformat();break
                except ValueError:pass
            row=record(hit.get('title') or url,url,text,'Codex web',
                {'endpoint':'native web search','query':event.get('query',''),
                 'action':event.get('action',{}).get('type','search'),
                 'event_id':event.get('id'),'source_ref':hit.get('ref_id'),
                 'verification':'Tool-observed excerpt; full page and publication date not inferred'},
                published,access='tool-observed excerpt' if text else 'metadata only')
            row.update(source_ref=hit.get('ref_id'),date_kind='publication' if published else 'unknown')
            rows.append(row)
    return rows


def assessments(envelope,rows,messages):
    """Validate each output independently so one bad claim cannot erase sources."""
    try:result=ResearchResult.model_validate(envelope.get('result',{})).model_dump()
    except ValueError:return {},'Research output could not be validated; collected evidence is retained.'
    refs={}
    for row in rows:
        if row.get('source_ref'):refs.setdefault(row['source_ref'],row)
    validated={};errors=0
    for finding in result['findings']:
        ref=finding['source_id'];row=refs.get(ref)
        quote=finding.pop('supporting_quote')
        if not row or ref in validated or not quote.strip() or quote not in row['text']:
            errors+=1;continue
        try:
            checked=validate_analysis({'findings':[finding]},[{**row,'id':ref}],messages)['findings'][0]
        except DeskError:errors+=1;continue
        checked['supporting_quote']=quote
        validated[ref]=checked
    return validated,(f'{errors} assessments need evidence review.' if errors else '')


def remap(assessment,source_id):
    import copy
    result=copy.deepcopy(assessment);result['source_id']=source_id
    for message in result['messages']:
        for evidence in message['evidence']:evidence['source_id']=source_id
    return result

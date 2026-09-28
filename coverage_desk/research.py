"""Translate observed native search evidence, never model-authored sources."""
from datetime import datetime,timedelta
import ipaddress
from urllib.parse import urlsplit
from .config import DeskError
from .models import ResearchResult, validate_analysis
from .sources import record
import re


def search_tasks(monitor,plan,scope):
    """Cover every selected category; topic phrases are not Boolean requirements."""
    from .discovery import PLATFORMS
    def relaxed(query):
        query=re.sub(r'(?:site|after|before):\S+','',query,flags=re.I)
        return ' '.join(query.replace('"',' ').replace('\u201c',' ').replace('\u201d',' ').split())[:450]
    name=monitor['name']
    focus=next((q['query'] for q in plan['queries'] if q['purpose']=='focus'),None)
    broad=next((q['query'] for q in plan['queries'] if q['purpose']=='broad'),name)
    topic=relaxed((focus or name+' '+monitor['campaign']) if monitor.get('campaign') else broad)
    tasks=[]
    for target in monitor['sources']:
        query=topic
        if target in PLATFORMS:
            domains=PLATFORMS[target][1]
            query+=' '+('('+ ' OR '.join('site:'+domain for domain in domains)+')' if len(domains)>1 else 'site:'+domains[0])
        elif target=='news':query+=' latest news'
        tasks.append({'query':query,'target':target,'purpose':'focus' if monitor.get('campaign') else 'broad'})
    if monitor.get('campaign'):
        target='news' if 'news' in monitor['sources'] else monitor['sources'][0]
        # A planner can accidentally repeat the campaign in its "broad" query.
        # Keep one guaranteed subject-wide route independent of focus/messages.
        broad_query=relaxed(name+' news')
        if target in PLATFORMS:broad_query+=' site:'+PLATFORMS[target][1][0]
        tasks.append({'query':broad_query,'target':target,'purpose':'broad'})
        # A lexical alternative prevents a named slogan from being the only route.
        variants=[q for q in plan['queries'] if q['purpose']=='contrary']
        if variants:
            target='web' if 'web' in monitor['sources'] else monitor['sources'][0]
            query=relaxed(variants[0]['query'])
            if target in PLATFORMS:query+=' site:'+PLATFORMS[target][1][0]
            tasks.append({'query':query,'target':target,'purpose':'contrary'})
    # Search engines may ignore date operators. Add a calendar-word variant,
    # while retaining all ordinary queries; only verified dates gate relevance.
    window=scope['window']
    if window['start']:
        end=datetime.fromisoformat(window['end'])-timedelta(microseconds=1)
        start=datetime.fromisoformat(window['start'])
        if (end-start).days<=62:
            target='news' if 'news' in monitor['sources'] else 'web' if 'web' in monitor['sources'] else monitor['sources'][0]
            query=topic+' '+end.strftime('%B %Y')
            if target in PLATFORMS:query+=' site:'+PLATFORMS[target][1][0]
            tasks.insert(0,{'query':query,'target':target,'purpose':'focus' if monitor.get('campaign') else 'broad'})
    for task in tasks:
        window=scope['window']
        if window['start']:task['query']+=' after:'+window['start'][:10]
        end=datetime.fromisoformat(window['end'])
        if end.time().isoformat()!='00:00:00':end+=timedelta(days=1)
        task['query']+=' before:'+end.date().isoformat()
    return tasks


def event_queries(event):
    action=event.get('action') or {}
    if action.get('type') not in (None,'search'):return []
    return action.get('queries') or [action.get('query') or event.get('query') or '']


def search_statuses(tasks,events):
    from .discovery import platform
    normalize=lambda q:' '.join(q.lower().split())
    statuses=[]
    for task in tasks:
        matches=[e for e in events if any(normalize(q)==normalize(task['query']) for q in event_queries(e))]
        count=sum(len(e.get('results') or []) for e in matches)
        statuses.append({**task,'source':task['target'],'requested':bool(matches),'results':count,
            'platform_matches':sum(platform(hit.get('url',''))==task['target'] for e in matches for hit in e.get('results') or [] if isinstance(hit,dict)),
            'status':('Results' if count else 'No indexed matches') if matches else 'Not searched'})
    return statuses


def needs_publication_check(row,monitor):
    assessment=row.get('analysis') or {}
    return (assessment.get('relevance')=='relevant'
        and (not monitor.get('campaign') or assessment.get('campaign_relevance')=='relevant')
        and row.get('date_kind')!='publication'
        and not row.get('provenance',{}).get('publication_check')
        and row['provider']!='Manual contribution')


def evidence_priority(row):
    """Interleave query rankings so one prolific query cannot monopolize assessment."""
    return min((o.get('provenance',{}).get('result_rank',0),o.get('provenance',{}).get('task_order',0))
        for o in row.get('observations',[row]))


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
        for rank,hit in enumerate(event.get('results') or []):
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
                 'result_rank':rank,
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

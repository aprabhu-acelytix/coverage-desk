"""Translate observed native search evidence, never model-authored sources."""
from datetime import datetime,timedelta
import ipaddress
from urllib.parse import urlsplit
from .config import DeskError
from .models import ResearchResult, validate_analysis
from .sources import record
import re


def social_names(monitor):
    """Owner-supplied public identity terms, never inferred account ownership."""
    handles=re.findall(r'(?<![\w.])@[A-Za-z0-9_][A-Za-z0-9_.]{1,49}',monitor.get('domains',''))
    values=[monitor['name']]+monitor.get('aliases',[])[:4]+handles[:3]
    return list(dict.fromkeys(' '.join(re.sub(r'(?:site|after|before):\S+','',v,flags=re.I)
        .replace('"',' ').replace('\u201c',' ').replace('\u201d',' ').split())[:120] for v in values if v.strip()))


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
            # Social posts often use a handle or short name without the campaign
            # wording. Message criteria and private notes never enter queries.
            names=social_names(monitor)
            subject='('+' OR '.join(n for n in names if n)+')'
            # Keep campaign focus separate from the later broad route. OR-ing
            # the entire focus with a short brand collapses to brand-only search.
            focus_terms=topic
            for term in sorted(names,key=len,reverse=True):
                focus_terms=re.sub(r'(?<!\w)'+re.escape(term)+r'(?!\w)',' ',focus_terms,flags=re.I)
            if not monitor.get('campaign'):focus_terms=re.sub(r'\b(?:news|latest|coverage)\b',' ',focus_terms,flags=re.I)
            query=subject+(' '+' '.join(focus_terms.split()) if focus_terms.strip() else '')
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
            query=(next(t['query'] for t in tasks if t['target']==target) if target in PLATFORMS else topic)+' '+end.strftime('%B %Y')
            tasks.insert(0,{'query':query,'target':target,'purpose':'focus' if monitor.get('campaign') else 'broad'})
    for task in tasks:
        window=scope['window']
        if window['start']:task['query']+=' after:'+window['start'][:10]
        end=datetime.fromisoformat(window['end'])
        if end.time().isoformat()!='00:00:00':end+=timedelta(days=1)
        task['query']+=' before:'+end.date().isoformat()
    return tasks


def initial_tasks(tasks,limit):
    """Cover selected sites before spending spare capacity on adaptive work."""
    from .discovery import PLATFORMS
    if not any(t['target'] in PLATFORMS for t in tasks):return tasks[:limit]
    seen=set();selected=[]
    for task in tasks:
        if task['target'] not in seen:
            selected.append(task);seen.add(task['target'])
    # Preserve a neutral reporting route when a campaign is present. Broad
    # social discovery must not crowd established news coverage out of the run.
    broad=next((t for t in tasks if t['purpose']=='broad' and t['target'] not in PLATFORMS and t not in selected),None)
    if broad and len(selected)<limit-2:selected.append(broad)
    return selected[:limit]


def followup_tasks(monitor,scope,tasks,events,limit):
    """One bounded second pass, selected from observed evidence, never prose."""
    from .discovery import PLATFORMS,platform
    from .models import canonical_url
    if limit<=0:return []
    statuses=search_statuses(tasks,events)
    reporting=[]
    # Date operators/calendar wording can suppress launch-week coverage. Reserve
    # the first spare route for reporting before optional social follow-ups.
    for task in tasks:
        if task['target'] not in ('news','web') or task.get('purpose')!='focus':continue
        if not any(s['query']==task['query'] and s['requested'] for s in statuses):continue
        query=' '.join(re.sub(r'(?:after|before):\S+','',task['query'],flags=re.I).split())
        end=datetime.fromisoformat(scope['window']['end'])-timedelta(microseconds=1)
        query=re.sub(r'\s+'+re.escape(end.strftime('%B %Y'))+r'$','',query)
        if query!=task['query'] and query not in [t['query'] for t in reporting]:
            reporting.append({'query':query,'target':task['target'],'purpose':'focus','date_strategy':'Verify publication after discovery'})
        if len(reporting)>=1:break
    if len(reporting)>=limit:return reporting[:limit]
    targets=[t for t in monitor['sources'] if t in PLATFORMS and
             any(s['target']==t and s['requested'] for s in statuses)]
    # Give sparse sites another route first; stable ties preserve user selection.
    targets.sort(key=lambda t:sum(s['platform_matches'] for s in statuses if s['target']==t))
    hits={t:[] for t in targets};seen=set()
    for row in registry({'observed':[{**e,'type':'webSearch'} for e in events]}):
        target=platform(row['url']);key=canonical_url(row['url'])
        if target in hits and key not in seen:
            hits[target].append(row);seen.add(key)
    end=datetime.fromisoformat(scope['window']['end'])-timedelta(microseconds=1)
    start=datetime.fromisoformat(scope['window']['start']) if scope['window']['start'] else None
    month=(' '+end.strftime('%B %Y')) if start and (end-start).days<=62 else ''
    def clean(value):
        return ' '.join(re.sub(r'(?:site|after|before):\S+','',value,flags=re.I).replace('"',' ').split())[:120]
    names=social_names(monitor)
    subject='('+' OR '.join(dict.fromkeys(n for n in names if n))+')'
    queues={}
    for target in targets:
        domain=PLATFORMS[target][1][0]
        broad={'query':subject+' site:'+domain+month,'target':target,'purpose':'broad','date_strategy':'Verify publication after discovery'}
        candidates=[]
        original=next(t['query'] for t in tasks if t['target']==target)
        relaxed=' '.join(re.sub(r'(?:after|before):\S+','',original,flags=re.I).split())
        focused={'query':relaxed,'target':target,'purpose':'focus','date_strategy':'Verify publication after discovery'}
        # URL-targeted search can expose additional indexed text without granting
        # a scraper, browser login, or treating an attempted open as evidence.
        def is_post(row):
            path=urlsplit(row['url']).path.lower()
            return any(part in path for part in ('/status/','/posts/','/pulse/','/feed/update/','/p/','/reel/','/video/','/videos/','/comments/','/shorts/','/watch','/permalink')) or urlsplit(row['url']).hostname=='youtu.be'
        focus_words=[w.lower() for w in re.findall(r'\w{4,}',monitor.get('campaign','')) if w.lower() not in ('agent','launch','campaign','product','everything','possible')]
        promising=next((r for r in hits[target] if is_post(r) and any(n.lower().lstrip('@') in (r['title']+' '+r['text']).lower()
                          for n in names if len(n.lstrip('@'))>=3) and (not focus_words or any(w in (r['title']+' '+r['text']).lower() for w in focus_words))),None)
        if promising:
            candidates.append({'query':promising['url']+' '+clean(monitor['name']),
                'target':target,'purpose':'evidence','source_url':promising['url'],'date_strategy':'Verify publication after discovery'})
        if monitor.get('campaign'):candidates.append(focused)
        candidates.append(broad)
        if promising:
            tags=list(dict.fromkeys(re.findall(r'(?<!\w)#[\w]{2,40}',promising['title']+' '+promising['text'])))[:2]
            if tags:candidates.append({'query':clean(monitor['name'])+' '+' '.join(tags)+' site:'+domain+month,
                'target':target,'purpose':'related','date_strategy':'Verify publication after discovery'})
        queues[target]=candidates
    result=list(reporting);used={t['query'] for t in tasks+reporting}
    for round_number in range(4):
        for target in targets:
            queue=queues[target]
            if round_number<len(queue) and queue[round_number]['query'] not in used:
                task=queue[round_number];result.append(task);used.add(task['query'])
                if len(result)>=limit:return result
    return result


def platform_summary(monitor,rows,statuses,followups):
    from .discovery import PLATFORMS,platform
    from .models import canonical_url
    result=[]
    for target in monitor['sources']:
        if target not in PLATFORMS:continue
        groups={}
        for row in rows:
            if platform(row['url'])==target:groups.setdefault(canonical_url(row['url']),[]).append(row)
        attempted=any(s.get('target')==target and s.get('requested') for s in statuses)
        result.append({'platform':target,'found':len(groups),
            'assessed':sum(any(bool(r.get('analysis')) and not r.get('analysis_error') for r in group) for group in groups.values()),
            'excerpt_only':sum(any(bool(r.get('text')) for r in group) for group in groups.values()),
            'metadata_only':sum(not any(bool(r.get('text')) for r in group) for group in groups.values()),
            'followup':any(t['target']==target for t in followups),
            'status':'Public results found' if groups else 'No accessible results found' if attempted else 'Not searched'})
    return result


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
            published=None;precision='timestamp'
            # Only explicitly named provider publication metadata is accepted.
            for field in ('published_at','datePublished','publication_date'):
                raw=hit.get(field)
                if not isinstance(raw,str):continue
                try:
                    parsed=datetime.fromisoformat(raw.replace('Z','+00:00'))
                    if parsed.tzinfo:published=parsed.isoformat();break
                    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',raw):published=raw;precision='day';break
                except ValueError:pass
            row=record(hit.get('title') or url,url,text,'Codex web',
                {'endpoint':'native web search','query':event.get('query',''),
                 'action':event.get('action',{}).get('type','search'),
                 'event_id':event.get('id'),'source_ref':hit.get('ref_id'),
                 'result_rank':rank,
                 'verification':'Tool-observed excerpt; full page and publication date not inferred'},
                published,access='tool-observed excerpt' if text else 'metadata only')
            row.update(source_ref=hit.get('ref_id'),date_kind='publication' if published else 'unknown',date_precision=precision)
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

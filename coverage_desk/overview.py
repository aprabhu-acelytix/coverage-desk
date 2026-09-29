"""One deterministic coverage projection: articles, outlets, chart and snapshots."""
from collections import Counter
from datetime import datetime,timezone
from urllib.parse import urlsplit
import time
from .scope import scope_key,snapshot,identity,version
from .models import digest

CONTENT_TYPES={'reporting':'Reporting','client_owned':'Client-owned announcements',
    'press_release':'Press-release distribution','sponsored':'Sponsored content','social':'Social', 'unknown':'Unknown type'}
STATES={'confirmed':'Confirmed period','date_unconfirmed':'Relevant, date unconfirmed',
    'unassessed':'Unassessed','uncertain':'Relevance needs review','excluded':'Not relevant', 'outside':'Outside period'}

def host(url):
    return (urlsplit(url).hostname or '').lower().rstrip('.')

def source_text(row):
    return row.get('text','')+'\n'+row.get('full_title',row.get('title',''))

def publication_dates(observations):
    dates=set()
    for row in observations:
        if row.get('date_kind')!='publication' or not row.get('published'):continue
        try:
            value=datetime.fromisoformat(row['published'].replace('Z','+00:00'))
            if value.tzinfo:dates.add(value.astimezone(timezone.utc).isoformat())
        except (ValueError,TypeError):pass
    return dates

def publication_days(observations):
    from datetime import date
    days=set()
    for row in observations:
        if row.get('date_kind')=='publication' and row.get('date_precision')=='day':
            try:days.add(date.fromisoformat(row['published']).isoformat())
            except (ValueError,TypeError,KeyError):pass
    return days

def article_state(row,monitor,window):
    assessment=row.get('analysis')
    row['assessment_status']='Assessed' if assessment else 'Unassessed'
    row['relevance']='unassessed' if not assessment else assessment['relevance']
    if assessment and monitor.get('campaign'):
        if assessment.get('campaign_relevance') in ('not_relevant','not_applicable'):row['relevance']='not_relevant'
        elif assessment.get('campaign_relevance')=='uncertain' and row['relevance']=='relevant':row['relevance']='uncertain'
    correction=row.get('coverage_correction',{})
    if correction.get('relevance'):
        row['relevance']=correction['relevance'];row['assessment_status']='Owner reviewed'
    row['date_status']='unconfirmed'
    if row.get('date_kind') in ('publication','owner_confirmed') and row.get('published'):
        try:
            if row.get('date_precision')=='day':
                from datetime import date
                published=date.fromisoformat(row['published'])
                end=datetime.fromisoformat(window['end'])
                before_end=published<end.date() or (published==end.date() and bool(end.hour or end.minute or end.second or end.microsecond))
                row['date_status']='confirmed' if before_end and (not window['start'] or published>=datetime.fromisoformat(window['start']).date()) else 'outside'
            else:
                date=datetime.fromisoformat(row['published'].replace('Z','+00:00'))
                if date.tzinfo:
                    row['date_status']='confirmed' if date<datetime.fromisoformat(window['end']) and (not window['start'] or date>=datetime.fromisoformat(window['start'])) else 'outside'
        except (ValueError,TypeError):pass
    if row['relevance']=='unassessed':return 'unassessed'
    if row['relevance']=='not_relevant':return 'excluded'
    if row['relevance']=='uncertain':return 'uncertain'
    if row['date_status']=='outside':return 'outside'
    return 'confirmed' if row['date_status']=='confirmed' else 'date_unconfirmed'

def project_articles(store,actor,monitor,at=None,history=False):
    """Retained compatible observations across runs; no AI, network or pagination."""
    from .discovery import platform
    monitor=store.get(actor,monitor['id'],'monitor')
    at=time.time() if at is None else at
    key=scope_key(monitor);scope=snapshot(monitor,at)
    runs=[r for r in store.list(actor,'run') if r['monitor_id']==monitor['id'] and r.get('scope',{}).get('key')==key and r['created']<=at]
    run=runs[0] if runs else None
    raw=[r for r in store.list(actor,'finding') if r.get('monitor_id')==monitor['id'] and r['created']<=at]
    compatible=lambda r:r.get('scope_key')==key and r.get('monitor_revision')==monitor['revision']
    raw=[r for r in raw if not compatible(r)] if history else [r for r in raw if compatible(r)]
    reviews=[r for r in store.list(actor,'coverage_review') if r.get('monitor_id')==monitor['id'] and r.get('scope_key')==key and r['created']<=at]
    aliases=[a for a in store.list(actor,'outlet_alias') if a['created']<=at]
    alias_groups={}
    for alias in aliases:alias_groups.setdefault(alias['outlet_key'],alias)
    grouped={}
    for row in raw:grouped.setdefault(identity(actor.workspace,row['owner'],row.get('canonical') or row['url']),[]).append(row)
    result=[]
    for article_id,observations in grouped.items():
        observations.sort(key=lambda r:(r['retrieved'],r['created'],r['id']),reverse=True)
        # An unassessed retry does not erase retained assessed evidence. A newer
        # assessment (including a negative one) takes precedence over older ones.
        assessed=[r for r in observations if r.get('analysis_scope_key')==key and r.get('analysis')]
        row=dict(assessed[0] if assessed else observations[0]);row['article_id']=article_id
        if not assessed:row.pop('analysis',None)
        row['observations']=[{k:r.get(k) for k in ('id','url','provider','retrieved','run_id','version_id','provenance','expires')} for r in observations]
        identities={article_id,*[r.get('article_id') for r in observations]}
        review=next((r for r in reviews if r['article_id'] in identities),None)
        if review:
            row['coverage_correction']=review['changes'];row['correction_audit']=review
            if 'published' in review['changes']:
                row.update(published=review['changes']['published'],date_kind='owner_confirmed' if review['changes']['published'] else 'unknown',date_precision=review['changes'].get('date_precision','timestamp'))
        elif not row.get('published') or row.get('date_kind')!='publication':
            dates=publication_dates(observations)
            if len(dates)==1:row.update(published=next(iter(dates)),date_kind='publication')
        dates=publication_dates(observations)
        if len(dates)>1 and not (review and 'published' in review['changes']):row.update(published=None,date_kind='conflicting')
        days=publication_days(observations)
        if days and not (review and 'published' in review['changes']):
            if len(days)>1 or dates and any(d[:10] not in days for d in dates):row.update(published=None,date_kind='conflicting')
            elif not dates:row.update(published=next(iter(days)),date_kind='publication',date_precision='day')
        profile=(row.get('provenance',{}).get('publication_check') or {}).get('source_profile',{})
        classification=row.get('coverage') or (row.get('analysis') or {}).get('coverage') or {}
        row['content_type']=classification.get('content_type','unknown')
        row['classification_evidence']={'method':'AI assessment' if classification else 'Unknown',
            'quote':classification.get('evidence',''),'source_id':row['id'],'url':row['url']}
        domain=host(row['url']);outlet_name=profile.get('publisher') or domain
        name=classification.get('outlet_name')
        if name and name in source_text(row):outlet_name=name
        if platform(row['url']):
            row['content_type']='social';row['classification_evidence']={'method':'Exact public platform hostname','quote':domain,'url':row['url']}
        official=[host(x if '://' in x else 'https://'+x) for x in monitor.get('domains','').replace(',',' ').split() if '.' in x and not x.startswith('@')]
        if domain in official:
            row['content_type']='client_owned';row['classification_evidence']={'method':'Owner-configured official domain','quote':domain,'url':row['url']}
        row['redistribution']=classification.get('redistribution') or ''
        if review:
            row['content_type']=review['changes'].get('content_type',row['content_type'])
            if 'content_type' in review['changes']:
                evidence=review.get('field_evidence',{}).get('content_type',{})
                row['classification_evidence']={'method':'Owner correction','quote':evidence.get('reason',review['reason']),
                    'source_id':evidence.get('source_id',review['source_id']),'url':row['url'],'author':review['owner'],'at':evidence.get('at',review['created'])}
            if 'redistribution' in review['changes']:row['redistribution']=review['changes']['redistribution']
        alias=next((a for a in aliases if a['domain']==domain),None)
        outlet_key=alias['outlet_key'] if alias else domain
        group_alias=alias_groups.get(outlet_key)
        row.update(outlet_id=digest(outlet_key),outlet_key=outlet_key,outlet_name=group_alias['name'] if group_alias else outlet_name,
            outlet_evidence={'method':'Owner-reviewed exact-host alias','reason':group_alias['reason'],'domain':domain} if group_alias else
                {'method':'Publisher metadata' if profile.get('publisher') else 'Observed title' if name and name in source_text(row) else 'Exact-host fallback','domain':domain})
        row['coverage_state']=article_state(row,monitor,scope['window'])
        if history:row['coverage_state']='uncertain'
        row['eligibility']={'confirmed':'relevant','outside':'outside','excluded':'excluded'}.get(row['coverage_state'],'review')
        row['match_reason']=STATES[row['coverage_state']]
        # All evidence needed for a projection must still be retained at share time.
        row['projection_expires']=min([r['expires'] for r in observations]+([review['expires']] if review else [])+([alias['expires']] if alias else [])+([group_alias['expires']] if group_alias else []))
        result.append(row)
    result.sort(key=lambda r:(r.get('published') or '',r['retrieved'],r['article_id']),reverse=True)
    from .outlets import rank_articles
    rank_articles(result,store,actor,at)
    return {'rows':result,'run':run,'scope':scope,'at':at}

def coverage_overview(store,actor,monitor,preferences=None,at=None):
    p=preferences or {};at=at if at is not None else p.get('snapshot',time.time())
    projected=project_articles(store,actor,monitor,at)
    category=p.get('content_type','reporting')
    if category not in (*CONTENT_TYPES,'all'):category='reporting'
    rows=projected['rows'];filtered=[r for r in rows if category=='all' or r['content_type']==category]
    confirmed=[r for r in filtered if r['coverage_state']=='confirmed']
    outlets={}
    for row in confirmed:
        entry=outlets.setdefault(row['outlet_id'],{'id':row['outlet_id'],'key':row['outlet_key'],'name':row['outlet_name'],'articles':[],'count':0})
        entry['articles'].append(row);entry['count']+=1
    ordered=sorted(outlets.values(),key=lambda r:(-r['count'],r['name'].casefold(),r['key']))
    run=projected['run'];states=dict(Counter(r['coverage_state'] for r in rows))
    pending=sum(states.get(s,0) for s in ('unassessed','date_unconfirmed','uncertain'))
    partial=not run or bool(pending) or bool(run.get('limited')) or run.get('outcome') in ('Researching','Unavailable','Partial results','Interrupted','Cancelled') or bool(run.get('error')) or any(not s.get('requested',True) for s in run.get('statuses',[]))
    caveats=['Coverage found in retained sources; not a complete census of online coverage.',
        'Counts are unique article appearances per outlet. Syndicated copies at different outlets are not independent stories.']
    if partial:caveats.append('Partial collection: unassessed, unverified or unfinished evidence is excluded from confirmed totals.')
    return {**projected,'category':category,'articles':confirmed,'outlets':ordered,'article_count':len(confirmed),'outlet_count':len(ordered),
        'states':states,'category_counts':dict(Counter(r['content_type'] for r in rows if r['coverage_state']=='confirmed')),
        'partial':partial,'caveats':caveats,'freshness':run.get('checked') if run else None}

def chart_block(overview):
    outlets=overview['outlets']
    if not outlets:return None
    points=[{'label':f'{i+1} {o["name"]}'[:20],'value':o['count']} for i,o in enumerate(outlets[:8])]
    if len(outlets)>8:points.append({'label':'Other outlets','value':sum(o['count'] for o in outlets[8:])})
    return {'type':'data_visualization','title':'Articles by outlet','chart':{'type':'bar',
        'series':[{'name':'Unique articles','data':points}],
        'axis_config':{'categories':[p['label'] for p in points],'x_label':'Outlet','y_label':'Unique articles'}}}

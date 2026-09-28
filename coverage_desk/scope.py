"""Immutable research scope, article identity and evidence eligibility."""
from datetime import datetime, timedelta, timezone
import json
import time
from .models import digest, canonical_url

CRITERIA = ('name','aliases','domains','notes','campaign','messages','sources','language','country','freshness','interpretation')


def scope_key(monitor):
    return digest(json.dumps({k:monitor.get(k, [] if k in ('aliases','messages','sources') else '') for k in CRITERIA},sort_keys=True))


def snapshot(monitor, now=None):
    now=time.time() if now is None else now
    value=monitor.get('freshness','pw')
    end=datetime.fromtimestamp(now,timezone.utc)
    start=None
    if value in ('pd','pw','pm','py'):
        start=end-timedelta(days={'pd':1,'pw':7,'pm':31,'py':365}[value])
    elif 'to' in value:
        left,right=value.split('to')
        start=datetime.fromisoformat(left).replace(tzinfo=timezone.utc)
        end=datetime.fromisoformat(right).replace(tzinfo=timezone.utc)+timedelta(days=1)
    window={'start':start.isoformat() if start else None,'end':end.isoformat(),'timezone':'UTC'}
    key=scope_key(monitor)
    return {'key':key,'id':digest(json.dumps({'key':key,'window':window},sort_keys=True)),
            'criteria':{k:monitor.get(k) for k in CRITERIA},'window':window,'at':now}


def identity(workspace,owner,url):
    return digest(json.dumps([workspace,owner,canonical_url(url)]))


def version(row):
    return digest(json.dumps({k:row.get(k) for k in ('title','text','published','date_kind','provider','access')},sort_keys=True))


def eligibility(row,monitor,run_scope):
    a=row.get('analysis')
    if row.get('analysis_scope_key')!=scope_key(monitor) or not a:
        return 'review','Not assessed for this scope'
    published=row.get('published')
    if not published or row.get('date_kind')!='publication':
        return 'review','Publication date needs verification'
    try:
        stamp=datetime.fromisoformat(published.replace('Z','+00:00'))
        if stamp.tzinfo is None:return 'review','Publication timezone is unknown'
        window=run_scope['window']
        if stamp>=datetime.fromisoformat(window['end']) or (window['start'] and stamp<datetime.fromisoformat(window['start'])):
            return 'outside','Outside the requested dates'
    except (ValueError,TypeError):return 'review','Publication date needs verification'
    if a['relevance']=='uncertain':return 'review','Client relevance needs review'
    if a['relevance']!='relevant':return 'excluded','Different subject'
    if monitor.get('campaign'):
        if a['campaign_relevance']=='uncertain':return 'review','Campaign relevance needs review'
        if a['campaign_relevance']!='relevant':return 'excluded','Outside the campaign focus'
    return 'relevant',a['explanation']

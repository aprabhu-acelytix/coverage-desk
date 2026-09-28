"""Shared discovery labels, hostname classification and stable result selection."""
from urllib.parse import urlsplit
import time

PLATFORMS = {
    'instagram': ('Instagram', ('instagram.com',)),
    'x': ('X', ('x.com', 'twitter.com')),
    'linkedin': ('LinkedIn', ('linkedin.com',)),
    'facebook': ('Facebook', ('facebook.com', 'fb.com')),
    'tiktok': ('TikTok', ('tiktok.com',)),
    'reddit': ('Reddit', ('reddit.com', 'redd.it')),
    'youtube': ('YouTube', ('youtube.com', 'youtu.be')),
}
SOURCE_CHOICES = [('News', 'news'), ('Web', 'web')] + [(v[0], k) for k, v in PLATFORMS.items()]
DEFAULT_SOURCES = ['news', 'web', 'instagram', 'x', 'linkedin']
FILTER_CHOICES = [('All sources', 'all'), ('News search', 'news'), ('Other web pages', 'web'), ('All social sites', 'social')] + [(v[0], k) for k, v in PLATFORMS.items()] + [('Manual contributions', 'manual')]


def platform(url):
    host = (urlsplit(url).hostname or '').lower().rstrip('.')
    return next((key for key, (_, domains) in PLATFORMS.items()
                 if any(host == domain or host.endswith('.' + domain) for domain in domains)), None)


def source_label(key):
    return {value:label for label,value in SOURCE_CHOICES}.get(key, key.capitalize())


def matches_source(row, selected):
    social = platform(row['url'])
    if selected == 'all': return True
    if selected == 'social': return bool(social)
    if selected in PLATFORMS: return social == selected
    if selected == 'manual': return row['provider'] == 'Manual contribution'
    if selected == 'news': return row['provider'] == 'Brave news'
    if selected == 'web': return row['provider'] in ('Brave web','Codex web') and not social
    return False


def finding_selection(store, actor, preferences):
    from .scope import scope_key,snapshot,identity,eligibility,version
    p=preferences
    monitors=store.list(actor,'monitor')
    monitor=next((m for m in monitors if m['id']==p.get('monitor')),None)
    if not monitor:return {'rows':[],'visible':[],'page':0,'new':0,'total':0,'counts':{'relevant':0,'review':0,'all':0},'run':None}
    key=scope_key(monitor)
    runs=[r for r in store.list(actor,'run') if r['monitor_id']==monitor['id'] and r.get('scope',{}).get('key')==key]
    boundary=p.get('snapshot',time.time())
    stable=[r for r in runs if r['created']<=boundary]
    run=stable[0] if stable else runs[0] if runs else None
    history=p.get('history','current')=='previous'
    raw=[r for r in store.list(actor,'finding') if r.get('monitor_id')==monitor['id']]
    current=lambda r:r.get('scope_key')==key and r.get('monitor_revision')==monitor['revision']
    if history:raw=[r for r in raw if not current(r)]
    else:raw=[r for r in raw if current(r) and (not run or r.get('run_id')==run['id'] or r['provider']=='Manual contribution')]
    run_scope=run['scope'] if run else snapshot(monitor)
    # Identity projection precedes relevance filters, totals and pagination.
    grouped={}
    for r in raw:grouped.setdefault(r.get('article_id') or identity(actor.workspace,actor.user,r['url']),[]).append(r)
    projected=[]
    for article_id,observations in grouped.items():
        observations.sort(key=lambda r:(r['retrieved'],r['created'],r['id']),reverse=True)
        row=dict(observations[0]);row['article_id']=article_id
        same_version=[r for r in observations if version(r)==version(row) and r.get('analysis_scope_key')==key and r.get('analysis')]
        if same_version:row.update(analysis=same_version[0]['analysis'],analysis_scope_key=key)
        row['observations']=[{'id':r['id'],'url':r['url'],'provider':r['provider'],'retrieved':r['retrieved'],
            'run_id':r.get('run_id'),'version_id':r.get('version_id'),'provenance':r.get('provenance',{})} for r in observations]
        row['eligibility'],row['match_reason']=eligibility(row,monitor,run_scope)
        if history:row.update(eligibility='review',match_reason='Previous scope; not a current assessment')
        projected.append(row)
    source_rows=[r for r in projected if matches_source(r,p.get('source_filter','all'))]
    stable_rows=[r for r in source_rows if r['created']<=boundary]
    counts={'relevant':sum(r['eligibility']=='relevant' for r in stable_rows),
            'review':sum(r['eligibility']=='review' for r in stable_rows),'all':len(stable_rows)}
    filt=p.get('filter','relevant')
    if filt in ('uncertain','unassessed'):filt='review'
    if filt=='not_relevant':filtered=[r for r in source_rows if r['eligibility'] in ('excluded','outside')]
    else:filtered=[r for r in source_rows if filt=='all' or r['eligibility']==filt]
    # A research job advances the results snapshot when it finishes; browsing never does.
    rows=[r for r in filtered if r['created']<=boundary]
    rows.sort(key=lambda r:(r.get('published') or '',r['retrieved'],r['article_id']),reverse=True)
    page=min(max(0,p.get('page',0)),max(0,(len(rows)-1)//5))
    return {'rows':rows,'visible':rows[page*5:page*5+5],'page':page,
        'new':sum(r['created']>boundary for r in filtered),'total':len(projected),'counts':counts,'run':run}

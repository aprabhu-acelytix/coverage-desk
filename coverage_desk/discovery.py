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
    # Corporate newsrooms are publications, not posts on the owned platform.
    if host=='about.fb.com':return None
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
    if selected == 'news': return row['provider'] == 'Brave news' or (not social and any('news' in o.get('provenance',{}).get('targets',[]) for o in row.get('observations',[row])))
    if selected == 'web': return row['provider'] in ('Brave web','Codex web') and not social
    return False


def finding_selection(store, actor, preferences):
    from .scope import scope_key,snapshot,identity,eligibility,version
    p=preferences
    monitors=store.list(actor,'monitor')
    monitor=next((m for m in monitors if m['id']==p.get('monitor')),None)
    if not monitor:return {'rows':[],'visible':[],'page':0,'new':0,'total':0,'counts':{'relevant':0,'review':0,'all':0},'run':None}
    from .overview import project_articles
    boundary=p.get('snapshot',time.time())
    projected_data=project_articles(store,actor,monitor,boundary,p.get('history')=='previous')
    projected=projected_data['rows'];run=projected_data['run']
    if p.get('content_type','all')!='all':projected=[r for r in projected if r['content_type']==p['content_type']]
    if p.get('outlet'):projected=[r for r in projected if r['outlet_id']==p['outlet']]
    if p.get('coverage_state','all')!='all':projected=[r for r in projected if r['coverage_state']==p['coverage_state']]
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
    # project_articles already applies reviewed outlet/owner priority and stable
    # date ties before pagination. Filtering must not silently undo that order.
    page=min(max(0,p.get('page',0)),max(0,(len(rows)-1)//5))
    # Count unseen identities without shifting the user's stable page.
    known={r['article_id'] for r in projected_data['rows']}
    newer={r.get('article_id') or identity(actor.workspace,actor.user,r['url'])
        for r in store.list(actor,'finding') if r.get('monitor_id')==monitor['id'] and r['created']>boundary
        and r.get('scope_key')==scope_key(monitor) and r.get('monitor_revision')==monitor['revision']}
    return {'rows':rows,'visible':rows[page*5:page*5+5],'page':page,
        'new':len(newer-known),'total':len(projected),'counts':counts,'run':run}

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
    if selected == 'web': return row['provider'] == 'Brave web' and not social
    return False


def finding_selection(store, actor, preferences):
    """One selection path for rendering and analysis; new arrivals do not move pages."""
    p = preferences
    all_rows = [r for r in store.list(actor, 'finding')
                if not r.get('monitor_id') or r['monitor_id'] == p.get('monitor')]
    def selected(row):
        return (matches_source(row, p.get('source_filter', 'all')) and
                (p.get('filter', 'all') == 'all' or
                 (row.get('analysis') or {}).get('relevance', 'unassessed') == p['filter']))
    filtered = [r for r in all_rows if selected(r)]
    snapshot = p.get('snapshot', time.time())
    rows = [r for r in filtered if r['created'] <= snapshot]
    rows.sort(key=lambda r: (r.get('published') or '', r['retrieved'], r['id']), reverse=True)
    page = min(max(0, p.get('page', 0)), max(0, (len(rows)-1)//5))
    return {'rows': rows, 'visible': rows[page*5:page*5+5], 'page': page,
            'new': sum(r['created'] > snapshot for r in filtered), 'total': len(all_rows)}

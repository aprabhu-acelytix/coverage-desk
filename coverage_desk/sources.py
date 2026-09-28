from datetime import datetime, timezone
import html
import re
import time
import httpx
from .config import DeskError, require_live
from .models import safe_url, canonical_url, digest
from .discovery import PLATFORMS, platform, source_label

def queries(monitor):
    if monitor.get('_planned_query'):
        return [(monitor.get('_planned_purpose','planned'),monitor['_planned_query'])]
    names = [monitor['name'], *monitor.get('aliases',[])][:5]
    general = ' OR '.join('"'+n.replace('"','')+'"' for n in names)
    result = [('client',general)]
    if monitor.get('campaign'):
        result.append(('campaign',f'({general}) {monitor["campaign"]}'))
    return result

def clean(value):
    return html.unescape(re.sub('<[^>]*>', '', value or ''))

def record(title, url, text, provider, provenance, published=None, access=None):
    safe_url(url)
    return {'title':clean(title)[:300], 'full_title':clean(title), 'url':url, 'canonical':canonical_url(url), 'text':clean(text)[:8000],
        'provider':provider,'platform':platform(url),'source_kind':source_kind(url,provider),'provenance':provenance,'published':published,'retrieved':time.time(),
        'access':access or ('excerpt only' if text else 'metadata only'), 'hash':digest(clean(text)[:8000]),
        'analysis':None, 'analysis_status':'Unassessed'}

def source_kind(url,provider):
    from urllib.parse import urlsplit
    if platform(url):return 'Public social page'
    p=urlsplit(url)
    if any(part in p.path.lower() for part in ('/products/','/collections/','/shop/')):return 'Product / catalog page'
    if p.hostname in ('en.wikipedia.org','www.zoominfo.com'):return 'Reference / profile'
    return 'News search result' if provider=='Brave news' else 'Web page'

class Brave:
    def __init__(self,s,store,client=None):
        self.s,self.store = s,store
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)

    def retrieve(self, monitor, cancel, on_page=None, progress=None):
        require_live(self.s)
        if not self.s.brave_key:
            raise DeskError('Brave is not connected. Configure BRAVE_API_KEY locally.')
        if not self.s.storage_allowed:
            raise DeskError('Brave is awaiting owner-supplied storage permission.')
        targets = list(dict.fromkeys(t for t in monitor.get('sources', ['news', 'web']) if t in ('news', 'web') or t in PLATFORMS))
        findings, statuses, calls = [], [], 0
        counts = {t: 0 for t in targets}
        done, checked = set(), set()
        variants = []
        for variant, base_query in queries(monitor):
            variants.append((variant, base_query, 0))
            if any(len(PLATFORMS.get(t, ('', ()))[1]) > 1 for t in targets):
                variants.append((variant+'_alternate_domain', base_query, 1))
        def emit(target='', stage='Searching', retained=None):
            if progress:
                progress({'stage': stage, 'active_target': source_label(target) if target else '',
                          'checked_targets': len(checked), 'total_targets': len(targets),
                          'requests': calls, 'retained': len(findings) if retained is None else retained, 'updated': time.time()})
        # Breadth first: all first general-query pages before campaign variants or page two.
        for page in range(self.s.pages):
            for variant, base_query, domain_index in variants:
                for target in targets:
                    if domain_index and len(PLATFORMS.get(target, ('', ()))[1]) <= domain_index:
                        continue
                    unit = (target, variant)
                    if unit in done:
                        continue
                    reason = ('Cancelled' if cancel.is_set() else 'Collection cap reached'
                              if calls >= self.s.calls or counts[target] >= self.s.results else None)
                    if reason:
                        statuses.append({'target': target, 'source': target, 'status': reason, 'variant': variant, 'page': page, 'results': 0})
                        done.add(unit)
                        continue
                    endpoint = target if target in ('news', 'web') else 'web'
                    q = base_query
                    if target in PLATFORMS:
                        domains = PLATFORMS[target][1]
                        q = 'site:' + domains[domain_index] + ' ' + base_query
                    params = {'q': q, 'count': min(20, self.s.results-counts[target]), 'offset': page,
                              'search_lang': monitor.get('language', 'en'), 'country': monitor.get('country', 'US'),
                              'safesearch': 'moderate', 'text_decorations': 'false'}
                    if monitor.get('freshness'):
                        params['freshness'] = monitor['freshness']
                    if target in PLATFORMS:
                        params.update(operators='true', spellcheck='false')
                    provenance = {'endpoint': endpoint, 'target': target, 'variant': variant, 'query': q,
                                  'page': page, 'filters': params.copy(), 'checked': time.time()}
                    emit(target)
                    page_rows = []
                    requested = False
                    try:
                        self.store.consume('source')
                        calls += 1
                        requested = True
                        response = self.client.get(f'https://api.search.brave.com/res/v1/{endpoint}/search', params=params,
                            headers={'X-Subscription-Token': self.s.brave_key, 'Accept': 'application/json'})
                        if response.status_code != 200:
                            raise DeskError({401:'Source authentication failed',403:'Source access denied',429:'Source rate limit'}.get(response.status_code,'Source unavailable'))
                        data = response.json()
                        query_metadata = data.get('query') or {}
                        if isinstance(query_metadata.get('altered'),str):
                            provenance['query_altered'] = query_metadata['altered']
                        applied=(query_metadata.get('search_operators') or {}).get('applied')
                        if isinstance(applied,bool):provenance['operators_applied']=applied
                        results = data.get('results', []) if endpoint == 'news' else data.get('web', {}).get('results', [])
                        if not isinstance(results, list):
                            raise DeskError('Malformed source response')
                        for item in results:
                            try:
                                stamp = item.get('page_age')
                                if stamp:
                                    stamp = datetime.fromisoformat(stamp.replace('Z', '+00:00')).isoformat()
                                page_rows.append(record(item.get('title','Untitled source'), item['url'], item.get('description',''),
                                                        f'Brave {endpoint}', provenance, stamp))
                            except (KeyError, ValueError, TypeError, DeskError):
                                statuses.append({'source': target, 'target': target, 'status': 'One malformed result excluded; no safe URL', 'page': page})
                        findings.extend(page_rows)
                        counts[target] += len(page_rows)
                        statuses.append({**provenance, 'source': endpoint, 'requested': True, 'status': 'Results' if results else 'No matches', 'results': len(page_rows)})
                        if target in PLATFORMS:
                            matched=sum(r['platform']==target for r in page_rows)
                            statuses[-1]['platform_matches']=matched
                            if matched<len(page_rows):
                                statuses.append({**provenance,'source':endpoint,'requested':True,'results':0,
                                    'status':f'{len(page_rows)-matched} results were outside the requested platform; kept in All sources'})
                        if not results or len(results) < params['count'] or (endpoint == 'web' and not data.get('query',{}).get('more_results_available',False)):
                            done.add(unit)
                    except Exception as exc:
                        statuses.append({**provenance, 'source': endpoint, 'requested': requested, 'status': str(exc) if isinstance(exc,DeskError) else 'Source request failed; no retry', 'results': 0})
                        done.add(unit)
                    if requested:checked.add(target)
                    # Persistence failures must propagate, not masquerade as provider failures.
                    if on_page:
                        emit(target, 'Saving', len(findings)-len(page_rows))
                        on_page(page_rows, statuses.copy())
                    emit(target)
        # Show unrequested targets even when the request cap/cancellation prevented every attempt.
        emit(stage='Saving')
        return findings, statuses

def demo_records(monitor):
    return [record('[Fixture] '+monitor['name']+' announces a repair program','https://example.com/fixture/repair',
        monitor['name']+' says its new repair program helps customers keep products longer.',
        'Synthetic fixture',{'endpoint':'fixture','query':'fixture','page':0},'2026-09-20T12:00:00+00:00')]

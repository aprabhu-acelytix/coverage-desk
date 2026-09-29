"""Reviewable public outlet context; never an AI credibility score or filter."""
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

PRIORITIES={'high':3,'standard':1,'low':0}
PRIORITY_LABELS={'high':'Higher priority','standard':'Standard priority','low':'Lower priority','default':'Use default'}


@lru_cache(maxsize=1)
def catalog():
    entries=json.loads(Path(__file__).with_name('outlet_profiles.json').read_text(encoding='utf-8'))
    return {host:entry for entry in entries for host in entry['hosts']}


def outlet_context(row,override=None):
    host=(urlsplit(row['url']).hostname or '').lower().rstrip('.')
    entry=catalog().get(host)
    # No suffix matching, publisher-name matching, or common-owner inheritance.
    if entry:
        context={**entry,'reviewed':True,'rank':2 if row.get('content_type')=='reporting' else 1,
            'priority_label':'Established reporting' if row.get('content_type')=='reporting' else 'Standard priority',
            'priority_reason':'Reviewed editorial profile; article-level evidence still needs evaluation.'}
    else:
        kind=row.get('content_type','unknown')
        descriptions={'client_owned':'A client-owned source: useful for what the organization says about itself, not independent corroboration.',
            'social':'A social-platform page. Assess the individual author and supporting evidence; the platform name does not establish credibility.',
            'press_release':'A distributed announcement. Verify its claims against independent reporting.',
            'sponsored':'Content with sponsorship evidence. Consider the disclosed commercial relationship.'}
        context={'name':row.get('outlet_name') or host,'description':descriptions.get(kind,'A public website with no reviewed outlet profile in Coverage Desk yet.'),
            'significance':'Audience and subject expertise have not been established here.',
            'signals':'Not reviewed. This is not a finding that the outlet is unreliable.',
            'references':[],'reviewed':False,'rank':1,'priority_label':'Standard priority',
            'priority_reason':'No reviewed editorial profile; kept visible at standard priority.'}
    context['host']=host
    context['override']=override or {}
    if override and override['priority'] in PRIORITIES:
        context.update(rank=PRIORITIES[override['priority']],priority_label=PRIORITY_LABELS[override['priority']],
            priority_reason='Your outlet preference: '+override['reason'])
    return context


def rank_articles(rows,store,actor,at):
    latest={}
    for item in store.list(actor,'outlet_priority'):
        if item['owner']==actor.user and item['created']<=at:latest.setdefault(item['host'],item)
    for row in rows:
        host=(urlsplit(row['url']).hostname or '').lower().rstrip('.')
        row['outlet_context']=outlet_context(row,latest.get(host))
    # Existing recency/identity ordering is the stable tie-breaker. Rank before
    # pagination; counts, relevance, period, and outlet chart ordering do not change.
    rows.sort(key=lambda r:r['outlet_context']['rank'],reverse=True)
    return rows

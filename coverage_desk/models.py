import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .config import DeskError

def safe_url(value):
    p = urlsplit(value.strip())
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password or any(c in value for c in '<>\n\r|'):
        raise DeskError('Use a valid public HTTP or HTTPS source link.')
    return value.strip()

def canonical_url(value):
    p = urlsplit(safe_url(value))
    params = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid','msclkid','trk','ref_src')]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(params), ''))

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class PlannedQuery(Strict):
    query: str = Field(min_length=1,max_length=550)
    target: Literal['news','web','instagram','x','linkedin','facebook','tiktok','reddit','youtube']
    purpose: Literal['broad','focus','contrary']
    rationale: str = Field(max_length=300)

class ResearchPlan(Strict):
    interpretation: str = Field(max_length=500)
    queries: list[PlannedQuery] = Field(min_length=1,max_length=3)

class NativeCandidate(Strict):
    title: str = Field(max_length=300)
    url: str
    quote: str = Field(max_length=500)

class NativeResearch(Strict):
    interpretation: str = Field(max_length=500)
    candidates: list[NativeCandidate] = Field(max_length=5)

class DiscoveryResult(Strict):
    summary: str = Field(max_length=500)

class Evidence(Strict):
    source_id: str
    quote: str = Field(max_length=500)

class Assessment(Strict):
    message: str = Field(max_length=500)
    label: Literal['supported','contradicted','not_observed_in_available_text','insufficient_evidence']
    explanation: str = Field(max_length=800)
    evidence: list[Evidence] = Field(max_length=4)

class CoverageClassification(Strict):
    content_type: Literal['reporting','client_owned','press_release','sponsored','social','unknown']
    evidence: str = Field(max_length=400)
    outlet_name: str = Field(max_length=180)
    redistribution: str = Field(max_length=400)

class Classification(Strict):
    source_id: str
    relevance: Literal['relevant','uncertain','not_relevant']
    campaign_relevance: Literal['relevant','uncertain','not_relevant','not_applicable']
    explanation: str = Field(max_length=800)
    messages: list[Assessment] = Field(max_length=8)
    coverage: CoverageClassification | None = None

class Analysis(Strict):
    findings: list[Classification] = Field(max_length=15)

class LiveClassification(Classification):
    # Legacy stored assessments may omit coverage. New structured runtime output
    # must require every property, including an explicit unknown classification.
    coverage: CoverageClassification

class LiveAnalysis(Strict):
    findings: list[LiveClassification] = Field(max_length=15)

class CoverageFinding(Strict):
    source_id: str
    coverage: CoverageClassification

class CoverageAnalysis(Strict):
    findings: list[CoverageFinding] = Field(max_length=15)

class ResearchFinding(Classification):
    supporting_quote: str = Field(min_length=1,max_length=500)

class ResearchResult(Strict):
    interpretation: str = Field(max_length=500)
    findings: list[ResearchFinding] = Field(max_length=15)

class BriefingPoint(Strict):
    text: str = Field(max_length=250)
    source_id: str
    quote: str = Field(max_length=300)

class BriefingAnalysis(Strict):
    what_changed: list[BriefingPoint] = Field(min_length=1,max_length=5)
    message_evidence: list[BriefingPoint] = Field(max_length=5)
    worth_discussing: str = Field(max_length=300)

def validate_briefing(raw,sources):
    try:result=BriefingAnalysis.model_validate(raw)
    except ValueError:raise DeskError('Invalid evidence: briefing response did not match the required schema.') from None
    lookup={r['id']:r for r in sources}
    for point in result.what_changed+result.message_evidence:
        if point.source_id not in lookup or not observed_quote(point.quote,lookup[point.source_id]):
            raise DeskError('Invalid briefing evidence: source or exact quotation did not match.')
    return result.model_dump()

def observed_quote(quote,source):
    """Both retained headlines and excerpts are observed evidence, never generated prose."""
    return bool(quote.strip()) and (quote in source['text'] or quote in source.get('full_title',source.get('title','')))

def classification_quote(quote,source):
    profile=source.get('provenance',{}).get('publication_check',{}).get('source_profile',{})
    values=[profile.get('publisher',''),*profile.get('authors',[]),*profile.get('article_types',[])]
    return observed_quote(quote,source) or bool(quote.strip()) and any(quote in v for v in values)

def validate_analysis(raw, sources, messages):
    try:result = Analysis.model_validate(raw)
    except ValueError:raise DeskError('Invalid evidence: analysis response did not match the required schema.') from None
    lookup = {s['id']: s for s in sources}
    if len(result.findings) != len(lookup) or {f.source_id for f in result.findings} != set(lookup):
        raise DeskError('Invalid evidence: output must assess each selected source once.')
    for f in result.findings:
        if f.coverage:
            c=f.coverage;source=lookup[f.source_id]
            if c.content_type!='unknown' and not classification_quote(c.evidence,source):
                # Preserve valid message assessments even when type evidence fails.
                c.content_type='unknown';c.evidence=''
            if c.outlet_name and not classification_quote(c.outlet_name,source):c.outlet_name=''
            if c.redistribution and not observed_quote(c.redistribution,source):c.redistribution=''
        if [a.message for a in f.messages] != messages:
            raise DeskError('Invalid evidence: message criteria changed.')
        for a in f.messages:
            if a.label in ('supported', 'contradicted') and not a.evidence:
                raise DeskError('Invalid evidence: a supported or contradicted claim needs a quotation.')
            for ev in a.evidence:
                if ev.source_id != f.source_id or not observed_quote(ev.quote,lookup[ev.source_id]):
                    raise DeskError('Invalid evidence: quotation did not match the selected source text.')
    return result.model_dump()

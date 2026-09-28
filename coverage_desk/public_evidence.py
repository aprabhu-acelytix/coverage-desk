"""Bounded metadata verification for native research hits, never manual URLs.

DNS answers must all be public. Connect to the validated address while retaining
the original hostname for TLS verification. Redirects repeat these checks.
"""
from datetime import datetime,timezone
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import socket
import ssl
import time
import threading
import queue
from urllib.parse import urlsplit,urljoin
from .research import public_url
from .config import DeskError,require_live


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__();self.dates=[];self.publishers=[];self.authors=[];self.types=[];self.script=False;self.parts=[]
        self.descriptions=[];self.article_bodies=[];self.paragraphs=[];self.paragraph=None;self.in_article=0;self.blocked=0;self.paywalled=False;self.canonical=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='article':self.in_article+=1
        if tag in ('script','style','noscript'):self.blocked+=1
        if tag=='p' and self.in_article and not self.blocked:self.paragraph=[]
        if tag=='link' and attrs.get('rel')=='canonical':self.canonical=attrs.get('href')
        if tag=='meta' and (attrs.get('property') or attrs.get('name')) in ('og:description','description'):
            self.descriptions.append(attrs.get('content',''))
        if tag=='meta' and (attrs.get('property') or attrs.get('name')) in ('article:published_time','datePublished'):
            self.dates.append(attrs.get('content',''))
        if tag=='meta' and (attrs.get('property') or attrs.get('name'))=='og:site_name':
            self.publishers.append(attrs.get('content',''))
        if tag=='meta' and attrs.get('name')=='author':self.authors.append(attrs.get('content',''))
        if tag=='meta' and attrs.get('property')=='og:type':self.types.append(attrs.get('content',''))
        if tag=='script' and attrs.get('type')=='application/ld+json':self.script=True;self.parts=[]
    def handle_data(self,data):
        if self.script:self.parts.append(data)
        elif self.paragraph is not None and not self.blocked:self.paragraph.append(data)
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.blocked=max(0,self.blocked-1)
        if tag=='article':self.in_article=max(0,self.in_article-1)
        if tag=='p' and self.paragraph is not None:
            self.paragraphs.append(''.join(self.paragraph).strip());self.paragraph=None
        if tag!='script' or not self.script:return
        self.script=False
        try:data=json.loads(''.join(self.parts))
        except (ValueError,RecursionError):return
        values=data if isinstance(data,list) else [data]
        for item in values:
            if not isinstance(item,dict):continue
            candidates=[item]+(item.get('@graph',[]) if isinstance(item.get('@graph'),list) else [])
            for node in candidates:
                if isinstance(node,dict):
                    if node.get('isAccessibleForFree') in (False,'false'):self.paywalled=True
                    if isinstance(node.get('articleBody'),str):self.article_bodies.append(node['articleBody'])
                if isinstance(node,dict) and isinstance(node.get('datePublished'),str):self.dates.append(node['datePublished'])
                if isinstance(node,dict) and isinstance(node.get('publisher'),dict) and isinstance(node['publisher'].get('name'),str):self.publishers.append(node['publisher']['name'])
                if isinstance(node,dict) and node.get('datePublished'):
                    if isinstance(node.get('@type'),str):self.types.append(node['@type'])
                    authors=node.get('author',[]);authors=authors if isinstance(authors,list) else [authors]
                    for author in authors:
                        if isinstance(author,dict) and isinstance(author.get('name'),str):self.authors.append(author['name'])


def publication(text):
    parser=Metadata();parser.feed(text)
    dates=set()
    for value in parser.dates:
        try:
            parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
            if parsed.tzinfo:dates.add(parsed.astimezone(timezone.utc).isoformat())
        except (ValueError,TypeError):pass
    # Conflicting metadata and timezone-free dates remain reviewable, not guessed.
    return next(iter(dates)) if len(dates)==1 else None


def fetch_metadata(url,settings,store,cancel):
    require_live(settings)
    original=url
    for redirect in range(3):
        if cancel.is_set():raise DeskError('Cancelled before publication-date verification.')
        public_url(url);p=urlsplit(url)
        if p.port not in (None,80,443):raise DeskError('Nonstandard public source port is unavailable.')
        port=p.port or (443 if p.scheme=='https' else 80)
        resolved=queue.Queue(maxsize=1)
        def resolve(host=p.hostname,number=port,output=resolved):
            try:output.put(socket.getaddrinfo(host,number,type=socket.SOCK_STREAM))
            except Exception:output.put(None)
        threading.Thread(target=resolve,daemon=True).start()
        try:addresses=resolved.get(timeout=8)
        except queue.Empty:raise DeskError('Public source DNS lookup timed out.') from None
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise DeskError('Source address is not a permitted public host.')
        address=addresses[0][4][0]
        store.consume('source')
        connection=http.client.HTTPConnection(p.hostname,port,timeout=8)
        try:
            stream=socket.create_connection((address,port),timeout=8)
            if p.scheme=='https':
                try:stream=ssl.create_default_context().wrap_socket(stream,server_hostname=p.hostname)
                except Exception:stream.close();raise
            connection.sock=stream
            connection.request('GET',(p.path or '/')+('?' +p.query if p.query else ''),headers={
                'User-Agent':'CoverageDesk/1.0 public publication metadata check','Accept':'text/html','Accept-Encoding':'identity'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise DeskError('Source redirect has no destination.')
                url=urljoin(url,location);continue
            if response.status!=200:raise DeskError('Public source did not permit page access.')
            if 'text/html' not in (response.getheader('Content-Type') or '').lower():raise DeskError('Source is not an HTML page.')
            if response.getheader('Content-Encoding') not in (None,'identity'):raise DeskError('Encoded source metadata is unavailable.')
            chunks=[];size=0;deadline=time.monotonic()+12
            while size<=262144:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise DeskError('Public metadata verification timed out.')
                stream.settimeout(min(remaining,8))
                chunk=response.read1(min(16384,262145-size))
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
            body=b''.join(chunks)
            truncated=len(body)>262144
            body=body[:262144]
            # Retain only publication/publisher metadata, never the whole page.
            text=body.decode('utf-8',errors='replace');date=publication(text)
            parser=Metadata();parser.feed(text)
            precision='timestamp'
            # Publisher date-only metadata is a calendar date, not an invented
            # midnight publication timestamp. URL/retrieval dates are never used.
            if not date:
                from datetime import date as calendar_date
                dates=set()
                for value in parser.dates:
                    try:
                        if len(value)==10:dates.add(calendar_date.fromisoformat(value).isoformat())
                    except (ValueError,TypeError):pass
                if len(dates)==1 and all(len(x)==10 for x in parser.dates):date=next(iter(dates));precision='day'
            names={name.strip()[:180] for name in parser.publishers if name.strip()}
            profile={'publisher':next(iter(names)),'method':'Publisher HTML site-name metadata'} if len(names)==1 else {}
            profile.update(authors=sorted({a[:180] for a in parser.authors if a})[:4],article_types=sorted({t[:100] for t in parser.types if t})[:4])
            visible=parser.descriptions if parser.paywalled else (parser.article_bodies or parser.paragraphs or parser.descriptions)
            excerpt=' '.join(' '.join(visible).split())[:1200]
            canonical=urljoin(url,parser.canonical) if parser.canonical else None
            # Only publisher-declared same-host article aliases are usable.
            if canonical:
                try:
                    public_url(canonical)
                    if urlsplit(canonical).hostname!=p.hostname or urlsplit(canonical).path in ('','/'):canonical=None
                except (ValueError,DeskError):canonical=None
            return {'url':url,'original_url':original,'published':date,'method':'Publisher HTML publication metadata (bounded prefix)',
                'truncated':truncated,'source_profile':profile,'date_precision':precision,'excerpt':excerpt,'canonical_url':canonical,
                'access':'Public metadata summary; paywall respected' if parser.paywalled else 'Bounded public publisher excerpt',
                'fetch_version':2,'checked':time.time(),
                'status':'Verified publication metadata' if date else 'Publication metadata absent or ambiguous'}
        finally:connection.close()
    raise DeskError('Public source exceeded the redirect limit.')

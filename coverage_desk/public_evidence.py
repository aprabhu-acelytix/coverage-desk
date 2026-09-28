"""Bounded metadata verification for native research hits, never manual URLs.

DNS answers must all be public. Connect to the validated address while retaining
the original hostname for TLS verification. Redirects repeat these checks.
"""
from datetime import datetime
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
        super().__init__();self.dates=[];self.script=False;self.parts=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='meta' and (attrs.get('property') or attrs.get('name')) in ('article:published_time','datePublished'):
            self.dates.append(attrs.get('content',''))
        if tag=='script' and attrs.get('type')=='application/ld+json':self.script=True;self.parts=[]
    def handle_data(self,data):
        if self.script:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag!='script' or not self.script:return
        self.script=False
        try:data=json.loads(''.join(self.parts))
        except (ValueError,RecursionError):return
        values=data if isinstance(data,list) else [data]
        for item in values:
            if not isinstance(item,dict):continue
            candidates=[item]+(item.get('@graph',[]) if isinstance(item.get('@graph'),list) else [])
            for node in candidates:
                if isinstance(node,dict) and isinstance(node.get('datePublished'),str):self.dates.append(node['datePublished'])


def publication(text):
    parser=Metadata();parser.feed(text)
    dates=set()
    for value in parser.dates:
        try:
            parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
            if parsed.tzinfo:dates.add(parsed.isoformat())
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
            if len(body)>262144:raise DeskError('Public page exceeds the metadata verification size limit.')
            # Only publication metadata retained, never a whole publisher page.
            date=publication(body.decode('utf-8',errors='replace'))
            return {'url':url,'original_url':original,'published':date,'method':'Publisher HTML publication metadata',
                'status':'Verified publication metadata' if date else 'Publication metadata absent or ambiguous'}
        finally:connection.close()
    raise DeskError('Public source exceeded the redirect limit.')

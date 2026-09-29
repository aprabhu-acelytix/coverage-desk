"""Finish a finite owner-selected evidence set in bounded, cancellable batches."""
import json,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from .config import DeskError,require_live
from .models import digest,canonical_url
from .scope import scope_key,version
from .overview import project_articles
from .discovery import platform

def batches(rows,settings,messages=0,monitor=None):
    from .models import LiveAnalysis,CoverageAnalysis
    limit=min(settings.ai_items,max(1,settings.output_job//(700+250*messages)))
    schema=(LiveAnalysis if monitor else CoverageAnalysis).model_json_schema()
    criteria={k:monitor[k] for k in ('name','aliases','domains','notes','campaign','messages')} if monitor else {}
    base=len(json.dumps({'sources':[],'criteria':criteria,'schema':schema,'operation':'classify_coverage'}))+100
    batch=[];size=base
    for row in rows:
        source={k:row.get(k,'') for k in ('id','title','text','url','access','provider')}
        profile=row.get('provenance',{}).get('publication_check',{}).get('source_profile',{})
        source['publisher_metadata']={k:profile[k] for k in ('publisher','authors','article_types') if k in profile}
        cost=len(json.dumps(source))+2
        if cost+base>settings.input_job:raise DeskError('An article and its criteria exceed the assessment input size; shorten the contributed excerpt or criteria.')
        if batch and (len(batch)>=limit or size+cost>settings.input_job):yield batch;batch=[];size=base
        batch.append(row);size+=cost
    if batch:yield batch


def read_sources(desk,actor,monitor,rows,cancel):
    from .public_evidence import fetch_metadata
    candidates=[]
    for row in rows:
        if row['provider'] not in ('Codex web','Brave news','Brave web') or platform(row['url']):continue
        check=row.get('provenance',{}).get('publication_check',{})
        # A failed/denied fetch is not repeatedly retried, including across restarts.
        if check and (check.get('fetch_version')==2 or not check.get('published') and 'source_profile' not in check):continue
        desk.allowed_source(row);candidates.append(row)
    def fetch(row):
        if cancel.is_set():return None
        try:result=fetch_metadata(row['url'],desk.s,desk.store,cancel)
        except Exception as exc:
            result={'published':None,'status':str(exc) if isinstance(exc,DeskError) else 'Public page unavailable; retained search evidence used.'}
        return {**result,'fetch_version':2,'checked':time.time()}
    completed=0
    with ThreadPoolExecutor(max_workers=3,thread_name_prefix='publisher') as pool:
        futures={pool.submit(fetch,row):row for row in candidates}
        for future in as_completed(futures):
            metadata=future.result();row=futures[future];completed+=1
            if metadata is None or cancel.is_set():continue
            if desk.store.get(actor,monitor['id'],'monitor')['revision']!=monitor['revision']:cancel.set();raise DeskError('Search scope changed; old page evidence was not applied.')
            for item in desk.store.list(actor,'finding'):
                if item.get('monitor_id')!=monitor['id'] or item.get('scope_key')!=scope_key(monitor) or canonical_url(item['url'])!=canonical_url(row['url']):continue
                item.setdefault('provenance',{})['publication_check']=metadata
                if metadata.get('published'):
                    item.update(published=metadata['published'],date_kind='publication',date_precision=metadata.get('date_precision','timestamp'))
                excerpt=metadata.get('excerpt','')
                if excerpt and excerpt not in item['text']:
                    room=max(0,desk.s.input_item-len(item['text'])-24)
                    if room:
                        item['provenance'].setdefault('discovery_excerpt',item['text'])
                        item['text']+='\n\nPublisher excerpt:\n'+excerpt[:room]
                        item['access']=metadata.get('access','Bounded public publisher excerpt')
                        item['hash']=digest(item['text'])
                if metadata.get('canonical_url'):item['canonical']=canonical_url(metadata['canonical_url'])
                item['version_id']=version(item)
                desk.store.update(actor,item['id'],item)
            desk.progress(actor,{'stage':f'Reading available pages: {completed}/{len(candidates)}','pages_checked':completed,'pages_total':len(candidates)})


def combine_social_evidence(desk,actor,monitor,rows):
    """Assess retained same-URL search excerpts together; keep their provenance."""
    raw=desk.store.list(actor,'finding')
    for row in rows:
        if not platform(row['url']) or row['provider']!='Codex web':continue
        matches=[r for r in raw if r.get('monitor_id')==monitor['id'] and r.get('scope_key')==scope_key(monitor)
                 and r.get('monitor_revision')==monitor['revision'] and r['provider']=='Codex web'
                 and canonical_url(r['url'])==canonical_url(row['url'])]
        # Keep the representative's already-assessed text intact. If a later
        # assessment fails, earlier exact quotations still have their evidence.
        parts=[row['text']] if row.get('text') else []
        length=len(row.get('text',''));included=[row] if parts else []
        for item in sorted(matches,key=lambda r:(r['created'],r['id']),reverse=True):
            text=item.get('provenance',{}).get('original_search_excerpt',item.get('text',''))
            if not text or text in '\n\n'.join(parts):continue
            remaining=desk.s.input_item-length-(2 if parts else 0)
            if remaining<=0:break
            parts.append(text[:remaining]);length+=len(parts[-1])+(2 if len(parts)>1 else 0);included.append(item)
        combined='\n\n'.join(parts)
        if combined and combined!=row['text']:
            item=desk.store.get(actor,row['id'],'finding')
            item.setdefault('provenance',{}).setdefault('original_search_excerpt',item['text'])
            item['provenance']['combined_search_sources']=[r['id'] for r in included]
            item.update(text=combined,hash=digest(combined),access='Combined tool-observed search excerpts; full post not accessed')
            item['version_id']=version(item)
            expires=min([item['expires']]+[r['expires'] for r in included])
            with desk.store.transaction():
                desk.store.update(actor,item['id'],item)
                desk.store.db.execute('UPDATE objects SET expires=MIN(expires,?) WHERE id=?',(expires,item['id']))


def complete(desk,actor,monitor_id,cancel):
    desk.store.authorize(actor,owner=True);require_live(desk.s)
    monitor=desk.store.get(actor,monitor_id,'monitor');at=time.time()
    rows=lambda:project_articles(desk.store,actor,monitor,at)['rows']
    attempted=[];error=None
    try:
        if cancel.is_set():return []
        combine_social_evidence(desk,actor,monitor,rows())
        read_sources(desk,actor,monitor,rows(),cancel)
        current=rows();total=len(current)
        pending=[r for r in current if not r.get('analysis') or r.get('analysis_scope_key')!=scope_key(monitor) or r.get('analysis_key')!=desk.analysis_key(actor,r,monitor)]
        count=total-len(pending)
        for batch in batches(pending,desk.s,len(monitor['messages']),monitor):
            if cancel.is_set():break
            desk.progress(actor,{'stage':f'Assessing articles: {count}/{total}','assessed':count,'total':total})
            desk.analyze(actor,monitor_id,[r['id'] for r in batch],cancel,partial=True)
            attempted.extend(r['id'] for r in batch);count+=len(batch)
            desk.progress(actor,{'stage':f'Assessing articles: {count}/{total}','assessed':count,'total':total})
        # Content-type follow-up cannot starve relevance assessment. Only an
        # unchanged unknown result is skipped; never loop/retry failed batches.
        current=rows()
        unknown=[r for r in current if r.get('relevance')=='relevant' and r['date_status']!='outside' and r['content_type']=='unknown'
            and r.get('coverage_key')!=desk.analysis_key(actor,r,monitor)]
        for index,batch in enumerate(batches(unknown,desk.s)):
            if cancel.is_set():break
            desk.progress(actor,{'stage':f'Checking article types: batch {index+1}'})
            desk.classify_coverage(actor,monitor,batch,cancel)
    except Exception as exc:
        error=str(exc) if isinstance(exc,DeskError) else 'Evidence assessment could not finish. Completed work was retained.'
        raise
    finally:
        current=rows();remaining=sum(not r.get('analysis') or bool(r.get('analysis_error')) for r in current)
        runs=[r for r in desk.store.list(actor,'run') if r.get('monitor_id')==monitor_id and r.get('scope',{}).get('key')==scope_key(monitor)]
        outcome='Cancelled' if cancel.is_set() else 'Incomplete' if remaining or error else 'Assessed'
        if runs:
            run=runs[0];run.update(assessed_count=len(current)-remaining,pending_count=remaining,unique_count=len(current),outcome=outcome,
                assessment_complete=not remaining and not error and not cancel.is_set(),checked=time.time())
            if run.get('path')=='Codex native web':
                from .research import platform_summary
                run['platforms']=platform_summary(monitor,current,run.get('statuses',[]),run.get('followups',[]))
            if error:
                if run.get('error') and not run.get('assessment_error'):run['collection_error']=run['error']
                run['assessment_error']=error;run['error']=error
            elif not remaining and not cancel.is_set():
                if run.get('assessment_error') or run.get('error','').startswith(('AI ','Unexpected runtime item','Unexpected tool activity')):
                    run['error']=run.get('collection_error','');run.pop('assessment_error',None)
            desk.store.update(actor,run['id'],run)
        desk.store.preferences(actor,{'snapshot':time.time(),'page':0,'explore_view':'overview','outlet':'','outlet_page':0,'notice':''})
        desk.progress(actor,{'stage':f'{len(current)-remaining}/{len(current)} articles assessed','outcome':outcome,'assessed':len(current)-remaining,'total':len(current)})
    return attempted

"""Slack-native outlet overview and read-only article drill-down."""
import json,time
from .overview import coverage_overview,CONTENT_TYPES,STATES,chart_block
from . import ui

def period(window):
    start=window['start'][:10] if window['start'] else 'Any time'
    return start+' to '+window['end'][:16].replace('T',' ')+' UTC (end exclusive)'

def home_blocks(desk,actor,monitor,p):
    p=dict(p)
    if p.get('content_type','reporting') not in ('reporting','all'):p['content_type']='all'
    owner=actor.user==desk.s.owner
    overview=coverage_overview(desk.store,actor,monitor,p)
    blocks=[ui.actions(ui.button('Overview','coverage_view_overview','overview',p.get('explore_view','overview')=='overview'),
        ui.button('Articles','coverage_view_articles','articles',p.get('explore_view')=='articles'))]
    job=desk.jobs.get(actor.user,{})
    busy=job.get('state') in ('Working','Queued')
    partial=overview['partial'] or busy
    blocks.append(ui.para(f"Coverage found · {overview['article_count']} articles · {overview['outlet_count']} outlets"))
    freshness=time.strftime('%d %b, %H:%M UTC',time.gmtime(overview['freshness'])) if overview['freshness'] else 'Not collected yet'
    blocks.append(ui.context(ui.esc(period(overview['scope']['window']))+' | '+('Partial collection' if partial else 'Retained collection')+' | Last checked '+freshness))
    view=p.get('explore_view','overview')
    if view=='overview':
        capabilities=desk.store.list(actor,'slack_capabilities')
        supported=capabilities and capabilities[0].get('home',{}).get('data_visualization',{}).get('supported')
        chart=chart_block(overview)
        if chart and supported:blocks.append(chart)
        elif chart:blocks.append(ui.context('Native chart availability is unverified or unavailable here. Exact outlet counts are listed below.'))
        blocks.append(ui.actions(ui.select('coverage_category',[('Reporting','reporting'),('All source types','all')],overview['category'])))
        if not overview['outlets']:
            blocks.append(ui.para('No confirmed '+CONTENT_TYPES.get(overview['category'],'coverage').lower()+' in this period yet. Open Articles to see available evidence and any access or date limitations.'))
        outlets=overview['outlets'];page=min(max(0,p.get('outlet_page',0)),max(0,(len(outlets)-1)//8))
        for number,outlet in enumerate(outlets[page*8:page*8+8],start=page*8+1):
            blocks.append(ui.section('*'+str(number)+'. '+ui.esc(outlet['name'])+'* · '+str(outlet['count'])+' article'+('' if outlet['count']==1 else 's')))
            titles='\n'.join('• '+r['title'][:160] for r in outlet['articles'][:2])
            blocks.append(ui.para(titles))
            blocks.append(ui.actions(ui.button('View articles','coverage_outlet',outlet['id'])))
        if len(outlets)>8:
            controls=[]
            if page:controls.append(ui.button('Previous outlets','outlet_page_previous',page-1))
            if (page+1)*8<len(outlets):controls.append(ui.button('More outlets','outlet_page_next',page+1))
            blocks.append(ui.context(f"Outlets {page*8+1}–{min((page+1)*8,len(outlets))} of {len(outlets)}. Chart: first eight outlets plus the combined remainder."))
            if controls:blocks.append(ui.actions(*controls))
    else:
        from .discovery import matches_source
        from .overview import project_articles
        historical=p.get('history')=='previous'
        selected=p.get('outlet')
        if selected:
            outlet=next((o for o in overview['outlets'] if o['id']==selected),None)
            blocks.append(ui.para('Articles from '+(outlet['name'] if outlet else 'the selected outlet')))
            blocks.append(ui.actions(ui.button('Back to overview','coverage_back'),ui.button('Clear outlet','coverage_clear')))
        candidates=project_articles(desk.store,actor,monitor,overview['at'],history=True)['rows'] if historical else overview['rows']
        if historical:blocks.append(ui.para('Previous-scope sources: retained for inspection, excluded from the current overview.'))
        rows=[r for r in candidates if (not selected or overview['category']=='all' or r['content_type']==overview['category']) and (not selected or r['outlet_id']==selected) and matches_source(r,p.get('source_filter','all'))]
        state=p.get('coverage_state','confirmed')
        state={'unassessed':'attention','date_unconfirmed':'attention','uncertain':'attention','outside':'confirmed','excluded':'all'}.get(state,state)
        blocks.append(ui.actions(ui.select('coverage_state',[('Relevant','confirmed'),('Needs attention','attention'),('All results','all')],state)))
        blocks.append(ui.context('Established reporting first, then newest within each priority. Inspect > Source details explains why.'))
        if state=='attention':blocks.append(ui.context('Already relevant? Its date or article type may still need checking. Mark relevant changes the match only.'))
        rows=[r for r in rows if r['date_status']!='outside']
        if state=='confirmed':rows=[r for r in rows if r['relevance']=='relevant']
        elif state=='attention':rows=[r for r in rows if r['coverage_state'] in ('unassessed','uncertain','date_unconfirmed') or r.get('analysis_error') or (r['relevance']=='relevant' and r['content_type']=='unknown')]
        page=min(max(0,p.get('page',0)),max(0,(len(rows)-1)//5))
        for row in rows[page*5:page*5+5]:
            blocks.extend(ui.finding_row(row,can_review=owner and not historical))
        if not rows:blocks.append(ui.para('No articles match these filters. Clear the outlet or choose another filter.'))
        blocks.extend(ui.pagination(page,len(rows)))
        blocks.append(ui.actions(ui.button('Source & history filters','filters')))
        if p.get('source_filter','all')!='all':blocks.append(ui.context('Source filter: '+p['source_filter']+' · Change it in Source & history filters.'))
    states=overview['states']
    attention=sum(r['date_status']!='outside' and (r['coverage_state'] in ('unassessed','uncertain','date_unconfirmed') or bool(r.get('analysis_error')) or (r['relevance']=='relevant' and r['content_type']=='unknown')) for r in overview['rows'])
    if attention:blocks.append(ui.context(f'{attention} findings need attention: unavailable dates, limited source access or uncertain matches/types.'))
    controls=[ui.button('Search options','search_options',monitor['id'])]
    if overview['run']:controls.append(ui.button('Collection details','run_status',overview['run']['id']))
    if owner and overview['article_count']:controls.append(ui.button('Preview & share overview','overview_share',monitor['id']))
    blocks.append(ui.actions(*controls))
    if busy:
        blocks.append(ui.context(job.get('stage','Working')+' · Retained coverage stays visible.'))
        blocks.append(ui.actions(ui.button('Cancel','cancel')))
    elif owner and (states.get('unassessed') or any(r.get('analysis_error') for r in overview['rows'])):
        blocks.append(ui.actions(ui.button('Finish research','continue_research',monitor['id'])))
    if overview['run'] and overview['run'].get('error'):blocks.append(ui.para(overview['run']['error']))
    return blocks

def correction_modal(row,field='relevance',reason='',parent=None):
    fields=[('Relevance','relevance'),('Article type','content_type'),('Outlet name','outlet_name'),('Publication date','published')]
    if field not in dict((value,label) for label,value in fields):field='relevance'
    blocks=[ui.para(row['title']),ui.context('Change one detail. Your correction stays linked to its source.'),
        ui.actions(ui.select('coverage_correct_field',fields,field))]
    if field=='relevance':blocks.append(ui.input_select('relevance','Is this about your search?',
        [('Relevant','relevant'),('Not relevant','not_relevant'),('Not sure','uncertain')],row.get('relevance','uncertain') if row.get('relevance') in ('relevant','not_relevant','uncertain') else 'uncertain'))
    elif field=='content_type':blocks.append(ui.input_select('content_type','What kind of article is this?',[(name,key) for key,name in CONTENT_TYPES.items()],row.get('content_type','unknown')))
    elif field=='outlet_name':blocks.append(ui.input_text('outlet_name','Outlet name',row.get('outlet_name',''),max_length=180))
    else:
        element={'type':'datepicker','action_id':'value','placeholder':ui.plain('Choose publication date')}
        if row.get('published'):element['initial_date']=row['published'][:10]
        blocks.append({'type':'input','block_id':'published','optional':True,'label':ui.plain('Publication date'),'element':element})
        blocks.append(ui.context('Use the date on the article. Clear it if the date cannot be verified.'))
    blocks.append(ui.input_text('reason','What supports this correction?',reason,False,True,1000,hint='A short note about the source is enough.'))
    return ui.modal('Edit finding',blocks,'coverage_correct_submit',{'id':row['id'],'field':field,'parent':parent},submit='Save changes')


def outlet_priority_modal(row,parent=None):
    from .outlets import PRIORITY_LABELS,outlet_context
    context=row.get('outlet_context') or outlet_context(row)
    override=context.get('override',{})
    return ui.modal('Outlet priority',[
        ui.para(context['name']+' ('+context['host']+')'),
        ui.context('Applies to this exact website in your Explore lists. This changes order, not relevance, credibility or coverage totals. Preferences expire with retained source evidence.'),
        ui.input_select('priority','How should this outlet appear?',[(label,key) for key,label in PRIORITY_LABELS.items()],override.get('priority','default')),
        ui.input_text('reason','Why this priority?',override.get('reason',''),max_length=500)
    ],'outlet_priority_submit',{'id':row['id'],'parent':parent},submit='Save priority')


def snapshot_blocks(draft):
    data=draft['overview']
    blocks=[ui.header('Coverage found'),ui.para(data['client']+(' · '+data['campaign'] if data.get('campaign') else '')),
        ui.context(period(data['scope']['window'])),
        ui.para(f"{data['article_count']} unique article appearances · {data['outlet_count']} outlets · {CONTENT_TYPES.get(data['category'],'All content types')}"),
        ui.context('Frozen '+time.strftime('%d %b %Y, %H:%M UTC',time.gmtime(data['at']))+' · '+('Partial collection' if data['partial'] else 'Retained collection'))]
    for outlet in data['outlets'][:8]:blocks.append(ui.para(outlet['name']+' — '+str(outlet['count'])))
    if len(data['outlets'])>8:blocks.append(ui.para('Other outlets: '+str(sum(o['count'] for o in data['outlets'][8:]))+' appearances at '+str(len(data['outlets'])-8)+' outlets.'))
    blocks.append(ui.para('Source examples'))
    for source in data['sources'][:5]:blocks.append(ui.section('<'+ui.esc(source['url'])+'|'+ui.esc(source['title'][:200])+'>'))
    blocks.append(ui.para('The frozen outlet breakdown and complete source list are available in Coverage Desk → Briefings after sharing.'))
    blocks.extend(ui.para(c) for c in data['caveats'])
    return blocks

def snapshot_modal(draft,page=0,tab='sources'):
    data=draft['overview'];sources=data['sources'];page=min(max(0,page),max(0,(len(sources)-1)//5))
    blocks=[ui.para(data['client']+' · '+str(data['article_count'])+' article appearances / '+str(data['outlet_count'])+' outlets'),ui.context(period(data['scope']['window']))]
    blocks.append(ui.actions(ui.button('Sources','overview_snapshot_sources',0,tab=='sources'),ui.button('Outlet breakdown','overview_snapshot_outlets',0,tab=='outlets')))
    if tab=='outlets':
        outlets=data['outlets'];page=min(max(0,page),max(0,(len(outlets)-1)//12))
        blocks.extend(ui.para(o['name']+' — '+str(o['count'])+' articles') for o in outlets[page*12:page*12+12])
        controls=[]
        if page:controls.append(ui.button('Previous outlets','overview_outlets_previous',page-1))
        if (page+1)*12<len(outlets):controls.append(ui.button('More outlets','overview_outlets_next',page+1))
        if controls:blocks.append(ui.actions(*controls))
        return ui.modal('Coverage snapshot',blocks,metadata={'id':draft['id']})
    for s in sources[page*5:page*5+5]:
        blocks.extend([ui.section('*'+ui.esc(s['outlet_name'])+'*\n<'+ui.esc(s['url'])+'|'+ui.esc(s['title'])+'>'),
            ui.context(str(s['published'])+' · '+CONTENT_TYPES[s['content_type']]),ui.para(s['text'][:2000])])
        if s.get('classification_evidence',{}).get('quote'):blocks.append(ui.para('Content-type evidence: '+s['classification_evidence']['quote']))
    controls=[]
    if page:controls.append(ui.button('Previous sources','overview_sources_previous',page-1))
    if (page+1)*5<len(sources):controls.append(ui.button('More sources','overview_sources_next',page+1))
    if controls:blocks.append(ui.actions(*controls))
    blocks.append(ui.context(f'Sources {page*5+1}–{min((page+1)*5,len(sources))} of {len(sources)}. Frozen counts do not change when newer searches finish.'))
    return ui.modal('Coverage snapshot',blocks,metadata={'id':draft['id']})

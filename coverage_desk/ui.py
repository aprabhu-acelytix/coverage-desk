"""Native Slack views: quiet hierarchy, five rows, explicit disclosure and previews."""
import json
import time
from urllib.parse import urlsplit
from collections import Counter
from .config import DeskError
from .discovery import PLATFORMS, SOURCE_CHOICES, FILTER_CHOICES, DEFAULT_SOURCES, platform, source_label, finding_selection

def esc(text):
    return str(text).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def plain(text):
    return {'type':'plain_text','text':str(text),'emoji':False}

def section(text):
    return {'type':'section','text':{'type':'mrkdwn','text':text[:3000],'verbatim':True}}

def para(text):
    return {'type':'section','text':plain(str(text)[:3000])}

def context(text):
    return {'type':'context','elements':[{'type':'mrkdwn','text':text[:2000],'verbatim':True}]}

def header(text):
    return {'type':'header','text':plain(text[:150])}

def button(label,action,value='-',primary=False,confirm=None):
    b={'type':'button','text':plain(label[:75]),'action_id':action,'value':str(value)}
    if primary:b['style']='primary'
    if confirm:b['confirm']={'title':plain('Share with workspace?'),'text':plain(confirm),'confirm':plain('Share'),'deny':plain('Keep private')}
    return b

def actions(*elements):
    return {'type':'actions','elements':list(elements)}

def option(label,value):
    return {'text':plain(str(label)[:75]),'value':str(value)}

def select(action,choices,selected=None,placeholder='Choose'):
    opts=[option(a,b) for a,b in choices][:100]
    e={'type':'static_select','action_id':action,'placeholder':plain(placeholder),'options':opts}
    initial=next((o for o in opts if o['value']==str(selected)),None)
    if initial:e['initial_option']=initial
    return e

def input_text(key,label,value='',optional=False,multiline=False,max_length=300,hint=None):
    e={'type':'plain_text_input','action_id':'value','multiline':multiline,'max_length':max_length}
    if value:e['initial_value']=value
    block={'type':'input','block_id':key,'label':plain(label),'optional':optional,'element':e}
    if hint:block['hint']=plain(hint)
    return block

def input_select(key,label,choices,value=None):
    return {'type':'input','block_id':key,'label':plain(label),'element':select('value',choices,value)}

def modal(title,blocks,callback=None,metadata=None,submit='Save'):
    m={'type':'modal','title':plain(title[:24]),'close':plain('Close'),'blocks':blocks,'private_metadata':json.dumps(metadata or {},ensure_ascii=False)}
    if callback:m.update(callback_id=callback,submit=plain(submit))
    return m

def date(row):
    if not row.get('published'):return 'Publication date unknown'
    return row['published'][:10]+(' (page date)' if row.get('date_kind') not in ('publication','owner_confirmed') and row.get('provider','').startswith('Brave') else '')

def source_line(row):
    from .overview import CONTENT_TYPES
    publisher=row.get('outlet_name') or urlsplit(row['url']).hostname or 'Source'
    social=platform(row['url'])
    kind=CONTENT_TYPES.get(row.get('content_type'),row.get('source_kind','Web page'))
    return f"{esc(PLATFORMS[social][0] if social else publisher)} · {date(row)} · {esc(kind)}"


def author(user):
    import re
    return '<@'+user+'>' if re.fullmatch(r'[UW][A-Z0-9]+',user or '') else 'Teammate'


def finding_row(row,board=False,duplicates=1,can_delete=False,can_review=False):
    short=row['title'][:180]+('...' if len(row['title'])>180 else '')
    blocks=[section(f"*<{esc(row['url'])}|{esc(short)}>*"),context(source_line(row))]
    if board:
        blocks.append(context(f"{row['status']} · {'Workspace shared' if row['visibility']=='shared' else 'Private to you'} · {len(row['perspectives'])} perspectives"))
        controls=[button('View finding','inspect_board',row['id'])]
        if can_delete:controls.append(button('Delete','delete_board',row['id']))
        blocks.append(actions(*controls))
    else:
        reason=row.get('match_reason') or (row.get('analysis') or {}).get('explanation') or 'Needs assessment'
        if row.get('relevance')=='relevant':
            reason='Relevant'+(' | Publication date unverified' if row.get('date_status')=='unconfirmed' else '')
            if row.get('content_type')=='unknown':reason+=' | Article type unverified'
        priority=row.get('outlet_context',{}).get('priority_label')
        if priority and priority!='Standard priority':reason+=' | '+priority
        controls=[button('Inspect','inspect',row['id']),button('Save','save',row['id'])]
        if can_review and row.get('relevance')!='relevant':controls.append(button('Mark relevant','mark_relevant',row['id']))
        blocks.extend([context(esc(reason[:220])),actions(*controls)])
    blocks.append({'type':'divider'})
    return blocks


TAB_HELP={
    'explore':('Explore','Find coverage and check what it says.', 'Choose a client and period. Refresh searches and assesses evidence, then opens Coverage Overview. Select an outlet to inspect its articles, dates and message evidence. Save useful findings to the Team board, or preview an overview for sharing. Only the owner can start research. Filters change your view, never the stored findings.'),
    'board':('Team board','Save useful findings and discuss them with your team.', 'Findings saved from Explore appear here. Private findings are visible only to you. Workspace-shared findings let teammates add a perspective and update review status. Open a finding to contribute. Select saved findings when creating a briefing.'),
    'briefings':('Briefings','Turn selected findings into an editable, source-linked update.', 'Create a draft from up to five saved findings. Edit the wording and inspect the attached evidence. Only the owner can start AI or publish. Preview & publish shows the exact content and destination before anything is sent.')}


def help_modal(tab):
    title,short,description=TAB_HELP[tab]
    return modal('How '+title.lower()+' works',[header(title),para(short),para(description)])


def job_blocks(job):
    busy=job['state'] in ('Queued','Working')
    if job.get('run_id') or job['label']=='Collecting coverage':
        stage=job.get('stage','Queued') if busy else job['state']
        text=f"{stage} · {job.get('retained',0)} findings saved"
        if busy:
            text+=f"\nQueued → Searching → Saving → Ready\n{job.get('active_target') or 'Preparing collection'} · {job.get('checked_targets',0)} of {job.get('total_targets',0)} sources checked"
        elif stage in ('Partial results','Unavailable','Cancelled','Interrupted'):
            text+='\nYour saved findings are available. Open collection details to see what was not searched.'
        blocks=[para(text)]
        if job.get('error'):blocks.append(para(job['error']))
        if job.get('run_id'):blocks.append(actions(button('Collection details','run_status',job['run_id'])))
    else:blocks=[context(esc(job['label']+' · '+job['state']))]
    if busy and job.get('cancel_requested'):
        blocks.append(context('Stopping after the current request. Findings already saved will remain available.'))
    elif busy:blocks.append(actions(button('Cancel','cancel')))
    return blocks


def home(desk,actor):
    st=desk.store;p=st.preferences(actor);tab=p['tab'];owner=actor.user==desk.s.owner
    tabs=[('Explore','explore'),('Team board','board'),('Briefings','briefings')]
    navigation=section('   |   '.join('*'+label+'*' if tab==key else label for label,key in tabs))
    navigation['accessory']=select('nav_switch',tabs,tab,placeholder='Switch tab')
    blocks=[navigation,{'type':'divider'}]
    job=desk.jobs.get(actor.user)
    busy=job and job['state'] in ('Queued','Working')
    if desk.s.mode=='demo':blocks.append(context('Demo: synthetic evidence, no live research.'))
    if p.get('notice') and tab!='explore':blocks.append(para(p['notice']))
    if job and job.get('error') and not busy and tab!='explore':
        blocks.append(para(job['error']))
    if tab=='explore':
        monitors=st.list(actor,'monitor')
        selected=next((m for m in monitors if m['id']==p['monitor']),monitors[0] if monitors else None)
        if selected:
            if p['monitor']!=selected['id']:p=st.preferences(actor,{'monitor':selected['id'],'snapshot':time.time(),'page':0})
            controls=[select('monitor_select',[(m['name']+(' | '+m['campaign'] if m.get('campaign') else ''),m['id']) for m in monitors],selected['id'])]
            if owner:controls.append(button('Refresh','refresh',selected['id'],True))
            if owner:controls.append(button('Edit scope','edit_monitor',selected['id']))
            blocks.append(actions(*controls))
            blocks.append(context(esc(selected['campaign'] or 'General coverage')+' | '+range_label(selected.get('freshness','pw'))))
        else:
            blocks.extend([para('Find and assess public coverage, then save useful findings for your team.'),actions(button('Find coverage','new_monitor',primary=True))] if owner else
                          [para('Open Team board to review shared findings and add your perspective.')])
        if selected:
            from .overview_ui import home_blocks
            blocks.extend(home_blocks(desk,actor,selected,p))
        if p.get('notice'):blocks.append(para(p['notice']))
        if job and job.get('error') and not busy:blocks.append(para(job['error']))
    elif tab=='board':
        rows=st.list(actor,'board');bf=p.get('board_filter','all')
        controls=[select('board_filter',[('All saved','all'),('Workspace shared','shared'),('Private to me','private')],bf)]
        if bf!='all':rows=[r for r in rows if r['visibility']==bf]
        if owner and rows:controls.append(button('Create briefing','new_briefing',primary=True))
        blocks.append(actions(*controls))
        page=min(max(0,p['page']),max(0,(len(rows)-1)//5))
        for row in rows[page*5:page*5+5]:blocks.extend(finding_row(row,board=True,can_delete=row['owner']==actor.user or owner))
        if not rows:blocks.append(para('Save a finding from Explore to discuss it here. Choose private or workspace shared when saving.'))
        blocks.extend(pagination(page,len(rows)))
    else:
        rows=st.list(actor,'briefing')
        if owner and st.list(actor,'board'):blocks.append(actions(button('Create briefing','new_briefing',primary=True)))
        page=min(max(0,p['page']),max(0,(len(rows)-1)//5))
        for d in rows[page*5:page*5+5]:
            blocks.extend([section('*'+esc(d['title'])+'*'),context(d['status']+' | '+('Workspace shared' if d['visibility']=='shared' else 'Private')+' | '+str(len(d['sources']))+' source'+('' if len(d['sources'])==1 else 's'))])
            elems=[button('View draft' if d['status']=='Draft' else 'View briefing','draft_detail',d['id'])]
            if d['status']=='Draft':
                if not d.get('overview'):elems.append(button('Edit','edit_draft',d['id']))
                if owner:elems.append(button('Preview & publish','preview',d['id']))
            if d['owner']==actor.user or owner:elems.append(button('Delete','delete_briefing',d['id']))
            blocks.extend([actions(*elems),{'type':'divider'}])
        if not rows:blocks.append(para('Select saved findings on Team board to prepare an editable, source-linked briefing.'))
        blocks.extend(pagination(page,len(rows)))
    blocks.append(actions(button('About '+TAB_HELP[tab][0],'tab_help',tab),button('Settings','settings')))
    return {'type':'home','blocks':blocks}


def pagination(page,count):
    els=[]
    if page>0:els.append(button('Previous','page_previous',page-1))
    if (page+1)*5<count:els.append(button('Next','page_next',page+1))
    text=f'Showing {page*5+1}–{min((page+1)*5,count)} of {count}' if count else '0 findings'
    return [context(text)]+([actions(*els)] if els else [])


def range_label(value):
    return {'pd':'Past day','pw':'Past week','pm':'Past month','py':'Past year','':'Any time','any':'Any time'}.get(value,'Custom dates: '+str(value))


def assessment_label(value):
    return {'all':'All collected','review':'Needs review','relevant':'Relevant','uncertain':'Needs review','not_relevant':'Likely a different subject','unassessed':'Not analyzed yet'}.get(value,value)


def monitor_modal(m=None,expanded=False):
    m=m or {};editing=bool(m.get('id'))
    selected=m.get('sources',DEFAULT_SOURCES)
    source_input={'type':'input','block_id':'sources','label':plain('Where to search'),
        'hint':plain('Social sources use public web search, not a direct platform connection. Coverage may be limited.'),
        'element':{'type':'multi_static_select','action_id':'value','options':[option(a,b) for a,b in SOURCE_CHOICES],
                   'initial_options':[option(a,b) for a,b in SOURCE_CHOICES if b in selected]}}
    if not source_input['element']['initial_options']:
        source_input['element'].pop('initial_options')
    blocks=[input_text('name','Company, brand, or person',m.get('name',''),max_length=100,hint='Example: Patagonia'),
        input_text('campaign','Campaign or product focus',m.get('campaign',''),True,hint='Optional. General coverage is collected too.'),
        input_text('messages','Messages to check', '\n'.join(m.get('messages',[])),True,True,3000,hint='Optional, one per line. Example: The company supports repairing clothing. Research checks these against available evidence.'),
        input_select('freshness','Time range',[('Past day','pd'),('Past week','pw'),('Past month','pm'),('Past year','py'),('Any time','any')],m.get('freshness','pw') if m.get('freshness','pw') in ('pd','pw','pm','py') else 'any'),source_input,
        actions(button('Fewer options' if expanded else 'More options','monitor_options','hide' if expanded else 'show'))]
    if expanded:
        blocks.extend([input_select('research_path','Research path',[('Codex web research','Codex native web'),('AI-planned Brave','AI-planned Brave')],m.get('research_path','Codex native web')),
            input_text('aliases','Other names','\n'.join(m.get('aliases',[])),True,True,400,hint='Optional nicknames or abbreviations, one per line.'),
            input_text('domains','Official website or handles',m.get('domains',''),True,False,500,hint='Helps AI identify the right subject; does not restrict source discovery.'),
            input_text('interpretation','What should this search include?',m.get('interpretation',''),True,True,500,hint='Optional editorial scope. Leave blank for general coverage of the subject.'),
            input_text('notes','Help identify the right subject',m.get('notes',''),True,True,1000,hint='Example: Patagonia the clothing brand, not the region.'),
            input_select('language','Search language',[('English','en'),('Spanish','es'),('French','fr'),('German','de')],m.get('language','en')),
            input_select('country','Search region',[('United States','US'),('United Kingdom','GB'),('Canada','CA'),('Australia','AU')],m.get('country','US')),
            input_text('custom_range','Custom dates',m.get('custom_range') or (m.get('freshness','') if 'to' in m.get('freshness','') else ''),True,False,22,hint='Optional: YYYY-MM-DDtoYYYY-MM-DD. Overrides Time range; clear this to use Time range.')])
    blocks.append(context('Saving starts owner-operated research and evidence assessment. Publishing always needs a separate exact-preview confirmation.'))
    return modal('Edit coverage search' if editing else 'New coverage search',blocks,'monitor_submit',
                 {'id':m.get('id'),'expanded':expanded,'values':{k:v for k,v in m.items() if k in ('aliases','domains','notes','interpretation','research_path','language','country','custom_range')}},submit='Save & refresh' if editing else 'Find coverage')


def filters_modal(p):
    return modal('Filter findings',[input_select('source_filter','Platform or source',FILTER_CHOICES,p.get('source_filter','all')),
        input_select('history','Collection',[('Current search','current'),('Previous search scope','previous')],p.get('history','current')),
        context('Filters only change this view. No searches run and no findings are removed.')],'filters_submit',submit='Apply filters')


def detail(row,board=False,tab='overview',page=0):
    if tab not in ('overview','evidence','source','discussion'):raise DeskError('Unknown finding view.')
    ident=row['id'];meta={'id':ident,'board':board,'tab':tab,'page':page}
    blocks=[section(f"*<{esc(row['url'])}|{esc(row['title'])}>*"),context(source_line(row)),actions(
        *[button(label,'detail_'+key,key) for label,key in [('Overview','overview'),('Evidence','evidence'),('Source details','source'),('Discussion','discussion')]]),{'type':'divider'}]
    content=[]
    if tab=='overview':
        a=row.get('analysis')
        content=[header('Overview'),para(row['text'][:600]+('...' if len(row['text'])>600 else '') if row['text'] else 'No excerpt available. Open the original source to read more.'),context('Available text: '+row['access'])]
        full=row.get('full_title',row['title'])
        if full!=row['title']:content=[para(full[i:i+2200]) for i in range(0,len(full),2200)]+content
        content.append(para(a['explanation'] if a else 'Not analyzed yet. You can still inspect the source and save it to your board.'))
        if board:content.append(context(row['status']+' · '+('Workspace shared' if row['visibility']=='shared' else 'Private to you')))
    elif tab=='evidence':
        content=[header('Available source text')]
        excerpt=row['text'] or 'No excerpt available. Metadata only.'
        content.extend(para(excerpt[i:i+2200]) for i in range(0,len(excerpt),2200))
        a=row.get('analysis');content.append(header('AI assessment'))
        if not a:content.append(para('Not analyzed or not shared. This does not mean the source is irrelevant.'))
        else:
            content.append(para(assessment_label(a['relevance'])+' · '+a['explanation']))
            for m in a['messages']:
                label={'supported':'Supported in available text','contradicted':'Contradicted in available text','not_observed_in_available_text':'Not found in available text','insufficient_evidence':'Not enough evidence'}.get(m['label'],m['label'].replace('_',' ').capitalize())
                content.append(para(m['message']+'\n'+label+' · '+m['explanation']))
                for e in m['evidence']:
                    origin='Excerpt' if e['quote'] in row['text'] else 'Headline'
                    content.append(para(origin+' quote: '+chr(8220)+e['quote']+chr(8221)))
            content.append(context('AI interpretations need review. Matching quotes verify the words, not the conclusion.'))
    elif tab=='source':
        content=[header('Source details'),para('Discovery: '+('Found through Brave Web' if row['provider']=='Brave web' else row['provider'])),
                 para('Date: '+date(row)+'\nCollected: '+time.strftime('%d %b %Y, %H:%M UTC',time.gmtime(row['retrieved']))+'\nAvailable text: '+row['access'])]
        check=row.get('provenance',{}).get('publication_check',{})
        from .outlets import outlet_context
        outlet=row.get('outlet_context') or outlet_context(row)
        about=[header('About this outlet'),para(outlet['name']+' | '+outlet['host']+'\n'+outlet['description']),
            para('Significance: '+outlet['significance']+'\nEditorial signals: '+outlet['signals']),
            para('List priority: '+outlet['priority_label']+'\n'+outlet['priority_reason'])]
        if outlet['references']:
            about.append(section(' | '.join('<'+esc(r['url'])+'|'+esc(r['label'])+'>' for r in outlet['references'])))
            about.append(context('Profile reviewed '+outlet['reviewed_on']+'. Publisher-provided information; not a guarantee of article accuracy.'))
        content=about+content
        if check.get('status'):content.append(para('Public page check: '+check['status']))
        if board:content.append(para(row.get('verification','Provider-returned evidence.')))
        else:
            if row.get('content_type'):
                from .overview import CONTENT_TYPES
                content.extend([para('Outlet: '+row['outlet_name']+'\nContent: '+CONTENT_TYPES[row['content_type']]),
                    para('Match: '+{'relevant':'Relevant','not_relevant':'Not relevant','uncertain':'Needs attention','unassessed':'Assessment incomplete'}.get(row.get('relevance'),'Needs attention')),
                    para('Article-type evidence: '+row['classification_evidence']['method']+'\n'+row['classification_evidence'].get('quote','No supporting type evidence yet.')),
                    para('Outlet identity: '+row['outlet_evidence']['method']+'\n'+row['outlet_evidence'].get('reason',row['outlet_evidence']['domain']))])
                if row.get('redistribution'):content.append(para('Redistribution evidence: '+row['redistribution']))
                if row.get('correction_audit'):
                    audit=row['correction_audit']
                    content.extend([context('Owner correction by '+author(audit['owner'])+' · '+time.strftime('%d %b %Y, %H:%M UTC',time.gmtime(audit['created']))),para(audit['reason'])])
            prov=row.get('provenance',{});filters=prov.get('filters',{})
            profile=prov.get('publication_check',{}).get('source_profile',{})
            if profile:
                content.append(para('Observed publisher metadata\nPublisher: '+profile.get('publisher','Not established')+'\nByline: '+(', '.join(profile.get('authors',[])) or 'Not supplied')+'\nPage type: '+(', '.join(profile.get('article_types',[])) or 'Not supplied')))
            if prov.get('query'):content.append(para('Search terms: '+prov['query']))
            if prov.get('query_altered'):content.append(para('Provider adjusted the query: '+prov['query_altered']))
            if prov.get('target') in PLATFORMS and platform(row['url'])!=prov['target']:
                content.append(para('This page is outside the requested '+source_label(prov['target'])+' site. It is kept in All sources with its actual website attribution.'))
            if filters:content.append(para('Time range: '+range_label(filters.get('freshness',''))+'\nLanguage / region: '+filters.get('search_lang','Unknown')+' / '+filters.get('country','Unknown')+'\nSafe search: '+filters.get('safesearch','Unknown')+'\nResults page: '+str(prov.get('page',0)+1)))
            if prov.get('verification'):content.append(para(prov['verification']))
            observations=row.get('observations',[])
            if observations:
                content.append(para(str(len(observations))+' retained retrieval observations of this article.'))
                for observation in observations:
                    p=observation.get('provenance',{})
                    content.append(para(observation['provider']+' | '+time.strftime('%d %b %Y, %H:%M UTC',time.gmtime(observation['retrieved']))+
                        '\n'+str(p.get('query') or 'No query recorded')+'\n'+observation['url']))
        if platform(row['url']):content.append(context('A public page discovered through web search. This is not a direct social-platform integration.'))
    else:
        content=[header('Discussion')]
        if not board and row.get('comment'):content.append(para('Your private note: '+row['comment']))
        notes=row.get('perspectives',[])
        if not notes:content.append(para('No perspectives yet. Add your interpretation.' if board else 'Save this finding to the board to add a perspective.'))
        for note in notes:content.extend([context(author(note['author'])+' · '+time.strftime('%d %b, %H:%M UTC',time.gmtime(note['at']))),para(note['text'])])
    page=min(max(0,page),max(0,(len(content)-1)//6));meta['page']=page
    blocks.extend(content[page*6:page*6+6])
    if len(content)>6:
        els=[]
        if page:els.append(button('Previous section','detail_page_previous',page-1))
        if (page+1)*6<len(content):els.append(button('More','detail_page_next',page+1))
        blocks.extend([context(f'Section {page+1} of {(len(content)+5)//6}'),actions(*els)])
    blocks.append({'type':'divider'})
    if board:blocks.append(actions(button('Add perspective','perspective',ident),button('Review status','review',ident)))
    else:
        controls=[button('Save to board','save',ident)]
        if row.get('can_review'):
            controls.append(button('Edit finding','coverage_correct',ident))
            if row.get('relevance')!='relevant':controls.append(button('Mark relevant','mark_relevant',ident))
            if tab=='source':controls.append(button('Outlet priority','outlet_priority',ident))
        blocks.append(actions(*controls))
    return modal('Finding details',blocks,metadata=meta)


def collection_modal(run):
    if run.get('path')=='Codex native web':
        blocks=[para(run.get('interpretation') or 'Public coverage research'),context(run['path']+' | '+run.get('outcome','Researching')),
            para(f"{run.get('unique_count',0)} unique findings from {run['count']} observations. {run.get('assessed_count',0)} assessed; {run.get('pending_count',0)} pending."),
            para('Dates: '+str(run['scope']['window']['start'] or 'Any time')+' to '+run['scope']['window']['end']),
            para('Assessments use retained search evidence and available public publisher excerpts. Missing publication dates stay in Needs attention. Requested source categories guide search; this is not an exhaustive search of every platform.')]
        for status in run.get('statuses',[]):
            detail=str(status['results'])+' returned'
            if status['target'] in PLATFORMS:detail+='; '+str(status.get('platform_matches',0))+' on this platform'
            blocks.append(para(source_label(status['target'])+': '+status['status']+' ('+detail+')\n'+status['query']))
        for event in ([] if run.get('statuses') else run.get('observed_actions',[])):
            a=event.get('action') or {}
            text=event.get('query') or a.get('url') or 'Public web action'
            if a.get('queries'):text='; '.join(a['queries'])
            blocks.append(para(str(text)+'\n'+str(event.get('returned_results',0))+' observed source results'))
        if run.get('error'):blocks.append(para(run['error']))
        blocks.append(context('One source slot reserved per planned search plus one cancellation-boundary slot. Observable actions do not disclose the provider\'s internal request count. No automatic retries.'))
        return modal('Search details',blocks)
    blocks=[header(run.get('outcome','Collection details')),para(f"{run['count']} findings saved · Checked {time.strftime('%d %b, %H:%M UTC',time.gmtime(run['checked']))}")]
    if run.get('path')=='AI-planned Brave':
        blocks.extend([context('AI-planned Brave | No-tools evidence assessment'),para(run.get('interpretation') or 'Planning public coverage research')])
        for query in run.get('plan',[]):blocks.append(para(query['purpose'].capitalize()+': '+query['query']+'\n'+query['rationale']))
        blocks.append(para(f"{run.get('unique_count',0)} unique articles; {run.get('assessed_count',0)} assessed; {run.get('pending_count',0)} pending. Publication dates require publisher verification; Brave page dates may be modification dates."))
    statuses=run.get('statuses',[])
    for target in run.get('enabled_sources',['news','web']):
        entries=[x for x in statuses if x.get('target',x.get('source'))==target]
        total=sum(x.get('results',0) for x in entries)
        matches=sum(x.get('platform_matches',0) for x in entries)
        failures=list(dict.fromkeys(x['status'] for x in entries if x['status'] not in ('Results','No matches')))
        attempted=any(x.get('requested','checked' in x) for x in entries)
        message=('Not searched'+(': '+'; '.join(failures) if failures else '') if not attempted else
                 '; '.join(failures) if failures else 'No indexed matches returned' if not total else 'Search completed')
        count_text=f'{total} findings'
        if target in PLATFORMS and any('platform_matches' in x for x in entries):count_text+=f' ({matches} on this platform)'
        blocks.extend([section('*'+source_label(target)+'*'),para(count_text+': '+message)])
    blocks.append(context('Counts describe these searches, not all online coverage. Failed or capped searches are not retried automatically.'))
    blocks.append(context(f"Collection limits: up to {run['calls_cap']} requests and {run['pages_cap']} pages per query."))
    return modal('Collection details',blocks)


def briefing_blocks(d):
    if d.get('overview'):
        from .overview_ui import snapshot_blocks
        return snapshot_blocks(d)
    blocks=[header(d['title']),para(d['text']),header('Sources')]
    for source in d['sources']:
        blocks.append(section(f"<{esc(source['url'])}|{esc(source['title'])}>\n{esc(source['provider'])} · {esc(source['access'])}"))
    if 'perspectives' in d:
        blocks.append(header('Team perspectives'))
        if not d['perspectives']:blocks.append(para('No team perspectives added.'))
        if d.get('perspective_count',len(d['perspectives']))>len(d['perspectives']):
            blocks.append(context(f"Latest {len(d['perspectives'])} of {d['perspective_count']} perspectives included. Full discussion remains on the Team board."))
        for note in d['perspectives']:
            blocks.extend([context(author(note['author'])),para(note['text'])])
    if d.get('ai_evidence'):
        lookup=dict(zip(d['board_ids'],d['sources']))
        blocks.append(header('AI evidence · exact quotes'))
        for point in d['ai_evidence']['what_changed']+d['ai_evidence']['message_evidence']:
            source=lookup[point['source_id']]
            blocks.append(section(f"“{esc(point['quote'])}”\n<{esc(source['url'])}|{esc(source['title'])}>"))
        if d.get('edits'):blocks.append(context('Draft text was edited by a collaborator. These quotes preserve the original AI evidence for review.'))
    blocks.append(context('Coverage Desk · Reviewed snapshot of selected retrieved sources. Excerpts are not full articles.'))
    return blocks

def briefing_message(d):
    blocks=briefing_blocks(d)
    # Readable fallback includes the same content for screen readers/notifications.
    fallback=[]
    for block in blocks:
        if block['type'] in ('header','section'):
            text=block['text']['text']
            fallback.append(esc(text) if block['text']['type']=='plain_text' else text)
        elif block['type']=='context':fallback.extend(e['text'] for e in block['elements'])
    return {'text':'\n\n'.join(fallback),'blocks':blocks}

def settings_modal(desk,actor):
    s=desk.s
    blocks=[header('Sources & permissions'),para('Codex web research: Default. Public web discovery through the owner’s managed ChatGPT connection. Only the owner starts research.'),
        para('Optional Brave News / Web: '+('Connected configuration · storage permission supplied by owner, not independently verified.' if s.brave_key and s.storage_allowed else 'Requires a key and owner-supplied storage permission. Not needed for Codex web research.')),
        para('Manual contributions: Available. Submitted URLs are never fetched automatically.'),
        para('YouTube Data API: '+('Configured; metadata integration pending permitted-use review.' if s.youtube_key else 'Not connected. YouTube web discovery is available separately.')),
        para('X · Instagram · TikTok · Reddit: Not integrated. Social links found by Web Search are web-discovered only.'),
        header('AI & data'),para('Only the configured owner initiates Codex analysis. Selected source evidence and monitor criteria go to ChatGPT/Codex; team notes do not. ChatGPT data controls apply. Local execution does not mean offline inference.'),
        para('Seven-day maximum retention. Local SQLite is not encrypted. Already published Slack copies and provider-held data are not deleted by local expiry.'),
        header('Scheduling'),para('Optional source-refresh previews. Disabled until configured locally and explicitly enabled by the owner. Never scheduled AI or automatic channel posts.')]
    if actor.user==s.owner:
        usage=desk.store.budgets()
        blocks.append(para(f"Recorded usage: {usage['source']['used']} source slots · {usage['ai']['used']} AI jobs. No lifetime app cap. Per-search safeguards and provider limits still apply."))
        blocks.append(para('AI connection: '+desk.runtime_state))
        blocks.append(actions(button('Check AI connection','runtime_check'),button('Configure schedule','schedule')))
    return modal('Settings & sources',blocks)

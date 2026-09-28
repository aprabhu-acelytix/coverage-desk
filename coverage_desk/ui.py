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
    return row.get('published','')[:10] if row.get('published') else 'Publication date unknown'

def source_line(row):
    publisher=urlsplit(row['url']).hostname or 'Source'
    social=platform(row['url'])
    return f"{esc(PLATFORMS[social][0] if social else publisher)} · {date(row)}"


def author(user):
    import re
    return '<@'+user+'>' if re.fullmatch(r'[UW][A-Z0-9]+',user or '') else 'Teammate'


def finding_row(row,board=False,duplicates=1):
    blocks=[section(f"*<{esc(row['url'])}|{esc(row['title'])}>*"),context(source_line(row))]
    if board:
        blocks.append(context(f"{row['status']} · {'Workspace shared' if row['visibility']=='shared' else 'Private to you'} · {len(row['perspectives'])} perspectives"))
        blocks.append(actions(button('View finding','inspect_board',row['id'])))
    else:
        assessment=row.get('analysis')
        label={'relevant':'Relevant to this client','uncertain':'Needs review','not_relevant':'Likely a different subject'}
        status=label.get((assessment or {}).get('relevance'),'Not analyzed yet')
        if duplicates>1:status+=f' · {duplicates} matching records'
        blocks.extend([context(status),actions(button('View finding','inspect',row['id']),button('Save to board','save',row['id']))])
    blocks.append({'type':'divider'})
    return blocks


TAB_HELP={
    'explore':('Explore','Find coverage and check what it says.', 'Choose or create a coverage search. Collect sources, open a finding to inspect the available evidence, then save useful findings to your board. AI analysis is optional and only the owner can start it. Filters change your view, never the stored findings.'),
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
    title,description,_=TAB_HELP[tab]
    blocks=[header('Coverage Desk'),actions(button('Explore','nav_explore','explore'),button('Team board','nav_board','board'),button('Briefings','nav_briefings','briefings')),
            {'type':'divider'},header(title),para(description),actions(button('How it works','tab_help',tab),button('Settings','settings'))]
    job=desk.jobs.get(actor.user)
    if job and (job['state'] in ('Queued','Working') or
                (tab=='explore' and (not job.get('monitor_id') or job['monitor_id']==p.get('monitor')))):
        blocks.extend(job_blocks(job))
    if desk.s.mode=='demo':blocks.append(context('Demo · Synthetic examples, no live retrieval or AI.'))
    if p.get('notice'):blocks.append(para(p['notice']))
    if tab=='explore':
        monitors=st.list(actor,'monitor')
        selected=next((m for m in monitors if m['id']==p['monitor']),monitors[0] if monitors else None)
        if selected:
            if p['monitor']!=selected['id']:p=st.preferences(actor,{'monitor':selected['id'],'snapshot':time.time(),'page':0})
            blocks.append(actions(select('monitor_select',[(m['name'],m['id']) for m in monitors],selected['id'])))
            blocks.append(context(esc(selected['campaign'] or 'General coverage')+' · '+range_label(selected.get('freshness','pw'))))
            if owner:blocks.append(actions(button('Collect coverage','refresh',selected['id'],True),button('New coverage search','new_monitor'),button('Edit search','edit_monitor',selected['id'])))
        elif owner:
            blocks.extend([para('Start with a company, brand, or person. Add campaign messages only if you want to check for them.'),actions(button('New coverage search','new_monitor',primary=True))])
        else:blocks.append(para('Your team’s shared findings are on the Team board. You can also contribute a source here.'))
        if 'snapshot' not in p:p=st.preferences(actor,{'snapshot':time.time()})
        selection=finding_selection(st,actor,p);rows=selection['rows'];page=selection['page']
        blocks.append(actions(button('Filters','filters'),button('Add a source','manual')))
        filt=p.get('filter','all');sf=p.get('source_filter','all')
        blocks.append(context({value:label for label,value in FILTER_CHOICES}.get(sf,'All sources')+' · '+assessment_label(filt)))
        if filt!='all' or sf!='all':blocks.append(actions(button('Clear filters','clear_filters')))
        if selection['new']:blocks.append(actions(button(f"Show {selection['new']} new findings",'show_new')))
        if selected and not (job and job.get('monitor_id')==selected['id']):
            runs=[r for r in st.list(actor,'run') if r['monitor_id']==selected['id']]
            if runs:
                r=runs[0];blocks.append(context(f"Last collection: {r.get('outcome','Saved')} · {r['count']} findings"))
                blocks.append(actions(button('Collection details','run_status',r['id'])))
        if owner and selection['visible'] and selected:
            eligible=[r for r in selection['visible'] if r.get('monitor_id')==selected['id']]
            if eligible:blocks.append(actions(button(f'Analyze these {len(eligible)} findings','analyze_page',selected['id'])))
        counts=Counter(r['canonical'] for r in rows)
        for row in selection['visible']:blocks.extend(finding_row(row,duplicates=counts[row['canonical']]))
        if not rows:
            if selected and sf in PLATFORMS and sf not in selected['sources']:
                blocks.append(para(source_label(sf)+' has not been targeted by this search. Edit search to include it, then collect coverage. Any links found through general Web search also appear here.'))
            else:
                blocks.append(para('No findings match these filters. Clear filters or collect coverage from the selected sources.' if filt!='all' or sf!='all' else 'Findings will appear here after collection. You can also add a source yourself.'))
        blocks.extend(pagination(page,len(rows)))
    elif tab=='board':
        rows=st.list(actor,'board');bf=p.get('board_filter','all')
        blocks.append(actions(select('board_filter',[('All saved','all'),('Workspace shared','shared'),('Private to me','private')],bf)))
        if bf!='all':rows=[r for r in rows if r['visibility']==bf]
        if owner and rows:blocks.append(actions(button('Create briefing','new_briefing',primary=True)))
        page=min(max(0,p['page']),max(0,(len(rows)-1)//5))
        for row in rows[page*5:page*5+5]:blocks.extend(finding_row(row,board=True))
        if not rows:blocks.append(para('Save a useful finding from Explore. Choose Private to me or Shared with this workspace.'))
        blocks.extend(pagination(page,len(rows)))
    else:
        rows=st.list(actor,'briefing')
        if owner and st.list(actor,'board'):blocks.append(actions(button('Create briefing','new_briefing',primary=True)))
        page=min(max(0,p['page']),max(0,(len(rows)-1)//5))
        for d in rows[page*5:page*5+5]:
            blocks.extend([section('*'+esc(d['title'])+'*'),context(f"{d['status']} · {'AI-assisted' if d.get('ai_evidence') else 'Source-linked'} · {'Workspace shared' if d['visibility']=='shared' else 'Private'} · {len(d['sources'])} sources")])
            elems=[button('View draft','draft_detail',d['id'])]
            if d['status']=='Draft':
                elems.append(button('Edit','edit_draft',d['id']))
                if owner:elems.append(button('Preview & publish','preview',d['id']))
            blocks.extend([actions(*elems),{'type':'divider'}])
        if not rows:blocks.append(para('Start by saving findings to the Team board, then choose Create briefing.'))
        blocks.extend(pagination(page,len(rows)))
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
    return {'all':'All assessments','relevant':'Relevant','uncertain':'Needs review','not_relevant':'Likely a different subject','unassessed':'Not analyzed yet'}.get(value,value)


def monitor_modal(m=None,expanded=False):
    m=m or {};editing=bool(m.get('id'))
    selected=m.get('sources',DEFAULT_SOURCES)
    source_input={'type':'input','block_id':'sources','label':plain('Where to search'),
        'hint':plain('Social sites use Brave’s public web index, not a direct platform connection. Coverage may be limited.'),
        'element':{'type':'multi_static_select','action_id':'value','options':[option(a,b) for a,b in SOURCE_CHOICES],
                   'initial_options':[option(a,b) for a,b in SOURCE_CHOICES if b in selected]}}
    if not source_input['element']['initial_options']:
        source_input['element'].pop('initial_options')
    blocks=[input_text('name','Company, brand, or person',m.get('name',''),max_length=100,hint='Example: Patagonia'),
        input_text('campaign','Campaign or product focus',m.get('campaign',''),True,hint='Optional. General coverage is collected too.'),
        input_text('messages','Messages to check', '\n'.join(m.get('messages',[])),True,True,3000,hint='Optional, one per line. Example: The company supports repairing clothing. AI checks these only when you ask.'),
        input_select('freshness','Time range',[('Past day','pd'),('Past week','pw'),('Past month','pm'),('Past year','py'),('Any time','any')],m.get('freshness','pw') if m.get('freshness','pw') in ('pd','pw','pm','py') else 'any'),source_input,
        actions(button('Fewer options' if expanded else 'More options','monitor_options','hide' if expanded else 'show'))]
    if expanded:
        blocks.extend([input_text('aliases','Other names','\n'.join(m.get('aliases',[])),True,True,400,hint='Optional nicknames or abbreviations, one per line.'),
            input_text('domains','Official website or handles',m.get('domains',''),True,False,500,hint='Helps AI identify the right subject; does not restrict source discovery.'),
            input_text('notes','Help identify the right company',m.get('notes',''),True,True,1000,hint='Example: Patagonia the clothing brand, not the region.'),
            input_select('language','Search language',[('English','en'),('Spanish','es'),('French','fr'),('German','de')],m.get('language','en')),
            input_select('country','Search region',[('United States','US'),('United Kingdom','GB'),('Canada','CA'),('Australia','AU')],m.get('country','US')),
            input_text('custom_range','Custom dates',m.get('custom_range') or (m.get('freshness','') if 'to' in m.get('freshness','') else ''),True,False,22,hint='Optional: YYYY-MM-DDtoYYYY-MM-DD. Overrides Time range; clear this to use Time range.')])
    blocks.append(context('Only source collection starts on save. AI analysis and publishing are separate actions.' if not editing else 'Saving changes does not start collection.'))
    return modal('Edit coverage search' if editing else 'New coverage search',blocks,'monitor_submit',
                 {'id':m.get('id'),'expanded':expanded,'values':{k:v for k,v in m.items() if k in ('aliases','domains','notes','language','country','custom_range')}},submit='Save changes' if editing else 'Save & collect')


def filters_modal(p):
    return modal('Filter findings',[input_select('source_filter','Platform or source',FILTER_CHOICES,p.get('source_filter','all')),
        input_select('filter','Assessment',[(assessment_label(k),k) for k in ('all','relevant','uncertain','not_relevant','unassessed')],p.get('filter','all')),
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
                for e in m['evidence']:content.append(para('Source quote: '+chr(8220)+e['quote']+chr(8221)))
            content.append(context('AI interpretations need review. Matching quotes verify the words, not the conclusion.'))
    elif tab=='source':
        content=[header('Source details'),para('Discovery: '+('Found through Brave Web' if row['provider']=='Brave web' else row['provider'])),
                 para('Published: '+date(row)+'\nCollected: '+time.strftime('%d %b %Y, %H:%M UTC',time.gmtime(row['retrieved']))+'\nAvailable text: '+row['access'])]
        if board:content.append(para(row.get('verification','Provider-returned evidence.')))
        else:
            prov=row.get('provenance',{});filters=prov.get('filters',{})
            if prov.get('query'):content.append(para('Search terms: '+prov['query']))
            if prov.get('query_altered'):content.append(para('Provider adjusted the query: '+prov['query_altered']))
            if prov.get('target') in PLATFORMS and platform(row['url'])!=prov['target']:
                content.append(para('This page is outside the requested '+source_label(prov['target'])+' site. It is kept in All sources with its actual website attribution.'))
            if filters:content.append(para('Time range: '+range_label(filters.get('freshness',''))+'\nLanguage / region: '+filters.get('search_lang','Unknown')+' / '+filters.get('country','Unknown')+'\nSafe search: '+filters.get('safesearch','Unknown')+'\nResults page: '+str(prov.get('page',0)+1)))
            if prov.get('verification'):content.append(para(prov['verification']))
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
    else:blocks.append(actions(button('Save to board','save',ident)))
    return modal('Finding details',blocks,metadata=meta)


def collection_modal(run):
    blocks=[header(run.get('outcome','Collection details')),para(f"{run['count']} findings saved · Checked {time.strftime('%d %b, %H:%M UTC',time.gmtime(run['checked']))}")]
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
    blocks=[header('Sources & permissions'),para('Brave News / Web: '+('Connected configuration · storage permission supplied by owner, not independently verified.' if s.brave_key and s.storage_allowed else 'Awaiting key or storage permission.')),
        para('Manual contributions: Available. Submitted URLs are never fetched automatically.'),
        para('YouTube Data API: '+('Configured; metadata integration pending permitted-use review.' if s.youtube_key else 'Not connected. YouTube web discovery is available separately.')),
        para('X · Instagram · TikTok · Reddit: Not integrated. Social links found by Web Search are web-discovered only.'),
        header('AI & data'),para('Only the configured owner initiates Codex analysis. Selected source evidence and monitor criteria go to ChatGPT/Codex; team notes do not. ChatGPT data controls apply. Local execution does not mean offline inference.'),
        para('Seven-day maximum retention. Local SQLite is not encrypted. Already published Slack copies and provider-held data are not deleted by local expiry.'),
        header('Scheduling'),para('Optional source-refresh previews. Disabled until configured locally and explicitly enabled by the owner. Never scheduled AI or automatic channel posts.')]
    if actor.user==s.owner:
        usage=desk.store.budgets()
        blocks.append(para(f"Source requests: {usage['source']['used']} of {usage['source']['cap']} · AI jobs: {usage['ai']['used']} of {usage['ai']['cap']}"))
        blocks.append(para('AI connection: '+desk.runtime_state))
        blocks.append(actions(button('Check AI connection','runtime_check'),button('Configure schedule','schedule')))
    return modal('Settings & sources',blocks)

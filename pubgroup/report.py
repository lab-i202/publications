"""Scientific production report in LaTeX, with conferences and a linked roster."""
import shutil
import subprocess
from datetime import date
from pathlib import Path
from . import __version__, BUILD
from .events import conferences, display_name
from .model import TYPES, metrics, tex_escape, safe_url

E = tex_escape

def link(url, label):
    url=safe_url(url)
    return r'\href{'+E(url)+'}{'+E(label)+'}' if url else ''

def event_dates(event):
    start,end=event.get('start_date'),event.get('end_date')
    if not start:return str(event.get('year',''))+' · dates unavailable'
    a,b=date.fromisoformat(start),date.fromisoformat(end)
    if a.year==b.year and a.month==b.month:
        return f'{a.day}-{b.day} {a:%B %Y}' if a!=b else f'{a.day} {a:%B %Y}'
    return f'{a.day} {a:%B %Y} - {b.day} {b:%B %Y}'

def chart(dataset, m):
    lines=[]
    years={p.get('date','')[:4] for p in dataset['publications'] if p.get('date')}
    if len(years)>1:lines.append('Calendar months combined across the selected years.')
    known=[sum(v for k,v in m['publication_months'].items() if k.endswith(f'-{i:02}')) for i in range(1,13)]
    events=[sum(v for k,v in m['conference_months'].items() if k.endswith(f'-{i:02}')) for i in range(1,13)]
    maximum=max([1]+[a+b for a,b in zip(known,events)])
    lines.append(r'\begin{tikzpicture}[x=1.12cm,y=1cm]')
    for i,(pub,event) in enumerate(zip(known,events)):
        a,b=2.6*pub/maximum,2.6*(pub+event)/maximum
        lines.append(r'\fill[accent] ('+f'{i+.1},0) rectangle ({i+.7},{a:.4f});')
        lines.append(r'\fill[teal] ('+f'{i+.1},{a:.4f}) rectangle ({i+.7},{b:.4f});')
        month=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][i]
        lines.append(r'\node[font=\scriptsize,text=muted] at ('+f'{i+.4},-.3)'+'{'+month+'};')
        if pub+event:lines.append(r'\node[font=\scriptsize] at ('+f'{i+.4},{b+.18:.4f})'+'{'+str(pub+event)+'};')
    lines.append(r'\draw[line] (0,0)--(12,0);\end{tikzpicture}')
    lines.append(r'{\small\color{accent}\rule{8pt}{8pt} Publication month\quad'+r'\color{teal}\rule{8pt}{8pt} Verified conference month}')
    lines.append(E(f"{sum(known)+sum(events)} of {m['total']} outputs have a known publication or conference month. {m['unknown_month']} have no known month."))
    lines.append(r'{\small\color{muted}Conference contributions use the event month when their publication month is missing. Event dates do not change the bibliographic publication date.}')
    return lines

def render_tex(dataset):
    pubs=dataset['publications'];m=metrics(pubs);events=conferences(pubs)
    period,group=dataset['period_label'],dataset['group']
    lines=[r'''\documentclass[11pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{texgyreheros}[Extension=.otf,UprightFont=*-regular,BoldFont=*-bold,ItalicFont=*-italic,BoldItalicFont=*-bolditalic]
\usepackage[margin=22mm,headheight=16pt]{geometry}
\usepackage{xcolor,hyperref,fancyhdr,tabularx,booktabs,needspace,tikz}
\definecolor{ink}{HTML}{15181D}
\definecolor{muted}{HTML}{697386}
\definecolor{accent}{HTML}{2367D1}
\definecolor{teal}{HTML}{17815B}
\definecolor{pale}{HTML}{EDF4FF}
\definecolor{line}{HTML}{D9DEE7}
\hypersetup{colorlinks=true,urlcolor=accent,linkcolor=accent,pdfauthor={Publication Group},pdftitle={Scientific production}}
\color{ink}\setlength{\parindent}{0pt}\setlength{\parskip}{7pt}
\renewcommand{\arraystretch}{1.22}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\small\color{muted}SCIENTIFIC PRODUCTION}
\fancyhead[R]{\small\color{muted}'''+E(period)+r'''}
\fancyfoot[L]{\scriptsize\color{muted}'''+E(group)+r'''}
\fancyfoot[R]{\small\color{muted}\thepage}
\renewcommand{\headrulewidth}{0.3pt}\emergencystretch=4em
\begin{document}\thispagestyle{empty}
{\color{accent}\rule{\linewidth}{3pt}}
\vspace{14mm}

{\small\color{accent}\bfseries '''+E(group.upper())+r'''}
\vspace{5mm}

{\fontsize{32}{37}\selectfont\bfseries Scientific production}

{\fontsize{25}{30}\selectfont\color{muted}'''+E(period)+r'''}
\vspace{8mm}

Publications, conference contributions and research activity from the group.

{\small\color{muted}Prepared '''+E(dataset['generated_at'][:10])+r'''}
\vspace{12mm}

\begin{tabularx}{\linewidth}{@{}XXX@{}}
{\fontsize{29}{34}\selectfont\bfseries '''+str(m['total'])+r'''} &
{\fontsize{29}{34}\selectfont\bfseries '''+str(m['conference_records'])+r'''} &
{\fontsize{29}{34}\selectfont\bfseries '''+str(len(events))+r'''}\\
Scientific outputs & Conference contributions & Conferences represented\\
\end{tabularx}
\vspace{10mm}

This report brings together journal articles, conference papers, book chapters,
posters, abstracts and other scientific outputs. Shared publications appear once.
Accepted and in-press work is labelled alongside published work.

The following pages present an overview of the scientific output, conference
participation, the bibliography and the researchers considered in the report.

\vfill
{\small\color{muted}Based on the researchers' public publication records.}
''']
    if any(s['status']!='ok' for s in dataset.get('sources',[])):
        lines.append(r'{\small\color{muted}Some profiles were unavailable; their previously collected publications are included.}')
    lines += [r'\newpage\section*{Scientific output}',r'\begin{tabularx}{\linewidth}{@{}Xr@{}}\toprule Output & Total\\\midrule']
    for kind,count in sorted(m['types'].items(),key=lambda x:(-x[1],x[0])):
        lines.append(E(TYPES.get(kind,kind))+' & '+str(count)+r'\\')
    lines += [r'\bottomrule\end{tabularx}',r'\subsection*{Scientific output by month}']+chart(dataset,m)
    lines += [r'\newpage\section*{Conferences and participation}',
        'Conferences associated with the group\'s papers, posters and abstracts. A listed contribution does not establish which authors attended; confirmed attendance is identified where available.']
    if not events:lines.append('No conference contributions are listed for this period.')
    for event in events:
        lines += [r'\par\begin{minipage}{\linewidth}',r'{\small\color{accent}\bfseries '+E(event_dates(event))+'}',
                  r'{\large\bfseries '+E(event['name'])+'}']
        if event.get('location'):lines.append(E(event['location']))
        lines.append(E(' · '.join(f'{count} {TYPES[kind].lower()}{"s" if count!=1 else ""}' for kind,count in sorted(event['types'].items()))))
        lines.append(r'{\small\color{muted}'+('Attendance confirmed.' if event.get('confirmed_attendees') else 'Contributions listed; individual attendance not confirmed.')+'}')
        if event.get('source_url'):lines.append(link(event['source_url'],'Conference dates and information'))
        lines += [r'{\color{line}\rule{\linewidth}{0.35pt}}',r'\end{minipage}\par\vspace{3mm}']
    lines += [r'\newpage\section*{Publications}']
    if not pubs:lines.append('No scientific outputs are listed for the selected period.')
    for i,p in enumerate(pubs,1):
        if len(pubs)<=20 and i>1 and (i-1)%4==0:lines.append(r'\newpage')
        tags=[p.get('date') or 'Date unavailable',TYPES.get(p['type'],p['type'])]
        if p['status'] in ('accepted','in press'):tags.append(p['status'].capitalize())
        lines += [r'\par\begin{minipage}{\linewidth}',r'{\small\color{accent}\bfseries '+E(f'{i:02}  '+' | '.join(tags))+'}',
                  r'{\large\bfseries '+E(p['title'])+'}',E('; '.join(display_name(a) for a in p['authors']))]
        if p.get('venue'):lines.append(r'{\small '+E(p['venue'])+'}')
        if p.get('event'):
            e=p['event'];text='Conference: '+event_dates(e)
            if e.get('location'):text+=' · '+e['location']
            lines.append(r'{\small\color{muted}'+E(text)+'}')
        links=[link(p.get('url'),'Publication')]
        if p.get('doi') and p.get('doi_check',{}).get('status')!='title conflict':
            links.append(link('https://doi.org/'+p['doi'],'DOI: '+p['doi']))
        if any(links):lines.append(r'{\small '+r'\quad '.join(x for x in links if x)+'}')
        lines += [r'{\color{line}\rule{\linewidth}{0.35pt}}',r'\end{minipage}\par\vspace{3mm}']
    lines += [r'\newpage\section*{Researchers considered}',
              'The report considers publications listed on the following public researcher profiles.']
    for r in dataset['researchers']:
        lines += [r'\Needspace{3\baselineskip}',r'{\bfseries '+E(display_name(r['name']))+'}'+r'\par',
                  link(r['url'],'CiênciaVitae · '+r['id'])+r'\par\vspace{2mm}']
    lines.append(r'\vfill{\scriptsize\color{muted}Publication Group '+E(__version__)+' · build '+E(BUILD)+r'}\end{document}')
    return '\n\n'.join(lines)+'\n'

def write_report(dataset, folder, compile_pdf=True):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    tex=folder/'publications.tex';pdf=tex.with_suffix('.pdf')
    tex.write_text(render_tex(dataset),encoding='utf-8');pdf.unlink(missing_ok=True)
    if not compile_pdf:return tex,None
    compiler=shutil.which('xelatex')
    if not compiler:raise RuntimeError('XeLaTeX is required. Install MacTeX, TeX Live or MiKTeX, or use --no-pdf.')
    for _ in range(2):
        r=subprocess.run([compiler,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error',tex.name],cwd=folder,capture_output=True,text=True,timeout=180)
        if r.returncode:
            (folder/'build-error.log').write_text(r.stdout+r.stderr)
            raise RuntimeError('LaTeX failed; see '+str(folder/'build-error.log'))
    if not pdf.is_file():raise RuntimeError('XeLaTeX returned without a PDF')
    return tex,pdf

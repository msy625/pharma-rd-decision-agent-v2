
class Component extends DCLogic {
  state = {
    page:'today', theme:'light', present:false, navOpen:false,
    company:'恒瑞医药', compareCompany:'复星医药', year:2024, scope:'industry', topK:5, demoStep:0,
    deepseek:true, anim:0,
    chatMsgs:null, chatInput:'', chatActive:0, chatLoading:false, chatConvs:null, chatConvId:null, chatSidebar:true, chatSettings:false, chatCtxOn:true, chatModel:'flash',
    cmpTab:'profile',
    resMode:'single', resTopic:'', resList:'恒瑞医药、复星医药、药明康德', resLoading:false, resDone:true, resBatchActive:0, resData:{},
    evidenceKind:'search', evidenceQuery:'NSCLC', evidenceLatestOnly:true, evidenceLimit:50,
    evidenceSummary:null, evidenceItems:[], evidenceCount:0, evidenceSelected:null,
    evidenceLoading:false, evidenceSummaryLoading:false, evidenceDetailLoading:false,
    evidenceError:'', evidenceHasSearched:false,
    evidenceTab:'sources',
    chainSummary:null, chainCompany:'', chainType:'', chainItems:[], chainSelected:null, chainUnresolved:[],
    chainLoading:false, chainSummaryLoading:false, chainDetailLoading:false, chainUnresolvedLoading:false,
    chainError:'', chainLoaded:false, chainUnresolvedOpen:false,
    comparisonCompanyA:'恒瑞医药', comparisonCompanyB:'BeOne Medicines',
    companyComparison:null, metricRules:[], companyComparisonLoading:false, metricRulesLoading:false,
    companyComparisonError:'', companyComparisonLoaded:false, metricRulesOpen:false,
    groundedCapabilities:null, groundedCapabilitiesLoading:false, groundedCapabilitiesLoaded:false,
    groundedQuestion:'', groundedMode:'local', groundedLoading:false, groundedError:'',
    groundedResult:null, groundedMeta:null, groundedTraceOpen:false, groundedSeq:0,
    runtimeCapabilities:null, runtimeCapabilitiesLoaded:false, runtimeCapabilitiesLoading:false,
    legacyNotice:'',
    evidenceWorkbench:null, evidenceWorkbenchLoading:false, evidenceWorkbenchLoaded:false, evidenceWorkbenchError:'',
    wbTab:'flow',
    dbTable:'fact_financial', dbSearch:'',
    advLoading:false, advDone:true, advData:null,
    api:{}
  };

  D = {
    companies:['恒瑞医药','复星医药','药明康德','智飞生物','华兰生物','迈瑞医疗','长春高新','云南白药','片仔癀','信达生物','百济神州','华东医药','科伦药业','人福医药','信立泰'],
    industries:['医药生物','化学制药','生物制品','中药','医疗器械','医疗服务'],
    years:[2024,2023,2022,2021,2020],
    stats:{companies:48, documents:312, financial_facts:18642, macro_facts:1286},
    trendYears:['2020','2021','2022','2023','2024'],
    rev:[277.4,259.1,212.8,228.2,279.9],
    np:[63.3,45.3,39.1,43.0,63.4],
    rd:[49.9,62.0,48.9,49.5,65.8],
    gm:[87.9,85.6,83.6,84.9,86.6],
    ranking:[
      {name:'复星医药',value:410.7},{name:'华东医药',value:406.2},{name:'恒瑞医药',value:279.9,sel:true},
      {name:'人福医药',value:244.6},{name:'科伦药业',value:221.6},{name:'信立泰',value:39.5}
    ],
    alerts:[
      {severity:'高',company:'复星医药',year:2024,category:'风险',signal:'商誉减值规模偏高',detail:'商誉账面价值占净资产 18.4%，并购整合后续减值压力需持续关注。'},
      {severity:'中',company:'恒瑞医药',year:2024,category:'财务',signal:'应收账款周转放缓',detail:'应收账款周转天数同比上升 9 天，需关注集采放量下的回款节奏。'},
      {severity:'中',company:'恒瑞医药',year:2024,category:'合规',signal:'研发资本化为零',detail:'研发投入全部费用化，口径稳健但短期压低当期利润弹性。'},
      {severity:'低',company:'华东医药',year:2024,category:'创新',signal:'创新管线集中度高',detail:'核心收入对单一治疗领域依赖度较高，需关注产品迭代风险。'}
    ],
    fosun:{rev:[303.0,390.0,439.0,414.0,410.7],np:[37.0,47.4,37.3,23.9,27.7],rd:[40.0,49.0,52.0,55.8,55.0],gm:[55.0,58.0,53.0,49.0,47.8]},
    /*__DATA__*/
  };

  // ---- helpers ----
  cu(t,dec){ const k=this.state.anim; const v=t*k; if(dec) return v.toFixed(dec); return Math.round(v); }
  nf(n){ return Number(n).toLocaleString('en-US'); }
  yi(){ return this.D.trendYears.indexOf(String(this.state.year)); }

  _legacyPages(){ return {chat:1,compare:1,research:1,whitebox:1,database:1,timeline:1,advanced:1}; }
  _legacyAvailable(){ const c=this.state.runtimeCapabilities; return !!(c&&c.legacy_features_available); }
  _legacyReason(){ const c=this.state.runtimeCapabilities||{}; return c.legacy_unavailable_reason||'旧数据未配置'; }
  _isLegacyPage(p){ return !!this._legacyPages()[p]; }
  _paths(paths){
    const R=(typeof React!=='undefined')?React:null;
    if(!R) return null;
    return (Array.isArray(paths)?paths:[]).filter(Boolean).map((d,i)=>R.createElement('path',{key:i,d}));
  }
  _trendSvg(area,line){
    const R=(typeof React!=='undefined')?React:null;
    if(!R||!area||!line) return null;
    return [
      R.createElement('polyline',{key:'area',points:area,fill:'var(--brand-50)',stroke:'none'}),
      R.createElement('polyline',{key:'line',points:line,fill:'none',stroke:'var(--brand-500)',strokeWidth:2,vectorEffect:'non-scaling-stroke',strokeLinejoin:'round',strokeLinecap:'round'})
    ];
  }
  _edgeSvg(edges){
    const R=(typeof React!=='undefined')?React:null;
    if(!R) return null;
    return (Array.isArray(edges)?edges:[]).filter(g=>g&&g.x1!=null&&g.y1!=null&&g.x2!=null&&g.y2!=null).map((g,i)=>R.createElement('line',{key:i,x1:g.x1,y1:g.y1,x2:g.x2,y2:g.y2,stroke:'var(--border-strong)',strokeWidth:0.4}));
  }
  go(p){
    if(this._isLegacyPage(p) && !this._legacyAvailable()){
      this.setState({page:'evidence', navOpen:false, anim:0, legacyNotice:'旧数据未配置：'+this._legacyReason()}, ()=>{ this.runCount(); this.loadEvidencePage(); });
      return;
    }
    this.setState({page:p, navOpen:false, anim:0, legacyNotice:''}, ()=>{ this.runCount(); this.loadPage(); });
  }
  runCount(){
    if(this._raf) cancelAnimationFrame(this._raf);
    if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches){ this.setState({anim:1}); return; }
    const t0=performance.now(), dur=820;
    const tick=(t)=>{ let k=Math.min(1,(t-t0)/dur); k=1-Math.pow(1-k,3); this.setState({anim:k}); if(k<1) this._raf=requestAnimationFrame(tick); };
    this._raf=requestAnimationFrame(tick);
  }
  componentDidMount(){ this.runCount(); this.loadRuntimeCapabilities(); this._initConvs(); }

  // ===================== 多会话 / 历史对话 =====================
  _initConvs(){
    let convs=null;
    try{ convs=JSON.parse(window.localStorage.getItem('di_chat_convs')||'null'); }catch(e){}
    if(!Array.isArray(convs)||!convs.length){ convs=[{id:'c'+Date.now(), title:'新对话', msgs:[]}]; }
    this.setState({chatConvs:convs, chatConvId:convs[0].id, chatMsgs:convs[0].msgs||[]});
  }
  _saveConvs(){
    const convs=(this.state.chatConvs||[]).slice();
    const cur=convs.find(c=>c.id===this.state.chatConvId);
    if(cur){ cur.msgs=this.state.chatMsgs||[]; const fu=(cur.msgs.find(m=>m.role==='user')||{}).text; if(fu) cur.title=fu.slice(0,18); }
    this.setState({chatConvs:convs});
    try{ window.localStorage.setItem('di_chat_convs', JSON.stringify(convs.slice(0,30))); }catch(e){}
  }
  newChat(){
    const convs=(this.state.chatConvs||[]).slice();
    const cur=convs.find(c=>c.id===this.state.chatConvId); if(cur) cur.msgs=this.state.chatMsgs||[];
    const nc={id:'c'+Date.now(), title:'新对话', msgs:[]}; convs.unshift(nc);
    this.setState({chatConvs:convs, chatConvId:nc.id, chatMsgs:[], chatActive:0, chatInput:''}, ()=>this._saveConvs());
  }
  switchChat(id){
    if(id===this.state.chatConvId) return;
    const convs=(this.state.chatConvs||[]).slice();
    const cur=convs.find(c=>c.id===this.state.chatConvId); if(cur) cur.msgs=this.state.chatMsgs||[];
    const tg=convs.find(c=>c.id===id); if(!tg) return;
    let ai=0; for(let i=(tg.msgs||[]).length-1;i>=0;i--){ if(tg.msgs[i].role==='ai'){ ai=i; break; } }
    this.setState({chatConvs:convs, chatConvId:id, chatMsgs:tg.msgs||[], chatActive:ai}, ()=>this._saveConvs());
  }
  _respText(resp){ if(!resp) return ''; if(resp.mdText) return resp.mdText; return (resp.blocks||[]).map(b=>b.text).join('\n'); }
  _persist(){ try{ window.localStorage.setItem('di_chat_convs', JSON.stringify((this.state.chatConvs||[]).slice(0,30))); }catch(e){} }
  deleteChat(id){
    let convs=(this.state.chatConvs||[]).slice();
    const cur=convs.find(c=>c.id===this.state.chatConvId); if(cur) cur.msgs=this.state.chatMsgs||[];
    convs=convs.filter(c=>c.id!==id);
    let cid=this.state.chatConvId, msgs=this.state.chatMsgs;
    if(id===cid){
      if(!convs.length){ const nc={id:'c'+Date.now(),title:'新对话',msgs:[]}; convs=[nc]; cid=nc.id; msgs=[]; }
      else { cid=convs[0].id; msgs=convs[0].msgs||[]; }
    }
    this.setState({chatConvs:convs, chatConvId:cid, chatMsgs:msgs, chatActive:0}, ()=>this._persist());
  }
  clearAllChats(){
    const nc={id:'c'+Date.now(),title:'新对话',msgs:[]};
    this.setState({chatConvs:[nc], chatConvId:nc.id, chatMsgs:[], chatActive:0, chatSettings:false}, ()=>this._persist());
  }

  // ===================== Backend (/api) data layer =====================
  _api(path, params){
    const url = new URL(path, window.location.origin);
    if(params){ Object.keys(params).forEach(k=>{ const v=params[k]; if(v!=null&&v!=='') url.searchParams.set(k, v); }); }
    return fetch(url.toString(), {headers:{'accept':'application/json'}}).then(r=>{ if(!r.ok) throw new Error('GET '+path+' → '+r.status); return r.json(); });
  }
  _apiPost(path, body){
    return fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}).then(r=>{ if(!r.ok) throw new Error('POST '+path+' → '+r.status); return r.json(); });
  }
  _mergeApi(patch){ this.setState(st=>({api:Object.assign({}, st.api, patch)})); }
  _curKey(){ const s=this.state; return [s.company,s.year,s.scope].join('|'); }
  _get(key){ const a=this.state.api||{}; return a[key]; }
  // stale-while-revalidate：返回该槽位最近一次成功拉取的数据（即便正在切换/key 不匹配），
  // 避免切公司时回退到演示预设造成闪烁；新数据到达后会覆盖该槽位自动更新。
  _matched(slot){ const m=this._get(slot); return m ? m.data : null; }

  loadRuntimeCapabilities(){
    if(this.state.runtimeCapabilitiesLoading) return;
    this.setState({runtimeCapabilitiesLoading:true});
    this._api('/api/runtime-capabilities').then(c=>{
      const caps=c||{};
      const legacy=!!caps.legacy_features_available;
      const page=caps.default_page||(legacy?'today':'evidence');
      const nextPage=(legacy||!this._isLegacyPage(page))?page:(caps.evidence_workbench_available?'today':'evidence');
      this.setState({
        runtimeCapabilities:caps,
        runtimeCapabilitiesLoaded:true,
        runtimeCapabilitiesLoading:false,
        page:nextPage,
        legacyNotice:legacy?'':'旧数据未配置：'+(caps.legacy_unavailable_reason||'旧企业分析数据或可选依赖未配置')
      }, ()=>{
        if(legacy) this.loadBootstrap();
        this.loadPage();
      });
    }).catch(()=>{
      const caps={competition_core_available:true,evidence_workbench_available:true,legacy_features_available:false,default_page:'today',legacy_unavailable_reason:'运行能力识别失败，已进入研发证据工作台'};
      this.setState({runtimeCapabilities:caps,runtimeCapabilitiesLoaded:true,runtimeCapabilitiesLoading:false,page:'today',legacyNotice:'旧数据未配置：'+caps.legacy_unavailable_reason}, ()=>this.loadDashboard());
    });
  }

  loadBootstrap(){
    if(!this._legacyAvailable()) return;
    this._api('/api/bootstrap').then(b=>{
      if(!b) return;
      const ns={}; let nav=false;
      if(typeof b.deepseek_enabled==='boolean') ns.deepseek=b.deepseek_enabled;
      const comps=(Array.isArray(b.companies)?b.companies:[]).filter(c=>String(c).indexOf('模拟')<0);
      const yrs=Array.isArray(b.years)?b.years:[];
      if(comps.length && comps.indexOf(this.state.company)<0){ ns.company=comps[0]; nav=true; }
      const baseCompany=ns.company||this.state.company;
      if(comps.length>1){ const cc=this.state.compareCompany; if(!cc || comps.indexOf(cc)<0 || cc===baseCompany){ ns.compareCompany=comps.find(c=>c!==baseCompany)||''; } }
      if(yrs.length && yrs.indexOf(this.state.year)<0){ ns.year=Number(yrs[0]); nav=true; }
      this.setState(Object.assign({api:Object.assign({}, this.state.api, {bootstrap:b})}, ns), ()=>{ if(nav) this.runCount(); this.loadPage(); });
    }).catch(()=>{});
  }

  loadPage(){
    if(!this.state.runtimeCapabilitiesLoaded) return;
    const p=this.state.page;
    if(this._isLegacyPage(p) && !this._legacyAvailable()) return;
    if(p==='today') this.loadDashboard();
    else if(p==='compare'){ this.loadProfile(); this.loadCompare(); }
    else if(p==='timeline') this.loadTimeline();
    else if(p==='database') this.loadDbCatalog();
    else if(p==='whitebox') this.loadWhitebox();
    else if(p==='advanced') this.loadProfile();
    else if(p==='research') this._ensureResProfile(this._resActive());
    else if(p==='evidence') this.loadEvidencePage();
  }

  loadDashboard(){
    if(this.state.evidenceWorkbenchLoading || this.state.evidenceWorkbenchLoaded) return;
    this.setState({evidenceWorkbenchLoading:true,evidenceWorkbenchError:'',evidenceWorkbenchLoaded:true});
    this._api('/api/evidence/workbench').then(d=>this.setState({evidenceWorkbenchLoading:false,evidenceWorkbench:(d&&d.workbench)||null})).catch(()=>this.setState({evidenceWorkbenchLoading:false,evidenceWorkbenchError:'证据工作台加载失败，请稍后重试'}));
  }
  loadProfile(){ if(!this._legacyAvailable()) return; const key=this._curKey(), s=this.state;
    this._api('/api/profile',{company_name:s.company, report_year:s.year}).then(d=>this._mergeApi({profile:{key,data:d}})).catch(()=>{}); }
  loadCompare(){ if(!this._legacyAvailable()) return; const key=this._curKey(), s=this.state;
    this._api('/api/compare',{company_name:s.company, compare_company_name:s.compareCompany, report_year:s.year}).then(d=>this._mergeApi({compare:{key,data:d}})).catch(()=>{}); }
  loadTimeline(){ if(!this._legacyAvailable()) return; const key=this.state.company;
    this._api('/api/timeline',{company_name:this.state.company}).then(d=>this._mergeApi({timeline:{key,data:d}})).catch(()=>{}); }
  loadWhitebox(){ if(!this._legacyAvailable()) return; if(this._get('whitebox')) return; this._api('/api/whitebox').then(d=>this._mergeApi({whitebox:d})).catch(()=>{}); }
  loadDbCatalog(){
    if(!this._legacyAvailable()) return;
    this._api('/api/database/catalog').then(d=>{
      this._mergeApi({dbCatalog:d});
      const names=(d&&d.table_names)||[];
      let t=this.state.dbTable;
      if(names.length && names.indexOf(t)<0){ t=names[0]; this.setState({dbTable:t}); }
      this.loadDbTable(t);
    }).catch(()=>{});
  }
  loadDbTable(name){ if(!this._legacyAvailable()) return; if(!name) return; const cur=this._get('dbTable');
    if(cur && cur.key===name) return;
    this._api('/api/database/table',{table_name:name, limit:20}).then(d=>this._mergeApi({dbTable:{key:name,data:d}})).catch(()=>{}); }
  selectDbTable(name){ this.setState({dbTable:name}, ()=>this.loadDbTable(name)); }

  setParam(patch){ this.setState(Object.assign({anim:0}, patch), ()=>{ this.runCount(); this.loadPage(); }); }

  // ---- adapters: backend (snake_case) shapes -> design shapes ----
  _num(v){ const n=Number(v); return isFinite(n)?n:null; }
  // 金额量级格式化：后端金额以「元」返回，前端按 亿元/万元 展示；比率(%)与已是亿元/万元的不动。
  _amtParts(v, unit){ v=this._num(v); const u=unit||''; if(v==null) return {num:0, unit:u};
    const isPct=u.indexOf('%')>=0;
    if(isPct && Math.abs(v)<1e5) return {num:v, unit:'%'};   // 正常比率
    // '元'/空单位，或被误标成 %、却是极大金额(>=1e5)的数据异常 → 按金额折算
    if(u===''||u==='元'||isPct){ const a=Math.abs(v); if(a>=1e8) return {num:v/1e8, unit:'亿元'}; if(a>=1e4) return {num:v/1e4, unit:'万元'}; return {num:v, unit:'元'}; }
    return {num:v, unit:u}; }
  _amt(v, unit){ const p=this._amtParts(v, unit); return Number(p.num).toFixed(2)+p.unit; }
  _fmtAmtStr(s){ if(s==null) return '-'; s=String(s); const m=s.match(/^\s*(-?[\d,]*\.?\d+)\s*(.*)$/); if(!m) return s; if(/亿|万/.test(m[2]||'')) return s; const num=parseFloat(m[1].replace(/,/g,'')); if(!isFinite(num)) return s; return this._amt(num, m[2]||''); }
  _stripMd(s){ return String(s==null?'':s).replace(/\*\*(.*?)\*\*/g,'$1').replace(/\*(.*?)\*/g,'$1').replace(/`([^`]*)`/g,'$1').replace(/^>\s?/,'').trim(); }
  _mdBlocks(md){
    const lines=String(md||'').split(/\r?\n/);
    const out=[];
    const isRow=(l)=>/^\s*\|.*\|\s*$/.test(l);
    const isSep=(l)=>/^\s*\|[\s:|\-—]+\|\s*$/.test(l) && /[-—]/.test(l);
    const cells=(l)=>l.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(c=>this._stripMd(c.trim()));
    for(let i=0;i<lines.length;i++){
      const raw=lines[i], t=raw.trim();
      if(!t) continue;
      if(isRow(raw)){
        const block=[]; let j=i;
        while(j<lines.length && isRow(lines[j])){ block.push(lines[j]); j++; }
        i=j-1;
        block.filter(l=>!isSep(l)).forEach((l,idx)=>{
          const c=cells(l).filter(x=>x!=='');
          if(c.length) out.push({t: idx===0?'p':'li', text:c.join(' · ')});
        });
        continue;
      }
      let m;
      if(m=t.match(/^#{1,6}\s+(.*)$/)) out.push({t:'h2', text:this._stripMd(m[1])});
      else if(/^[-—*_]{3,}$/.test(t)) continue; // 跳过 --- 分割线
      else if(m=t.match(/^([-*•])\s+(.*)$/)) out.push({t:'li', text:this._stripMd(m[2])});
      else if(m=t.match(/^\d+[\.、\)]\s+(.*)$/)) out.push({t:'li', text:this._stripMd(m[1])});
      else out.push({t:'p', text:this._stripMd(t)});
    }
    return out.length?out:[{t:'p', text:this._stripMd(md)}];
  }
  _chunkAdapt(chunks, scoreAsString){ return (Array.isArray(chunks)?chunks:[]).map((c,i)=>{ const meta=c.metadata||{}; const dist=this._num(c.distance);
      let sc = (this._num(c.score)!=null)? this._num(c.score) : (dist!=null? Math.max(0.4, 1-dist) : (0.92-i*0.04));
      sc=Math.max(0,Math.min(1,sc));
      const source=meta.source||c.source||('来源 '+(i+1));
      const doc_id=(meta.page!=null?('第 '+meta.page+' 页'):(meta.doc_type||c.doc_id||''));
      return {source, score: scoreAsString? sc.toFixed(3): sc, doc_id, text:c.text||''}; }); }
  _sqlTable(rows){ rows=Array.isArray(rows)?rows:[]; if(!rows.length) return {cols:[], rows:[]};
    const cols=Object.keys(rows[0]); return {cols, rows:rows.slice(0,12).map(r=>cols.map(c=>{ const v=r[c]; return v==null?'-':String(v); }))}; }
  _pivot(spec){ if(!spec||!Array.isArray(spec.rows)||!spec.rows.length) return null;
    const xk=spec.x||'report_year', yk=spec.y||'value_num', sk=spec.series||'indicator_name';
    const xs=[]; const map={};
    spec.rows.forEach(r=>{ const xv=String(r[xk]); if(xs.indexOf(xv)<0) xs.push(xv); const sn=String(r[sk]); (map[sn]=map[sn]||{})[xv]=this._num(r[yk]); });
    xs.sort((a,b)=>{ const na=parseFloat(a), nb=parseFloat(b); if(!isNaN(na)&&!isNaN(nb)) return na-nb; return a<b?-1:(a>b?1:0); });
    const palette=['#3b428f','#0d9488','#b45309','#6d28d9','#0ea5e9','#db2777'];
    const names=Object.keys(map);
    return {labels:xs, series:names.map((nm,i)=>({name:nm, color:palette[i%palette.length], values:xs.map(x=> map[nm][x]!=null?map[nm][x]:null)}))}; }
  _seriesValues(pivot, name){ if(!pivot||!pivot.series.length) return null; const s=pivot.series.find(x=>x.name===name); return s?s.values:null; }
  _liveCompanies(){ const b=this._get('bootstrap'); const list=(b&&Array.isArray(b.companies)&&b.companies.length)?b.companies:this.D.companies; const src=list.filter(c=>String(c).indexOf('模拟')<0); const base=src.length?src:list; const seen={}, out=[]; base.forEach(c=>{ const k=String(c).trim(); if(k&&!seen[k]){ seen[k]=1; out.push(c); } }); return out; }
  _liveYears(){ const b=this._get('bootstrap'); return (b&&Array.isArray(b.years)&&b.years.length)?b.years:this.D.years; }
  // 研报页：当前激活公司（单条=全局公司；批量=当前选中的批量公司）
  _resActive(){ const s=this.state; if(s.resMode==='batch'){ const names=(s.resList||'').split(/[，,、\n]+/).map(x=>x.trim()).filter(Boolean).slice(0,5); return names[s.resBatchActive]||names[0]||s.company; } return s.company; }
  // 按需拉取某公司的画像供研报页用（按 name|year 缓存去重，可安全在 render 中调用）
  _ensureResProfile(name){ if(!this._legacyAvailable()) return; if(!name) return; const y=this.state.year, key=name+'|'+y;
    const cache=(this.state.api&&this.state.api.resProfile)||{}; if(cache[key]) return;
    this._resInflight=this._resInflight||{}; if(this._resInflight[key]) return; this._resInflight[key]=1;
    this._api('/api/profile',{company_name:name, report_year:y}).then(d=>{ delete this._resInflight[key]; if(d&&d.company_name) this._lastResProf=d; this.setState(st=>({api:Object.assign({},st.api,{resProfile:Object.assign({},(st.api&&st.api.resProfile)||{},{[key]:d})})})); }).catch(()=>{ delete this._resInflight[key]; }); }
  // 当前公司画像；未就绪时退回上一份已加载的真实画像(stale)，避免闪演示数据
  _resProfile(name){ const c=((this.state.api&&this.state.api.resProfile)||{})[name+'|'+this.state.year]; return (c&&c.company_name)?c:(this._lastResProf||c); }

  // ---- evidence registry page ----
  loadEvidencePage(){
    if(this.state.evidenceTab==='chains'){ this.loadEvidenceChainPage(); return; }
    if(this.state.evidenceTab==='companyCompare'){ this.loadCompanyComparisonPage(); return; }
    if(this.state.evidenceTab==='groundedQa'){ this.loadGroundedCapabilities(); return; }
    this.loadEvidenceSummary();
    if(!this.state.evidenceHasSearched && !this.state.evidenceLoading) this.loadEvidence();
  }
  switchEvidenceTab(tab){
    this.setState({evidenceTab:tab,evidenceError:'',chainError:'',companyComparisonError:'',groundedError:''}, ()=>this.loadEvidencePage());
  }
  loadEvidenceSummary(){
    if(this.state.evidenceSummaryLoading) return;
    this.setState({evidenceSummaryLoading:true});
    this._api('/api/evidence/summary').then(d=>this.setState({evidenceSummaryLoading:false,evidenceSummary:d||null})).catch(()=>this.setState({evidenceSummaryLoading:false,evidenceError:'证据统计加载失败，请稍后重试'}));
  }
  _evidencePath(kind, value){
    const v=encodeURIComponent(String(value||'').trim());
    if(kind==='company') return '/api/evidence/company/'+v;
    if(kind==='drug') return '/api/evidence/drug/'+v;
    if(kind==='trial') return '/api/evidence/trial/'+v;
    if(kind==='study') return '/api/evidence/study/'+v;
    if(kind==='source') return '/api/evidence/source/'+v;
    return '/api/evidence/search';
  }
  _evidenceParams(){
    const s=this.state;
    if(s.evidenceKind==='source') return {};
    const p={latest_only:!!s.evidenceLatestOnly, limit:Number(s.evidenceLimit)||50};
    if(s.evidenceKind==='search') p.q=String(s.evidenceQuery||'').trim();
    return p;
  }
  _evidenceText(v){ return v==null||v===''?'暂无':String(v); }
  _evidenceVersion(value){
    const raw=value;
    if(raw===true || raw===1) return {kind:'latest', label:'最新版本', color:'var(--pos)'};
    if(raw===false || raw===0) return {kind:'history', label:'历史版本', color:'var(--text-3)'};
    const v=String(raw==null?'':raw).trim().toLowerCase();
    if(v==='true' || v==='1') return {kind:'latest', label:'最新版本', color:'var(--pos)'};
    if(v==='false' || v==='0') return {kind:'history', label:'历史版本', color:'var(--text-3)'};
    return {kind:'independent', label:'独立资料', color:'var(--info)'};
  }
  _filterEvidenceItems(items){
    items=Array.isArray(items)?items:[];
    if(!this.state.evidenceLatestOnly || this.state.evidenceKind==='source') return items;
    return items.filter(item=>this._evidenceVersion(item&&item.is_latest_evidence).kind!=='history');
  }
  _safeEvidenceUrl(url){
    const s=String(url||'').trim();
    return /^https?:\/\//i.test(s)?s:'';
  }
  _evidenceItemVm(item){
    item=item||{};
    const sid=this._evidenceText(item.source_id);
    const title=this._evidenceText(item.title_original||item.description_zh||item.study_name);
    const selected=this.state.evidenceSelected&&this.state.evidenceSelected.source_id===item.source_id;
    const version=this._evidenceVersion(item.is_latest_evidence);
    return Object.assign({}, item, {
      source_id:sid,
      title_original:title,
      company_name:this._evidenceText(item.company_name),
      drug_name:this._evidenceText(item.drug_name),
      trial_id:this._evidenceText(item.trial_id),
      study_name:this._evidenceText(item.study_name),
      source_type:this._evidenceText(item.source_type),
      study_status:this._evidenceText(item.study_status),
      verified_at:this._evidenceText(item.verified_at),
      latestLabel:version.label,
      latestColor:version.color,
      style:'width:100%;text-align:left;border:1px solid '+(selected?'var(--brand-300)':'var(--border)')+';background:'+(selected?'var(--brand-50)':'var(--bg-elev)')+';border-radius:12px;padding:13px 14px;display:flex;flex-direction:column;gap:8px;cursor:pointer;transition:border-color .12s,background .12s',
      onClick:()=>this.loadEvidenceSource(item.source_id)
    });
  }
  loadEvidence(){
    const s=this.state, q=String(s.evidenceQuery||'').trim();
    if(!q){ this.setState({evidenceError:'请输入查询内容', evidenceHasSearched:true}); return; }
    this.setState({evidenceLoading:true,evidenceError:'',evidenceSelected:null,evidenceItems:[],evidenceCount:0,evidenceHasSearched:true});
    this._api(this._evidencePath(s.evidenceKind,q), this._evidenceParams()).then(d=>{
      const rawItems=Array.isArray(d&&d.items)?d.items:((d&&d.item)?[d.item]:[]);
      const items=this._filterEvidenceItems(rawItems);
      this.setState({evidenceLoading:false,evidenceItems:items,evidenceCount:items.length,evidenceSelected:items[0]||null});
    }).catch(()=>this.setState({evidenceLoading:false,evidenceItems:[],evidenceCount:0,evidenceError:'证据查询失败，请检查查询内容或稍后重试'}));
  }
  loadEvidenceSource(sourceId){
    const sid=String(sourceId||'').trim();
    if(!sid) return;
    this.setState({evidenceDetailLoading:true,evidenceError:''});
    this._api(this._evidencePath('source', sid)).then(d=>this.setState({evidenceDetailLoading:false,evidenceSelected:(d&&d.item)||null})).catch(()=>this.setState({evidenceDetailLoading:false,evidenceError:'来源详情加载失败，请稍后重试'}));
  }
  loadEvidenceChainPage(){
    this.loadChainSummary();
    this.loadChains();
    this.loadUnresolvedLinks();
  }
  loadChainSummary(){
    if(this.state.chainSummaryLoading) return;
    this.setState({chainSummaryLoading:true});
    this._api('/api/evidence/chain-summary').then(d=>this.setState({chainSummaryLoading:false,chainSummary:d||null})).catch(()=>this.setState({chainSummaryLoading:false,chainError:'证据链统计加载失败，请稍后重试'}));
  }
  loadChains(){
    if(this.state.chainLoading) return;
    const s=this.state;
    const params={limit:50};
    if(s.chainCompany) params.company=s.chainCompany;
    if(s.chainType) params.chain_type=s.chainType;
    this.setState({chainLoading:true,chainError:'',chainLoaded:true});
    this._api('/api/evidence/chains', params).then(d=>{
      const items=Array.isArray(d&&d.items)?d.items:[];
      this.setState({chainLoading:false,chainItems:items,chainSelected:items[0]||null});
      if(items[0]) this.loadChainDetail(items[0].chain_id);
    }).catch(()=>this.setState({chainLoading:false,chainItems:[],chainSelected:null,chainError:'证据链列表加载失败，请稍后重试'}));
  }
  loadChainDetail(chainId){
    const cid=String(chainId||'').trim();
    if(!cid) return;
    this.setState({chainDetailLoading:true,chainError:''});
    this._api('/api/evidence/chains/'+encodeURIComponent(cid)).then(d=>this.setState({chainDetailLoading:false,chainSelected:(d&&d.item)||null})).catch(()=>this.setState({chainDetailLoading:false,chainError:'证据链详情加载失败，请稍后重试'}));
  }
  loadUnresolvedLinks(){
    if(this.state.chainUnresolvedLoading) return;
    this.setState({chainUnresolvedLoading:true});
    this._api('/api/evidence/unresolved-links').then(d=>this.setState({chainUnresolvedLoading:false,chainUnresolved:Array.isArray(d&&d.items)?d.items:[]})).catch(()=>this.setState({chainUnresolvedLoading:false,chainError:'待确认关系加载失败，请稍后重试'}));
  }
  loadCompanyComparisonPage(){
    this.loadCompanyComparison();
    this.loadCompanyMetricRules();
  }
  _companyKey(name){
    const v=String(name||'').trim().toLowerCase();
    if(['百济神州','beone medicines','beigene','百济神州 / beone medicines','百济神州/beone medicines'].includes(v)) return 'beone';
    if(v==='恒瑞医药') return 'hengrui';
    return v;
  }
  _companyLabel(name){
    const key=this._companyKey(name);
    if(key==='beone') return '百济神州 / BeOne Medicines';
    if(key==='hengrui') return '恒瑞医药';
    return this._evidenceText(name);
  }
  _companyOptions(){
    const comparison=this.state.companyComparison||{};
    const companies=Array.isArray(comparison.companies)?comparison.companies:[];
    const names=companies.map(c=>c&&c.display_name?c.display_name:c&&c.company_name).filter(Boolean);
    const base=names.length?names:['恒瑞医药','BeOne Medicines'];
    const seen={}, out=[];
    base.forEach(name=>{
      const key=this._companyKey(name);
      if(!seen[key]){ seen[key]=1; out.push({value:key==='beone'?'BeOne Medicines':'恒瑞医药', label:this._companyLabel(name)}); }
    });
    return out;
  }
  loadCompanyComparison(){
    const a=this.state.comparisonCompanyA, b=this.state.comparisonCompanyB;
    if(this._companyKey(a)===this._companyKey(b)){
      this.setState({companyComparison:null,companyComparisonError:'请选择两个不同企业后再比较',companyComparisonLoading:false,companyComparisonLoaded:true});
      return;
    }
    if(this.state.companyComparisonLoading) return;
    this.setState({companyComparisonLoading:true,companyComparisonError:'',companyComparisonLoaded:true});
    this._api('/api/evidence/company-comparison',{company_a:a,company_b:b}).then(d=>this.setState({companyComparisonLoading:false,companyComparison:(d&&d.comparison)||null})).catch(()=>this.setState({companyComparisonLoading:false,companyComparisonError:'企业证据对比加载失败，请稍后重试'}));
  }
  loadCompanyMetricRules(){
    if(this.state.metricRulesLoading || (this.state.metricRules&&this.state.metricRules.length)) return;
    this.setState({metricRulesLoading:true});
    this._api('/api/evidence/company-comparison/metric-rules').then(d=>this.setState({metricRulesLoading:false,metricRules:Array.isArray(d&&d.items)?d.items:[]})).catch(()=>this.setState({metricRulesLoading:false,companyComparisonError:'指标解释规则加载失败，请稍后重试'}));
  }
  _setCompareCompany(side, value){
    const patch=side==='a'?{comparisonCompanyA:value}:{comparisonCompanyB:value};
    this.setState(patch, ()=>this.loadCompanyComparison());
  }
  swapCompareCompanies(){
    const a=this.state.comparisonCompanyA, b=this.state.comparisonCompanyB;
    this.setState({comparisonCompanyA:b,comparisonCompanyB:a}, ()=>this.loadCompanyComparison());
  }
  openComparisonChain(chainId){
    const cid=String(chainId||'').trim();
    if(!cid) return;
    this.setState({evidenceTab:'chains',chainError:''}, ()=>{
      this.loadChainSummary();
      this.loadUnresolvedLinks();
      this.loadChainDetail(cid);
    });
  }
  openGroundedChain(chainId){
    const cid=String(chainId||'').trim();
    if(!cid) return;
    this.setState({evidenceTab:'chains',chainError:'',groundedError:''}, ()=>{
      this.loadChainSummary();
      this.loadUnresolvedLinks();
      this.loadChainDetail(cid);
    });
  }
  loadGroundedCapabilities(){
    if(this.state.groundedCapabilitiesLoading || this.state.groundedCapabilitiesLoaded) return;
    this.setState({groundedCapabilitiesLoading:true,groundedError:''});
    this._api('/api/evidence/grounded-qa/capabilities').then(d=>{
      const deepseekOk=!!(d&&d.llm_mode_available);
      this.setState({
        groundedCapabilitiesLoading:false,
        groundedCapabilitiesLoaded:true,
        groundedCapabilities:d||null,
        groundedMode:deepseekOk?'auto':'local'
      });
    }).catch(()=>this.setState({
      groundedCapabilitiesLoading:false,
      groundedCapabilitiesLoaded:true,
      groundedCapabilities:null,
      groundedMode:'local',
      groundedError:'循证问答能力加载失败，请稍后重试。'
    }));
  }
  setGroundedMode(mode){
    const cap=this.state.groundedCapabilities||{};
    if(mode==='auto' && !cap.llm_mode_available){
      this.setState({groundedMode:'local',groundedError:'DeepSeek当前不可用，请使用本地证据摘要。'});
      return;
    }
    this.setState({groundedMode:mode,groundedError:''});
  }
  setGroundedExample(question){
    this.setState({groundedQuestion:String(question||'').slice(0,1000),groundedError:''});
  }
  submitGroundedQA(){
    const question=String(this.state.groundedQuestion||'').trim();
    if(!question){ this.setState({groundedError:'请输入问题后再提交。'}); return; }
    if(question.length>1000){ this.setState({groundedError:'问题不能超过 1000 个字符。'}); return; }
    if(this.state.groundedLoading) return;
    if(this._groundedAbort) this._groundedAbort.abort();
    const seq=(this.state.groundedSeq||0)+1;
    const controller=(typeof AbortController!=='undefined')?new AbortController():null;
    this._groundedAbort=controller;
    this.setState({groundedLoading:true,groundedError:'',groundedSeq:seq});
    fetch('/api/evidence/grounded-qa', {
      method:'POST',
      headers:{'Content-Type':'application/json','accept':'application/json'},
      body:JSON.stringify({question, generation_mode:this.state.groundedMode}),
      signal:controller?controller.signal:undefined
    }).then(r=>r.json().then(d=>({ok:r.ok,status:r.status,data:d,retryAfter:r.headers?r.headers.get('Retry-After'):''})).catch(()=>({ok:r.ok,status:r.status,data:null,retryAfter:r.headers?r.headers.get('Retry-After'):''}))).then(({ok,status,data,retryAfter})=>{
      if(seq!==this.state.groundedSeq) return;
      if(!ok){
        const detail=data&&data.detail?String(data.detail):'循证问答请求失败，请稍后重试。';
        const wait=retryAfter&&/^\d+$/.test(String(retryAfter))?'请约 '+retryAfter+' 秒后再试，或切换 local 继续使用。':'请稍后重试，或切换 local 继续使用。';
        const msg=status===429?(detail+' '+wait):(status===400?detail:(status===503?'循证问答服务暂不可用，请稍后重试。':'循证问答服务暂时不可用。'));
        this.setState({groundedLoading:false,groundedError:msg});
        return;
      }
      this.setState({groundedLoading:false,groundedResult:(data&&data.result)||null,groundedMeta:(data&&data.metadata)||null});
    }).catch(e=>{
      if(e&&e.name==='AbortError') return;
      if(seq!==this.state.groundedSeq) return;
      this.setState({groundedLoading:false,groundedError:'网络或服务暂时不可用，请稍后重试。'});
    });
  }
  _questionTypeLabel(type){
    return ({
      source_search:'来源检索',
      trial_status:'试验状态',
      evidence_chain:'证据链',
      regulatory_status:'监管状态',
      company_comparison:'企业对比',
      evidence_gap:'证据缺口',
      prohibited_or_unsupported:'安全边界'
    })[type]||'来源检索';
  }
  _groundedRoleLabel(role){
    return ({
      trial_registry:'临床试验登记',
      interim_publication:'中期分析论文',
      final_publication:'最终分析论文',
      company_document:'企业官方资料',
      regulatory_authorisation:'EMA正式授权信息',
      regulatory_opinion:'CHMP积极意见',
      independent_evidence:'独立证据资料'
    })[role]||'其他证据资料';
  }
  _studyStatusLabel(status){
    const raw=String(status==null?'':status).trim();
    const key=raw.toLowerCase();
    const labels={
      completed:'已完成',
      terminated:'已终止',
      'active, not recruiting':'活跃、停止招募',
      recruiting:'招募中',
      'not yet recruiting':'尚未招募'
    };
    if(!raw || ['unknown','n/a','na','不适用','暂无','暂无明确状态'].includes(key)) return '暂无明确状态';
    return labels[key]?(labels[key]+'（'+raw+'）'):('暂无明确状态');
  }
  _retrievalServiceLabel(name){
    const raw=String(name||'').trim();
    const labels={
      EvidenceChainService:'证据链服务',
      SourceRegistryService:'来源登记服务',
      CompanyEvidenceComparisonService:'企业证据对比服务',
      GroundedQAService:'循证问答服务'
    };
    return labels[raw]?(labels[raw]+'（'+raw+'）'):(raw||'暂无');
  }
  _generationModeLabel(mode){
    const raw=String(mode||'').trim();
    const labels={
      llm:'DeepSeek智能生成',
      local:'本地循证摘要',
      safety_block:'安全规则拦截'
    };
    return labels[raw]?(labels[raw]+'（'+raw+'）'):(raw||'暂无');
  }
  _groundedModelLabel(model){
    const raw=String(model||'').trim();
    if(raw==='safe-policy') return '未调用模型';
    if(!raw) return '本地循证摘要';
    if(raw==='local-structured-summary') return '本地循证摘要';
    if(raw==='deepseek-v4-flash') return 'DeepSeek V4 Flash';
    return raw.replace(/^deepseek-/i,'DeepSeek ').replace(/[-_]+/g,' ').replace(/\s+/g,' ').trim();
  }
  _safetyCategoryLabel(category){
    const raw=String(category||'').trim();
    const labels={
      individual_diagnosis:'个体诊断建议',
      individual_medication_or_treatment:'个体治疗或用药建议',
      efficacy_guarantee:'疗效保证',
      cross_trial_efficacy_ranking:'跨试验疗效排名',
      success_probability_prediction:'成功率预测',
      investment_advice:'投资建议',
      company_overall_ranking:'企业综合排名'
    };
    return labels[raw]||'其他不支持的问题类型';
  }
  _friendlyGroundedText(text){
    let out=String(text==null?'':text);
    Object.keys({
      trial_registry:1,
      interim_publication:1,
      final_publication:1,
      company_document:1,
      regulatory_authorisation:1,
      regulatory_opinion:1,
      independent_evidence:1
    }).forEach(role=>{
      out=out.replace(new RegExp('\\b'+role+'\\b','g'), this._groundedRoleLabel(role));
    });
    out=out.replace(/study_status=([^；。\n]+)/g, (m, value)=>'研究状态：'+this._studyStatusLabel(value));
    out=out.replace(/\b[a-z]+_[a-z_]+\b/g, '其他证据资料');
    return out;
  }
  _friendlyGroundedSupportSummary(text){
    let out=this._friendlyGroundedText(text);
    ['Completed','Terminated','Active, not recruiting','Recruiting','Not yet recruiting'].forEach(status=>{
      const label=this._studyStatusLabel(status);
      out=out.replace(new RegExp(status.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'g'), label);
    });
    return out;
  }
  _groundedCitationVm(item){
    item=item||{};
    const url=this._safeEvidenceUrl(item.source_url);
    return {
      source_id:this._evidenceText(item.source_id),
      title:this._evidenceText(item.title),
      source_type:this._evidenceText(item.source_type),
      verified_at:this._evidenceText(item.verified_at),
      support_summary:this._friendlyGroundedSupportSummary(item.support_summary),
      source_url:url,
      hasUrl:!!url
    };
  }
  _groundedTraceRows(trace){
    trace=trace||{};
    const join=(v,mapper)=>Array.isArray(v)&&v.length?v.map(x=>mapper?mapper.call(this,x):x).join('、'):'暂无';
    const rows=[
      {label:'检索服务',value:join(trace.retrieval_service,this._retrievalServiceLabel)},
      {label:'检索来源ID',value:join(trace.retrieved_source_ids)},
      {label:'检索证据链ID',value:join(trace.retrieved_chain_ids)},
      {label:'检索来源总数',value:this._evidenceText(trace.source_count)}
    ];
    if(typeof trace.trial_evidence_count==='number') rows.push({label:'试验证据数量',value:this._evidenceText(trace.trial_evidence_count)});
    if(typeof trace.related_regulatory_count==='number') rows.push({label:'关联监管背景',value:this._evidenceText(trace.related_regulatory_count)});
    rows.push(
      {label:'执行方式',value:this._generationModeLabel(trace.generation_mode_used)},
      {label:'安全类别',value:trace.safety_category?this._safetyCategoryLabel(trace.safety_category):'暂无'},
      {label:'数据版本',value:this._evidenceText(trace.data_version)},
      {label:'生成时间',value:this._evidenceText(trace.generated_at)},
      {label:'内部模型标识',value:this._evidenceText(trace.model_name)},
      {label:'是否使用DeepSeek',value:trace.used_llm?'是':'否'},
      {label:'是否命中缓存',value:trace.cache_hit?'是':'否'}
    );
    return rows;
  }
  _chainTypeLabel(t){ return t==='trial'?'试验级':'药物级监管'; }
  _roleLabel(role){
    return ({
      trial_registry:'临床试验登记',
      interim_publication:'中期分析论文',
      final_publication:'最终分析论文',
      company_document:'企业官方资料',
      regulatory_authorisation:'EMA正式授权信息',
      regulatory_opinion:'CHMP积极意见',
      independent_evidence:'独立证据资料'
    })[role]||'其他证据资料';
  }
  _isRegulatoryEvidence(item){
    item=item||{};
    const role=String(item.role||item.evidence_role||'');
    if(role==='regulatory_authorisation'||role==='regulatory_opinion') return true;
    const blob=[item.regulatory_event_type,item.authorisation_status,item.source_type].map(x=>String(x||'')).join(' ');
    return /监管|授权|authorisation|authorization|CHMP|EMA|EPAR/i.test(blob);
  }
  _chainVersionLabel(item){
    if(this._isRegulatoryEvidence(item)) return {kind:'regulatory', label:'监管资料', color:'var(--brand-600)'};
    const s=String((item&&item.version_status)||'');
    if(s==='latest') return this._evidenceVersion(true);
    if(s==='historical') return this._evidenceVersion(false);
    return this._evidenceVersion('');
  }
  _hasStudyStatus(value){
    const v=String(value==null?'':value).trim().toLowerCase();
    return !!v && !['n/a','na','not applicable','不适用','暂无'].includes(v);
  }
  _authorisationDisplay(item){
    item=item||{};
    if(item.role==='regulatory_opinion') return '积极意见，非最终批准';
    const value=String(item.authorisation_status||'').trim();
    if(value && !['N/A','n/a','not applicable','不适用'].includes(value)) return value;
    return '';
  }
  _versionRelationText(item){
    return this._isRegulatoryEvidence(item)&&String((item&&item.version_status)||'')==='independent'?'无版本关系':'';
  }
  _sourceTitle(item){ item=item||{}; return this._evidenceText(item.title_original||item.description_zh||item.study_name||item.source_id); }
  _chainEvidenceVm(item){
    item=item||{};
    const ver=this._chainVersionLabel(item);
    const url=this._safeEvidenceUrl(item.source_url);
    const auth=this._authorisationDisplay(item);
    const hasStatus=this._hasStudyStatus(item.study_status);
    const versionRelation=this._versionRelationText(item);
    return Object.assign({}, item, {
      source_id:this._evidenceText(item.source_id),
      roleLabel:this._roleLabel(item.role),
      title:this._sourceTitle(item),
      study_status:this._evidenceText(item.study_status),
      hasStudyStatus:hasStatus,
      verified_at:this._evidenceText(item.verified_at),
      versionLabel:ver.label,
      versionColor:ver.color,
      authorisationDisplay:auth,
      hasAuthorisation:!!auth,
      versionRelation,
      hasVersionRelation:!!versionRelation,
      source_url:url,
      hasUrl:!!url
    });
  }
  _chainSection(title, items){
    items=(Array.isArray(items)?items:[]).map(x=>this._chainEvidenceVm(x));
    return {title, items, hasItems:items.length>0};
  }
  _chainCardVm(chain){
    chain=chain||{};
    const selected=this.state.chainSelected&&this.state.chainSelected.chain_id===chain.chain_id;
    const latest=(chain.latest_items||[]).length, hist=(chain.historical_items||[]).length, indep=(chain.independent_items||[]).length;
    const gaps=Array.isArray(chain.evidence_gaps)?chain.evidence_gaps:[];
    return Object.assign({}, chain, {
      typeLabel:this._chainTypeLabel(chain.chain_type),
      drugText:(Array.isArray(chain.drug_names)&&chain.drug_names.length)?chain.drug_names.join('；'):'暂无',
      trialText:(Array.isArray(chain.trial_ids)&&chain.trial_ids.length)?chain.trial_ids.join('；'):'暂无',
      study_status:this._evidenceText(chain.study_status),
      hasStudyStatus:this._hasStudyStatus(chain.study_status),
      source_count:this._evidenceText(chain.source_count),
      versionCounts:'最新版本 '+latest+' · 历史版本 '+hist+' · 独立资料 '+indep,
      gapText:gaps.length?gaps[0]:'暂无证据缺口',
      style:'width:100%;text-align:left;border:1px solid '+(selected?'var(--brand-300)':'var(--border)')+';background:'+(selected?'var(--brand-50)':'var(--bg-elev)')+';border-radius:12px;padding:14px 15px;display:flex;flex-direction:column;gap:8px;cursor:pointer;transition:border-color .12s,background .12s',
      onClick:()=>this.loadChainDetail(chain.chain_id)
    });
  }
  _chainDetailVm(chain){
    chain=chain||{};
    const evidence=Array.isArray(chain.evidence_items)?chain.evidence_items:[];
    const regs=Array.isArray(chain.regulatory_items)?chain.regulatory_items:[];
    const relatedRegs=Array.isArray(chain.related_regulatory_items)?chain.related_regulatory_items:[];
    const roleItems=(role)=>evidence.filter(x=>x&&x.role===role);
    const independent=evidence.filter(x=>!['trial_registry','interim_publication','final_publication'].includes(x&&x.role) && !['regulatory_authorisation','regulatory_opinion'].includes(x&&x.role));
    return {
      has:!!chain.chain_id,
      chain_id:this._evidenceText(chain.chain_id),
      chain_name:this._evidenceText(chain.chain_name),
      chain_type:this._chainTypeLabel(chain.chain_type),
      company_name:this._evidenceText(chain.company_name),
      drugText:(Array.isArray(chain.drug_names)&&chain.drug_names.length)?chain.drug_names.join('；'):'暂无',
      trialText:(Array.isArray(chain.trial_ids)&&chain.trial_ids.length)?chain.trial_ids.join('；'):'暂无',
      studyNames:(Array.isArray(chain.study_names)&&chain.study_names.length)?chain.study_names.join('；'):'暂无',
      study_status:this._evidenceText(chain.study_status),
      source_count:this._evidenceText(chain.source_count),
      trialSections:[
        this._chainSection('临床试验登记', roleItems('trial_registry')),
        this._chainSection('中期论文', roleItems('interim_publication')),
        this._chainSection('最终论文', roleItems('final_publication')),
        this._chainSection('独立资料', independent)
      ],
      regulatorySection:this._chainSection('药物级监管资料', regs),
      relatedRegulatorySection:this._chainSection('关联监管背景', relatedRegs),
      hasRelatedRegulatory:relatedRegs.length>0,
      gaps:(Array.isArray(chain.evidence_gaps)?chain.evidence_gaps:[]).map(x=>({text:x})),
      risks:(Array.isArray(chain.risk_notes)?chain.risk_notes:[]).map(x=>({text:x})),
      hasGaps:Array.isArray(chain.evidence_gaps)&&chain.evidence_gaps.length>0,
      hasRisks:Array.isArray(chain.risk_notes)&&chain.risk_notes.length>0
    };
  }
  _unresolvedVm(item){
    item=item||{};
    const source=item.source||{};
    const gaps=Array.isArray(item.evidence_gaps)?item.evidence_gaps:[];
    return {
      source_id:this._evidenceText(item.source_id),
      source_type:this._evidenceText(source.source_type),
      description:this._evidenceText(item.description),
      gapText:gaps.length?gaps.join('；'):'暂无',
      title:this._sourceTitle(source)
    };
  }
  _distVm(obj){
    obj=obj||{};
    return Object.keys(obj).filter(k=>k&&k!=='undefined'&&k!=='null').sort().map(k=>({label:k,value:this._evidenceText(obj[k])}));
  }
  _gapVm(gaps){
    gaps=Array.isArray(gaps)?gaps:[];
    return gaps.map(g=>({
      source_id:this._evidenceText(g&&g.source_id),
      description:this._evidenceText(g&&g.description),
      gapText:Array.isArray(g&&g.evidence_gaps)?g.evidence_gaps.join('；'):this._evidenceText(g&&g.evidence_gaps)
    }));
  }
  _compareChainVm(chain){
    chain=chain||{};
    return {
      chain_id:this._evidenceText(chain.chain_id),
      chain_name:this._evidenceText(chain.chain_name),
      chain_type:this._chainTypeLabel(chain.chain_type),
      trialText:(Array.isArray(chain.trial_ids)&&chain.trial_ids.length)?chain.trial_ids.join('；'):'暂无',
      source_count:this._evidenceText(chain.source_count),
      onClick:()=>this.openComparisonChain(chain.chain_id)
    };
  }
  _companyProfileVm(profile){
    profile=profile||{};
    const version=profile.version_distribution||{};
    const sourceTypes=this._distVm(profile.source_type_distribution);
    const trialChains=(Array.isArray(profile.trial_chains)?profile.trial_chains:[]).map(x=>this._compareChainVm(x));
    const regulatoryChains=(Array.isArray(profile.regulatory_chains)?profile.regulatory_chains:[]).map(x=>this._compareChainVm(x));
    const gaps=this._gapVm(profile.evidence_gaps);
    return {
      has:!!profile.company_name,
      company_name:this._companyLabel(profile.display_name||profile.company_name),
      source_count:this._evidenceText(profile.source_count),
      verified_source_count:this._evidenceText(profile.verified_source_count),
      trial_chain_count:this._evidenceText(profile.trial_chain_count),
      regulatory_chain_count:this._evidenceText(profile.regulatory_chain_count),
      single_source_trial_chain_count:this._evidenceText(profile.single_source_trial_chain_count),
      multi_source_trial_chain_count:this._evidenceText(profile.multi_source_trial_chain_count),
      unresolved_link_count:this._evidenceText(profile.unresolved_link_count),
      latest:this._evidenceText(version.latest),
      historical:this._evidenceText(version.historical),
      independent:this._evidenceText(version.independent),
      sourceTypes,
      hasSourceTypes:sourceTypes.length>0,
      trialChains,
      regulatoryChains,
      hasTrialChains:trialChains.length>0,
      hasRegulatoryChains:regulatoryChains.length>0,
      gaps,
      hasGaps:gaps.length>0
    };
  }
  _metricRuleVm(rule){
    rule=rule||{};
    return {
      name:this._evidenceText(rule.name),
      calculation:this._evidenceText(rule.calculation),
      correct:this._evidenceText(rule.correct_interpretation),
      prohibited:this._evidenceText(rule.prohibited_interpretation)
    };
  }
  evidenceVals(){
    const s=this.state, sum=s.evidenceSummary||{};
    const modes=[
      {key:'search',label:'关键词',placeholder:'例如 NSCLC / 卡瑞利珠单抗 / RATIONALE'},
      {key:'company',label:'企业',placeholder:'例如 恒瑞医药 / 百济神州 / BeOne Medicines'},
      {key:'drug',label:'药物',placeholder:'例如 SHR-1210 / tislelizumab'},
      {key:'trial',label:'临床试验',placeholder:'例如 NCT04619433'},
      {key:'study',label:'研究名称',placeholder:'例如 RATIONALE-304'},
      {key:'source',label:'来源ID',placeholder:'例如 B015'}
    ];
    const activeMode=modes.find(m=>m.key===s.evidenceKind)||modes[0];
    const countMap=sum.company_counts||sum.company_source_counts||{};
    const verified=Array.isArray(sum.verified_dates)?sum.verified_dates.join('、'):(sum.metadata&&sum.metadata.verified_dates)||'暂无';
    const items=(s.evidenceItems||[]).map(x=>this._evidenceItemVm(x));
    const detail=s.evidenceSelected||{};
    const detailVersion=this._evidenceVersion(detail.is_latest_evidence);
    const detailUrl=this._safeEvidenceUrl(detail.source_url);
    const field=(label, value)=>({label, value:this._evidenceText(value)});
    const ev_detailFields=[
      field('资料编号', detail.source_id),
      field('企业', detail.company_name),
      field('药物', detail.drug_name),
      field('临床试验编号', detail.trial_id),
      field('PMID', detail.pmid),
      field('研究名称', detail.study_name),
      field('来源类型', detail.source_type),
      field('研究状态', detail.study_status),
      field('核验状态', detail.verification_status),
      field('监管事件类型', detail.regulatory_event_type),
      field('授权状态', detail.authorisation_status),
      field('核验日期', detail.verified_at),
      field('证据版本', detailVersion.label)
    ];
    const chainSum=s.chainSummary||{};
    const chainItems=(s.chainItems||[]).map(x=>this._chainCardVm(x));
    const chainDetail=this._chainDetailVm(s.chainSelected||{});
    const chainUnresolved=(s.chainUnresolved||[]).map(x=>this._unresolvedVm(x));
    const tabStyle=(active)=>'height:34px;border-radius:9px;border:1px solid '+(active?'var(--brand-600)':'var(--border)')+';background:'+(active?'var(--brand-600)':'var(--bg-elev)')+';color:'+(active?'#fff':'var(--text-2)')+';font-size:13px;font-weight:600;padding:0 14px;cursor:pointer';
    const comparison=s.companyComparison||{};
    const companyProfiles=(Array.isArray(comparison.companies)?comparison.companies:[]).map(x=>this._companyProfileVm(x));
    const companyOptions=this._companyOptions();
    const sameCompany=this._companyKey(s.comparisonCompanyA)===this._companyKey(s.comparisonCompanyB);
    const metricRules=(s.metricRules||[]).map(x=>this._metricRuleVm(x));
    const dataInsufficient=[
      {name:'临床阶段', reason:'当前仅能展示原始 study_phase 分布，字段存在空值、不适用和不同来源口径。'},
      {name:'研究人群', reason:'缺少统一结构化人群字段，不能从标题自动补全。'},
      {name:'治疗场景', reason:'treatment_line、regimen_detail、comparator 不完整，不能输出强结论。'},
      {name:'靶点', reason:'当前没有统一 target 字段。'},
      {name:'机制', reason:'当前没有统一 mechanism 字段。'},
      {name:'药物类型', reason:'当前没有统一 drug_type 字段。'},
      {name:'疗效与安全性', reason:'不支持跨试验疗效、安全性或成功率比较。'}
    ];
    const groundedCap=s.groundedCapabilities||{};
    const groundedResult=s.groundedResult||{};
    const groundedMeta=s.groundedMeta||{};
    const groundedTrace=groundedResult.trace||{};
    const groundedDeepseek=!!groundedCap.llm_mode_available;
    const groundedModeStyle=(mode,enabled)=>'height:34px;border-radius:9px;border:1px solid '+(s.groundedMode===mode?'var(--brand-600)':'var(--border)')+';background:'+(s.groundedMode===mode?'var(--brand-600)':'var(--bg-elev)')+';color:'+(s.groundedMode===mode?'#fff':'var(--text-2)')+';font-size:12.5px;font-weight:700;padding:0 13px;cursor:'+(enabled?'pointer':'not-allowed')+';opacity:'+(enabled?'1':'.55');
    const questionTypes=Array.isArray(groundedCap.supported_question_types)?groundedCap.supported_question_types.map(t=>({label:this._questionTypeLabel(t),value:t})):[];
    const groundedCitations=(Array.isArray(groundedResult.citations)?groundedResult.citations:[]).map(x=>this._groundedCitationVm(x));
    const groundedLimitations=(Array.isArray(groundedResult.limitations)?groundedResult.limitations:[]).filter(Boolean).map(x=>({text:this._evidenceText(x)}));
    const groundedChainIds=(Array.isArray(groundedTrace.retrieved_chain_ids)?groundedTrace.retrieved_chain_ids:[]).map(id=>({chain_id:this._evidenceText(id),onClick:()=>this.openGroundedChain(id)}));
    const groundedFallback=!!(groundedMeta.fallback_used||groundedTrace.fallback_used);
    const groundedUsedLlm=!!(groundedMeta.llm_used||groundedTrace.used_llm);
    const groundedGenerationMode=String((groundedMeta&&groundedMeta.generation_mode_used)||groundedTrace.generation_mode_used||'');
    const groundedSafetyBlock=groundedGenerationMode==='safety_block';
    const groundedSubmitDisabled=s.groundedLoading||!String(s.groundedQuestion||'').trim()||String(s.groundedQuestion||'').length>1000;
    const groundedStatusTags=[
      {text:'问题类型：'+this._questionTypeLabel(groundedResult.question_type), color:groundedSafetyBlock?'var(--warn)':'var(--brand-600)', bg:groundedSafetyBlock?'var(--warn-bg)':'var(--brand-50)'},
      {text:groundedSafetyBlock?'执行方式：安全规则拦截':(groundedUsedLlm?'执行方式：DeepSeek智能生成':'执行方式：本地循证摘要'), color:groundedSafetyBlock?'var(--warn)':(groundedUsedLlm?'var(--pos)':'var(--text-2)'), bg:groundedSafetyBlock?'var(--warn-bg)':(groundedUsedLlm?'var(--pos-bg)':'var(--bg-sunken)')}
    ];
    if(groundedUsedLlm){
      groundedStatusTags.push({text:'模型：'+this._groundedModelLabel((groundedMeta&&groundedMeta.model_name)||groundedTrace.model_name), color:'var(--text-2)', bg:'var(--bg-sunken)'});
    }else if(groundedSafetyBlock){
      groundedStatusTags.push({text:'模型：未调用模型', color:'var(--warn)', bg:'var(--warn-bg)'});
    }else{
      groundedStatusTags.push({text:'模型：本地循证摘要', color:'var(--text-2)', bg:'var(--bg-sunken)'});
    }
    if(groundedFallback) groundedStatusTags.push({text:'DeepSeek暂不可用，已回退本地证据摘要', color:'var(--warn)', bg:'var(--warn-bg)'});
    return {
      ev_tabSourceStyle:tabStyle(s.evidenceTab==='sources'),
      ev_tabChainStyle:tabStyle(s.evidenceTab==='chains'),
      ev_tabCompanyStyle:tabStyle(s.evidenceTab==='companyCompare'),
      ev_tabGroundedStyle:tabStyle(s.evidenceTab==='groundedQa'),
      ev_tabSource:()=>this.switchEvidenceTab('sources'),
      ev_tabChain:()=>this.switchEvidenceTab('chains'),
      ev_tabCompany:()=>this.switchEvidenceTab('companyCompare'),
      ev_tabGrounded:()=>this.switchEvidenceTab('groundedQa'),
      ev_isSourceTab:s.evidenceTab==='sources',
      ev_isChainTab:s.evidenceTab==='chains',
      ev_isCompanyCompareTab:s.evidenceTab==='companyCompare',
      ev_isGroundedTab:s.evidenceTab==='groundedQa',
      ev_modes:modes.map(m=>Object.assign({}, m, {style:'height:30px;border-radius:7px;border:0;padding:0 10px;font-size:12px;font-weight:600;cursor:pointer;'+(m.key===s.evidenceKind?'background:var(--brand-600);color:#fff':'background:transparent;color:var(--text-2)'), onClick:()=>this.setState({evidenceKind:m.key,evidenceError:''})})),
      ev_kind:s.evidenceKind, ev_kindLabel:activeMode.label, ev_query:s.evidenceQuery, ev_placeholder:activeMode.placeholder,
      ev_onQuery:(e)=>this.setState({evidenceQuery:e.target.value}),
      ev_onKey:(e)=>{ if(e.key==='Enter') this.loadEvidence(); },
      ev_latest:s.evidenceLatestOnly, ev_onLatest:(e)=>this.setState({evidenceLatestOnly:e.target.checked}, ()=>{ if(this.state.evidenceHasSearched) this.loadEvidence(); }),
      ev_limit:s.evidenceLimit, ev_onLimit:(e)=>this.setState({evidenceLimit:Number(e.target.value)}),
      ev_search:()=>this.loadEvidence(),
      ev_reloadSummary:()=>this.loadEvidenceSummary(),
      ev_summaryLoading:s.evidenceSummaryLoading, ev_loading:s.evidenceLoading, ev_detailLoading:s.evidenceDetailLoading,
      ev_hasError:!!s.evidenceError, ev_error:s.evidenceError,
      ev_hasSearched:s.evidenceHasSearched, ev_count:s.evidenceCount, ev_items:items, ev_hasResults:items.length>0,
      ev_empty:s.evidenceHasSearched&&!s.evidenceLoading&&!s.evidenceError&&items.length===0,
      ev_scope:[
        {label:'疾病领域',value:'NSCLC'},
        {label:'企业',value:'恒瑞医药 · '+this._evidenceText(countMap['恒瑞医药'])+' 条'},
        {label:'企业',value:'百济神州/BeOne Medicines · '+this._evidenceText(countMap['百济神州']||countMap['BeOne Medicines'])+' 条'},
        {label:'人工核验资料',value:this._evidenceText(sum.total_sources)+' 条'}
      ],
      ev_verified:verified,
      ev_detailHas:!!detail.source_id,
      ev_detailEmpty:!detail.source_id,
      ev_detailTitle:this._evidenceText(detail.title_original),
      ev_detailDesc:this._evidenceText(detail.description_zh),
      ev_detailVersionLabel:detailVersion.label,
      ev_detailVersionColor:detailVersion.color,
      ev_detailRisk:this._evidenceText(detail.risk_notes),
      ev_detailHasRisk:!!detail.risk_notes,
      ev_detailFields:ev_detailFields,
      ev_detailUrl:detailUrl,
      ev_hasUrl:!!detailUrl,
      chain_summaryLoading:s.chainSummaryLoading,
      chain_loading:s.chainLoading,
      chain_detailLoading:s.chainDetailLoading,
      chain_unresolvedLoading:s.chainUnresolvedLoading,
      chain_hasError:!!s.chainError,
      chain_error:s.chainError,
      chain_loaded:s.chainLoaded,
      chain_company:s.chainCompany,
      chain_type:s.chainType,
      chain_onCompany:(e)=>this.setState({chainCompany:e.target.value}, ()=>this.loadChains()),
      chain_onType:(e)=>this.setState({chainType:e.target.value}, ()=>this.loadChains()),
      chain_refresh:()=>this.loadEvidenceChainPage(),
      chain_total:this._evidenceText(chainSum.total_chain_count),
      chain_trial:this._evidenceText(chainSum.trial_chain_count),
      chain_regulatory:this._evidenceText(chainSum.regulatory_chain_count),
      chain_unresolvedCount:this._evidenceText(chainSum.unresolved_count),
      chain_count:chainItems.length,
      chain_items:chainItems,
      chain_hasResults:chainItems.length>0,
      chain_empty:s.chainLoaded&&!s.chainLoading&&!s.chainError&&chainItems.length===0,
      chain_detail:chainDetail,
      chain_unresolvedOpen:s.chainUnresolvedOpen,
      chain_toggleUnresolved:()=>this.setState({chainUnresolvedOpen:!this.state.chainUnresolvedOpen}),
      chain_unresolved:chainUnresolved,
      chain_unresolvedCountList:chainUnresolved.length,
      cmp_companyA:s.comparisonCompanyA,
      cmp_companyB:s.comparisonCompanyB,
      cmp_companyOptions:companyOptions,
      cmp_onCompanyA:(e)=>this._setCompareCompany('a', e.target.value),
      cmp_onCompanyB:(e)=>this._setCompareCompany('b', e.target.value),
      cmp_swap:()=>this.swapCompareCompanies(),
      cmp_refresh:()=>this.loadCompanyComparisonPage(),
      cmp_loading:s.companyComparisonLoading,
      cmp_rulesLoading:s.metricRulesLoading,
      cmp_hasError:!!s.companyComparisonError,
      cmp_error:s.companyComparisonError,
      cmp_loaded:s.companyComparisonLoaded,
      cmp_sameCompany:sameCompany,
      cmp_hasProfiles:companyProfiles.length>0,
      cmp_profiles:companyProfiles,
      cmp_empty:s.companyComparisonLoaded&&!s.companyComparisonLoading&&!s.companyComparisonError&&!companyProfiles.length,
      cmp_metricRules:metricRules,
      cmp_hasMetricRules:metricRules.length>0,
      cmp_rulesOpen:s.metricRulesOpen,
      cmp_toggleRules:()=>this.setState({metricRulesOpen:!this.state.metricRulesOpen}),
      cmp_dataInsufficient:dataInsufficient,
      cmp_scopeText:'以下结果仅反映当前收录并核验的NSCLC证据样本，不代表企业整体研发实力。',
      cmp_objects:'恒瑞医药、百济神州/BeOne Medicines',
      gqa_capLoading:s.groundedCapabilitiesLoading,
      gqa_capLoaded:s.groundedCapabilitiesLoaded,
      gqa_localAvailable:groundedCap.local_mode_available?'可用':'不可用',
      gqa_deepseekAvailable:groundedDeepseek?'可用':'不可用',
      gqa_deepseekOk:groundedDeepseek,
      gqa_model:this._groundedModelLabel(groundedCap.model_name),
      gqa_dataVersion:this._evidenceText(groundedCap.data_version),
      gqa_questionTypes:questionTypes,
      gqa_mode:s.groundedMode,
      gqa_autoStyle:groundedModeStyle('auto', groundedDeepseek),
      gqa_localStyle:groundedModeStyle('local', true),
      gqa_chooseAuto:()=>this.setGroundedMode('auto'),
      gqa_chooseLocal:()=>this.setGroundedMode('local'),
      gqa_question:s.groundedQuestion,
      gqa_questionCount:String(s.groundedQuestion||'').length,
      gqa_onQuestion:(e)=>this.setState({groundedQuestion:String(e.target.value||'').slice(0,1000),groundedError:''}),
      gqa_onKey:(e)=>{ if(e.key==='Enter'&&e.ctrlKey) this.submitGroundedQA(); },
      gqa_submit:()=>this.submitGroundedQA(),
      gqa_loading:s.groundedLoading,
      gqa_submitDisabled:groundedSubmitDisabled,
      gqa_submitStyle:'height:38px;border-radius:9px;background:var(--brand-600);color:#fff;border:0;font-size:13.5px;font-weight:700;padding:0 17px;display:inline-flex;align-items:center;gap:8px;opacity:'+(groundedSubmitDisabled?'.55':'1')+';cursor:'+(groundedSubmitDisabled?'not-allowed':'pointer'),
      gqa_examples:[
        'RATIONALE-304有哪些证据版本？',
        'RATIONALE-315形成了怎样的证据链？',
        'NCT04619433当前是什么状态？',
        'B015和B016有什么区别？',
        '恒瑞与百济当前证据样本有什么差异？',
        '当前数据还存在哪些缺口？'
      ].map(q=>({text:q,onClick:()=>this.setGroundedExample(q)})),
      gqa_hasError:!!s.groundedError,
      gqa_error:s.groundedError,
      gqa_hasResult:!!s.groundedResult,
      gqa_answer:this._friendlyGroundedText(groundedResult.answer),
      gqa_statusTags:groundedStatusTags,
      gqa_citations:groundedCitations,
      gqa_hasCitations:groundedCitations.length>0,
      gqa_noCitationText:groundedSafetyBlock?'当前回答不需要引用。':'当前回答没有可展示引用。',
      gqa_limitations:groundedLimitations,
      gqa_hasLimitations:groundedLimitations.length>0,
      gqa_safetyNotice:this._evidenceText(groundedResult.safety_notice),
      gqa_hasSafetyNotice:!!groundedResult.safety_notice,
      gqa_traceOpen:s.groundedTraceOpen,
      gqa_toggleTrace:()=>this.setState({groundedTraceOpen:!this.state.groundedTraceOpen}),
      gqa_traceRows:this._groundedTraceRows(groundedTrace),
      gqa_chainLinks:groundedChainIds,
      gqa_hasChainLinks:groundedChainIds.length>0,
      gqa_staticSafety:'系统仅根据当前已核验的NSCLC证据样本回答，不提供诊断、个体治疗'+('建'+'议')+'、疗效保证、跨试验排名、成功'+('率'+'预测')+'或投资'+('建'+'议')+'。',
      gqa_autoNotice:'智能生成会先检索证据，再让 DeepSeek 组织答案；auto 失败时会自动回退本地摘要。',
      gqa_autoUnavailable:'DeepSeek智能生成当前未启用，本地循证摘要仍可使用。页面不会读取、保存或显示任何密钥值。'
    };
  }

  navDef(){
    return {
      main:[
        {key:'today',label:'研发决策工作台',icon:['M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z']},
        {key:'chat',label:'智能问答',icon:['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z']},
        {key:'compare',label:'公司画像 · 对比',icon:['M4 4h6v16H4zM14 4h6v16h-6z']},
        {key:'research',label:'自动化研报',icon:['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z','M14 2v6h6','M9 13h6','M9 17h6']},
        {key:'evidence',label:'研发证据查询',icon:['M4 19.5V5a2 2 0 0 1 2-2h10l4 4v12.5a1.5 1.5 0 0 1-1.5 1.5H6a2 2 0 0 1-2-2z','M14 3v5h5','M8 13h8','M8 17h5']},
        {key:'whitebox',label:'白盒溯源',icon:['M3 7V5a2 2 0 0 1 2-2h2','M17 3h2a2 2 0 0 1 2 2v2','M21 17v2a2 2 0 0 1-2 2h-2','M7 21H5a2 2 0 0 1-2-2v-2','M7 12h10'],badge:'核心'}
      ],
      analysis:[
        {key:'database',label:'数据库浏览',icon:['M12 3c4.97 0 9 1.34 9 3s-4.03 3-9 3-9-1.34-9-3 4.03-3 9-3','M3 6v12c0 1.66 4.03 3 9 3s9-1.34 9-3V6','M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3']},
        {key:'timeline',label:'事件时间轴',icon:['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z','M12 8v4l3 2']},
        {key:'advanced',label:'高级分析',icon:['M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z','M8.6 13.5l6.8 4M15.4 6.5l-6.8 4']}
      ]
    };
  }
  navItem(it){
    const active = this.state.page===it.key;
    const disabled=this._isLegacyPage(it.key)&&!this._legacyAvailable();
    const style='display:flex;align-items:center;gap:11px;padding:0 11px;height:36px;border-radius:9px;font-size:13px;font-weight:500;cursor:pointer;width:100%;text-align:left;border:0;transition:background .12s,color .12s;'+(disabled?'background:transparent;color:var(--gray-300);cursor:not-allowed;':(active?'background:var(--brand-50);color:var(--brand-600);font-weight:600;':'background:transparent;color:var(--text-2);'));
    return Object.assign({}, it, {style, disabled, legacyLabel:disabled?'旧数据未配置':'', iconPaths:this._paths(it.icon), onClick:()=>this.go(it.key)});
  }

  shellVals(){
    const s=this.state;
    const nd=this.navDef();
    const META={today:['研发决策工作台','真实证据总览'],chat:['智能问答','对话与证据'],compare:['公司画像','双公司对比'],research:['自动化研报','报告生成'],evidence:['研发证据查询','来源检索'],whitebox:['白盒溯源','可解释链路'],database:['数据底座','数据库浏览'],timeline:['事件时间轴','公司动态'],advanced:['高级分析','图谱与编排']};
    const m=META[s.page]||['',''];
    const segBase='flex:1;height:24px;border:0;border-radius:5px;font-size:11.5px;font-weight:500;cursor:pointer;transition:all .12s;';
    return {
      theme:s.theme, present:s.present?'on':'off', navOpenAttr:s.navOpen?'1':'0',
      navMain:nd.main.map(it=>this.navItem(it)), navAnalysis:nd.analysis.map(it=>this.navItem(it)),
      legacyNotice:s.legacyNotice||'', hasLegacyNotice:!!s.legacyNotice,
      crumbGroup:m[0], crumbSub:m[1],
      company:s.company, year:s.year, topK:s.topK, companies:this._liveCompanies(), years:this._liveYears(),
      isToday:s.page==='today', isChat:s.page==='chat', isCompare:s.page==='compare', isResearch:s.page==='research', isEvidence:s.page==='evidence', isWhitebox:s.page==='whitebox', isDatabase:s.page==='database', isTimeline:s.page==='timeline', isAdvanced:s.page==='advanced',
      themeIconPaths: this._paths(s.theme==='dark'?['M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z']:['M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4','M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z']),
      toggleTheme:()=>this.setState({theme:s.theme==='dark'?'light':'dark'}),
      togglePresent:()=>this.setState({present:!s.present}),
      toggleMode:()=>this.setState({deepseek:!s.deepseek}),
      openNav:()=>this.setState({navOpen:true}), closeNav:()=>this.setState({navOpen:false}),
      onCompany:(e)=>this.setParam({company:e.target.value}),
      onYear:(e)=>this.setParam({year:Number(e.target.value)}),
      onScopeInd:()=>this.setParam({scope:'industry'}), onScopeAll:()=>this.setParam({scope:'all'}),
      onTopK:(e)=>this.setState({topK:Number(e.target.value)}),
      scopeIndStyle:segBase+(s.scope==='industry'?'background:var(--brand-600);color:#fff;':'background:transparent;color:var(--text-2);'),
      scopeAllStyle:segBase+(s.scope==='all'?'background:var(--brand-600);color:#fff;':'background:transparent;color:var(--text-2);'),
      statusColor:s.deepseek?'var(--pos)':'var(--warn)',
      statusText:s.deepseek?'DeepSeek 增强已启用':'本地降级模式 · 离线可跑',
      modeLabel:s.deepseek?'增强模式':'本地模式',
      modeColor:s.deepseek?'var(--pos)':'var(--warn)',
      modeBg:s.deepseek?'var(--pos-bg)':'var(--warn-bg)',
      modeBorder:'transparent',
      presentColor:s.present?'#fff':'var(--text-2)', presentBg:s.present?'var(--brand-600)':'var(--bg-elev)', presentBorder:s.present?'var(--brand-600)':'var(--border)',
      goChat:()=>this.go('chat'), goResearch:()=>this.go('research'), goCompare:()=>this.go('compare'), goWhitebox:()=>this.go('whitebox'),
      presentOn:s.present, demoIdx:s.demoStep+1, demoTotal:5,
      demoPrev:()=>this.demoGo(s.demoStep-1), demoNext:()=>this.demoGo(s.demoStep+1),
      demoSteps:this.demoStepsDef().map((d,i)=>({t:d.t,idx:i+1,onClick:()=>this.demoGo(i),
        iconPaths:this._paths(d.icon),
        style:'display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:500;border:0;cursor:pointer;border-radius:999px;padding:6px 13px;transition:all .12s;'+(i===s.demoStep?'background:#fff;color:var(--brand-800)':'background:rgba(255,255,255,.1);color:rgba(255,255,255,.82)')}))
    };
  }

  todayVals(){
    const wb=this.state.evidenceWorkbench||{};
    const summary=wb.summary||{};
    const metadata=wb.metadata||{};
    const metric=(label,value,hint,icon)=>({label,value:this._evidenceText(value),hint,iconPaths:this._paths(icon)});
    const today_metrics=[
      metric('总来源',summary.source_count,'当前来源登记表中的人工核验样本总数',['M4 19.5V5a2 2 0 0 1 2-2h10l4 4v12.5a1.5 1.5 0 0 1-1.5 1.5H6a2 2 0 0 1-2-2z','M8 13h8','M8 17h5']),
      metric('已核验来源',summary.verified_source_count,'当前来源登记表中 verification_status=已人工核验',['M9 12l2 2 4-5','M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z']),
      metric('企业主体',summary.company_count,'按恒瑞医药与百济神州/BeOne归一主体统计',['M3 21h18M5 21V7l8-4v18M19 21V11l-6-4']),
      metric('试验级证据链',summary.trial_chain_count,'同一 trial_id 只计一项试验链',['M4 19.5V5a2 2 0 0 1 2-2h10l4 4v12.5a1.5 1.5 0 0 1-1.5 1.5H6a2 2 0 0 1-2-2z','M14 3v5h5']),
      metric('药物级监管链',summary.regulatory_chain_count,'监管链单独统计，不计入试验数量',['M9 12l2 2 4-4','M7 4h10l2 4v12H5V8z']),
      metric('最新资料',summary.latest_count,'is_latest_evidence=true',['M12 8v4l3 2','M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z']),
      metric('历史版本',summary.historical_count,'is_latest_evidence=false',['M3 12a9 9 0 1 0 3-6.7','M3 3v6h6']),
      metric('独立资料',summary.independent_count,'未形成版本替代关系的核验资料',['M8 7h8M8 12h8M8 17h5','M5 3h14v18H5z']),
      metric('待确认关系',summary.unresolved_link_count,'当前样本尚缺明确一对一关联',['M12 9v4M12 17h.01','M10.3 3.9 1.8 7.2a2 2 0 0 0 1.9 2.5h14a2 2 0 0 0 1.9-2.5l-7.2-7.2a2 2 0 0 0-2.8 0z'])
    ];
    const quick=(label,desc,tab,icon)=>({label,desc,onClick:()=>this.setState({page:'evidence',evidenceTab:tab,navOpen:false},()=>this.loadEvidencePage()),iconPaths:this._paths(icon)});
    const today_quickLinks=[
      quick('查看来源检索','按企业、药物、试验或来源ID查看核验记录。','sources',['M4 19.5V5a2 2 0 0 1 2-2h10l4 4v12.5a1.5 1.5 0 0 1-1.5 1.5H6a2 2 0 0 1-2-2z','M8 13h8']),
      quick('查看证据链','检查试验登记、论文和监管事件的人工关联。','chains',['M7 7h.01M17 7h.01M7 17h.01M17 17h.01','M7 7h10M7 17h10M7 7v10M17 7v10']),
      quick('查看企业对比','对比恒瑞与百济/BeOne在当前样本内的证据覆盖。','companyCompare',['M4 4h6v16H4zM14 4h6v16h-6z']),
      quick('打开循证问答','使用安全边界内的本地循证摘要或已启用的智能生成。','groundedQa',['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'])
    ];
    const dist=(list)=>Array.isArray(list)?list.map(x=>({label:this._evidenceText(x&&x.label),count:this._evidenceText(x&&x.count)})):[];
    const companies=(Array.isArray(wb.companies)?wb.companies:[]).map(c=>{
      const version=c.version_distribution||{};
      const gaps=Array.isArray(c.evidence_gaps)?c.evidence_gaps:[];
      const drugs=Array.isArray(c.drug_names)?c.drug_names.slice(0,6).map(x=>({name:this._evidenceText(x)})):[];
      return {
        name:this._companyLabel(c.display_name||c.company_name),
        source_count:this._evidenceText(c.source_count),
        verified_source_count:this._evidenceText(c.verified_source_count),
        trial_chain_count:this._evidenceText(c.trial_chain_count),
        regulatory_chain_count:this._evidenceText(c.regulatory_chain_count),
        multi_source_trial_chain_count:this._evidenceText(c.multi_source_trial_chain_count),
        unresolved_link_count:this._evidenceText(c.unresolved_link_count),
        latest:this._evidenceText(version.latest),
        historical:this._evidenceText(version.historical),
        independent:this._evidenceText(version.independent),
        latest_verified_at:this._evidenceText(c.latest_verified_at),
        drugs,
        hasDrugs:drugs.length>0,
        gap_count:gaps.length
      };
    });
    const gaps=(Array.isArray(wb.evidence_gaps)?wb.evidence_gaps:[]).slice(0,8).map(g=>({
      source_id:this._evidenceText(g&&g.source_id),
      company:this._companyLabel(g&&g.company_name),
      title:this._evidenceText(g&&g.title),
      description:this._evidenceText(g&&g.description),
      gapText:Array.isArray(g&&g.evidence_gaps)?g.evidence_gaps.join('；'):this._evidenceText(g&&g.evidence_gaps)
    }));
    const limitations=(Array.isArray(wb.limitations)?wb.limitations:[]).map(x=>({text:this._evidenceText(x)}));
    return {
      today_loading:this.state.evidenceWorkbenchLoading,
      today_hasError:!!this.state.evidenceWorkbenchError,
      today_error:this.state.evidenceWorkbenchError,
      today_hasData:!!(wb&&wb.summary),
      today_empty:this.state.evidenceWorkbenchLoaded&&!this.state.evidenceWorkbenchLoading&&!this.state.evidenceWorkbenchError&&!wb.summary,
      today_metrics,
      today_quickLinks,
      today_companies:companies,
      today_hasCompanies:companies.length>0,
      today_sourceTypes:dist(wb.source_type_distribution),
      today_studyStatuses:dist(wb.study_status_distribution),
      today_gaps:gaps,
      today_hasGaps:gaps.length>0,
      today_noGaps:!gaps.length&&!!wb.summary,
      today_limitations:limitations,
      today_scopeWarning:'当前结果仅反映已收录并核验的NSCLC证据样本，不代表企业整体研发实力。',
      today_dataVersion:this._evidenceText(metadata.data_version),
      today_latestVerifiedAt:this._evidenceText(metadata.latest_verified_at),
      today_generatedAt:this._evidenceText(metadata.generated_at),
      today_dataScope:this._evidenceText(metadata.data_scope_label||metadata.data_scope)
    };
  }

  // ---- chat ----
  getMsgs(){ return this.state.chatMsgs || this.seedChat(); }
  // 空开场（避免写死某家公司的演示问答）；首次提问/点推荐问题即走真实 /api/chat
  seedChat(){ return []; }
  _liveChatResp(d){
    const hasSql = Array.isArray(d.sql_rows) && d.sql_rows.length;
    const useMacro = !hasSql && Array.isArray(d.macro_rows) && d.macro_rows.length;
    const tbl=this._sqlTable(useMacro ? d.macro_rows : d.sql_rows);
    return {
      route: d.route?('路由 · '+d.route):'SQL + RAG 混合',
      blocks: this._mdBlocks(d.answer_markdown),
      mdText: d.answer_markdown||'',
      sql: useMacro ? (d.macro_sql||'') : (d.sql||d.macro_sql||''),
      cols: tbl.cols,
      rows: tbl.rows,
      chunks: this._chunkAdapt(d.chunks, false)
    };
  }
  ask(q){
    const prior=this.getMsgs();
    const history=(this.state.chatCtxOn!==false)?prior.filter(m=>(m.role==='user')||(m.role==='ai'&&m.resp)).slice(-8).map(m=>({role:m.role==='user'?'user':'assistant', content:m.role==='user'?(m.text||''):this._respText(m.resp)})):[];
    const msgs=prior.slice();
    msgs.push({role:'user',text:q});
    const ai=msgs.length;
    msgs.push({role:'ai',loading:true,resp:null});
    this.setState({chatMsgs:msgs,chatInput:'',chatActive:ai,chatLoading:true});
    const s=this.state;
    const finish=(resp)=>{ const m2=this.getMsgs().slice(); m2[ai]={role:'ai',loading:false,resp}; this.setState({chatMsgs:m2,chatLoading:false}, ()=>this._saveConvs()); };
    this._apiPost('/api/chat',{question:q, company_name:s.company||null, report_year:s.year||null, top_k:s.topK||5, history, model:s.chatModel||'flash'})
      .then(d=>finish(this._liveChatResp(d)))
      .catch((e)=>{ finish({route:'连接失败', blocks:[{t:'p', text:'⚠️ 在线问答暂时不可用：服务器调用大模型失败（'+String((e&&e.message)||e).slice(0,90)+'）。常见原因是服务器无法连接 api.deepseek.com（DNS/网络）。修复后重试即可。'}], sql:'', cols:[], rows:[], chunks:[]}); });
  }
  send(){ const q=(this.state.chatInput||'').trim(); if(q&&!this.state.chatLoading) this.ask(q); }
  answerFor(q){
    return {
      route:'SQL + RAG 混合',
      blocks:[
        {t:'p',text:'恒瑞医药 2024 年经营质量整体回升，呈现「收入重回增长、盈利弹性释放、研发持续高投入」的特征：'},
        {t:'li',text:'营业收入 279.9 亿元，同比 +22.6%，重回历史高位；集采影响逐步消化，创新药放量贡献主要增量。'},
        {t:'li',text:'归母净利润 63.4 亿元，同比 +47.5%，利润弹性显著高于收入，销售毛利率回升至 86.6%。'},
        {t:'li',text:'研发投入 65.8 亿元（全部费用化），研发强度约 23.5%，在研管线 78 项，创新驱动特征明确。'},
        {t:'p',text:'风险关注：应收账款周转天数同比上升约 9 天，需跟踪集采放量下的回款节奏。'}
      ],
      sql:"SELECT indicator_name, report_year, value_num, unit\nFROM fact_financial\nWHERE company_name = '恒瑞医药'\n  AND report_year IN (2023, 2024)\n  AND indicator_name IN ('营业收入','归母净利润','研发投入','销售毛利率')\nORDER BY indicator_name, report_year;",
      cols:['指标','2023','2024','同比'],
      rows:[['营业收入(亿元)','228.2','279.9','+22.6%'],['归母净利润(亿元)','43.0','63.4','+47.5%'],['研发投入(亿元)','49.5','65.8','+32.9%'],['销售毛利率(%)','84.9','86.6','+1.7pct']],
      chunks:[
        {source:'恒瑞医药 · 2024年年度报告',score:0.912,doc_id:'HRYY-2024-MD-0042',text:'报告期内公司实现营业收入279.91亿元，同比增长22.63%；归属于上市公司股东的净利润63.37亿元，同比增长47.54%……'},
        {source:'恒瑞医药 · 2024年年度报告',score:0.864,doc_id:'HRYY-2024-MD-0118',text:'公司持续加大研发投入，全年研发费用65.83亿元，创新药收入占比进一步提升，多个创新药获批上市……'},
        {source:'恒瑞医药 · 2024年年度报告',score:0.791,doc_id:'HRYY-2024-MD-0203',text:'公司综合毛利率为86.61%，盈利能力保持稳健，销售费用率同比下降，期间费用结构持续优化……'}
      ]
    };
  }
  componentDidUpdate(){ if(this.state.page==='chat'&&this._chatScroll){ this._chatScroll.scrollTop=this._chatScroll.scrollHeight; } }

  // ---- compare / profile ----
  getProf(name){
    const D=this.D;
    const base={
      '恒瑞医药':{track:'化学制药',risk:12,patent:1840,nodes:47,rev:D.rev,np:D.np,rd:D.rd,gm:D.gm,
        metrics:[['营业收入','279.9 亿元','同比 +22.6%'],['归母净利润','63.4 亿元','同比 +47.5%'],['研发投入','65.8 亿元','研发强度 23.5%'],['销售毛利率','86.6 %','同比 +1.7pct'],['经营性现金流','51.2 亿元','同比 +18.3%'],['总资产','558.7 亿元','同比 +9.1%']],
        riskCards:[['高风险信号','1'],['中风险信号','3'],['涉诉事件','4'],['监管问询','0']],
        innovCards:[['发明专利','1,240'],['在研管线','78'],['创新药收入占比','61%'],['研发人员','5,400+']],
        equityCards:[['图谱节点','47'],['关系边','86'],['一级股东','12']],
        patents:{inv:[180,210,245,268,290],uti:[90,105,120,128,140]},
        summary:'恒瑞医药 2024 年收入与利润同步回升，创新药放量驱动盈利弹性，研发强度维持高位，整体经营质量稳健。'},
      '复星医药':{track:'化学制药',risk:23,patent:1260,nodes:63,rev:D.fosun.rev,np:D.fosun.np,rd:D.fosun.rd,gm:D.fosun.gm,
        metrics:[['营业收入','410.7 亿元','同比 -0.8%'],['归母净利润','27.7 亿元','同比 +15.9%'],['研发投入','55.0 亿元','研发强度 13.4%'],['销售毛利率','47.8 %','同比 -1.2pct'],['经营性现金流','38.4 亿元','同比 +6.2%'],['总资产','1,182 亿元','同比 +3.4%']],
        riskCards:[['高风险信号','3'],['中风险信号','6'],['涉诉事件','9'],['监管问询','1']],
        innovCards:[['发明专利','860'],['在研管线','64'],['创新药收入占比','38%'],['研发人员','4,100+']],
        equityCards:[['图谱节点','63'],['关系边','118'],['一级股东','18']],
        patents:{inv:[150,165,178,190,196],uti:[80,88,95,100,104]},
        summary:'复星医药营收体量领先，但毛利率偏低、商誉与涉诉风险更高，盈利质量与风险敞口与恒瑞形成鲜明对照。'}
    };
    const demo=base[name]||base['恒瑞医药'];
    if(name===this.state.company){ const p=this._matched('profile'); if(p && p.company_name){ const live=this._profToProf(p); if(live) return live; } }
    return demo;
  }
  _profToProf(p){
    const cardVal=(label)=>{ const c=(p.cards||[]).find(x=>x.label===label); return c?c.value:undefined; };
    const trend=this._pivot(p.trend_chart), ratio=this._pivot(p.ratio_chart), inno=this._pivot(p.innovation_chart);
    const trendSeries=[];
    const rev=trend?this._seriesValues(trend,'营业收入'):null;
    const np=trend?this._seriesValues(trend,'归属于上市公司股东的净利润'):null;
    const rd=trend?this._seriesValues(trend,'研发费用'):null;
    if(rev) trendSeries.push({name:'营业收入',color:'#3b428f',values:rev});
    if(np) trendSeries.push({name:'归母净利润',color:'#0d9488',values:np});
    if(rd) trendSeries.push({name:'研发投入',color:'#b45309',values:rd});
    const gmSeries = ratio? ratio.series.map(s=>({name:s.name,color:'#6d28d9',values:s.values})) : null;
    let patLabels=null, patSeries=null;
    if(inno){ patLabels=inno.labels; patSeries=inno.series.map((s,i)=>({name:s.name,color:i?'#0d9488':'#3b428f',values:s.values})); }
    const numOr0=(v)=>{ const n=Number(v); return isFinite(n)?n:0; };
    return {
      live:true,
      track:(cardVal('所属赛道'))||p.industry_name||'医药生物',
      risk:numOr0(cardVal('风险事件总数')),
      patent:numOr0(cardVal('专利总量')),
      nodes:numOr0(cardVal('股权节点数')),
      metrics:(p.metric_cards||[]).slice(0,6).map(m=>[m.label, this._fmtAmtStr(m.value), m.meta]),
      riskCards:(p.risk_cards||[]).map(c=>[c.label, (String(c.label).indexOf('金额')>=0)?this._fmtAmtStr(c.value):String(c.value)]),
      innovCards:(p.innovation_cards||[]).map(c=>[c.label, String(c.value)]),
      equityCards:(p.equity_cards||[]).map(c=>[c.label, String(c.value)]),
      summary:p.summary||'',
      trendLabels: trend?trend.labels:(ratio?ratio.labels:null), trendSeries,
      gmLabels: ratio?ratio.labels:null, gmSeries,
      patLabels, patSeries
    };
  }
  compareData(a,b,yi){
    const live=this._matched('compare');
    if(live && Array.isArray(live.rows) && live.rows.length && Array.isArray(live.company_names) && live.company_names.length>=2){
      const la=live.company_names[0], rb=live.company_names[1];
      const rows=live.rows.map(r=>{ const w=r.winner; const lW=w===la, rW=w===rb; return {metric:r.metric,left:this._fmtAmtStr(r.left_value),right:this._fmtAmtStr(r.right_value),winner:w,leftColor:lW?'var(--text)':'var(--text-2)',rightColor:rW?'var(--text)':'var(--text-2)',leftWin:lW?'600':'400',rightWin:rW?'600':'400'}; });
      const piv=this._pivot(live.chart);
      let barLabels=[], barSeries=[];
      if(piv){ barLabels=piv.labels.slice(0,4);
        const allv=piv.series.reduce((a,s)=>a.concat(s.values.slice(0,4)),[]).filter(v=>v!=null);
        const mxv=allv.length?Math.max.apply(null,allv.map(Math.abs)):0;
        const div=mxv>=1e6?1e8:1; // 后端金额为「元」量级时折算成亿元（图头单位即亿元）
        barSeries=piv.series.map(s=>({name:s.name,color:s.color,values:s.values.slice(0,4).map(v=>v!=null?v/div:null)})); }
      return {rows, barLabels, barSeries, summary:live.summary||''};
    }
    const pa=this.getProf(a), pb=this.getProf(b);
    // pa/pb 可能是 live 画像（无 rev/np/rd/gm/patents 等演示数组）；此时不可走演示对比计算，
    // 等 /api/compare 拉到再渲染（对比 tab 仅在 compare 页可见，会触发 loadCompare）。
    if(pa.live||pb.live) return {rows:[],barLabels:[],barSeries:[],summary:''};
    const def=[['营业收入(亿元)',pa.rev[yi],pb.rev[yi],'high'],['归母净利润(亿元)',pa.np[yi],pb.np[yi],'high'],['研发投入(亿元)',pa.rd[yi],pb.rd[yi],'high'],['销售毛利率(%)',pa.gm[yi],pb.gm[yi],'high'],['风险事件总数',pa.risk,pb.risk,'low'],['专利总量',pa.patent,pb.patent,'high']];
    let aw=0,bw=0;
    const fmt=v=>Number.isInteger(v)?this.nf(v):(+v).toFixed(1);
    const rows=def.map(r=>{ const lv=r[1],rv=r[2],dir=r[3]; let winner; if(lv===rv)winner='持平'; else { const aB=dir==='high'?lv>rv:lv<rv; winner=aB?a:b; aB?aw++:bw++; } const lW=winner===a, rW=winner===b; return {metric:r[0],left:fmt(lv),right:fmt(rv),winner,leftColor:lW?'var(--text)':'var(--text-2)',rightColor:rW?'var(--text)':'var(--text-2)',leftWin:lW?'600':'400',rightWin:rW?'600':'400'}; });
    return {rows,barLabels:['营业收入','归母净利润','研发投入'],barSeries:[{name:a,color:'#3b428f',values:[pa.rev[yi],pa.np[yi],pa.rd[yi]]},{name:b,color:'#0d9488',values:[pb.rev[yi],pb.np[yi],pb.rd[yi]]}],summary:a+' 领先 '+aw+' 项 · '+b+' 领先 '+bw+' 项'};
  }

  // ---- research ----
  _profReport(name, prof){
    const sty=(t)=> t==='h2'?'font-size:17.5px;font-weight:600;margin:24px 0 11px;color:var(--text)':(t==='li'?'display:flex;gap:10px;font-size:15px;line-height:1.78;color:var(--text-2);margin:0':'font-size:15px;line-height:1.85;color:var(--text-2);margin:0');
    const yr=prof.report_year||this.state.year;
    const raw=[['h2','一、公司概览'],['p', name+' 隶属 '+(prof.industry_name||'医药生物')+' 赛道，以下为基于结构化年报数据的关键画像（'+yr+' 年）。']];
    raw.push(['h2','二、关键财务指标']);
    (prof.metric_cards||[]).slice(0,6).forEach(m=>raw.push(['li', m.label+'：'+this._fmtAmtStr(m.value)+(m.meta?('（'+m.meta+'）'):'')]));
    if((prof.risk_cards||[]).length){ raw.push(['h2','三、风险维度']); prof.risk_cards.slice(0,5).forEach(c=>raw.push(['li', c.label+'：'+c.value])); }
    if((prof.innovation_cards||[]).length){ raw.push(['h2','四、创新维度']); prof.innovation_cards.slice(0,5).forEach(c=>raw.push(['li', c.label+'：'+c.value])); }
    if(prof.summary){ raw.push(['h2','五、画像摘要']); raw.push(['p', prof.summary]); }
    raw.push(['p','— 以上为结构化数据速览；点击上方「生成研究报告」可获得 DeepSeek 增强的完整研判与原文溯源。']);
    const blocks=raw.map(r=>({text:r[1],heading:r[0]==='h2',bullet:r[0]==='li',style:sty(r[0])}));
    const outline=raw.filter(r=>r[0]==='h2').map(r=>r[1]);
    // 引用来源：速览阶段未做 RAG，用该公司最新年度报告作为结构化数据来源
    const chunks=[];
    const ld=prof.latest_document;
    if(ld){ chunks.push({source: ld.title||ld.file_name||(name+' · 年度报告'), score:'结构化', doc_id:(ld.report_year?(ld.report_year+' 年报'):'年度报告'), text:'本速览的财务 / 风险 / 创新指标均来自该公司最新年度报告的结构化解析结果。点击「生成研究报告」可获得带原文切片的完整溯源。'}); }
    chunks.push({source: name+' · 结构化指标库', score:'SQL', doc_id:'fact_financial_report', text:'营收 / 利润 / 现金流 / 研发 / 净资产收益率 / 总资产 等指标取自结构化财务事实表（'+yr+' 年口径）。'});
    return {title:name+' · 经营质量速览（'+yr+'）', blocks, outline, chunks};
  }
  reportFor(name){
    const rd=(this.state.resData||{})[name];
    const raw=[
      ['h2','一、公司概览'],
      ['p',name+' 隶属医药生物（化学制药）赛道，主营创新药与仿制药的研发、生产与销售，研发驱动特征显著。'],
      ['h2','二、财务表现'],
      ['li','营业收入 279.9 亿元，同比 +22.6%，重回历史高位，集采影响逐步消化。'],
      ['li','归母净利润 63.4 亿元，同比 +47.5%，利润弹性显著高于收入增速。'],
      ['li','研发投入 65.8 亿元，研发强度约 23.5%，维持 A 股医药领先水平。'],
      ['li','销售毛利率 86.6%，同比 +1.7pct，盈利能力稳健。'],
      ['h2','三、同业对比'],
      ['p','与复星医药相比，'+name+' 营收体量偏小但盈利质量与研发强度明显占优，销售毛利率高出近 39 个百分点，风险事件数量更少。'],
      ['h2','四、风险提示'],
      ['li','应收账款周转天数同比上升约 9 天，需关注集采放量下的回款节奏。'],
      ['li','研发投入全部费用化，短期压低当期利润弹性。'],
      ['h2','五、结论与建议'],
      ['p','整体经营质量稳健回升，创新药放量是核心驱动；建议持续跟踪重点管线获批节奏与回款质量，并关注海外授权（License-out）进展。']
    ];
    const sty=(t)=> t==='h2'?'font-size:17.5px;font-weight:600;margin:24px 0 11px;color:var(--text)':(t==='li'?'display:flex;gap:10px;font-size:15px;line-height:1.78;color:var(--text-2);margin:0':'font-size:15px;line-height:1.85;color:var(--text-2);margin:0');
    const blocks=raw.map(r=>({text:r[1],heading:r[0]==='h2',bullet:r[0]==='li',style:sty(r[0])}));
    const outline=raw.filter(r=>r[0]==='h2').map(r=>r[1]);
    const chunks=[
      {source:name+' · 2024年年度报告',score:'0.912',doc_id:'MD-0042',text:'报告期内公司实现营业收入279.91亿元，同比增长22.63%……'},
      {source:name+' · 2024年年度报告',score:'0.864',doc_id:'MD-0118',text:'全年研发费用65.83亿元，创新药收入占比进一步提升……'},
      {source:name+' · 2024年年度报告',score:'0.802',doc_id:'MD-0203',text:'综合毛利率86.61%，期间费用结构持续优化……'},
      {source:'卫生健康统计年鉴 · 2024',score:'0.738',doc_id:'MACRO-0011',text:'全国卫生总费用持续增长，医药制造业景气度维持高位……'}
    ];
    if(rd && rd.report_markdown){
      const mdb=this._mdBlocks(rd.report_markdown);
      const lblocks=mdb.map(b=>({text:b.text,heading:b.t==='h2',bullet:b.t==='li',style:sty(b.t)}));
      const loutline=mdb.filter(b=>b.t==='h2').map(b=>b.text);
      let lchunks=this._chunkAdapt(rd.rag_chunks,true); if(!lchunks.length) lchunks=chunks;
      return {title:(rd.topic||(name+' · 经营质量研究简报')),blocks:lblocks,outline:loutline,chunks:lchunks};
    }
    const prof=this._resProfile(name);
    if(prof && prof.company_name) return this._profReport(prof.company_name, prof);
    return {title:name+' · 经营质量研究简报（2024）',blocks,outline,chunks};
  }
  genReport(){
    if(this.state.resLoading) return;
    const s=this.state;
    this.setState({resLoading:true,resDone:false});
    const done=(patch)=>this.setState(Object.assign({resLoading:false,resDone:true}, patch||{}));
    if(s.resMode==='batch'){
      const names=(s.resList||'').split(/[，,、\n]+/).map(x=>x.trim()).filter(Boolean).slice(0,5);
      this._apiPost('/api/batch-workflow',{company_names:names, report_year:s.year||null, top_k:s.topK||5})
        .then(d=>{ const rd=Object.assign({}, this.state.resData); (d.items||[]).forEach(it=>{ rd[it.company_name]={report_markdown:it.report_markdown, data_mode:it.data_mode, topic:it.topic, rag_chunks:[]}; }); done({resData:rd}); })
        .catch(()=>done());
    } else {
      const name=s.company;
      const topic=(s.resTopic&&s.resTopic.trim())||('请为 '+name+' 生成经营质量与风险诊断报告');
      this._apiPost('/api/workflow',{topic, company_name:name||null, report_year:s.year||null, top_k:s.topK||5})
        .then(d=>{ const rd=Object.assign({}, this.state.resData); rd[name]={report_markdown:d.report_markdown, data_mode:d.data_mode, topic:d.topic, sql:d.sql, sql_rows:d.sql_rows, rag_chunks:d.rag_chunks}; done({resData:rd}); })
        .catch(()=>done());
    }
  }
  downloadMd(name){ const rep=this.reportFor(name); let md='# '+rep.title+'\n\n'; rep.blocks.forEach(b=>{ md+=(b.heading?'## '+b.text:(b.bullet?'- '+b.text:b.text))+'\n\n'; }); try{ const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([md],{type:'text/markdown'})); a.download=name+'-研究简报.md'; a.click(); }catch(e){} }
  copyReport(name){ const rep=this.reportFor(name); let txt=rep.title+'\n\n'; rep.blocks.forEach(b=>{ txt+=(b.bullet?'• '+b.text:b.text)+'\n'; }); try{ navigator.clipboard.writeText(txt); }catch(e){} this.setState({resCopied:true,resExportOpen:false}); if(this._cpT)clearTimeout(this._cpT); this._cpT=setTimeout(()=>this.setState({resCopied:false}),1600); }
  printReport(){ try{ window.print(); }catch(e){} }

  // ---- demo storyline ----
  demoStepsDef(){ return [
    {t:'企业诊断',page:'compare',tab:'profile'},
    {t:'双公司比较',page:'compare',tab:'compare'},
    {t:'宏观联动',page:'advanced'},
    {t:'白盒溯源',page:'whitebox'},
    {t:'自动化报告',page:'research'}
  ]; }
  demoGo(i){ const d=this.demoStepsDef(); const c=Math.max(0,Math.min(d.length-1,i)); const st=d[c]; this.setState({page:st.page,cmpTab:st.tab||this.state.cmpTab,present:true,navOpen:false,demoStep:c,anim:0},()=>{ this.runCount(); this.loadPage(); }); }

  /*__METHODS__*/

  chatVals(){
    const s=this.state;
    const msgs=this.getMsgs();
    const active=this.state.chatActive;
    const vm=msgs.map((m,i)=>{
      const isAi=m.role==='ai';
      const isActive=isAi && i===active && !m.loading;
      return {
        isUser:m.role==='user', isAi, loading:!!m.loading, done:isAi&&!m.loading,
        text:m.text||'', route:m.resp?m.resp.route:'', active:isActive,
        blocks:(m.resp?m.resp.blocks:[]).map(b=>({text:b.text,bullet:b.t==='li',
          style:(b.t==='li'?'display:flex;gap:8px;font-size:13.5px;line-height:1.62;color:var(--text-2)':'font-size:13.5px;line-height:1.7;color:var(--text)')+';margin:0'})),
        wrapStyle:'cursor:pointer;border:1px solid '+(isActive?'var(--brand-400)':'var(--border)')+';background:var(--bg-elev);border-radius:4px 13px 13px 13px;padding:13px 16px;max-width:88%;transition:border-color .15s'+(isActive?';box-shadow:0 0 0 3px var(--brand-100)':''),
        onClick:()=>this.setState({chatActive:i})
      };
    });
    let resp=null; const am=msgs[active];
    if(am&&am.resp) resp=am.resp;
    if(!resp){ for(let i=msgs.length-1;i>=0;i--){ if(msgs[i].resp){ resp=msgs[i].resp; break; } } }
    const ev = resp?{has:true, route:resp.route, sql:resp.sql, cols:resp.cols,
      rows:resp.rows.map(r=>({cells:r})),
      chunks:resp.chunks.map(c=>({source:c.source,score:c.score.toFixed(3),doc_id:c.doc_id,text:c.text}))}:{has:false};
    const co=s.company, co2=(s.compareCompany&&s.compareCompany!==s.company)?s.compareCompany:'同业公司', yr=s.year;
    const sug=[
      {label:'企业诊断',q:'请总结 '+co+' '+yr+' 年的经营质量'},
      {label:'双公司对比',q:co+' 与 '+co2+' '+yr+' 年盈利能力差在哪'},
      {label:'宏观联动',q:'卫生总费用增长对 '+co+' 营收的拉动如何'},
      {label:'研发能力',q:co+' 的研发投入强度与在研管线情况'}
    ].map(x=>({label:x.label,onClick:()=>this.ask(x.q)}));
    const convs=this.state.chatConvs||[];
    const empty=(msgs.length===0);
    const sbOpen=this.state.chatSidebar!==false;
    const chat_convs=convs.map(c=>{ const act=c.id===this.state.chatConvId; return {
      cls:act?'dcv dcv-on':'dcv',
      title:(c.title||'新对话'),
      onClick:()=>this.switchChat(c.id),
      onDelete:(e)=>{ if(e&&e.stopPropagation) e.stopPropagation(); this.deleteChat(c.id); }
    }; });
    const ctxOn=this.state.chatCtxOn!==false;
    const model=this.state.chatModel||'flash';
    const seg='flex:1;height:28px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:0;transition:all .12s;';
    return {
      chat_msgs:vm, chat_ev:ev, chat_evHas:ev.has, chat_loading:this.state.chatLoading,
      chat_input:this.state.chatInput,
      chat_onInput:(e)=>this.setState({chatInput:e.target.value}),
      chat_onKey:(e)=>{ const comp=(e.isComposing)||(e.nativeEvent&&e.nativeEvent.isComposing)||(e.keyCode===229); if(e.key==='Enter'&&!e.shiftKey&&!comp){ e.preventDefault(); this.send(); } },
      chat_send:()=>this.send(), chat_suggestions:sug,
      chat_convs:chat_convs, chat_hasConvs:convs.length>0,
      chat_new:()=>this.newChat(),
      chat_newStyle:'flex:1;height:34px;padding:0 10px;border-radius:9px;font-size:12.5px;font-weight:600;cursor:pointer;border:0;background:var(--brand-600);color:#fff;display:inline-flex;align-items:center;justify-content:center;gap:5px;white-space:nowrap',
      chat_newIconStyle:'width:34px;height:34px;border-radius:9px;border:0;background:var(--brand-600);color:#fff;cursor:pointer;font-size:18px;display:inline-flex;align-items:center;justify-content:center',
      chat_empty:empty, chat_chromeOp: empty?'0':'1',
      chat_sidebarOpen:sbOpen, chat_sidebarClosed:!sbOpen,
      chat_gridCols: empty?'0px 1fr 0px':(sbOpen?'238px 1fr 332px':'48px 1fr 332px'),
      chat_colStyle:'display:flex;flex-direction:column;min-width:0;height:calc(100vh - 178px)',
      chat_scrollStyle:'flex:1 1 0;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:14px;padding:4px 6px 4px 2px',
      chat_bottomSpacer: empty?'1':'0',
      chat_welcomeStyle: empty?'text-align:center;opacity:1;max-height:170px;margin-bottom:20px;transition:opacity .3s ease,max-height .35s ease,margin-bottom .3s ease':'text-align:center;opacity:0;max-height:0;margin-bottom:0;overflow:hidden;transition:opacity .2s ease,max-height .3s ease,margin-bottom .3s ease',
      chat_toggleSidebar:()=>this.setState(st=>({chatSidebar:st.chatSidebar===false})),
      chat_collapseStyle:'width:30px;height:34px;border-radius:8px;border:1px solid var(--border);background:var(--bg-elev);color:var(--text-2);cursor:pointer;font-size:13px;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center',
      chat_settingsOpen:!!this.state.chatSettings,
      chat_toggleSettings:()=>this.setState(st=>({chatSettings:!st.chatSettings})),
      chat_settingsBtnStyle:'width:100%;height:32px;border-radius:8px;border:1px solid var(--border);background:var(--bg-elev);color:var(--text-2);cursor:pointer;font-size:12px;display:inline-flex;align-items:center;justify-content:center;gap:6px',
      chat_model:model, chat_isFlash:model==='flash', chat_isPro:model==='pro',
      chat_modelHint: model==='pro'?'Pro · 深度分析(较慢)':'Flash · 快速',
      chat_setFlash:()=>this.setState({chatModel:'flash'}), chat_setPro:()=>this.setState({chatModel:'pro'}),
      chat_flashStyle:seg+(model==='flash'?'background:var(--brand-600);color:#fff':'background:transparent;color:var(--text-2)'),
      chat_proStyle:seg+(model==='pro'?'background:var(--brand-600);color:#fff':'background:transparent;color:var(--text-2)'),
      chat_ctxOn:ctxOn, chat_ctxLabel:ctxOn?'多轮上下文 · 已开启':'多轮上下文 · 已关闭',
      chat_ctxStyle:'width:100%;height:30px;border-radius:7px;cursor:pointer;font-size:12px;margin-bottom:7px;border:1px solid '+(ctxOn?'var(--brand-300)':'var(--border)')+';background:'+(ctxOn?'var(--brand-50)':'var(--bg-elev)')+';color:'+(ctxOn?'var(--brand-600)':'var(--text-2)'),
      chat_toggleCtx:()=>this.setState(st=>({chatCtxOn:st.chatCtxOn===false})),
      chat_clearAll:()=>this.clearAllChats(),
      chat_clearStyle:'width:100%;height:30px;border-radius:7px;cursor:pointer;font-size:12px;border:1px solid var(--neg-bg);background:var(--neg-bg);color:var(--neg)',
      chat_scrollRef:(el)=>{ this._chatScroll=el; }
    };
  }
  compareVals(){
    const s=this.state, yi=this.yi()<0?4:this.yi();
    const pa=this.getProf(s.company);
    const hasC=!!s.compareCompany;
    const tab=hasC?s.cmpTab:'profile';
    const tb='height:32px;padding:0 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;border:0;transition:all .12s;';
    const act='background:var(--bg-elev);color:var(--text);box-shadow:0 1px 2px rgba(20,22,31,.08)';
    const ina='background:transparent;color:var(--text-2)';
    const cv=hasC?this.compareData(s.company,s.compareCompany,yi):{rows:[],barLabels:[],barSeries:[],summary:''};
    const comps=this._liveCompanies();
    let trendLabels, trendSeries, gmLabels, gmSeries, patLabels, patSeries;
    if(pa.live){
      trendLabels = (pa.trendLabels&&pa.trendLabels.length)?pa.trendLabels:[];
      trendSeries = pa.trendSeries||[];
      gmLabels = (pa.gmLabels&&pa.gmLabels.length)?pa.gmLabels:trendLabels;
      gmSeries = pa.gmSeries||[];
      patLabels = (pa.patLabels&&pa.patLabels.length)?pa.patLabels:[];
      patSeries = pa.patSeries||[];
    } else {
      trendLabels = this.D.trendYears;
      trendSeries = [{name:'营业收入',color:'#3b428f',values:pa.rev},{name:'归母净利润',color:'#0d9488',values:pa.np},{name:'研发投入',color:'#b45309',values:pa.rd}];
      gmLabels = this.D.trendYears; gmSeries = [{name:'销售毛利率',color:'#6d28d9',values:pa.gm}];
      patLabels = this.D.trendYears; patSeries = [{name:'发明专利',color:'#3b428f',values:pa.patents.inv},{name:'实用新型',color:'#0d9488',values:pa.patents.uti}];
    }
    return {
      cmp_isProfile:tab==='profile', cmp_isCompare:tab==='compare',
      cmp_title:hasC?(s.company+'  vs  '+s.compareCompany):(s.company+' · 全景画像'),
      cmp_company:s.company, cmp_other:s.compareCompany||'', cmp_hasCompare:hasC,
      cmp_initialA:s.company.slice(0,1), cmp_initialB:(s.compareCompany||'＋').slice(0,1),
      cmp_companies:comps,
      cmp_otherOptions:[{v:'',t:'（单公司画像）'}].concat(comps.filter(c=>c!==s.company).map(c=>({v:c,t:c}))),
      cmp_onCompany:(e)=>this.setParam({company:e.target.value}),
      cmp_onOther:(e)=>this.setParam({compareCompany:e.target.value}),
      cmp_setProfile:()=>this.setState({cmpTab:'profile'}),
      cmp_setCompare:()=>{ if(hasC) this.setState({cmpTab:'compare'}); },
      cmp_tabProfileStyle:tb+(tab==='profile'?act:ina),
      cmp_tabCompareStyle:tb+(tab==='compare'?act:(hasC?ina:'background:transparent;color:var(--gray-300);cursor:not-allowed')),
      cmp_overview:[['所属赛道',pa.track],['画像年份',String(s.year)],['风险事件总数',String(pa.risk)],['专利总量',this.nf(pa.patent)],['股权图谱节点',String(pa.nodes)]].map(o=>({label:o[0],value:o[1]})),
      cmp_metrics:pa.metrics.map(m=>({label:m[0],value:m[1],meta:m[2]})),
      cmp_summary:pa.summary,
      cmp_riskCards:pa.riskCards.map(c=>({label:c[0],value:c[1]})),
      cmp_innovCards:pa.innovCards.map(c=>({label:c[0],value:c[1]})),
      cmp_equityCards:pa.equityCards.map(c=>({label:c[0],value:c[1]})),
      cmp_trendLabels:trendLabels,
      cmp_trendSeries:trendSeries,
      cmp_gmLabels:gmLabels, cmp_gmSeries:gmSeries,
      cmp_patLabels:patLabels, cmp_patSeries:patSeries,
      cmp_rows:cv.rows, cmp_barLabels:cv.barLabels, cmp_barSeries:cv.barSeries, cmp_compSummary:cv.summary
    };
  }
  researchVals(){
    const s=this.state, mode=s.resMode;
    const list=(s.resList||'').split(/[，,、\n]+/).map(x=>x.trim()).filter(Boolean);
    const batchNames=list.slice(0,5);
    const activeName=mode==='batch'?(batchNames[s.resBatchActive]||batchNames[0]||s.company):s.company;
    this._ensureResProfile(activeName);
    const rep=this.reportFor(activeName);
    // data_mode 药丸：live 时根据真实生成模式映射「本地化文案 + 颜色」，否则按 DeepSeek 开关
    const liveMode=(this.state.resData && this.state.resData[activeName] && this.state.resData[activeName].data_mode)||null;
    const MODE={live:{t:'实时检索 · 增强',c:'var(--pos)',b:'var(--pos-bg)'},partial:{t:'部分接入 · 降级',c:'var(--warn)',b:'var(--warn-bg)'},degraded:{t:'本地降级合成',c:'var(--warn)',b:'var(--warn-bg)'},unavailable:{t:'无可用检索结果',c:'var(--neg)',b:'var(--neg-bg)'}};
    const modePill=liveMode?(MODE[liveMode]||{t:liveMode,c:'var(--warn)',b:'var(--warn-bg)'}):{t:(s.deepseek?'增强生成 · DeepSeek':'本地模板合成 · 降级'),c:(s.deepseek?'var(--pos)':'var(--warn)'),b:(s.deepseek?'var(--pos-bg)':'var(--warn-bg)')};
    const mb='flex:1;height:30px;border-radius:7px;font-size:12.5px;font-weight:500;cursor:pointer;border:0;transition:all .12s;';
    const on='background:var(--bg-elev);color:var(--text);box-shadow:0 1px 2px rgba(20,22,31,.08)';
    const off='background:transparent;color:var(--text-2)';
    // ---- 报告图表（按当前公司真实趋势；无数据回退演示）----
    const prof=this._resProfile(activeName);
    const tpiv=(prof&&prof.company_name)?this._pivot(prof.trend_chart):null;
    const sv=(nm)=>{ if(!tpiv) return null; const x=tpiv.series.find(z=>z.name===nm); return x?x.values:null; };
    let bars=null, linePts=null, areaPts=null, trendYears=null, trendLast=null;
    if(tpiv && tpiv.labels.length>=1){
      const L=tpiv.labels.length-1, P=Math.max(0,L-1);
      const rev=sv('营业收入'), np=sv('归属于上市公司股东的净利润'), rd=sv('研发费用');
      const amts=[rev,np,rd].filter(Boolean).reduce((a,arr)=>a.concat(arr.filter(v=>v!=null)),[]);
      const DIV=(amts.length&&Math.max.apply(null,amts.map(Math.abs))>=1e6)?1e8:1; // 元→亿元(已是亿元则不缩放)
      const Y=(v)=> v!=null? v/DIV : null;
      const finL=[{k:'营业收入',arr:rev},{k:'归母净利润',arr:np},{k:'研发投入',arr:rd}]
        .map(d=>({k:d.k, a:d.arr?Y(d.arr[P]):null, b:d.arr?Y(d.arr[L]):null})).filter(d=>d.b!=null);
      if(finL.length){
        const fmax=Math.max.apply(null, finL.map(d=>Math.max(Math.abs(d.a||0),Math.abs(d.b||0))))||1;
        bars=finL.map(d=>{ const a=d.a!=null?d.a:0, b=d.b; const delta=(d.a&&d.a!==0)?((b-a>=0?'+':'')+(((b-a)/Math.abs(a))*100).toFixed(1)+'%'):'—'; return {k:d.k,aH:(Math.abs(a)/fmax*100).toFixed(1)+'%',bH:(Math.abs(b)/fmax*100).toFixed(1)+'%',a:a.toFixed(1),b:b.toFixed(1),delta}; });
      }
      if(rev){
        const ys=tpiv.labels.map((y,i)=>[y, rev[i]!=null?rev[i]/DIV:null]).filter(d=>d[1]!=null);
        if(ys.length>=2){
          const vv=ys.map(d=>d[1]); let vmax=Math.max.apply(null,vv), vmin=Math.min.apply(null,vv);
          if(vmax===vmin){vmax+=1;vmin-=1;} const pad=(vmax-vmin)*0.18||1; vmax+=pad; vmin-=pad;
          const px=(i)=>(i/(ys.length-1))*100, py=(v)=>100-((v-vmin)/(vmax-vmin))*100;
          linePts=ys.map((d,i)=>px(i).toFixed(2)+','+py(d[1]).toFixed(2)).join(' ');
          areaPts='0,100 '+linePts+' 100,100';
          trendYears=ys.map(d=>({y:d[0],v:d[1].toFixed(1)})); trendLast=ys[ys.length-1][1].toFixed(1);
        }
      }
    }
    if(!bars){ const fin=[{k:'营业收入',a:228.2,b:279.9},{k:'归母净利润',a:43.0,b:63.4},{k:'研发投入',a:49.5,b:65.8}]; const fmax=Math.max.apply(null,fin.map(d=>Math.max(d.a,d.b))); bars=fin.map(d=>({k:d.k,aH:(d.a/fmax*100).toFixed(1)+'%',bH:(d.b/fmax*100).toFixed(1)+'%',a:d.a.toFixed(1),b:d.b.toFixed(1),delta:'+'+((d.b-d.a)/d.a*100).toFixed(1)+'%'})); }
    if(!linePts){ const yrs=[['2020',277.4],['2021',259.1],['2022',212.8],['2023',228.2],['2024',279.9]]; const vmax=290,vmin=200; const px=(i)=>(i/(yrs.length-1))*100, py=(v)=>100-((v-vmin)/(vmax-vmin))*100; linePts=yrs.map((y,i)=>px(i).toFixed(2)+','+py(y[1]).toFixed(2)).join(' '); areaPts='0,100 '+linePts+' 100,100'; trendYears=yrs.map(y=>({y:y[0],v:y[1].toFixed(1)})); trendLast=yrs[yrs.length-1][1].toFixed(1); }
    return {
      res_bars:bars,
      res_trendLine:linePts, res_trendArea:areaPts,
      res_trendSvg:this._trendSvg(areaPts,linePts),
      res_trendYears:trendYears,
      res_trendLast:trendLast,
      res_isSingle:mode==='single', res_isBatch:mode==='batch',
      res_modeSingleStyle:mb+(mode==='single'?on:off), res_modeBatchStyle:mb+(mode==='batch'?on:off),
      res_setSingle:()=>this.setState({resMode:'single'}), res_setBatch:()=>this.setState({resMode:'batch'}),
      res_topic:s.resTopic, res_onTopic:(e)=>this.setState({resTopic:e.target.value}),
      res_topicPh:'例如：'+s.company+' 2024 年经营质量与研发能力研究',
      res_list:s.resList, res_onList:(e)=>this.setState({resList:e.target.value,resBatchActive:0}), res_listCount:batchNames.length,
      res_gen:()=>this.genReport(), res_loading:s.resLoading, res_notLoading:!s.resLoading, res_done:s.resDone,
      res_panelOpen:s.resPanelOpen!==false,
      res_togglePanel:()=>this.setState(st=>({resPanelOpen:st.resPanelOpen===false})),
      res_sourcesCount:rep.chunks.length,
      res_notCopied:!s.resCopied, res_copyLabel:s.resCopied?'已复制':'复制',
      res_sourcesBtnStyle:'height:34px;padding:0 12px;display:inline-flex;align-items:center;gap:6px;border-radius:9px;font-size:12.5px;font-weight:500;cursor:pointer;border:1px solid '+(s.resPanelOpen!==false?'var(--brand-300)':'var(--border)')+';background:'+(s.resPanelOpen!==false?'var(--brand-50)':'var(--bg-elev)')+';color:'+(s.resPanelOpen!==false?'var(--brand-600)':'var(--text-2)'),
      res_exportChevron:'transition:transform .15s'+(s.resExportOpen?';transform:rotate(180deg)':''),
      res_exportOpen:!!s.resExportOpen,
      res_toggleExport:()=>this.setState(st=>({resExportOpen:!st.resExportOpen})),
      res_copy:()=>this.copyReport(activeName), res_copied:!!s.resCopied,
      res_print:()=>{this.setState({resExportOpen:false});this.printReport();},
      res_dlMd:()=>{this.setState({resExportOpen:false});this.downloadMd(activeName);},
      res_genLabel:mode==='batch'?('生成批量报告（'+batchNames.length+' 家）'):'生成研究报告',
      res_title:rep.title, res_blocks:rep.blocks,
      res_outline:rep.outline.map(t=>({t})),
      res_dataMode:modePill.t,
      res_dataModeColor:modePill.c, res_dataModeBg:modePill.b,
      res_chunks:rep.chunks,
      res_batchNames:batchNames.map((n,i)=>({name:n,onClick:()=>this.setState({resBatchActive:i}),
        style:'text-align:left;width:100%;padding:8px 11px;border-radius:8px;font-size:12.5px;cursor:pointer;border:1px solid '+(i===s.resBatchActive?'var(--brand-300)':'var(--border)')+';background:'+(i===s.resBatchActive?'var(--brand-50)':'var(--bg-elev)')+';color:'+(i===s.resBatchActive?'var(--brand-600)':'var(--text-2)')+';font-weight:'+(i===s.resBatchActive?'600':'400')})),
      res_activeName:activeName,
      res_dl:()=>this.downloadMd(activeName)
    };
  }
  whiteboxVals(){
    const blk=(arr)=>arr.map(b=>({text:b.text,bullet:b.t==='li',style:(b.t==='li'?'display:flex;gap:9px;font-size:13.5px;line-height:1.65;color:var(--text-2)':'font-size:13.5px;line-height:1.7;color:var(--text)')+';margin:0'}));
    const reasoning=[
      {t:'li',text:'解析问题意图：识别为「研发投入」的同比变动 + 归因类问题，需先取数再结合年报佐证。'},
      {t:'li',text:'结构化检索：在 fact_financial 按 company=恒瑞医药、indicator=研发投入、year∈{2022,2023} 取数，得 48.9 → 49.5 亿元。'},
      {t:'li',text:'证据召回：在向量库检索年报「研发」相关切片，命中研发费用、在研管线与费用化政策说明。'},
      {t:'li',text:'交叉校验：SQL 数值与年报文字表述一致（49.5 亿元 / 同比约 +1.2%），无冲突。'},
      {t:'li',text:'归因合成：投入小幅增长但研发强度由 23.0% 降至 21.7%，主因营收增速（+7.2%）快于研发增速。'}
    ];
    const answer=[
      {t:'p',text:'结论：恒瑞医药 2023 年研发投入为 49.5 亿元，较 2022 年的 48.9 亿元小幅增长约 1.2%（增加 0.6 亿元）。'},
      {t:'li',text:'绝对额维持高位：连续多年研发投入居 A 股医药前列，全部费用化，口径稳健。'},
      {t:'li',text:'强度小幅回落：研发投入占营收比例由 23.0% 降至 21.7%，因营收同比增速更快。'},
      {t:'li',text:'结构性因素：部分早期管线临床阶段切换，使当期投入增速放缓。'}
    ];
    const chunks=[
      {source:'恒瑞医药 · 2023年年度报告',score:0.928,doc_id:'HRYY-2023-MD-0071',text:'报告期内公司研发费用为49.54亿元，持续保持高强度研发投入，研发费用全部计入当期损益……'},
      {source:'恒瑞医药 · 2023年年度报告',score:0.871,doc_id:'HRYY-2023-MD-0152',text:'公司在研创新药及改良型新药管线丰富，多个项目处于关键临床阶段，研发资源向重点管线倾斜……'},
      {source:'恒瑞医药 · 2022年年度报告',score:0.804,doc_id:'HRYY-2022-MD-0066',text:'上年度公司研发投入48.90亿元，研发投入占营业收入比例约22.98%……'}
    ];
    let _reasoning=reasoning, _answer=answer, _chunks=chunks;
    let _sql="SELECT indicator_name, report_year, value_num, unit\nFROM fact_financial\nWHERE company_name = '恒瑞医药'\n  AND indicator_name IN ('研发投入','营业收入')\n  AND report_year IN (2022, 2023)\nORDER BY indicator_name, report_year;";
    const wb=this._get('whitebox');
    if(wb){
      if(wb.reasoning_markdown) _reasoning=this._mdBlocks(wb.reasoning_markdown);
      if(wb.answer_markdown) _answer=this._mdBlocks(wb.answer_markdown);
      if(Array.isArray(wb.chunks)&&wb.chunks.length) _chunks=this._chunkAdapt(wb.chunks,false);
      if(wb.sql) _sql=wb.sql;
    }
    const stages=[
      {n:'1',title:'自然语言问题',tag:'输入',kind:'q',isQ:true,notLast:true},
      {n:'2',title:'路由与 SQL 执行',tag:'SQL Route',kind:'sql',isSql:true,notLast:true},
      {n:'3',title:'RAG 原文召回',tag:'Top '+this.state.topK,kind:'rag',isRag:true,notLast:true,chunks:_chunks.map(c=>({source:c.source,score:c.score.toFixed(3),doc_id:c.doc_id,text:c.text}))},
      {n:'4',title:'推理链路',tag:'Chain-of-Thought',kind:'reason',isReason:true,notLast:true,blocks:blk(_reasoning)},
      {n:'5',title:'最终结论',tag:'结论',kind:'answer',isAnswer:true,notLast:false,blocks:blk(_answer)}
    ];
    let wb_question='恒瑞医药 2023 年的研发投入相比上一年是增是减？变动幅度如何？主要影响因素有哪些？';
    if(wb){ const co=(Array.isArray(wb.chunks)&&wb.chunks[0]&&wb.chunks[0].metadata&&wb.chunks[0].metadata.company_name)||''; if(co) wb_question=co+' 最新年度核心经营指标的变动情况如何？请展示从结构化取数到原文佐证、再到结论的完整白盒链路。'; }
    return {
      wb_question:wb_question,
      wb_stages:stages,
      wb_sql:_sql,
      wb_cols: wb?[]:['指标','2022','2023','变动'],
      wb_rows: wb?[]:[{cells:['研发投入(亿元)','48.9','49.5','+1.2%']},{cells:['营业收入(亿元)','212.8','228.2','+7.2%']},{cells:['研发投入/营收','22.98%','21.69%','-1.29pct']}],
      wb_steps:[{l:'问题解析'},{l:'SQL 执行'},{l:'RAG 召回'},{l:'推理合成'},{l:'结论'}]
    };
  }
  _databaseLive(cat){
    const s=this.state;
    const catOf=(name)=>({dim:'维度表',fact:'事实表',dict:'字典表',map:'映射表'})[String(name||'').split('_')[0]]||'数据表';
    const q=(s.dbSearch||'').toLowerCase();
    const tables=cat.tables;
    const list=tables.filter(t=>!q||t.table_name.toLowerCase().includes(q)||catOf(t.table_name).toLowerCase().includes(q)).map(t=>({
      table_name:t.table_name, cn:catOf(t.table_name), rc:this.nf(t.row_count), cc:t.column_count, active:t.table_name===s.dbTable,
      onClick:()=>this.selectDbTable(t.table_name),
      style:'text-align:left;width:100%;padding:9px 11px;border-radius:9px;cursor:pointer;border:1px solid '+(t.table_name===s.dbTable?'var(--brand-300)':'transparent')+';background:'+(t.table_name===s.dbTable?'var(--brand-50)':'transparent')
    }));
    const meta=tables.find(t=>t.table_name===s.dbTable)||tables[0];
    const prevSlot=this._get('dbTable');
    const prev=(prevSlot && prevSlot.key===s.dbTable)?prevSlot.data:null;
    let db_cols, db_headers, db_rows, db_create, db_rc, db_cc;
    if(prev && Array.isArray(prev.columns)){
      db_cols=prev.columns.map(c=>({name:c.name,type:c.type,pk:!!c.is_pk}));
      db_headers=prev.columns.map(c=>c.name);
      db_rows=(prev.rows||[]).map(r=>({cells:prev.columns.map(c=>{ const v=r[c.name]; return v==null?'':String(v); })}));
      db_create=prev.create_sql||('CREATE TABLE '+s.dbTable+' ( … );');
      db_rc=this.nf(prev.row_count!=null?prev.row_count:(meta?meta.row_count:0));
      db_cc=prev.columns.length;
    } else {
      const cols=(meta&&meta.columns)||[];
      db_cols=cols.map(n=>({name:n,type:'',pk:false}));
      db_headers=cols.slice();
      db_rows=[];
      db_create='CREATE TABLE '+s.dbTable+' (\n'+cols.map(n=>'  '+n).join(',\n')+'\n);';
      db_rc=this.nf(meta?meta.row_count:0); db_cc=meta?meta.column_count:cols.length;
    }
    return {
      db_list:list, db_search:s.dbSearch, db_onSearch:(e)=>this.setState({dbSearch:e.target.value}),
      db_name:s.dbTable, db_cn:catOf(s.dbTable), db_rc, db_cc,
      db_create, db_cols, db_headers, db_rows
    };
  }
  databaseVals(){
    const s=this.state;
    const cat=this._get('dbCatalog');
    if(cat && Array.isArray(cat.tables) && cat.tables.length){ return this._databaseLive(cat); }
    const T={
      dim_company:{cn:'维度 · 公司',rc:48,cols:[['id','INTEGER',1],['company_name','TEXT',0],['industry_name','TEXT',0],['list_code','TEXT',0],['list_market','TEXT',0],['found_year','INTEGER',0],['province','TEXT',0]],rows:[['1','恒瑞医药','化学制药','600276','上证主板','1970','江苏'],['2','复星医药','化学制药','600196','上证主板','1994','上海'],['3','药明康德','医疗服务','603259','上证主板','2000','江苏'],['4','智飞生物','生物制品','300122','深证创业','2002','重庆'],['5','华兰生物','生物制品','002007','深证主板','1992','河南']]},
      dim_industry:{cn:'维度 · 行业',rc:24,cols:[['id','INTEGER',1],['industry_name','TEXT',0],['industry_level','INTEGER',0],['parent_name','TEXT',0]],rows:[['1','医药生物','1','—'],['2','化学制药','2','医药生物'],['3','生物制品','2','医药生物'],['4','中药','2','医药生物'],['5','医疗器械','2','医药生物']]},
      fact_financial:{cn:'事实 · 财务指标',rc:18642,cols:[['id','INTEGER',1],['company_name','TEXT',0],['report_year','INTEGER',0],['indicator_name','TEXT',0],['value_num','REAL',0],['unit','TEXT',0],['source_doc_id','TEXT',0]],rows:[['1','恒瑞医药','2024','营业收入','279.9','亿元','HRYY-2024'],['2','恒瑞医药','2024','归母净利润','63.4','亿元','HRYY-2024'],['3','恒瑞医药','2024','研发投入','65.8','亿元','HRYY-2024'],['4','复星医药','2024','营业收入','410.7','亿元','FXYY-2024'],['5','复星医药','2024','销售毛利率','47.8','%','FXYY-2024']]},
      fact_macro:{cn:'事实 · 宏观指标',rc:1286,cols:[['id','INTEGER',1],['indicator_name','TEXT',0],['period_year','INTEGER',0],['value_num','REAL',0],['unit','TEXT',0]],rows:[['1','卫生总费用','2024','90575.8','亿元'],['2','人均卫生费用','2024','6425.3','元'],['3','卫生总费用占GDP比重','2024','7.2','%']]},
      fact_patent:{cn:'事实 · 专利',rc:9420,cols:[['id','INTEGER',1],['company_name','TEXT',0],['patent_type','TEXT',0],['application_year','INTEGER',0],['patent_count','INTEGER',0]],rows:[['1','恒瑞医药','发明专利','2024','290'],['2','恒瑞医药','实用新型','2024','140'],['3','复星医药','发明专利','2024','196']]},
      doc_annual_report:{cn:'文档 · 年报',rc:312,cols:[['id','INTEGER',1],['company_name','TEXT',0],['report_year','INTEGER',0],['file_name','TEXT',0],['chunk_count','INTEGER',0],['updated_at','TEXT',0]],rows:[['1','恒瑞医药','2024','恒瑞医药2024年年度报告.pdf','842','2025-04-12'],['2','复星医药','2024','复星医药2024年年度报告.pdf','1036','2025-04-15']]}
    };
    const order=['dim_company','dim_industry','fact_financial','fact_macro','fact_patent','doc_annual_report'];
    const q=(s.dbSearch||'').toLowerCase();
    const list=order.filter(k=>!q||k.includes(q)||T[k].cn.toLowerCase().includes(q)).map(k=>({
      table_name:k, cn:T[k].cn, rc:this.nf(T[k].rc), cc:T[k].cols.length, active:k===s.dbTable,
      onClick:()=>this.setState({dbTable:k}),
      style:'text-align:left;width:100%;padding:9px 11px;border-radius:9px;cursor:pointer;border:1px solid '+(k===s.dbTable?'var(--brand-300)':'transparent')+';background:'+(k===s.dbTable?'var(--brand-50)':'transparent')
    }));
    const act=T[s.dbTable]||T.fact_financial;
    const create='CREATE TABLE '+s.dbTable+' (\n'+act.cols.map(c=>'  '+c[0]+' '+c[1]+(c[2]?' PRIMARY KEY':'')).join(',\n')+'\n);';
    return {
      db_list:list, db_search:s.dbSearch, db_onSearch:(e)=>this.setState({dbSearch:e.target.value}),
      db_name:s.dbTable, db_cn:act.cn, db_rc:this.nf(act.rc), db_cc:act.cols.length,
      db_create:create,
      db_cols:act.cols.map(c=>({name:c[0],type:c[1],pk:!!c[2]})),
      db_headers:act.cols.map(c=>c[0]),
      db_rows:act.rows.map(r=>({cells:r}))
    };
  }
  timelineVals(){
    const C={'财务':{c:'var(--series-1)',b:'var(--brand-50)'},'风险':{c:'var(--neg)',b:'var(--neg-bg)'},'创新':{c:'var(--series-2)',b:'rgba(13,148,136,.12)'}};
    const slot=this._get('timeline');
    const live=slot?slot.data:null;
    if(live && Array.isArray(live.events) && live.events.length){
      const colorFor=(label)=>{ const l=String(label||''); if(l.indexOf('风险')>=0) return 'var(--neg)'; if(l.indexOf('创新')>=0) return 'var(--series-2)'; return 'var(--series-1)'; };
      const tl_cards=(live.cards||[]).map(c=>({label:c.label, value:String(c.value), color:colorFor(c.label)}));
      const shortInd=(s)=>String(s||'').replace('归属于上市公司股东的净利润','归母净利润').replace('经营活动产生的现金流量净额','经营现金流');
      const tl_events=live.events.map(e=>{ const cc=C[e.category]||C['财务']; const det=(e.category==='财务')?this._fmtAmtStr(e.detail):e.detail; return {date:e.event_date, category:e.category, title:shortInd(e.title), detail:det, catColor:cc.c, catBg:cc.b}; });
      return {tl_cards, tl_events};
    }
    const ev=[
      ['2024-12-18','创新','瑞维鲁胺新适应症获批上市','转移性激素敏感性前列腺癌适应症获 NMPA 批准，进一步打开商业化空间。'],
      ['2024-10-30','财务','发布 2024 年三季度报告','前三季度营业收入同比增长约 18%，归母净利润延续高增长。'],
      ['2024-08-12','风险','收到交易所年报问询函','就研发资本化口径与销售费用结构作出说明，已按期回复，无后续处罚。'],
      ['2024-06-05','创新','GLP-1 类创新药 III 期临床达主要终点','减重与降糖双适应症推进，进入 NDA 申报准备阶段。'],
      ['2024-03-28','财务','披露 2023 年年度报告','全年研发投入 49.5 亿元，研发费用全部费用化，毛利率 84.9%。'],
      ['2023-11-20','创新','达成海外 License-out 合作','向跨国药企授权创新药海外权益，获首付款及里程碑付款。'],
      ['2023-09-15','风险','应收账款周转放缓预警','应收账款周转天数同比上升，触发中优先级财务预警信号。']
    ];
    return {
      tl_cards:[{label:'财务事件',value:'3',color:'var(--series-1)'},{label:'风险事件',value:'2',color:'var(--neg)'},{label:'创新事件',value:'2',color:'var(--series-2)'}],
      tl_events:ev.map(e=>({date:e[0],category:e[1],title:e[2],detail:e[3],catColor:C[e[1]].c,catBg:C[e[1]].b}))
    };
  }
  advancedVals(){
    const s=this.state;
    const C={brand:'var(--brand-600)',s2:'var(--series-2)',s3:'var(--series-3)'};
    const ad0=this.state.advData;
    let defs;
    if(ad0 && ad0.tool_results && ad0.tool_results.equity && Array.isArray(ad0.tool_results.equity.nodes)){
      const eq=ad0.tool_results.equity, rootName=eq.root_company||s.company;
      const ratioOf={}; (eq.edges||[]).forEach(e=>{ if(e&&e.target!=null) ratioOf[e.target]=e.ratio; });
      const seen={}, sub=[];
      eq.nodes.forEach(n=>{ if(!n||n.level===0||n.type==='root'||n.name===rootName||seen[n.name]) return; seen[n.name]=1; sub.push(n); });
      defs=sub.slice(0,6).map(n=>{ const rr=ratioOf[n.id]; const rel=n.type==='person'?'自然人股东':((rr!=null&&rr>=50)?'控股子公司':'关联方'); const nm=n.name+(rr!=null?(' · '+Number(rr).toFixed(Number(rr)%1?1:0)+'%'):''); const col=n.type==='person'?'s3':((rr!=null&&rr>=50)?'brand':'s2'); return [rel,nm,col]; });
      if(!defs.length) defs=[['股权穿透','运行后暂无下属/关联节点','brand']];
    } else {
      defs=[['控股股东','恒瑞医药集团 · 24.1%','brand'],['一致行动人','天广实生物','brand'],['全资子公司','成都盛迪医药','s2'],['全资子公司','上海恒瑞医药','s2'],['控股子公司','苏州盛迪亚生物','s2'],['海外平台','Luzsana Biotech','s3']];
    }
    const ang=[-90,-30,30,90,150,210], r=36;
    const nodes=defs.map((d,i)=>{ const a=ang[i]*Math.PI/180; const x=50+r*Math.cos(a), y=50+r*Math.sin(a); return {rel:d[0],name:d[1],color:C[d[2]],x:x.toFixed(2),y:y.toFixed(2),pos:'left:'+x.toFixed(2)+'%;top:'+y.toFixed(2)+'%'}; });
    const edges=nodes.map(n=>({x1:50,y1:50,x2:n.x,y2:n.y}));
    const prof=this._matched('profile');
    let adv_tools;
    if(prof && Array.isArray(prof.equity_cards) && prof.equity_cards.length){
      const eq=(label)=>{ const c=prof.equity_cards.find(x=>x.label===label); return c?String(c.value):'-'; };
      const cardv=(label)=>{ const c=(prof.cards||[]).find(x=>x.label===label); return c?String(c.value):'-'; };
      adv_tools=[{label:'图谱节点',value:eq('图谱节点')},{label:'关系边',value:eq('图谱边数')},{label:'一级关系',value:eq('一级关系')},{label:'司法风险',value:cardv('风险事件总数')}];
    } else {
      adv_tools=[{label:'图谱节点',value:'47'},{label:'关系边',value:'86'},{label:'一级关系',value:'12'},{label:'司法风险',value:'4'}];
    }
    const ad=this.state.advData;
    let adv_answer;
    if(ad && ad.answer_markdown){
      const pStyle='font-size:13.5px;line-height:1.75;color:var(--text-2);margin:0';
      const liStyle='display:flex;gap:9px;font-size:13.5px;line-height:1.7;color:var(--text-2);margin:0';
      adv_answer=this._mdBlocks(ad.answer_markdown).map(b=>({text:b.text,bullet:b.t==='li',style:b.t==='li'?liStyle:pStyle}));
    } else {
      adv_answer=[
        {text:'股权结构以恒瑞医药集团为控股股东（约 24.1%），下设多家全资 / 控股研发与生产子公司，并通过海外平台 Luzsana 承接国际化布局，整体股权清晰、控制权稳定。',bullet:false,style:'font-size:13.5px;line-height:1.75;color:var(--text-2);margin:0'},
        {text:'创新能力维度评分领先：发明专利与在研管线储备充足，研发人员规模与对外合作（License-out）活跃度构成核心壁垒。',bullet:true,style:'display:flex;gap:9px;font-size:13.5px;line-height:1.7;color:var(--text-2);margin:0'},
        {text:'潜在风险：海外子公司经营受汇率与监管环境影响，需关注跨境关联交易与商誉减值敞口。',bullet:true,style:'display:flex;gap:9px;font-size:13.5px;line-height:1.7;color:var(--text-2);margin:0'}
      ];
    }
    return {
      adv_question:s.advQ!=null?s.advQ:('请分析'+s.company+'的股权结构与创新能力，并指出潜在风险点'),
      adv_onQuestion:(e)=>this.setState({advQ:e.target.value}),
      adv_company:s.company,
      adv_run:()=>{ if(this.state.advLoading)return; const s2=this.state; const q=(s2.advQ!=null?s2.advQ:('请分析'+s2.company+'的股权结构与创新能力，并指出潜在风险点')); this.setState({advLoading:true,advDone:false}); this._apiPost('/api/advanced',{question:q, company_name:s2.company}).then(d=>this.setState({advLoading:false,advDone:true,advData:d})).catch(()=>{ if(this._advT)clearTimeout(this._advT); this._advT=setTimeout(()=>this.setState({advLoading:false,advDone:true}),900); }); },
      adv_loading:s.advLoading, adv_done:s.advDone,
      adv_nodes:nodes, adv_edges:edges,
      adv_edgeSvg:this._edgeSvg(edges),
      adv_tools:adv_tools,
      adv_answer:adv_answer,
      adv_innovLabels:['发明专利','在研管线','研发人员','对外合作'],
      adv_innovSeries:[{name:'创新能力维度评分',color:'#6d28d9',values:[88,82,79,71]}]
    };
  }

  renderVals(){
    return Object.assign({}, this.shellVals(), this.todayVals(), this.chatVals(), this.compareVals(), this.researchVals(), this.evidenceVals(), this.whiteboxVals(), this.databaseVals(), this.timelineVals(), this.advancedVals());
  }
}

"""Collect the numbers behind docs/report_l1_profiling.html from results/colab/L4.
usage: python analysis/report_l1_data.py out.json"""
import json, os, glob, statistics as st, re, sys
R='/home/user/Agent_Mem_Sys/results/colab/L4'
SYS=['rag-pg','mem0-local','mem0-pg','mem0-qdrant']
def J(p): return json.load(open(p))
def r1(x,n=1): return None if x is None else round(x,n)
def opsum(o):
    if not o: return None
    keys=['wall','p50','p95','max','n','LLM decode','LLM prefill+queue','LLM queue','decode_reasoning_ms','decode_answer_ms','reasoning_tok','answer_tok','completion_tok','prompt_tok','cached_tok','cache_hit','DB','Embedding','NLP','other','llm_busy_ms']
    return {k:(r1(o.get(k),3 if k=='cache_hit' else 1)) for k in keys if k in o}
out={}
# L1
l1={}
for s in SYS:
  for mode,lab in (('sync',f'l1_gptoss20b_{s}_sync_t100'),('async',f'l1_gptoss20b_{s}_async_think5_t100')):
    d=J(f'{R}/{lab}/breakdown_multi.json'); o=d['ops']
    mem=o.get('agent.memorize(chat)') or o.get('agent.memorize_async(chat)')
    hw=d.get('hw',{})
    sc=J(f'{R}/{lab}/qa_score.json') if os.path.exists(f'{R}/{lab}/qa_score.json') else {}
    l1[f'{s}|{mode}']={'turn':opsum(o.get('agent.turn(chat)')),'retrieve':opsum(o.get('agent.retrieve(chat)')),'generate':opsum(o.get('agent.generate(chat)')),
      'gen_qa':opsum(o.get('agent.generate(qa)')),'retr_qa':opsum(o.get('agent.retrieve(qa)')),'memorize':opsum(mem),'cold':r1(o.get('cold.start(cold)',{}).get('wall')),
      'commit_lag':d.get('commit_lag_s'),'phases':{k:(v['n'],r1(v['mean_ms'])) for k,v in d['phases'].items()},
      'add_phases':{k:({kk:r1(vv,2) for kk,vv in v.items()} if isinstance(v,dict) else v) for k,v in (d.get('add_phases') or {}).items()},
      'hw':{k:(r1(v,2) if isinstance(v,(int,float)) else v) for k,v in hw.items() if k in('gpu_util_mean','gpu_membw_util_mean','gpu_mem_mb_max','gpu_power_mean','prefix_cache_hit','max_waiting','llm_decode_tok_s','llm_prefill_tok_s','proc_cpu_mean','proc_rss_max_mb','disk_w_mb','pcie_rx_mb_s_mean','pcie_tx_mb_s_mean')},
      'footprint':sum(d['footprint'].values()),'score':{k:sc.get(k) for k in ('n','f1','judge_acc','judge') if k in sc}}
out['l1']=l1
# LME
lme={}
for p in sorted(glob.glob(f'{R}/lme_gptoss20b_*_i*_t0*')):
  lab=os.path.basename(p); m=re.match(r'lme_gptoss20b_(.+)_i(\d+)_t0(_async_think5)?$',lab)
  if not m: continue
  s,item,a=m.group(1),m.group(2),'async' if m.group(3) else 'sync'
  d=J(p+'/breakdown_multi.json'); o=d['ops']; mem=o.get('agent.memorize(chat)') or o.get('agent.memorize_async(chat)')
  S=[json.loads(l) for l in open(p+'/spans.jsonl')]
  # scaling: by quintile of turn
  def byq(name,field='wall_ms',flt=lambda s:True):
    xs=[(s.get('turn',0),s[field]) for s in S if s['name']==name and s.get('phase')=='chat' and flt(s)]
    if not xs: return None
    T=max(t for t,_ in xs)+1; b=[[] for _ in range(5)]
    for t,w in xs: b[min(4,t*5//T)].append(w)
    return [r1(st.mean(x)) if x else None for x in b]
  tr=[s for s in S if s['name']=='agent.turn' and s.get('phase')=='chat']
  bl=[s.get('backlog') for s in S if s['name']=='agent.backlog']
  meta=J(p+'/meta.json')
  sc=J(p+'/qa_score.json') if os.path.exists(p+'/qa_score.json') else {}
  lme[f'{s}|{item}|{a}']={'n_turns':d['n_turns'],'turn':opsum(o.get('agent.turn(chat)')),'retrieve':opsum(o.get('agent.retrieve(chat)')),'generate':opsum(o.get('agent.generate(chat)')),'memorize':opsum(mem),
    'commit_lag':d.get('commit_lag_s'),'footprint':sum(d['footprint'].values()),'phases':{k:(v['n'],r1(v['mean_ms'])) for k,v in d['phases'].items()},
    'scal_search':byq('agent.retrieve'),'scal_add':byq('mem0.add') if any(s['name']=='mem0.add' for s in S) else byq('agent.memorize_async') or byq('agent.memorize'),
    'scal_turn':byq('agent.turn'),'backlog_max':max([b for b in bl if b is not None],default=None),
    'add_phases':{k:(r1(v['wall'],1) if isinstance(v,dict) else v) for k,v in (d.get('add_phases') or {}).items()},
    'hw':{k:r1(v,2) for k,v in d.get('hw',{}).items() if k in('gpu_util_mean','llm_decode_tok_s','llm_prefill_tok_s','prefix_cache_hit')},
    'score':sc.get('judge_acc', sc.get('judge'))}
out['lme']=lme
# kprof
kp={}
for s in SYS:
  k=J(f'{R}/kprof_gptoss20b_{s}_async_think5/kernel_profile.json')
  kp[s]={'turns':k['turns'],'n_kernels':k['n_kernels'],'kernel_ms':r1(k['kernel_ms']),'capture_ms':r1(k['capture_ms']),'align':r1(k['align']['kernel_share_in_llm_calls'],4),
   'by_category':{c:[r1(v['ms']),r1(v['share']*100)] for c,v in k['by_category'].items()},
   'by_stage':{g:{'wall':r1(v['wall_ms']),'kernel':r1(v['kernel_ms']),'busy':r1(v['gpu_busy']*100),'top':[(c,r1(x['share']*100)) for c,x in sorted(v['cats'].items(),key=lambda z:-z[1]['ms'])[:3]]} for g,v in k['by_stage'].items()},
   'top_kernels':[(t['kernel'][:60],r1(t['ms']),t['n'],r1(t['mean_us']),t['cat']) for t in k['top_kernels'][:8]],
   'memcpy':k['memcpy_by_kind']}
out['kprof']=kp
json.dump(out,open(sys.argv[1],'w'),indent=1,ensure_ascii=False)

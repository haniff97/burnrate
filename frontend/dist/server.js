import { createId } from './ids.mjs';

// Optional same-origin Python service. The public static site keeps local mode.
export class ServerJournal {
  connected=false;
  capabilities={gemini:false,deepseek:false};
  revision=0;
  pending=null;
  running=null;
  blocked=false;
  async request(path,options={}) {
    const response=await fetch('/api/'+path,{...options,credentials:'same-origin',headers:{'Content-Type':'application/json',...options.headers},signal:AbortSignal.timeout(path.startsWith('food/')||path==='plans'||path==='reviews'?65000:10000)});
    const data=await response.json().catch(()=>({detail:'Service unavailable'}));
    if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:`Request validation failed (${response.status})`);error.status=response.status;throw error;}
    return data;
  }
  async initialize(local) {
    let health;
    try{health=await this.request('health');}catch{return null;}
    if(health.service!=='burnrate-python')return null;
    const session=await this.request('session');
    this.connected=true;this.capabilities=session.capabilities;this.revision=session.revision;
    if(session.state)return session.state;
    const saved=await this.queue(local);return saved.state;
  }
  queue(state) {
    if(this.blocked)return Promise.reject(new Error('Server journal changed elsewhere. Export your local edits, then reload.'));
    this.pending=structuredClone(state);
    if(!this.running){this.running=this.pump().finally(()=>{this.running=null;});}
    return this.running;
  }
  async pump() {
    let result;
    while(this.pending){
      const state=this.pending;this.pending=null;
      try{result=await this.request('state',{method:'PUT',body:JSON.stringify({expected_revision:this.revision,mutation_id:createId(),state})});this.revision=result.revision;}
      catch(error){this.pending=state;this.blocked=true;throw error;}
    }
    return result;
  }
  async flush(){if(this.blocked)throw new Error('Server saving is paused. Export local edits and reload.');if(this.running)await this.running;}
  async plan(date,useAI=false){await this.flush();return this.request('plans',{method:'POST',body:JSON.stringify({expected_revision:this.revision,date,use_ai:useAI})});}
  async analyze(dataUrl){await this.flush();return this.request('food/analyze',{method:'POST',body:JSON.stringify({data_url:dataUrl,draft_id:createId()})});}
  async confirm(draftId,date,slot,items){await this.flush();const result=await this.request(`food/drafts/${encodeURIComponent(draftId)}/confirm`,{method:'POST',body:JSON.stringify({expected_revision:this.revision,mutation_id:createId(),date,slot,items})});this.revision=result.revision;return result;}
  async review(date,useAI=false){await this.flush();return this.request('reviews',{method:'POST',body:JSON.stringify({expected_revision:this.revision,date,use_ai:useAI})});}
}

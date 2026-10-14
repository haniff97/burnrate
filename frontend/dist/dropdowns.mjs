// Keep native selects for FormData and existing change handlers; customize their UI.
export function installDropdowns(root=document) {
  const controls=new WeakMap();let active=null,sequence=0,typed='',typedAt=0;
  function close(){if(!active)return;const {menu,button}=active;active=null;button.setAttribute('aria-expanded','false');button.removeAttribute('aria-activedescendant');button.removeAttribute('aria-controls');if(typeof menu.hidePopover==='function'&&menu.matches(':popover-open'))menu.hidePopover();menu.remove();}
  function position(){
    if(!active)return;const {button,menu}=active,r=button.getBoundingClientRect(),v=window.visualViewport;
    const leftEdge=v?.offsetLeft||0,topEdge=v?.offsetTop||0,width=v?.width||innerWidth,height=v?.height||innerHeight;
    const w=Math.min(Math.max(r.width,180),width-24),below=topEdge+height-r.bottom-12,above=r.top-topEdge-12,up=below<160&&above>below;
    menu.style.width=w+'px';menu.style.maxHeight=Math.max(44,Math.min(280,up?above:below))+'px';
    menu.style.left=Math.max(leftEdge+12,Math.min(r.left,leftEdge+width-w-12))+'px';
    menu.style.top=(up?Math.max(topEdge+12,r.top-menu.getBoundingClientRect().height-6):r.bottom+6)+'px';
  }
  function highlight(index){
    if(!active)return;active.index=index;
    active.menu.querySelectorAll('[role="option"]').forEach(option=>option.classList.toggle('highlighted',Number(option.dataset.index)===index));
    const item=active.menu.querySelector(`[data-index="${index}"]`);
    if(item){active.button.setAttribute('aria-activedescendant',item.id);item.scrollIntoView({block:'nearest'});}
  }
  function choose(index){
    if(!active)return;const {select,button}=active,option=select.options[index];
    if(select.disabled||!option||option.disabled)return;
    select.selectedIndex=index;close();button.focus();
    select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));
  }
  function open(select,button){
    close();typed='';typedAt=0;if(select.disabled||!select.options.length)return;
    const menu=document.createElement('div');menu.className='custom-select-menu';menu.id='dropdown-menu-'+(++sequence);menu.setAttribute('role','listbox');menu.setAttribute('aria-label',button.getAttribute('aria-label'));menu.setAttribute('popover','manual');
    [...select.options].forEach((option,index)=>{
      const item=document.createElement('button');item.type='button';item.className='custom-select-option';item.id=menu.id+'-'+index;item.dataset.index=index;item.setAttribute('role','option');item.setAttribute('aria-selected',String(index===select.selectedIndex));item.tabIndex=-1;item.disabled=option.disabled;item.textContent=option.textContent;item.onclick=()=>choose(index);menu.append(item);
    });
    (select.closest('dialog')||document.body).append(menu);
    active={select,button,menu,index:select.selectedIndex};button.setAttribute('aria-controls',menu.id);button.setAttribute('aria-expanded','true');
    if(typeof menu.showPopover==='function')menu.showPopover();else menu.classList.add('popover-fallback');
    position();highlight(select.selectedIndex);
  }
  function enhance(select){
    if(controls.has(select)||select.multiple||select.size>1)return;
    const wrap=document.createElement('span');wrap.className='custom-select';select.before(wrap);wrap.append(select);
    const button=document.createElement('button');button.type='button';button.className='custom-select-trigger';button.setAttribute('role','combobox');button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-expanded','false');
    const label=select.closest('label');const name=select.getAttribute('aria-label')||(label?[...label.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ').trim():'Choose option');
    button.setAttribute('aria-label',name||'Choose option');
    const value=document.createElement('span');button.append(value);wrap.append(button);
    select.classList.add('custom-select-native');select.tabIndex=-1;select.setAttribute('aria-hidden','true');
    const sync=()=>{value.textContent=select.selectedOptions[0]?.textContent||'Choose an option';button.disabled=select.disabled;button.removeAttribute('aria-invalid');button.removeAttribute('title');};
    controls.set(select,{button,sync});sync();
    select.addEventListener('change',sync);select.addEventListener('focus',()=>button.focus());
    select.addEventListener('invalid',event=>{event.preventDefault();button.setAttribute('aria-invalid','true');button.focus();button.title=select.validationMessage;});
    button.onclick=()=>{if(active?.select===select)close();else open(select,button);};
    button.onkeydown=event=>{
      if(event.key==='Escape'&&active?.select===select){event.preventDefault();event.stopPropagation();close();return;}
      if(event.key==='Tab'){close();return;}
      if(['ArrowDown','ArrowUp','Home','End','Enter',' '].includes(event.key)){
        event.preventDefault();const wasOpen=active?.select===select;if(!wasOpen)open(select,button);if(!active)return;
        const eligible=[...select.options].map((o,i)=>o.disabled?-1:i).filter(i=>i>=0);if(!eligible.length)return;
        if((event.key==='Enter'||event.key===' ')&&wasOpen){choose(active.index);return;}
        if(event.key==='Home')highlight(eligible[0]);else if(event.key==='End')highlight(eligible.at(-1));
        else if(event.key.startsWith('Arrow')){const pos=eligible.indexOf(active.index),next=Math.max(0,Math.min(eligible.length-1,pos+(event.key==='ArrowDown'?1:-1)));highlight(eligible[next]);}
      }else if(event.key.length===1&&!event.ctrlKey&&!event.metaKey&&!event.altKey){
        event.preventDefault();if(active?.select!==select)open(select,button);const now=Date.now();typed=now-typedAt>700?event.key:typed+event.key;typedAt=now;
        const index=[...select.options].findIndex(o=>!o.disabled&&o.textContent.trim().toLowerCase().startsWith(typed.toLowerCase()));if(index>=0)highlight(index);
      }
    };
  }
  const scan=node=>{if(node.nodeType!==1&&node!==root)return;if(node.matches?.('select'))enhance(node);node.querySelectorAll?.('select').forEach(enhance);};
  scan(root);
  new MutationObserver(records=>{
    if(active&&!active.select.isConnected)close();
    for(const record of records){record.addedNodes.forEach(scan);const select=record.target.closest?.('select');if(select&&controls.has(select))controls.get(select).sync();}
  }).observe(root===document?document.documentElement:root,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','selected']});
  document.addEventListener('pointerdown',event=>{if(active&&!active.menu.contains(event.target)&&!active.button.contains(event.target))close();},true);
  document.addEventListener('close',close,true);
  window.addEventListener('resize',position);window.addEventListener('scroll',position,true);
  window.visualViewport?.addEventListener('resize',position);
}

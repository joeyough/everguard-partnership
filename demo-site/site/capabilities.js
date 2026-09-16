/* Coastline: USGS / Hawaii Statewide GIS Program, Terrestrial MapServer layer 3.
   Patrol positions and routes below are fictional demonstrations, not GPS data. */
(()=>{
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const route=location.pathname;
  const dispatchPage=route.includes('/dispatch-center/');
  const patrolPage=route.includes('/mobile-patrol/');
  const surveillancePage=route.includes('/surveillance-monitoring/');
  const overview=!document.querySelector('.service-hero');
  const mapHost=overview?document.querySelector('#dispatch-center'):dispatchPage||patrolPage?document.querySelector('.service-hero'):null;
  if(mapHost){
    mapHost.insertAdjacentHTML('afterend',`<section class="coverage-section" aria-labelledby="coverage-title">
      <div class="coverage-heading"><div><span class="eyebrow">Oʻahu / Connected coverage</span><h2 id="coverage-title">One island.<br><span class="orange">A coordinated presence.</span></h2></div><p>Field teams and dispatch.<br>Working from the same picture.</p></div>
      <div class="coverage-console"><div class="island-view"><div class="map-topline"><span>EG / FIELD OPERATIONS</span><span class="simulation-label">PATROL SIMULATION</span></div>
      <svg class="island-map" viewBox="0 0 760 620" role="img" aria-label="Oʻahu coastline with three illustrative patrol routes"><g class="island-geography"></g><g class="map-routes"></g><g class="map-labels"></g><g class="map-units"></g></svg>
      <p class="map-unavailable" hidden>The coverage illustration is unavailable.</p><div class="map-bottomline"><span><i></i>Illustrative routes · Not live tracking</span><button class="map-motion" type="button" aria-pressed="${reduced.matches}">${reduced.matches?'Play motion':'Pause motion'}</button></div></div>
      <aside class="unit-panel"><span class="eyebrow">On patrol</span><h3>Connected.<br> Every step.</h3><p class="unit-instruction">Select a unit to follow its route.</p><div class="unit-list" role="group" aria-label="Illustrative patrol units">
      ${[['01','West Oʻahu','Kapolei · ʻEwa'],['02','Honolulu','Town · Waikīkī'],['03','Windward','Kāneʻohe · Kailua']].map((u,i)=>`<button class="unit-select ${i===0?'selected':''}" type="button" data-unit="${i}" aria-pressed="${i===0}"><span class="unit-id">EG ${u[0]}</span><span><strong>${u[1]}</strong><small>${u[2]}</small></span><span class="unit-dot" aria-hidden="true"></span></button>`).join('')}</div><p class="unit-status" aria-live="polite">EG 01 · West Oʻahu route selected.</p><div class="dispatch-note"><span>FIELD → DISPATCH</span><p>A check-in. A clear update.<br> The next step, coordinated.</p></div></aside></div>
      <a class="map-credit" href="https://geodata.hawaii.gov/arcgis/rest/services/Terrestrial/MapServer/3" target="_blank" rel="noopener noreferrer">Coastline: USGS / Hawaiʻi Statewide GIS</a>
    </section>`);
    initMap(document.querySelector('.coverage-section'));
  }

  // A camera treatment stays local to the surveillance image.
  const cameraFigure=surveillancePage?document.querySelector('.service-photo'):document.querySelector('#surveillance-monitoring .service-photo');
  if(cameraFigure){
    cameraFigure.classList.add('camera-view');
    cameraFigure.insertAdjacentHTML('beforeend',`<div class="camera-overlay"><div class="camera-top"><span class="camera-rec"><i></i>REC</span><span>EG / MONITORING</span></div><div class="camera-bottom"><span>ILLUSTRATIVE VIEW</span><button class="camera-motion" type="button" aria-pressed="${reduced.matches}" aria-label="${reduced.matches?'Play':'Pause'} recording indicator">${reduced.matches?'Play indicator':'Pause indicator'}</button></div></div>`);
    cameraFigure.classList.toggle('motion-paused',reduced.matches);
    cameraFigure.querySelector('.camera-motion').addEventListener('click',e=>{
      const paused=cameraFigure.classList.toggle('motion-paused');
      e.currentTarget.setAttribute('aria-pressed',String(paused));
      e.currentTarget.setAttribute('aria-label',`${paused?'Play':'Pause'} recording indicator`);
      e.currentTarget.textContent=paused?'Play indicator':'Pause indicator';
    });
  }
  if(surveillancePage){
    document.querySelector('.service-hero').insertAdjacentHTML('afterend',`<section class="response-story" aria-labelledby="response-title"><div class="response-heading"><div><span class="eyebrow">From awareness to action</span><h2 id="response-title">See it. Assess it.<br><span class="orange">Coordinate the response.</span></h2></div><button class="response-play" type="button">See a response ${arrow()}</button></div><ol class="response-steps"><li><span>01 / DETECT</span><h3>Alert detected.</h3><p>Activity brings a camera view into focus.</p></li><li><span>02 / REVIEW</span><h3>A person reviews.</h3><p>An operator assesses what needs attention.</p></li><li><span>03 / COORDINATE</span><h3>The right next step.</h3><p>Information is shared with the appropriate team.</p></li></ol><div class="response-footer"><span>Illustrative workflow</span><p class="response-status" aria-live="polite">Follow an alert through three steps.</p></div></section>`);
    const story=document.querySelector('.response-story'),button=story.querySelector('.response-play'),steps=[...story.querySelectorAll('li')];
    let timers=[];
    button.addEventListener('click',()=>{
      timers.forEach(clearTimeout);timers=[];steps.forEach(el=>el.classList.remove('active','complete'));
      button.disabled=true;
      const delay=reduced.matches?0:1500;
      steps.forEach((el,i)=>timers.push(setTimeout(()=>{steps.forEach((s,j)=>{s.classList.toggle('active',j===i);s.classList.toggle('complete',j<i)});story.querySelector('.response-status').textContent=el.querySelector('h3').textContent;},i*delay)));
      timers.push(setTimeout(()=>{steps.forEach(el=>{el.classList.remove('active');el.classList.add('complete')});button.disabled=false;button.innerHTML=`Replay response ${arrow()}`;story.querySelector('.response-status').textContent='Reviewed. Shared. Ready for follow-through.';},3*delay));
    });
  }

  async function initMap(section){
    const svg=section.querySelector('svg'),ns='http://www.w3.org/2000/svg';
    const create=(name,attrs,parent)=>{const el=document.createElementNS(ns,name);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);parent.append(el);return el;};
    let data;
    try{const result=await fetch('/assets/oahu-coastline.geojson');if(!result.ok)throw new Error('coastline');data=await result.json();if(!data.features?.[0]?.geometry?.coordinates?.length)throw new Error('geometry');}
    catch{svg.hidden=true;section.querySelector('.map-unavailable').hidden=false;section.querySelector('.map-motion').disabled=true;return;}
    const rings=data.features[0].geometry.coordinates,points=rings.flat();
    const xs=points.map(p=>p[0]*Math.cos(21.5*Math.PI/180)),ys=points.map(p=>-p[1]);
    const bounds=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
    const scale=Math.min(620/(bounds[2]-bounds[0]),490/(bounds[3]-bounds[1]));
    const dx=(760-(bounds[2]-bounds[0])*scale)/2,dy=(620-(bounds[3]-bounds[1])*scale)/2;
    const project=([lon,lat])=>[(lon*Math.cos(21.5*Math.PI/180)-bounds[0])*scale+dx,(-lat-bounds[1])*scale+dy];
    const path=coords=>coords.map((p,i)=>`${i?'L':'M'}${project(p).map(v=>v.toFixed(2)).join(',')}`).join(' ');
    const geography=svg.querySelector('.island-geography');
    create('path',{d:rings.map(r=>path(r)+' Z').join(' '),class:'island-coast','fill-rule':'evenodd'},geography);
    const routes=[
      [[-158.085,21.335],[-158.072,21.344],[-158.051,21.352],[-158.029,21.353],[-158.016,21.337],[-158.010,21.321]],
      [[-157.871,21.326],[-157.855,21.316],[-157.842,21.304],[-157.829,21.295],[-157.816,21.286]],
      [[-157.811,21.414],[-157.799,21.406],[-157.781,21.401],[-157.757,21.393],[-157.740,21.397]]
    ];
    const lines=routes.map((coords,i)=>create('path',{d:path(coords),class:`patrol-route ${i===0?'selected':''}`},svg.querySelector('.map-routes')));
    const labels=[['Haleʻiwa',[-158.105,21.59],-12,-10],['Kahuku',[-157.952,21.671],12,-12],['Kapolei',[-158.085,21.335],-45,30],['Honolulu',[-157.858,21.306],-60,38],['Kailua',[-157.74,21.397],12,0]];
    for(const [name,coord,x,y] of labels){const p=project(coord);create('text',{x:p[0]+x,y:p[1]+y},svg.querySelector('.map-labels')).textContent=name;}
    const units=routes.map((coords,i)=>{const g=create('g',{class:`patrol-unit ${i===0?'selected':''}`},svg.querySelector('.map-units'));create('circle',{r:13,class:'unit-halo'},g);create('circle',{r:4.5,class:'unit-core'},g);create('text',{x:12,y:-12},g).textContent=`0${i+1}`;return g;});
    const names=['West Oʻahu','Honolulu','Windward'];
    section.querySelectorAll('.unit-select').forEach(button=>button.addEventListener('click',()=>{
      const index=Number(button.dataset.unit);
      section.querySelectorAll('.unit-select').forEach((b,i)=>{b.classList.toggle('selected',i===index);b.setAttribute('aria-pressed',String(i===index));});
      lines.forEach((el,i)=>el.classList.toggle('selected',i===index));units.forEach((el,i)=>el.classList.toggle('selected',i===index));
      section.querySelector('.unit-status').textContent=`EG 0${index+1} · ${names[index]} route selected.`;
    }));
    let paused=reduced.matches,visible=false,frame=null,elapsed=0,last=0;
    const lengths=lines.map(el=>el.getTotalLength());
    const paint=()=>units.forEach((unit,i)=>{const cycle=(elapsed/(22000+i*5000)+i*.28)%2;const p=lines[i].getPointAtLength((cycle<=1?cycle:2-cycle)*lengths[i]);unit.setAttribute('transform',`translate(${p.x},${p.y})`);});
    const tick=now=>{frame=null;if(paused||!visible){last=0;return;}if(last)elapsed+=now-last;last=now;paint();frame=requestAnimationFrame(tick);};
    const sync=()=>{section.classList.toggle('motion-paused',paused||!visible);if(frame)cancelAnimationFrame(frame);frame=null;last=0;if(!paused&&visible)frame=requestAnimationFrame(tick);};
    const motion=section.querySelector('.map-motion');
    motion.addEventListener('click',()=>{paused=!paused;motion.textContent=paused?'Play motion':'Pause motion';motion.setAttribute('aria-pressed',String(paused));sync();});
    reduced.addEventListener('change',e=>{if(e.matches){paused=true;motion.textContent='Play motion';motion.setAttribute('aria-pressed','true');sync();}});
    new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.05}).observe(section);
    paint();
  }
})();

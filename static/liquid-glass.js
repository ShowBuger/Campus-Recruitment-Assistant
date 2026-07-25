/*
 * Liquid Glass FX driver (vanilla JS)
 * Faithful port of liquid-glass-react's rendering core (MIT License)
 * https://github.com/rdev/liquid-glass-react — same SVG filter chain,
 * same displacement maps, same default parameters (scale 70, aberration 2,
 * saturation 140, blur 6px, elasticity 0.15). No React runtime required.
 * Active only when html[data-style="glass"]; Firefox skips the SVG filter
 * (mirrors the library's own fallback) and keeps the CSS frost.
 */
(function(){
var PANE_SEL='.card,.kpi,.funnel-step,.modal,.login-card,.chat-modal-window,.notification-panel,.toast,.topbar .btn,.btn-primary';
var ELASTIC_SEL='.btn-primary,.topbar .icon-btn';
var ELASTICITY=0.15,ACTIVATION_ZONE=200;
var active=false,mouse={x:0,y:0},raf=0,observer=null;
var isFirefox=navigator.userAgent.toLowerCase().indexOf('firefox')!==-1;

/* SVG filter replicated from GlassContainer's GlassFilter (standard mode) */
var FILTER_SVG='<svg style="position:absolute;width:0;height:0" aria-hidden="true"><defs>'
+'<filter id="lg-filter" x="-35%" y="-35%" width="170%" height="170%" color-interpolation-filters="sRGB">'
+'<feImage x="0" y="0" width="100%" height="100%" result="DISPLACEMENT_MAP" href="'+window.LG_MAP_STANDARD+'" preserveAspectRatio="xMidYMid slice"/>'
+'<feColorMatrix in="DISPLACEMENT_MAP" type="matrix" values="0.3 0.3 0.3 0 0 0.3 0.3 0.3 0 0 0.3 0.3 0.3 0 0 0 0 0 1 0" result="EDGE_INTENSITY"/>'
+'<feComponentTransfer in="EDGE_INTENSITY" result="EDGE_MASK"><feFuncA type="discrete" tableValues="0 0.1 1"/></feComponentTransfer>'
+'<feOffset in="SourceGraphic" dx="0" dy="0" result="CENTER_ORIGINAL"/>'
+'<feDisplacementMap in="SourceGraphic" in2="DISPLACEMENT_MAP" scale="-70" xChannelSelector="R" yChannelSelector="B" result="RED_DISPLACED"/>'
+'<feColorMatrix in="RED_DISPLACED" type="matrix" values="1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0" result="RED_CHANNEL"/>'
+'<feDisplacementMap in="SourceGraphic" in2="DISPLACEMENT_MAP" scale="-77" xChannelSelector="R" yChannelSelector="B" result="GREEN_DISPLACED"/>'
+'<feColorMatrix in="GREEN_DISPLACED" type="matrix" values="0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 1 0" result="GREEN_CHANNEL"/>'
+'<feDisplacementMap in="SourceGraphic" in2="DISPLACEMENT_MAP" scale="-84" xChannelSelector="R" yChannelSelector="B" result="BLUE_DISPLACED"/>'
+'<feColorMatrix in="BLUE_DISPLACED" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 1 0" result="BLUE_CHANNEL"/>'
+'<feBlend in="GREEN_CHANNEL" in2="BLUE_CHANNEL" mode="screen" result="GB_COMBINED"/>'
+'<feBlend in="RED_CHANNEL" in2="GB_COMBINED" mode="screen" result="RGB_COMBINED"/>'
+'<feGaussianBlur in="RGB_COMBINED" stdDeviation="0.3" result="ABERRATED_BLURRED"/>'
+'<feComposite in="ABERRATED_BLURRED" in2="EDGE_MASK" operator="in" result="EDGE_ABERRATION"/>'
+'<feComponentTransfer in="EDGE_MASK" result="INVERTED_MASK"><feFuncA type="table" tableValues="1 0"/></feComponentTransfer>'
+'<feComposite in="CENTER_ORIGINAL" in2="INVERTED_MASK" operator="in" result="CENTER_CLEAN"/>'
+'<feComposite in="EDGE_ABERRATION" in2="CENTER_CLEAN" operator="over"/>'
+'</filter></defs></svg>';

function $(id){return document.getElementById(id)}

function ensureDefs(){
  if($('lg-defs'))return;
  var d=document.createElement('div');
  d.id='lg-defs';d.style.cssText='position:absolute;width:0;height:0;overflow:hidden';
  d.innerHTML=FILTER_SVG;
  document.body.appendChild(d);
}

function warp(el){
  if(el.querySelector(':scope > .lg-warp'))return;
  var cs=getComputedStyle(el);
  if(cs.position==='static')el.style.position='relative';
  var s=document.createElement('span');
  s.className='lg-warp';
  s.setAttribute('aria-hidden','true');
  /* clip the warped frost to the element's rounded shape without touching
     its overflow (modals/sidebar need to keep scrolling) */
  if(cs.borderRadius&&cs.borderRadius!=='0px')s.style.clipPath='inset(0 round '+cs.borderRadius+')';
  el.appendChild(s);
}
function warpAll(){document.querySelectorAll(PANE_SEL).forEach(warp)}
function unwarpAll(){
  document.querySelectorAll('.lg-warp').forEach(function(s){s.parentNode.removeChild(s)});
  document.querySelectorAll(ELASTIC_SEL).forEach(function(el){el.style.transform=''});
  var d=$('lg-defs');if(d)d.parentNode.removeChild(d);
}

/* elasticity: same math as the component's calculateDirectionalScale /
   calculateElasticTranslation (activation zone 200px, clamp 0.8) */
function edgeInfo(el){
  var r=el.getBoundingClientRect();
  var cx=r.left+r.width/2,cy=r.top+r.height/2;
  var dx=mouse.x-cx,dy=mouse.y-cy;
  var ex=Math.max(0,Math.abs(dx)-r.width/2),ey=Math.max(0,Math.abs(dy)-r.height/2);
  var edge=Math.sqrt(ex*ex+ey*ey);
  return{dx:dx,dy:dy,edge:edge,fade:edge>ACTIVATION_ZONE?0:1-edge/ACTIVATION_ZONE};
}
function tick(){
  raf=0;
  document.querySelectorAll(ELASTIC_SEL).forEach(function(el){
    var info=edgeInfo(el);
    if(!info.fade){el.style.transform='';return}
    var cd=Math.sqrt(info.dx*info.dx+info.dy*info.dy);
    var tx=info.dx*ELASTICITY*0.1*info.fade,ty=info.dy*ELASTICITY*0.1*info.fade;
    var scale='';
    if(cd>0){
      var nx=info.dx/cd,ny=info.dy/cd;
      var si=Math.min(cd/300,1)*ELASTICITY*info.fade;
      var sx=1+Math.abs(nx)*si*0.3-Math.abs(ny)*si*0.15;
      var sy=1+Math.abs(ny)*si*0.3-Math.abs(nx)*si*0.15;
      scale=' scaleX('+Math.max(0.8,sx).toFixed(4)+') scaleY('+Math.max(0.8,sy).toFixed(4)+')';
    }
    el.style.transform='translate('+tx.toFixed(2)+'px,'+ty.toFixed(2)+'px)'+scale;
  });
}
function onMove(e){
  mouse.x=e.clientX;mouse.y=e.clientY;
  if(!raf)raf=requestAnimationFrame(tick);
}

function sync(enable){
  if(enable===active)return;
  active=enable;
  if(enable&&!isFirefox){
    ensureDefs();warpAll();
    observer=new MutationObserver(function(){if(active)warpAll()});
    observer.observe(document.body,{childList:true,subtree:true});
    window.addEventListener('mousemove',onMove,{passive:true});
    document.documentElement.classList.add('lg-live');
  }else{
    if(observer){observer.disconnect();observer=null}
    window.removeEventListener('mousemove',onMove);
    if(raf){cancelAnimationFrame(raf);raf=0}
    document.documentElement.classList.remove('lg-live');
    unwarpAll();
  }
}

window.LiquidGlassFX={sync:sync};
})();

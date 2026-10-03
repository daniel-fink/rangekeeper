const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('../../assets/routing.cjs');
const rect=(x=0,y=0,w=100,h=80)=>({x,y,w,h});
const make=(source,target,extra={})=>R.route({source,target,sourceId:'a',targetId:'b',...extra});
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`);
function check(r,s,t){
 assert.deepEqual(r.source,R.ports(s)[r.sourcePort]);assert.deepEqual(r.target,R.ports(t)[r.targetPort]);
 for(const [point,c,n] of [[r.source,r.controls[0],R.normals[r.sourcePort]],[r.target,r.controls.at(-1),R.normals[r.targetPort]]]){
  close((c.x-point.x)*n.y-(c.y-point.y)*n.x,0);
  assert.ok((c.x-point.x)*n.x+(c.y-point.y)*n.y>0);
 }
 for(const p of [r.source,r.target,...r.controls])assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.y));
}
test('all four directions snap both endpoints to side midpoints',()=>{
 for(const [target,sp,tp] of [[rect(0,-300),'top','bottom'],[rect(300,0),'right','left'],[rect(0,300),'bottom','top'],[rect(-300,0),'left','right']]){
  const r=make(rect(),target);assert.equal(r.sourcePort,sp);assert.equal(r.targetPort,tp);check(r,rect(),target);
 }
});
test('native reference is honoured; ties and six-unit hysteresis are stable',()=>{
 const box=rect(0,0,100,100);
 assert.equal(R.choosePort(box,{x:25,y:-25}), 'top');
 assert.equal(R.choosePort(box,{x:25,y:-25},'right'), 'right');
 assert.equal(R.choosePort(box,{x:27,y:-23},'top'), 'top');
 assert.equal(R.choosePort(box,{x:30,y:-20},'top'), 'right');
 const reference={x:0,y:40};assert.equal(make(rect(),rect(300,0),{sourceReference:reference}).sourcePort,'bottom');
});
test('header geometry rather than full box determines routing',()=>{
 const header={...rect(100,-200,400,36),nodePosition:{x:100,y:0}},member=rect(100,-100);
 const r=make(header,member);assert.equal(r.sourcePort,'bottom');check(r,header,member);
});
test('parallel and opposite directions separate internally but preserve tangents',()=>{
 const a=rect(),b=rect(300,0),curves=[];
 for(let lane=0;lane<3;lane++){const r=lane===2?make(b,a,{sourceId:'b',targetId:'a',lane,laneCount:3}):make(a,b,{lane,laneCount:3});check(r,lane===2?b:a,lane===2?a:b);curves.push(JSON.stringify(r.controls));}
 assert.equal(new Set(curves).size,3);
});
test('coincident and touching rectangles retain distinct defined ports',()=>{
 for(const b of [rect(),rect(100,0)])check(make(rect(),b),rect(),b);
 assert.equal(make(rect(),rect()).sourcePort,'right');
});
test('self loops align to ports on ordinary nodes and elevated Assembly headers',()=>{
 for(const s of [rect(),{...rect(100,-200,500,36),nodePosition:{x:100,y:0}}]){
  const r=make(s,s,{targetId:'a'});check(r,s,s);assert.ok(r.loop);assert.notEqual(r.sourcePort,r.targetPort);
 }
});
test('pure routing and native style generation preserve all inputs',()=>{
 const input={source:rect(),target:rect(80,160),sourceId:'a',targetId:'b'};const before=JSON.stringify(input);
 const r=R.route(input),styles=R.style(r,input.source,input.target);
 assert.equal(JSON.stringify(input),before);assert.equal(styles['curve-style'],'unbundled-bezier');
 assert.ok(!Object.values(styles).some(v=>String(v).includes('NaN')));
});

test('single edges have two controls; parallel separation spans two interior controls',()=>{
 assert.equal(make(rect(),rect(300,100)).controls.length,2);
 assert.equal(make(rect(),rect(300,100),{laneCount:2}).controls.length,4);
});
test('forward handles follow their own axes, not diagonal separation',()=>{
 const a={x:0,y:0},b={x:100,y:300};
 close(R.handleLength(a,b,R.normals.right),50);
 close(R.handleLength(a,{x:100,y:900},R.normals.right),50);
 close(R.handleLength(b,a,R.normals.top),120);
 close(R.handleLength(a,{x:60,y:100},R.normals.bottom),50);
});
test('short, perpendicular and backward handles remain bounded and nonzero',()=>{
 const a={x:0,y:0};
 close(R.handleLength(a,{x:2,y:0},R.normals.right),1.5);
 close(R.handleLength(a,{x:0,y:50},R.normals.right),32);
 close(R.handleLength(a,{x:-100,y:0},R.normals.right),62.5);
 close(R.handleLength(a,{x:-2,y:0},R.normals.right),1.5);
 for(const x of [-10000,-100,-1,-.001,0,.001,1,100,10000]){
  const b={x,y:5},h=R.handleLength(a,b,R.normals.right);
  assert.ok(h>0&&h<=120&&h<=Math.hypot(x,5)*.75);
 }
});

test('sideways approaches retain room to turn at both ports',()=>{
 const r=make(rect(),rect(140,220),{sourceReference:{x:50,y:0},targetReference:{x:90,y:220}});
 close(r.controls[0].x-r.source.x,32);
 close(r.target.x-r.controls.at(-1).x,32);
 check(r,rect(),rect(140,220));
});
test('labels follow their displayed span along the curve and stay readable in reverse',()=>{
 const r={source:{x:0,y:0},target:{x:200,y:60},controls:[{x:100,y:0},{x:100,y:60}]};
 // Short text follows the local turn; longer text averages a broader section.
 const angle=R.labelAngle(r,30);assert.ok(angle>R.labelAngle(r,100));
 close(angle,R.labelAngle({source:r.target,target:r.source,controls:[...r.controls].reverse()},30));
 close(R.labelAngle({source:{x:0,y:0},target:{x:200,y:0},controls:[{x:50,y:0},{x:150,y:0}]},50),0);
 for(const result of [make(rect(),rect(),{targetId:'a'}),make(rect(),rect()),make(rect(),rect(300,200),{laneCount:3})]){
  const value=R.labelAngle(result,50);assert.ok(Number.isFinite(value)&&Math.abs(value)<=Math.PI/2);
 }
});

test('label budget grows with the middle span and reserves endpoint clearance',()=>{
 const straight=span=>({source:{x:0,y:0},target:{x:span,y:0},controls:[]});
 close(R.labelWidth(straight(100)),42);
 close(R.labelWidth(straight(200)),92);
 close(R.labelWidth({...straight(200),controls:[{x:100,y:0},{x:100,y:0}]}),92);
 close(R.labelWidth(straight(10)),0);
 const r=make(rect(),rect(140,220),{sourceReference:{x:50,y:0},targetReference:{x:90,y:220}});
 assert.ok(R.labelWidth(r)>0);
 close(R.labelWidth(r),R.labelWidth({source:r.target,target:r.source,controls:[...r.controls].reverse()}));
 for(const result of [make(rect(),rect(),{targetId:'a'}),make(rect(),rect()),make(rect(),rect(300,200),{laneCount:3})]){
  assert.ok(Number.isFinite(R.labelWidth(result))&&R.labelWidth(result)>=0);
 }
});

test('parallel routes do not fold back for short facing ports, including opposing arrows',()=>{
 for(const gap of [1,5,20,50,100,400]) for(const dy of [0,5,-5]) for(const laneCount of [2,3,6]){
  const a=rect(),b=rect(100+gap,dy);
  for(let lane=0;lane<laneCount;lane++){
   const r=make(a,b,{lane,laneCount,sourceReference:{x:50,y:0},targetReference:{x:50+gap,y:dy}});
   check(r,a,b);
   let previous=r.source;
   for(let i=1;i<=256;i++){
    const point=R.curvePoint(r,i/256);
    assert.ok((point.x-previous.x)*gap+(point.y-previous.y)*dy>1e-10,`backtracking at gap ${gap}, lane ${lane}`);
    previous=point;
   }
   const reverse=make(b,a,{sourceId:'b',targetId:'a',lane,laneCount,
    sourceReference:{x:50+gap,y:dy},targetReference:{x:50,y:0}});
   r.controls.forEach((c,i)=>{close(c.x,reverse.controls.at(-1-i).x);close(c.y,reverse.controls.at(-1-i).y);});
  }
 }
});
test('parallel separation stays broad and shrinks with available space',()=>{
 const wide=make(rect(),rect(300,0),{lane:0,laneCount:2});
 const short=make(rect(),rect(120,0),{lane:0,laneCount:2});
 assert.ok(Math.abs(short.controls[1].y)<Math.abs(wide.controls[1].y));
 close(wide.controls[1].y,wide.controls[2].y);
 assert.ok(wide.controls[2].x>wide.controls[1].x);
});
test('label span centres on the native midpoint, not half the travelled length',()=>{
 const r={source:{x:0,y:0},target:{x:300,y:100},controls:[{x:10,y:0},{x:300,y:20}]};
 const arc=R.sampleCurve(r),centre=R.curvePoint(r,.5);
 assert.ok(Math.abs(arc.centreLength-arc.total/2)>1);
 close(arc.atLength(arc.centreLength).x,centre.x);close(arc.atLength(arc.centreLength).y,centre.y);
 const a=arc.atLength(arc.centreLength-20),b=arc.atLength(arc.centreLength+20);
 close(R.labelAngle(r,40,arc),Math.atan2(b.y-a.y,b.x-a.x));
 const degenerate={source:{x:0,y:0},target:{x:0,y:0},controls:[]};
 assert.equal(R.labelAngle(degenerate,40),0);
});
test('displayed text measurement accounts for ellipsis without changing source text',()=>{
 const text='Contains',measure=s=>s.length*6;
 assert.deepEqual(R.fitLabel(text,36,measure),{text:'Conta…',width:36});
 assert.deepEqual(R.fitLabel(text,100,measure),{text,width:48});
 assert.equal(text,'Contains');
});

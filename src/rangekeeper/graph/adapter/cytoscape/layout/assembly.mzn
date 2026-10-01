% Versioned experimental layout contract. Arithmetic checker is implemented separately.
include "all_different.mzn";
int: nn; int: ng; int: nm;
int: nc; array[1..nc] of int: ci; array[1..nc] of int: cj;
bool: hinted; bool: ceil_order;
array[1..ng] of bool: packed;
array[1..ng] of int: flow; array[1..ng] of int: alignment;
bool: neighborhood; array[1..nn+ng] of bool: free_object; array[1..ng] of bool: free_grid;
set of int: O = 1..nn+ng; set of int: G = 1..ng; set of int: M = 1..nm;
int: canvas_w; int: canvas_h; int: padding; int: header; int: gap;
array[O] of int: minimum_w; array[1..nn] of int: node_h;
array[M] of int: mg; array[M] of int: mo; array[M] of int: rank;
array[G] of int: count;
int: ne; array[1..ne] of int: en; array[1..ne] of int: eg;
int: na; array[1..na] of int: ai; array[1..na] of int: ao;
int: np; array[1..np] of int: pi; array[1..np] of int: px; array[1..np] of int: py;
bool: flexible; bool: strict; bool: fixed;
array[O] of int: sx; array[O] of int: sy; array[O] of int: sw; array[O] of int: sh;
array[G] of int: sgx; array[G] of int: sgy; array[G] of int: sc;
array[M] of int: ss;
array[G] of int: direction; array[G] of int: strength;
int: style_unit; array[1..5] of int: weights;
int: no; array[1..no] of int: ob; array[1..no] of int: oe;
array[1..no] of int: og; array[1..no] of int: axis;
int: nf; array[1..nf] of int: fl; array[1..nf] of int: fr;
array[1..nf] of int: fg; array[1..nf] of int: fw;
% phase=0 establishes feasibility, otherwise optimize the corresponding score.
int: phase; array[1..9] of int: proved; int: incumbent_bound;
array[O] of var 0..canvas_w: x;
array[O] of var 0..canvas_h: y;
array[O] of var 1..canvas_w: w;
array[O] of var 1..canvas_h: h;
constraint forall(i in O)(x[i]+w[i]<=canvas_w /\ y[i]+h[i]<=canvas_h /\ w[i]>=minimum_w[i]);
constraint forall(i in 1..nn)(w[i]=minimum_w[i] /\ h[i]=node_h[i]);
constraint forall(g in G)(h[nn+g]>=header+2*padding);
constraint forall(k in 1..np)(x[pi[k]]=px[k] /\ y[pi[k]]=py[k]);
constraint forall(k in M)(let {int:g=nn+mg[k], int:i=mo[k]} in
 x[i]>=x[g]+padding /\ y[i]>=y[g]+header+padding /\
 x[i]+w[i]<=x[g]+w[g]-padding /\ y[i]+h[i]<=y[g]+h[g]-padding);
predicate apart(var int:ax,var int:ay,var int:aw,var int:ah,
 var int:bx,var int:by,var int:bw,var int:bh) =
 ax+aw+gap<=bx \/ bx+bw+gap<=ax \/ ay+ah+gap<=by \/ by+bh+gap<=ay;
constraint forall(k in 1..nc)(let {int:i=ci[k],int:j=cj[k]} in apart(x[i],y[i],w[i],if i<=nn then h[i] else header endif,
 x[j],y[j],w[j],if j<=nn then h[j] else header endif));
array[1..ne] of var bool: excluded_node = [apart(x[en[k]],y[en[k]],w[en[k]],h[en[k]],
 x[eg[k]],y[eg[k]],w[eg[k]],h[eg[k]]) | k in 1..ne];
array[1..na] of var bool: excluded_group = [
 x[ai[k]]<x[ao[k]] \/ y[ai[k]]<y[ao[k]] \/
 x[ai[k]]+w[ai[k]]>x[ao[k]]+w[ao[k]] \/ y[ai[k]]+h[ai[k]]>y[ao[k]]+h[ao[k]] | k in 1..na];
constraint if strict then forall(excluded_node) /\ forall(excluded_group) else true endif;
array[G] of var 0..canvas_w: gx;
array[G] of var 0..canvas_h: gy;
array[G] of var 1..max([1]++count): cols;
array[M] of var 0..max([0]++count): slot;
array[G] of var 0..canvas_w+gap: pitch_x;
array[G] of var 0..canvas_h+gap: pitch_y;
constraint forall(g in G)(if count[g]>0 then
 cols[g]<=count[g] /\ gx[g]>=x[nn+g]+padding /\ gy[g]>=y[nn+g]+header+padding /\
 gx[g]<=x[nn+g]+w[nn+g]-padding /\ gy[g]<=y[nn+g]+h[nn+g]-padding /\
 pitch_x[g]=max([w[mo[k]]+gap|k in M where mg[k]=g]) /\
 pitch_y[g]=max([h[mo[k]]+gap|k in M where mg[k]=g]) /\
 all_different([slot[k]|k in M where mg[k]=g])
 else cols[g]=1 /\ gx[g]=0 /\ gy[g]=0 /\ pitch_x[g]=0 /\ pitch_y[g]=0 endif);
constraint forall(k in M)(slot[k]<count[mg[k]] /\ (if flexible then true else slot[k]=rank[k] endif));
constraint forall(g in G where count[g]>0 /\ flow[g]>0)(cols[g]=(if flow[g]=2 then 1 else count[g] endif));
constraint forall(k in M where flow[mg[k]]>0)(let {
 int:g=mg[k], int:i=mo[k], int:p=nn+g,
 var int:start=if flow[g]=2 then x[p]+padding else y[p]+header+padding endif,
 var int:span=if flow[g]=2 then w[p]-2*padding else h[p]-header-2*padding endif,
 var int:size=if flow[g]=2 then w[i] else h[i] endif
} in (if flow[g]=2 then x[i] else y[i] endif)=start+
 (if alignment[g]=0 then 0 elseif alignment[g]=1 then (span-size) div 2 else span-size endif));
constraint forall(k,l in M where k!=l /\ mg[k]=mg[l] /\ flow[mg[k]]>0)(slot[k]<slot[l] ->
 if flow[mg[k]]=2 then y[mo[k]]+h[mo[k]]+gap<=y[mo[l]] else x[mo[k]]+w[mo[k]]+gap<=x[mo[l]] endif);
array[M] of var int: packed_offset = [sum(l in M where mg[l]=mg[k])(
 if slot[l]<slot[k] then (if flow[mg[k]]=2 then h[mo[l]] else w[mo[l]] endif)+gap else 0 endif) | k in M];
constraint forall(k in M where packed[mg[k]])(if flow[mg[k]]=2 then
 y[mo[k]]=y[nn+mg[k]]+header+padding+packed_offset[k] else
 x[mo[k]]=x[nn+mg[k]]+padding+packed_offset[k] endif);
array[G] of var int: local_grid = [sum(k in M where mg[k]=g)(
 abs(x[mo[k]]-gx[g]-(if packed[g] then (if flow[g]=1 then packed_offset[k] else 0 endif) else (slot[k] mod cols[g])*pitch_x[g] endif)) +
 abs(y[mo[k]]-gy[g]-(if packed[g] then (if flow[g]=2 then packed_offset[k] else 0 endif) else (slot[k] div cols[g])*pitch_y[g] endif))) | g in G];
array[G] of var int: rows = [(count[g]+cols[g]-1) div cols[g] | g in G];
var int: grid_score = sum(g in G where count[g]>0)(strength[g]*(local_grid[g] div count[g]));
var int: direction_score = sum(g in G where count[g]>1)(strength[g]*style_unit*(
 if direction[g]=1 then max(0,2*rows[g]-cols[g])
 elseif direction[g]=2 then max(0,2*cols[g]-rows[g])
 elseif direction[g]=3 then abs(cols[g]-rows[g]) else 0 endif));
array[1..no] of var int: order_deficit = [max(0,if axis[k]=0 then
 2*x[ob[k]]+w[ob[k]]+2-2*x[oe[k]]-w[oe[k]] else
 2*y[ob[k]]+h[ob[k]]+2-2*y[oe[k]]-h[oe[k]] endif) | k in 1..no];
var int: order_score = sum(g in G where exists(k in 1..no)(og[k]=g))(
 strength[g]*((sum(k in 1..no where og[k]=g)(order_deficit[k]) + (if ceil_order then 2*sum(k in 1..no)(bool2int(og[k]=g))-1 else 0 endif)) div (2*sum(k in 1..no)(bool2int(og[k]=g)))));
array[1..nf] of var int: distance = [
 max([0,x[fl[k]]-x[fr[k]]-w[fr[k]],x[fr[k]]-x[fl[k]]-w[fl[k]]]) +
 max([0,y[fl[k]]-y[fr[k]]-h[fr[k]],y[fr[k]]-y[fl[k]]-h[fl[k]]]) | k in 1..nf];
var int: similarity_score = sum(g in G where exists(k in 1..nf)(fg[k]=g))(
 strength[g]*(sum(k in 1..nf where fg[k]=g)(fw[k]*distance[k]) div sum(k in 1..nf where fg[k]=g)(fw[k])));
var int: extent = max(i in O)(x[i]+w[i])+max(i in O)(y[i]+h[i]);
array[1..9] of var int: scores = [
 sum(k in 1..ne)(bool2int(not excluded_node[k]))+sum(k in 1..na)(bool2int(not excluded_group[k])),
 sum(local_grid), extent, sum(g in G)(w[nn+g]+h[nn+g]),
 grid_score,direction_score,order_score,similarity_score,
 weights[1]*grid_score+weights[2]*direction_score+weights[3]*order_score+weights[4]*similarity_score+weights[5]*extent];
constraint forall(k in 1..9 where proved[k]>=0)(scores[k]=proved[k]);
constraint if phase>0 then scores[phase]<=incumbent_bound else true endif;
constraint if fixed then
 forall(i in O)(x[i]=sx[i] /\ y[i]=sy[i] /\ w[i]=sw[i] /\ h[i]=sh[i]) /\
 forall(g in G)(gx[g]=sgx[g] /\ gy[g]=sgy[g] /\ cols[g]=sc[g]) /\
 forall(k in M)(slot[k]=ss[k]) else true endif;
constraint if neighborhood then
 forall(i in O where not free_object[i])(x[i]=sx[i] /\ y[i]=sy[i] /\ w[i]=sw[i] /\ h[i]=sh[i]) /\
 forall(g in G where not free_grid[g])(gx[g]=sgx[g] /\ gy[g]=sgy[g] /\ cols[g]=sc[g]) /\
 forall(k in M where not free_grid[mg[k]])(slot[k]=ss[k]) else true endif;
solve :: seq_search(if hinted then [
 warm_start(x,sx), warm_start(y,sy), warm_start(w,sw), warm_start(h,sh),
 warm_start(gx,sgx),warm_start(gy,sgy),warm_start(cols,sc),warm_start(slot,ss)
] else [] endif) minimize if phase=0 then 0 else scores[phase] endif;
output ["{\"x\":",show(x),",\"y\":",show(y),",\"w\":",show(w),",\"h\":",show(h),
 ",\"gx\":",show(gx),",\"gy\":",show(gy),",\"cols\":",show(cols),",\"slot\":",show(slot),",\"scores\":",show(scores),"}"];

/** Original vector fallback: crisp at any viewport, without animation or WebGL. */
export default function CityStill({selected}:{selected:number}){
 return <svg className="city-still" viewBox="0 0 1000 400" aria-hidden="true">
 <path d="M80 270 500 100 920 270 500 390Z" fill="#041628" stroke="#148fc0"/>
 {Array.from({length:60},(_,i)=>{const row=Math.floor(i/10),col=i%10,x=170+col*55+row*24,y=250+row*14-col*8,h=24+Math.abs(Math.sin(i*3.7))*85,district=Math.floor(col/2),c=district===selected?'#ffd18b':'#29b8ed';return <g key={i}>
 <path d={`M${x} ${y}v${-h}l14 -7 14 7v${h}l-14 7Z`} fill="#0a2b43" stroke={c} strokeWidth=".8"/>
 <path d={`M${x} ${y-h}l14 7 14 -7M${x+14} ${y-h+7}v${h}`} fill="none" stroke={c} opacity=".7"/>
 {[1,2,3,4].map(n=><path key={n} d={`M${x+4} ${y-h+n*h/5}l5 2m10 0 5 -2`} stroke={c} strokeWidth="2"/>)}
 </g>})}
 </svg>;
}

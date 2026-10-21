"use client";
import {useEffect,useState} from "react";
const choices=[
  {id:"signal",label:"Signal Noir"},
  {id:"command",label:"Command Red"},
];
export default function ThemeReview(){
  const [theme,setTheme]=useState("signal");
  useEffect(()=>{
    const stored=window.sessionStorage.getItem("nsh-visual-direction");
    const selected=choices.some(x=>x.id===stored)?stored:"signal";
    document.documentElement.dataset.nshTheme=selected;
    setTheme(selected);
  },[]);
  function choose(value){
    if(!choices.some(x=>x.id===value))return;
    document.documentElement.dataset.nshTheme=value;
    try{window.sessionStorage.setItem("nsh-visual-direction",value);}catch{}
    setTheme(value);
  }
  if(process.env.NEXT_PUBLIC_NSH_DESIGN_LAB!=="1")return null;
  return <div className="nsh-design-review" role="group" aria-label="Private design direction preview">
    <div className="nsh-design-review-top"><span className="nsh-design-review-dot"/> PRIVATE DESIGN COMPARISON</div>
    <div className="nsh-design-review-actions">{choices.map(c=><button type="button" key={c.id} aria-pressed={c.id===theme} className={c.id===theme?"active":""} onClick={()=>choose(c.id)}>{c.label}</button>)}</div>
  </div>;
}

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
const css=fs.readFileSync(new URL("../app/globals.css",import.meta.url),"utf8");
const component=fs.readFileSync(new URL("../components/ThemeReview.jsx",import.meta.url),"utf8");
test("red-black-white-yellow design tokens present",()=>{
  for(const token of ["--signal-red:","--signal-yellow:","--signal-ink:","--signal-black:"]){
    assert.ok(css.includes(token),token+" missing");
  }
  assert.match(css,/\[data-nsh-theme="command"\]/);
});
test("theme comparison limited to private design builds",()=>{
  assert.match(component,/NEXT_PUBLIC_NSH_DESIGN_LAB/);
  assert.match(component,/sessionStorage/);
  assert.match(component,/aria-pressed/);
});
test("warning severity remains meaningful beyond brand theme",()=>{
  assert.match(css,/\.alert-severity\.severity-severe/);
  assert.match(css,/\.alert-severity\.severity-moderate/);
});

function luminosity(hex){
 const a=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255)
  .map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);
 return .2126*a[0]+.7152*a[1]+.0722*a[2];
}
function contrast(a,b) {
 const aa=luminosity(a),bb=luminosity(b);
 return (Math.max(aa,bb)+0.05)/(Math.min(aa,bb)+0.05);
}
test("primary button text and warning source yellow have readable contrast",()=>{
 const white="#ffffff",dark="#08090d";
 assert.ok(contrast(white,"#c6233d")>=4.5,"primary CTA start must pass AA");
 assert.ok(contrast(white,"#d42c43")>=4.5,"primary CTA end must pass AA");
 assert.ok(contrast("#ffe05d",dark)>=7,"caution yellow must be strongly readable on near black");
});

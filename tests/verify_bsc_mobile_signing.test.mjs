import {test} from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import {createRequire} from "node:module";

const require=createRequire(import.meta.url);
const {Wallet,verifyMessage}=require("../contracts/escrow/node_modules/ethers");
const TEMPLATE=path.resolve("apps/empire-public-site/treasury-proof-template.html");

function harness({wallet, selected=wallet.address}) {
 const now=new Date();
 const proof={
   candidate_wallet:wallet.address,
   message:"Empire AI / EmpireOS — BSC Treasury Control Verification\nWallet: "+wallet.address+
     "\nNo transactions, token approvals, funds transfers are authorised.",
   expires_at:new Date(now.getTime()+3600000).toISOString(),
 };
 const nodes=new Map();
 for(const id of ["wallet","expiry","message","sign","status","result","signature","copy"]){
   nodes.set(id,{textContent:"",value:"",style:{display:"none"},listeners:{},
     addEventListener(name,callback){this.listeners[name]=callback},
     focus(){},select(){}});
 }
 const calls=[];
 const window={ethereum:{async request(req){
   calls.push(req);
   if(req.method==="eth_requestAccounts") return [selected];
   if(req.method==="personal_sign"){
     assert.equal(req.params.length,2);
     assert.equal(req.params[1],selected);
     assert.match(req.params[0],/^0x[0-9a-f]+$/);
     return wallet.signMessage(Buffer.from(req.params[0].slice(2),"hex"));
   }
   throw Error("UNEXPECTED_WALLET_RPC");
 }}};
 const html=fs.readFileSync(TEMPLATE,"utf8");
 const matches=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
 assert.equal(matches.length,1);
 const js=matches[0][1].replace("__ESCROW_CHALLENGE_JSON__",JSON.stringify(proof));
 vm.runInNewContext(js,{
   document:{getElementById:id=>{assert(nodes.has(id));return nodes.get(id)}},
   window,navigator:{clipboard:{writeText:async()=>{throw Error("NO_UPLOAD")}}},
   Date,TextEncoder,Array,Buffer,
 });
 return {nodes,calls,proof,window};
}

test("mobile personal_sign uses EIP-1193 hex UTF-8 and recovers exact account",async()=>{
 const wallet=Wallet.createRandom();
 const ui=harness({wallet});
 await ui.nodes.get("sign").listeners.click();
 assert.deepEqual(ui.calls.map(c=>c.method),["eth_requestAccounts","personal_sign"]);
 const signed=ui.calls[1].params;
 const hex=signed[0];
 assert.equal(Buffer.from(hex.slice(2),"hex").toString("utf8"),ui.proof.message);
 assert.equal(signed[1],wallet.address);
 assert.equal(verifyMessage(ui.proof.message,ui.nodes.get("result").value),wallet.address);
 assert.equal(ui.nodes.get("signature").style.display,"block");
 assert.match(ui.nodes.get("status").textContent,/No transaction was sent/);
 assert.equal(ui.calls.filter(x=>x.method==="eth_sendTransaction").length,0);
});

test("different active phone wallet is rejected before message signing",async()=>{
 const wallet=Wallet.createRandom(),other=Wallet.createRandom();
 const ui=harness({wallet,selected:other.address});
 await ui.nodes.get("sign").listeners.click();
 assert.deepEqual(ui.calls.map(c=>c.method),["eth_requestAccounts"]);
 assert.match(ui.nodes.get("status").textContent,/Wrong wallet selected/);
 assert.equal(ui.nodes.get("signature").style.display,"none");
});

test("page refuses all remote signature submission paths",()=>{
 const html=fs.readFileSync(TEMPLATE,"utf8");
 assert.ok(html.includes('new TextEncoder().encode(proof.message)'));
 assert.ok(html.includes('method:"personal_sign",params:[messageHex,account]'));
 for(const forbidden of ["eth_sendTransaction","eth_signTypedData","fetch(","XMLHttpRequest","<form","navigator.sendBeacon"]){
   assert.ok(!html.includes(forbidden),forbidden);
 }
});

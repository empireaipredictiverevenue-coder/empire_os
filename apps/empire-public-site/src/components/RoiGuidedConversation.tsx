"use client";

import { useState } from "react";
import type { RoiInputs, RoiScenario } from "@/lib/roi-assessment";
import { ROI_ENQUIRY_DRAFT_KEY, makeRoiEnquiryDraft, saveRoiEnquiryDraft } from "@/lib/roi-enquiry-transfer";
import {
  EMPTY_QUALIFICATION, qualificationBrief, respondToRoiQuestion,
  type Qualification,
} from "@/lib/roi-conversation";

type Message = { role: "visitor" | "guide"; body: string };
type Stage = "idle" | "sector" | "challenge" | "timing" | "done";

const sectors: NonNullable<Qualification["sector"]>[] =
  ["Roofing", "Solar", "HVAC", "Dental", "Other B2B"];
const challenges: NonNullable<Qualification["challenge"]>[] =
  ["Qualifying enquiries", "Slow follow-up", "Measuring conversion", "Understanding costs"];
const timing: NonNullable<Qualification["timing"]>[] =
  ["Exploring", "Within 3 months", "This month"];

/** Rule-based conversational pilot. No inference provider, network or storage. */
export default function RoiGuidedConversation({
  inputs, base, currency,
}: {
  inputs: RoiInputs; base: RoiScenario; currency: "GBP" | "USD";
}) {
  const [typed, setTyped] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {role:"guide",body:"I'm Empire AI's text-only guided assessment assistant. I can explain the figures you entered and help prepare a business enquiry. My replies follow reviewed rules, not a live generative AI model."},
  ]);
  const [qualifying, setQualifying] = useState<Stage>("idle");
  const [qualification, setQualification] = useState<Qualification>(EMPTY_QUALIFICATION);
  const [copyStatus, setCopyStatus] = useState("");

  function addMessages(...items: Message[]) {
    setMessages(previous => [...previous.slice(-16), ...items]);
  }

  function sendQuestion() {
    const question = typed.trim();
    if (!question || question.length > 220) return;
    addMessages(
      {role:"visitor",body:question},
      {role:"guide",body:respondToRoiQuestion(question,inputs,base,currency)},
    );
    setTyped("");
  }

  function beginQualification() {
    setQualification({...EMPTY_QUALIFICATION});
    setQualifying("sector");
    setCopyStatus("");
    addMessages({role:"guide",body:"Optional business-fit check — no names, contact details or submission. First, what sector best describes your business?"});
  }

  function chooseSector(sector: NonNullable<Qualification["sector"]>) {
    setQualification(previous=>({...previous,sector}));
    setQualifying("challenge");
    addMessages(
      {role:"visitor",body:sector},
      {role:"guide",body:"Thanks. Which business problem would you most like to investigate?"},
    );
  }

  function chooseChallenge(challenge: NonNullable<Qualification["challenge"]>) {
    setQualification(previous=>({...previous,challenge}));
    setQualifying("timing");
    addMessages(
      {role:"visitor",body:challenge},
      {role:"guide",body:"When would you want to review a potential solution? This is not a promise of delivery."},
    );
  }

  function chooseTiming(value: NonNullable<Qualification["timing"]>) {
    setQualification(previous=>({...previous,timing:value}));
    setQualifying("done");
    addMessages(
      {role:"visitor",body:value},
      {role:"guide",body:"Your optional business-fit brief is ready below. Nothing has been sent. You can copy it yourself, then use the existing founder-reviewed enquiry form and give separate consent if you want email follow-up or a nonbinding proposal. No calls are initiated automatically."},
    );
  }

  const brief = qualificationBrief(qualification,inputs,currency);
  function continueWithBrief() {
    const draft = makeRoiEnquiryDraft(qualification);
    if (!draft) {
      setCopyStatus("Complete the three optional answers to continue.");
      return;
    }
    try {
      saveRoiEnquiryDraft(window.sessionStorage, draft);
      window.location.assign("/commercial#commercial-enquiry");
    } catch {
      setCopyStatus("Secure browser handoff is unavailable. Copy your brief and paste it into the separate enquiry form instead.");
    }
  }
  async function copyBrief() {
    try {
      await navigator.clipboard.writeText(brief);
      setCopyStatus("Copied locally. Nothing has been submitted.");
    } catch {
      setCopyStatus("Automatic copy unavailable; select the text in the box and copy it manually.");
    }
  }

  return <section aria-labelledby="roi-conversation-title"
    className="mt-10 rounded-3xl border border-cyan-300/30 bg-[#071b34] p-5 text-slate-100 sm:p-8">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="text-xs font-bold uppercase tracking-[.15em] text-cyan-200">Text-only guided pilot · No AI inference charges</p>
        <h3 id="roi-conversation-title" className="mt-3 text-2xl font-semibold">Talk through your opportunity</h3>
      </div>
      <span className="rounded-full border border-cyan-200/35 px-3 py-1 text-xs text-cyan-100">Scripted assistant, not a human</span>
    </div>
    <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
      Ask about your current calculator result or complete three optional business-fit questions.
      Everything stays on this page until you deliberately choose the separate enquiry form.
      Please do not enter names, phone numbers or other personal information here.
    </p>
    <div aria-label="Guided conversation" aria-live="polite"
      className="mt-6 max-h-[420px] space-y-3 overflow-y-auto rounded-2xl border border-white/10 bg-[#041126] p-4 sm:p-5">
      {messages.map((message,index)=><div key={index}
        className={"max-w-[94%] rounded-xl border p-4 text-sm leading-6 sm:max-w-[87%] " +
          (message.role==="guide"
          ?"border-cyan-200/20 bg-[#0c2744] text-slate-100"
          :"ml-auto border-amber-200/20 bg-[#283047] text-amber-100")}>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          {message.role==="guide"?"Empire AI guided assistant":"You"}
        </p>
        <p className="whitespace-pre-wrap">{message.body}</p>
      </div>)}
    </div>
    <div role="group" aria-label="Ask a question without sending data" className="mt-5 flex flex-col gap-3 sm:flex-row">
      <label htmlFor="roi-conversation-question" className="sr-only">Ask a question about your assessment</label>
      <input id="roi-conversation-question" value={typed} onChange={e=>setTyped(e.target.value)}
        onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();sendQuestion();}}}
        maxLength={220} autoComplete="off"
        placeholder="What makes my estimated return change?"
        className="min-h-12 min-w-0 flex-1 rounded-xl border border-slate-500 bg-[#020c20] px-4 py-3 text-base text-white placeholder:text-slate-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-200" />
      <button type="button" onClick={sendQuestion} disabled={!typed.trim()}
        className="min-h-12 rounded-xl bg-cyan-200 px-6 py-3 text-sm font-bold text-[#02142c] hover:bg-white disabled:opacity-40">
        Ask
      </button>
    </div>

    <div className="mt-6 border-t border-white/10 pt-5">
      <p className="text-sm font-semibold text-white">Optional: prepare for a founder conversation</p>
      {qualifying==="idle" && <button type="button" onClick={beginQualification}
        className="mt-3 min-h-12 rounded-xl border border-amber-200/60 px-5 py-3 text-sm font-semibold text-amber-100 hover:bg-amber-200/10">
        Answer three business-fit questions
      </button>}
      {qualifying==="sector" && <div role="group" aria-label="Select your business sector" className="mt-3 flex flex-wrap gap-2">
        {sectors.map(sector=><button key={sector} type="button" onClick={()=>chooseSector(sector)}
          className="min-h-11 rounded-lg border border-cyan-200/35 px-4 py-2 text-sm hover:bg-cyan-200/10">{sector}</button>)}
      </div>}
      {qualifying==="challenge" && <div role="group" aria-label="Select your main challenge" className="mt-3 flex flex-wrap gap-2">
        {challenges.map(challenge=><button key={challenge} type="button" onClick={()=>chooseChallenge(challenge)}
          className="min-h-11 rounded-lg border border-cyan-200/35 px-4 py-2 text-sm hover:bg-cyan-200/10">{challenge}</button>)}
      </div>}
      {qualifying==="timing" && <div role="group" aria-label="Select your planning horizon" className="mt-3 flex flex-wrap gap-2">
        {timing.map(value=><button key={value} type="button" onClick={()=>chooseTiming(value)}
          className="min-h-11 rounded-lg border border-cyan-200/35 px-4 py-2 text-sm hover:bg-cyan-200/10">{value}</button>)}
      </div>}
      {qualifying==="done" && <div className="mt-4">
        <label htmlFor="roi-enquiry-brief" className="block text-sm font-semibold text-amber-100">Your editable enquiry brief (not sent)</label>
        <textarea id="roi-enquiry-brief" readOnly rows={11} value={brief}
          className="mt-2 w-full resize-y rounded-xl border border-slate-500 bg-[#020c20] p-4 font-mono text-xs leading-6 text-slate-100"/>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" onClick={continueWithBrief}
            className="min-h-12 rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-[#07172e] hover:bg-white">
            Continue to enquiry with my brief →
          </button>
          <button type="button" onClick={copyBrief}
            className="min-h-11 rounded-xl border border-cyan-200/50 px-5 py-3 text-sm font-semibold text-white hover:bg-cyan-200/10">
            Copy optional brief
          </button>
        </div>
        <p className="mt-3 text-xs leading-6 text-slate-300">Choosing “Continue” temporarily carries only your three selected business-fit answers to the next page in this browser tab. It does not carry your calculator figures or chat, and nothing is sent until you review the form and separately consent.</p>
        {copyStatus && <p role="status" className="mt-2 text-xs text-cyan-100">{copyStatus}</p>}
      </div>}
      {qualifying!=="idle" && <button type="button" onClick={()=>{
        setQualifying("idle");setQualification({...EMPTY_QUALIFICATION});setCopyStatus("");
        try { window.sessionStorage.removeItem(ROI_ENQUIRY_DRAFT_KEY); } catch { /* storage unavailable */ }
        setTyped("");
        setMessages([{role:"guide",body:"Conversation and business-fit answers cleared from this page. You can start again whenever you wish."}]);
      }}
        className="ml-3 mt-3 min-h-11 text-sm text-slate-300 underline underline-offset-4 hover:text-white">Clear conversation and business-fit answers</button>}
    </div>
    <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-white/10 pt-5">
      <a href="/commercial"
        className="inline-flex min-h-12 items-center rounded-full bg-amber-300 px-6 py-3 text-sm font-bold text-[#07172e] hover:bg-white">
        Open consented business enquiry →
      </a>
      <a href="/predictive-revenue" className="text-sm text-cyan-200 underline underline-offset-4">Product details</a>
      <a href="/trust" className="text-sm text-cyan-200 underline underline-offset-4">Evidence and trust</a>
    </div>
    <p className="mt-4 text-xs leading-6 text-slate-400">
      Email follow-up requires a separate, deliberate form submission and consent. For a human callback,
      explicitly request one in the enquiry form; a phone number alone never triggers a call.
      No terms or payments are agreed by this assistant. Its text remains local and is not sent to the CRM.
    </p>
  </section>;
}

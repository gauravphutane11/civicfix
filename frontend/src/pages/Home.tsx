import { Link } from "react-router-dom";
import PageFrame from "../components/common/PageFrame";
import { useAuth } from "../auth";

function Feature({n,title,copy}:{n:string;title:string;copy:string}){
 return <div className="card p-5 md:p-6">
   <div className="flex items-center justify-between"><span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-700 grid place-items-center text-xs font-bold">{n}</span><span className="text-[11px] text-slate-400 uppercase tracking-widest">CivicFix</span></div>
   <h3 className="font-display text-xl font-bold mt-6">{title}</h3>
   <p className="text-sm text-slate-500 leading-6 mt-2">{copy}</p>
 </div>
}

export default function Home(){
 const {user}=useAuth();
 const citizen=user?.role==="citizen";
 const admin=user?.role==="admin";
 return <PageFrame>
   <section className="civic-shell pt-12 md:pt-20 pb-14">
     <div className="grid lg:grid-cols-[1.08fr_.92fr] gap-8 items-stretch">
       <div className="card p-7 md:p-11 overflow-hidden relative grid-fade">
         <div className="absolute -right-16 -top-16 w-64 h-64 rounded-full bg-indigo-100/60 blur-3xl" />
         <div className="relative">
           <div className="tag bg-emerald-50 text-emerald-700"><span className="w-2 h-2 bg-emerald-500 rounded-full"/> Service desk open</div>
           <h1 className="font-display text-[clamp(3rem,7vw,6.8rem)] leading-[.92] tracking-[-.06em] font-extrabold mt-7 max-w-4xl">Make a local problem <span className="text-indigo-600">visible.</span></h1>
           <p className="text-lg md:text-xl text-slate-500 max-w-2xl leading-8 mt-7">Report a civic problem once. CivicFix turns your description and photo into a traceable case, looks for related reports and keeps the accountability trail clear.</p>
           <div className="flex flex-wrap gap-3 mt-8">
             {citizen ? <><Link to="/report" className="btn-primary">Report an issue <span>→</span></Link><Link to="/complaints" className="btn-secondary">My complaints</Link></> : admin ? <Link to="/admin" className="btn-primary">Open operations console →</Link> : <><Link to="/login" className="btn-primary">Sign in to report</Link><Link to="/register" className="btn-secondary">Create account</Link></>}
           </div>
           <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-sm text-slate-500">
             <span>✓ Photo-backed reports</span><span>✓ Explainable AI triage</span><span>✓ Duplicate-aware cases</span><span>✓ SLA visibility</span>
           </div>
         </div>
       </div>
       <div className="grid sm:grid-cols-2 lg:grid-cols-1 gap-4">
         <Feature n="01" title="One report → one accountable case" copy="CivicFix consolidates related reports around the same issue so staff can work the problem instead of chasing duplicates."/>
         <Feature n="02" title="Priority with a reason" copy="Every priority result is backed by visible factors such as severity, recurrence, location importance, age and public impact."/>
         <Feature n="03" title="Your evidence stays attached" copy="Your photo, category, location and case history remain linked to the account that submitted the report."/>
       </div>
     </div>
   </section>
   <section className="civic-shell pb-20">
     <div className="grid md:grid-cols-3 gap-4">
       <div className="card p-6"><div className="text-xs uppercase tracking-widest text-slate-400">01 / Report</div><div className="font-display text-2xl font-bold mt-3">Describe + photograph</div><p className="text-sm text-slate-500 leading-6 mt-2">Share what happened, attach a clear image and optionally use your current location.</p></div>
       <div className="card p-6"><div className="text-xs uppercase tracking-widest text-slate-400">02 / AI triage</div><div className="font-display text-2xl font-bold mt-3">Structure the signal</div><p className="text-sm text-slate-500 leading-6 mt-2">Classification, location matching, duplicate intelligence and explainable priority are generated automatically.</p></div>
       <div className="card p-6"><div className="text-xs uppercase tracking-widest text-slate-400">03 / Accountability</div><div className="font-display text-2xl font-bold mt-3">Follow the case</div><p className="text-sm text-slate-500 leading-6 mt-2">Track the service clock, status changes and the civic case your report contributes to.</p></div>
     </div>
   </section>
 </PageFrame>
}

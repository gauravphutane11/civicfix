import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth";

function Icon({name}:{name:"report"|"list"|"ops"|"arrow"|"user"|"logout"}){
 const paths={
  report:<><path d="M12 5v14M5 12h14"/><rect x="4" y="4" width="16" height="16" rx="4"/></>,
  list:<><path d="M6 7h12M6 12h12M6 17h8"/></>,
  ops:<><rect x="4" y="5" width="16" height="14" rx="3"/><path d="M8 9h8M8 13h3M15 13h1M8 17h8"/></>,
  arrow:<path d="M5 12h14M13 6l6 6-6 6"/>,
  user:<><circle cx="12" cy="8" r="3"/><path d="M5 20c.8-3.2 3.1-5 7-5s6.2 1.8 7 5"/></>,
  logout:<><path d="M10 6H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4"/><path d="M13 8l4 4-4 4M17 12H8"/></>
 };
 return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">{paths[name]}</svg>;
}

export default function PageFrame({children}:{children:ReactNode}){
 const { user, logout } = useAuth();
 const nav = useNavigate();
 const location = useLocation();
 const citizen = user?.role === "citizen";
 const admin = user?.role === "admin";
 const is = (path:string)=>location.pathname===path || location.pathname.startsWith(path+"/");
 return <div className="civic-app min-h-screen">
   <header className="civic-header">
     <div className="civic-shell h-[74px] flex items-center justify-between gap-6">
       <Link to="/" className="flex items-center gap-3 shrink-0">
         <div className="brand-mark">CF</div>
         <div>
           <div className="font-display font-extrabold tracking-tight text-[18px]">CivicFix</div>
           <div className="text-[11px] text-slate-500">Citizen service, made visible.</div>
         </div>
       </Link>
       <nav className="hidden md:flex items-center gap-1">
         {citizen && <>
           <Link to="/report" className={`nav-pill ${is("/report")?"active":""}`}><Icon name="report"/> Report issue</Link>
           <Link to="/complaints" className={`nav-pill ${is("/complaints")||is("/track")?"active":""}`}><Icon name="list"/> My complaints</Link>
         </>}
         {admin && <Link to="/admin" className={`nav-pill ${is("/admin")?"active":""}`}><Icon name="ops"/> Operations console</Link>}
       </nav>
       <div className="flex items-center gap-2">
         {user ? <>
           <div className="hidden sm:flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-50 border border-slate-100 max-w-[200px]">
             <span className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 grid place-items-center text-xs font-bold">{user.name.slice(0,1).toUpperCase()}</span>
             <div className="min-w-0"><div className="text-sm font-semibold truncate">{user.name}</div><div className="text-[10px] uppercase tracking-wider text-slate-400">{admin?"Administrator":"Citizen"}</div></div>
           </div>
           <button type="button" className="btn-secondary !px-3 !py-2" onClick={()=>{logout();nav("/",{replace:true});}} title="Sign out"><Icon name="logout"/><span className="hidden sm:inline">Sign out</span></button>
         </> : <>
           <Link to="/login" className="btn-secondary !px-4 !py-2.5">Sign in</Link>
           <Link to="/register" className="btn-primary !px-4 !py-2.5">Create account <Icon name="arrow"/></Link>
         </>}
       </div>
     </div>
   </header>
   <main>{children}</main>
 </div>
}

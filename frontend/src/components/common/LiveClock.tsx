import { useEffect, useState } from "react";
export default function LiveClock(){ const [now,setNow]=useState(new Date()); useEffect(()=>{const id=setInterval(()=>setNow(new Date()),1000);return()=>clearInterval(id)},[]); return <span className="font-mono text-xs tabular-nums">{now.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"})}</span> }

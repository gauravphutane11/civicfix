import { PRIORITY_COLORS, type PriorityBand } from "../../types";
export default function PriorityBadge({band,score,size="md"}:{band:PriorityBand;score:number;size?:"sm"|"md"|"lg"}){
 const color=PRIORITY_COLORS[band]; const dims=size==="lg"?"w-16 h-16 text-xl":size==="sm"?"w-8 h-8 text-[0.65rem]":"w-11 h-11 text-sm";
 return <div className="flex items-center gap-2.5"><div className={`${dims} rounded-full flex items-center justify-center font-mono font-semibold shrink-0`} style={{border:`2px solid ${color}`,color,background:`${color}14`}} title={`Priority score ${score}/100`}>{score}</div><span className="font-mono uppercase tracking-wide text-[0.68rem] font-semibold" style={{color}}>{band}</span></div>;
}

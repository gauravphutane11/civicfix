import { STATUS_LABELS } from "../../types";
const STAMP_COLORS:Record<string,string> = { open:"#3E6E8E", submitted:"#3E6E8E", triaged:"#3E6E8E", assigned:"#C99A2E", in_progress:"#D6541A", resolved:"#3F7D6B", rejected:"#8A8478", merged:"#8A8478" };
export default function StatusStamp({status,size="md"}:{status:string;size?:"sm"|"md"}){
 const color=STAMP_COLORS[status]??"#8A8478"; const label=STATUS_LABELS[status]??status;
 return <span className={`ink-stamp uppercase font-semibold ${size==="sm"?"text-[0.62rem] px-2 py-0.5":""}`} style={{color}}>{label}</span>;
}

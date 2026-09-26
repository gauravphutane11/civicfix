import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import type { AuthUser, CitizenOtpRequestResponse } from "./types";

type RegisterPayload={name:string;email:string;phone?:string;password:string};
type Value={
  user:AuthUser|null;
  loading:boolean;
  login:(email:string,password:string)=>Promise<AuthUser>;
  register:(payload:RegisterPayload)=>Promise<AuthUser>;
  requestCitizenOtp:(payload:{phone:string;name?:string;email?:string;language?:string})=>Promise<CitizenOtpRequestResponse>;
  verifyCitizenOtp:(phone:string,otp:string)=>Promise<AuthUser>;
  logout:()=>void;
};
const Context=createContext<Value|null>(null);
function save(user:AuthUser,token:string){localStorage.setItem("civicfix_token",token);localStorage.setItem("civicfix_user",JSON.stringify(user));}

export function AuthProvider({children}:{children:ReactNode}){
  const [user,setUser]=useState<AuthUser|null>(null);
  const [loading,setLoading]=useState(true);
  useEffect(()=>{
    const token=localStorage.getItem("civicfix_token");
    if(!token){setLoading(false);return;}
    api.getMe().then(setUser).catch(()=>{localStorage.removeItem("civicfix_token");localStorage.removeItem("civicfix_user");setUser(null);}).finally(()=>setLoading(false));
  },[]);
  const value=useMemo<Value>(()=>({
    user,loading,
    async login(email,password){const result=await api.login(email,password);save(result.user,result.access_token);setUser(result.user);return result.user;},
    async register(payload){const result=await api.register(payload);save(result.user,result.access_token);setUser(result.user);return result.user;},
    requestCitizenOtp(payload){return api.requestCitizenOtp(payload);},
    async verifyCitizenOtp(phone,otp){const result=await api.verifyCitizenOtp(phone,otp);save(result.user,result.access_token);setUser(result.user);return result.user;},
    logout(){localStorage.removeItem("civicfix_token");localStorage.removeItem("civicfix_user");setUser(null);},
  }),[user,loading]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useAuth(){const value=useContext(Context);if(!value)throw new Error("useAuth must be used inside AuthProvider");return value;}

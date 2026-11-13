"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import type {AdaptationEvent} from "@/lib/contracts";
type Capture={datasetId:string;lastClosedAt:string;status:string;gapCount:number;fetchedAt:string};
type Watch={id:string;enabled:boolean;status:string;datasetId?:string;message?:string};
type Review={id:string;state:string;message:string;evaluation?:{score:number|null;critique:string|null}};
async function request(path:string,method="GET"){
 const response=await fetch(path,{method,cache:"no-store"});
 const body=await response.json();
 if(!response.ok)throw Error(body.detail||`Request failed (${response.status})`);
 return body;
}
export default function ResearchControls({runId,datasetId,synthetic,events}:{runId:string;datasetId:string;synthetic:boolean;events:AdaptationEvent[]}){
 const [capture,setCapture]=useState<Capture|null>(null),[reviews,setReviews]=useState<Review[]>([]);
 const [watch,setWatch]=useState<Watch|null>(null);
 useEffect(()=>{let active=true;const refresh=()=>request("/api/market/watches").then((data:Watch[])=>{if(active)setWatch(data.find(w=>w.id===datasetId)||null);}).catch(()=>{});void refresh();const timer=setInterval(refresh,15000);return()=>{active=false;clearInterval(timer);};},[datasetId]);
 async function toggleWatch(){setBusy(true);setError("");try{const response=await fetch(`/api/market/${encodeURIComponent(datasetId)}/watch`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:!watch?.enabled})});const data=await response.json();if(!response.ok)throw Error(data.detail);setWatch(data);}catch(e){setError(e instanceof Error?e.message:"Recording could not start");}finally{setBusy(false);}}
 const [busy,setBusy]=useState(false),[error,setError]=useState("");
 useEffect(()=>{let active=true;const refresh=()=>request(`/api/replays/${runId}/reviews`).then(data=>{if(active)setReviews(data);}).catch(()=>{});setReviews([]);void refresh();const timer=setInterval(refresh,10000);return()=>{active=false;clearInterval(timer);};},[runId]);
 useEffect(()=>{setCapture(null);setError("");},[datasetId]);
 async function record(){setBusy(true);setError("");try{setCapture(await request(`/api/market/${encodeURIComponent(datasetId)}/capture`,"POST"));}catch(e){setError(e instanceof Error?e.message:"Capture failed");}finally{setBusy(false);}}
 async function review(){const event=events.at(-1);if(!event)return;setBusy(true);setError("");try{await request(`/api/adaptations/${encodeURIComponent(event.id)}/review`,"POST");setReviews(await request(`/api/replays/${runId}/reviews`));}catch(e){setError(e instanceof Error?e.message:"Review failed");}finally{setBusy(false);}}
 return <section className="panel research-controls" aria-label="Market recording and external review"><div className="panel-heading"><div><h2>Research tools</h2><span className="muted">Record the market. Review a change.</span></div></div><div className="research-actions"><button className="btn" disabled={busy||synthetic} onClick={record}>{busy?"Working…":"Record latest market"}</button><button className="btn" disabled={busy||synthetic} onClick={toggleWatch}>{watch?.enabled?"Stop recording":"Keep recording"}</button><button className="btn" disabled={busy||events.length===0} onClick={review}>Request reviewed change</button></div><p className="muted">Market captures use completed hourly candles in USD. Reviews run in the background and cannot override local risk checks.</p>{error&&<p role="alert">{error}</p>}{capture&&<p role="status">{capture.status} · Last close {capture.lastClosedAt} · {capture.gapCount} gaps · <Link href={`/terminal?scenario=${encodeURIComponent(capture.datasetId)}`}>Replay this capture →</Link></p>}{watch&&<p role="status">{watch.enabled?"Recording every minute":"Recording stopped"} · {watch.status} {watch.datasetId&&<Link href={`/terminal?scenario=${encodeURIComponent(watch.datasetId)}`}>Open latest capture →</Link>} {watch.message}</p>}{reviews.map(review=><details key={review.id}><summary>{review.state.replaceAll("_"," ")}</summary><p>{review.message}</p>{review.evaluation&&<p>Reasoning review score: {review.evaluation.score??"Awaiting settlement"}. {review.evaluation.critique}</p>}</details>)}</section>;
}

"use client";
import {useEffect,useState} from "react";
type Report={matchedBaseline:{finalEquityUsd:number;netReturnPct:number};interventions:{eventId:string;observedBars:number;differenceUsd:number;outcome:string}[]};
export default function InterventionReport({runId,cursor}:{runId:string;cursor:number}){
 const [data,setData]=useState<Report|null>(null);const [error,setError]=useState(false);
 useEffect(()=>{const controller=new AbortController();setData(null);setError(false);fetch(`/api/replays/${runId}/report`,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(setData).catch(e=>{if(e.name!=="AbortError")setError(true);});return()=>controller.abort();},[runId,cursor]);
 return <details><summary>Did the changes help?</summary>{error?<p>Comparison unavailable. Try advancing the replay again.</p>:!data?<p>Computing matched comparisons…</p>:<><p>Frozen starting weights (60/40): ${data.matchedBaseline.finalEquityUsd.toFixed(2)} · {data.matchedBaseline.netReturnPct.toFixed(2)}% simulated return.</p>{data.interventions.length===0?<p>No accepted changes yet.</p>:data.interventions.map(e=><p key={e.eventId}>{e.eventId} · {e.observedBars} subsequent candles · {e.outcome.replaceAll('_',' ')} · ${e.differenceUsd.toFixed(2)} difference.</p>)}<small>Each comparison freezes the old and new weights from the same portfolio state. Later changes are excluded. These are observed differences, not proof of future benefit.</small></>}</details>;
}

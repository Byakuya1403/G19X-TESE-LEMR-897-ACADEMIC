import React, {useState} from 'react';

const controls = [
 {key:'operating', label:'Ajuste de otros egresos', min:-50, max:50, help:'Modifica los gastos distintos de nómina: compras, servicios, mantenimiento y demás partidas.', example:'−10% reduce esos gastos; +10% los aumenta.'},
 {key:'inflation', label:'Cambio de precios (inflación)', min:-10, max:30, help:'Aplica un cambio de precios a los otros egresos, después del ajuste anterior. No modifica la nómina.', example:'+5% encarece esos gastos un 5% adicional.'},
 {key:'payroll', label:'Ajuste de nómina', min:-30, max:30, help:'Modifica únicamente los egresos cuya subcategoría es «Nómina».', example:'+10% aumenta el gasto total en nómina un 10%.'},
];

export function simulationBase(entries, period, currency, category) {
 const selected=entries.filter(r=>r.period===period&&r.currency===currency&&r.nature==='expense'&&(!category||r.category===category));
 const pending=selected.filter(r=>r.actual===null).length;
 const payroll=selected.filter(r=>r.subcategory.toLowerCase()==='nómina').reduce((sum,r)=>sum+(r.actual??0),0);
 const operating=selected.filter(r=>r.subcategory.toLowerCase()!=='nómina').reduce((sum,r)=>sum+(r.actual??0),0);
 return {count:selected.length,pending,payroll,operating,total:payroll+operating};
}

export default function Simulation({entries,period,currency,category,money,monthLabel,request,loading}) {
 const [values,setValues]=useState({operating:'0',inflation:'0',payroll:'0'});
 const [result,setResult]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const base=simulationBase(entries,period,currency,category);
 const unavailable=loading?'Cargando la base de cálculo…':!base.count?'No hay egresos para esta selección. Elige un mes y una categoría con gastos.':base.pending?`Hay ${base.pending} partidas de egresos pendientes. Elige un mes con resultados completos para simular.`:'';
 const valid=controls.every(c=>values[c.key].trim()!==''&&Number.isFinite(Number(values[c.key]))&&Number(values[c.key])>=c.min&&Number(values[c.key])<=c.max);
 const rates=Object.fromEntries(Object.entries(values).map(([k,v])=>[k,Number(v)]));
 const combined=valid?((1+rates.operating/100)*(1+rates.inflation/100)-1)*100:null;
 function change(key,value){setValues(v=>({...v,[key]:value}));setResult(null);setError('');}
 function reset(){setValues({operating:'0',inflation:'0',payroll:'0'});setResult(null);setError('');}
 async function calculate(e){e.preventDefault();if(unavailable||!valid||busy)return;setBusy(true);setError('');setResult(null);try{setResult(await request('/financial/simulations',{method:'POST',body:JSON.stringify({period,currency,department:category||null,...rates})}));}catch(e){setError(e.message);}finally{setBusy(false);}}
 const percent=v=>`${v>0?'+':''}${v.toLocaleString('es-MX',{maximumFractionDigits:2})}%`;
 return <div className="simulation">
  <article className="panel simulation-base"><p className="eyebrow">1 · REVISA LA BASE</p><h2>¿Qué gasto vas a modificar?</h2><p className="muted">{monthLabel(period)} · {currency} · {category||'Todas las categorías de egresos'}. Se usan gastos reales del CSV, no el presupuesto estimado. Los ingresos quedan fuera.</p>
   {unavailable?<p className="notice" role="status">{unavailable}</p>:<div className="simulation-totals"><div><span>Nómina</span><strong>{money(base.payroll)}</strong></div><div><span>Otros egresos</span><strong>{money(base.operating)}</strong></div><div><span>Gasto real total</span><strong>{money(base.total)}</strong></div></div>}
  </article>
  <div className="topgrid"><article className="panel"><p className="eyebrow">2 · DEFINE LOS CAMBIOS</p><h2>¿Qué pasaría si cambian tus gastos?</h2><p className="muted">Escribe un porcentaje. 0 mantiene el gasto; un valor negativo lo reduce y uno positivo lo aumenta.</p>
   <form onSubmit={calculate}><fieldset disabled={busy||Boolean(unavailable)} className="scenario-fields">
    {controls.map(c=>{const noBase=(c.key==='payroll'?base.payroll:base.operating)===0;return <div className="scenario-control" key={c.key}><label htmlFor={`scenario-${c.key}`}>{c.label}</label><p id={`help-${c.key}`}>{c.help}</p><div className="percent-input"><input id={`scenario-${c.key}`} type="number" min={c.min} max={c.max} step="any" required value={values[c.key]} disabled={noBase} aria-describedby={`help-${c.key} range-${c.key}`} onChange={e=>change(c.key,e.target.value)}/><span>%</span></div><small id={`range-${c.key}`}>{noBase?'No hay gasto base en este grupo; el ajuste no tendrá efecto.':`${c.example} Rango: ${c.min}% a +${c.max}%.`}</small></div>;})}
    {valid&&!unavailable&&<p className="note">Con ambos ajustes, los otros egresos cambiarían <b>{percent(combined)}</b>. Se aplican uno después del otro: +10% operativo y +5% de precios producen +15.5%.</p>}
    <div className="scenario-actions"><button disabled={!valid||Boolean(unavailable)} type="submit">{busy?'Calculando…':'Comparar con el gasto real'}</button><button type="button" className="secondary" onClick={reset}>Restablecer a 0%</button></div>
   </fieldset></form>{error&&<p className="error" role="alert">{error}</p>}
  </article>
  <article className="panel scenario-result"><p className="eyebrow">3 · COMPARA EL RESULTADO</p><h2>Gasto real frente al escenario</h2>{result?<div role="status"><p className="muted">{monthLabel(period)} · {category||'Todas las categorías de egresos'} · {currency}</p><dl><div><dt>Gasto real del mes</dt><dd>{money(result.baseline)}</dd></div><div className="projected-total"><dt>Gasto con tus ajustes</dt><dd>{money(result.projected)}</dd></div><div><dt>{result.difference>0?'Aumento del gasto':result.difference<0?'Reducción del gasto':'Sin cambio en el gasto'}</dt><dd>{money(Math.abs(result.difference))}</dd></div></dl><p>{result.baseline===0?'La base es cero; los ajustes porcentuales no generan gasto nuevo.':`El escenario ${result.difference>0?'aumenta':result.difference<0?'reduce':'mantiene'} el gasto${result.difference===0?'.':` en ${Math.abs(result.difference/result.baseline*100).toLocaleString('es-MX',{maximumFractionDigits:2})}%.`}`}</p><p className="muted">Ajustes aplicados: otros egresos {percent(rates.operating)}, precios {percent(rates.inflation)} y nómina {percent(rates.payroll)}.</p></div>:<div className="scenario-empty"><h3>{unavailable?'Hace falta una base completa':'Tu comparación aparecerá aquí'}</h3><p>{unavailable||'Define los cambios y pulsa «Comparar con el gasto real». También puedes calcular con 0% para comprobar la base.'}</p></div>}<p className="note">Este escenario responde a tus supuestos para el mes elegido. No es la predicción del siguiente mes. Calcular no modifica el CSV ni guarda cambios en tus presupuestos.</p></article>
  </div>
 </div>;
}

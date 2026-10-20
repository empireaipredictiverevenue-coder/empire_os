export default function InfrastructureStill({selected}:{selected:number}){
 return <div className="city-still infrastructure-poster" aria-hidden="true">
 <img src="/art/empire-atrium.webp" width="1672" height="941" alt="" loading="lazy"/>
 <span className="poster-stage" style={{left:(10+selected*20)+"%"}}/>
 </div>;
}

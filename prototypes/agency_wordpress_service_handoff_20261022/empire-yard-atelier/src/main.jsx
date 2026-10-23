import React, { Component, Suspense, useEffect, useId, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { motion, useReducedMotion } from 'motion/react'
import { ArrowUpRight, ArrowRight, ShieldCheck, ScanLine, CalendarDays, CarFront, Sparkles, Compass } from 'lucide-react'
const ShowroomScene = React.lazy(() => import('./ShowroomScene.jsx'))
import './tailwind.css'

// Local Magic UI-inspired animated-grid pattern (not externally loaded).
function AnimatedGrid({ reduce }) {
  const patternId = useId().replace(/:/g, '')
  return (
    <svg aria-hidden="true" className="pointer-events-none absolute inset-0 h-full w-full opacity-50" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice">
      <defs><pattern id={patternId} width="70" height="70" patternUnits="userSpaceOnUse">
        <path d="M70 0H0V70" stroke="#80b5be" strokeOpacity=".17" fill="none" strokeWidth=".7" />
      </pattern></defs>
      <rect width="800" height="600" fill={'url(#'+patternId+')'} />
      {Array.from({ length: 10 }, (_, i) => (
        <motion.rect key={i} x={(i * 127 + 70) % 750} y={(i * 79 + 80) % 550} width="70" height="70" fill="#b4dce4"
          initial={{ opacity: .025 }} animate={reduce ? { opacity: .04 } : { opacity: [.02, .14, .02] }}
          transition={{ duration: 4.2, delay: i * .42, repeat: reduce ? 0 : Infinity, ease: 'easeInOut' }}
        />
      ))}
    </svg>
  )
}
class WebGLErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { failed: false } }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <SceneFallback /> : this.props.children }
}
function SceneFallback({ launch3D }) {
  return <div data-3d-fallback="true" className="flex h-full w-full flex-col items-center justify-center gap-5 bg-[radial-gradient(ellipse_at_center,#294b56_0%,#102631_62%,#061823_100%)] px-5">
    <CarFront className="h-24 w-24 text-[#d2b77d]/90 sm:h-32 sm:w-32" strokeWidth={.65} aria-hidden="true" />
    <span className="text-center text-[10px] font-semibold uppercase tracking-[.29em] text-slate-300">Interactive showroom concept</span>
    {launch3D && <button type="button" data-launch-3d="true"
      onClick={launch3D} aria-label="Load interactive 3D vehicle showroom"
      className="relative z-20 min-h-12 rounded-md border border-[#dfbd82] bg-[#dfbd82] px-6 py-3 text-[11px] font-extrabold uppercase tracking-[.13em] text-[#10232b] transition-colors hover:bg-[#f2d8a9] focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-white">
      Explore in 3D
    </button>}
  </div>
}
const showroomViews = [
  { id: 'three-quarter', name: 'Three-quarter' },
  { id: 'side', name: 'Side profile' },
  { id: 'front', name: 'Front detail' },
]
const showroomFinishes = [
  { id: 'ocean', name: 'Ocean teal', body: '#1a3d46', roof: '#203c48', swatch: 'bg-[#1a3d46]' },
  { id: 'champagne', name: 'Champagne gold', body: '#9b8057', roof: '#b19b76', swatch: 'bg-[#9b8057]' },
  { id: 'silver', name: 'Arctic silver', body: '#7f9aa9', roof: '#9fb1ba', swatch: 'bg-[#7f9aa9]' },
]

function Hero3D({ reduce }) {
  const holder = useRef(null)
  const [inView, setInView] = useState(false)
  const [pageVisible, setPageVisible] = useState(true)
  const [supported, setSupported] = useState(false)
  const [mobileTouch, setMobileTouch] = useState(false)
  const [mobile3DRequested, setMobile3DRequested] = useState(false)
  const [view, setView] = useState('three-quarter')
  const [finish, setFinish] = useState('ocean')
  const selectedFinish = showroomFinishes.find(item => item.id === finish) || showroomFinishes[0]
  useEffect(() => {
    // Mobile launches WebGL on explicit request: avoid a multi-MB scene
    // download, GPU startup and battery use for visitors who only need stock.
    const media = window.matchMedia('(max-width: 640px) and (pointer: coarse)')
    const refresh = () => setMobileTouch(media.matches)
    refresh()
    media.addEventListener?.('change', refresh)
    return () => media.removeEventListener?.('change', refresh)
  }, [])
  useEffect(() => {
    const node = holder.current
    if (!node) return undefined
    const visibility = () => setPageVisible(document.visibilityState === 'visible')
    visibility()
    document.addEventListener('visibilitychange', visibility)
    if (!('IntersectionObserver' in window)) setInView(true)
    else {
      const observer = new IntersectionObserver(([entry]) => {
        setInView(entry.isIntersecting)
      }, { rootMargin: '100px 0px', threshold: 0.01 })
      observer.observe(node)
      return () => {
        observer.disconnect()
        document.removeEventListener('visibilitychange', visibility)
      }
    }
    return () => document.removeEventListener('visibilitychange', visibility)
  }, [])
  useEffect(() => {
    if (!inView || !pageVisible || reduce || (mobileTouch && !mobile3DRequested)) return
    try {
      const canvas = document.createElement('canvas')
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
      setSupported(!!gl)
      if (gl) gl.getExtension('WEBGL_lose_context')?.loseContext()
    } catch { setSupported(false) }
  }, [inView, pageVisible, reduce, mobileTouch, mobile3DRequested])
  const mobilePreviewOnly = mobileTouch && !mobile3DRequested
  const interactive = supported && inView && pageVisible && !reduce && !mobilePreviewOnly
  return <div ref={holder} data-showroom-active={interactive ? 'true' : 'false'} className="w-full">
    <div className="relative isolate h-[300px] w-full overflow-hidden rounded-t-2xl border border-white/10 bg-[#102630] shadow-[0_28px_90px_rgba(0,0,0,.45)] sm:h-[400px] lg:h-[510px]">
      {interactive ? <WebGLErrorBoundary><Suspense fallback={<SceneFallback />}><ShowroomScene motionAllowed={interactive} view={view} paint={selectedFinish} /></Suspense></WebGLErrorBoundary> : <SceneFallback launch3D={mobilePreviewOnly && !reduce ? () => setMobile3DRequested(true) : undefined} />}
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-4 sm:p-7">
        <span className="rounded-full border border-white/25 bg-[#102630]/80 px-3 py-2 text-[9px] font-bold uppercase tracking-[.23em] text-[#e2cc9a] backdrop-blur-md">3D Concept Studio</span>
        <span className="rounded-full border border-white/15 bg-black/25 px-3 py-2 text-[9px] font-semibold tracking-[.12em] text-slate-300 backdrop-blur-md">{interactive ? 'LIVE / EXPLORE' : 'VISUAL / PREVIEW'}</span>
      </div>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-[#07141d] via-[#07141d]/75 to-transparent px-4 pb-4 pt-10 sm:px-7 sm:pb-6">
        <span className="flex items-center gap-2 text-[10px] font-semibold tracking-[.13em] text-slate-200"><ScanLine className="h-4 w-4 text-[#d6b579]" /> Procedural vehicle geometry</span>
        <span className="text-[9px] font-bold uppercase tracking-[.16em] text-[#b6c5ca]">No external model</span>
      </div>
    </div>
    <div className="grid gap-4 rounded-b-2xl border border-t-0 border-white/15 bg-[#0c202a] px-4 py-4 sm:grid-cols-[1fr_auto] sm:items-center sm:px-6">
      <div role="group" aria-label="Showroom camera view" className="flex flex-wrap items-center gap-2">
        {showroomViews.map(option => <button key={option.id} type="button" data-camera-view={option.id}
          aria-pressed={view === option.id} onClick={() => setView(option.id)}
          className={'min-h-10 rounded-md border px-3 py-2 text-[10px] font-semibold tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#dfbd82] ' +
            (view === option.id ? 'border-[#d6b579] bg-[#d6b579] text-[#0b1e28]' : 'border-white/20 bg-white/5 text-slate-200 hover:border-white/50')}>{option.name}</button>)}
      </div>
      <div role="group" aria-label="Fictional vehicle paint finish" className="flex items-center gap-2">
        {showroomFinishes.map(option => <button key={option.id} type="button" data-paint-finish={option.id}
          aria-label={option.name} aria-pressed={finish === option.id} title={option.name}
          onClick={() => setFinish(option.id)}
          className={'flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#dfbd82] ' +
            (finish === option.id ? 'border-[#e8c791]' : 'border-white/20 hover:border-white/60')}>
          <span className={'h-6 w-6 rounded-full border border-white/30 ' + option.swatch} aria-hidden="true" />
        </button>)}
      </div>
    </div>
    <p className="sr-only" role="status">Showroom view: {showroomViews.find(item => item.id === view)?.name}. Concept paint: {selectedFinish.name}.{reduce ? ' Motion reduced.' : ''}</p>
  </div>
}

const brandDefaults = Object.freeze({
  name: 'Atelier Motors',
  strapline: 'Showroom concept',
  eyebrow: 'The future of the showroom',
  headline: 'Drive something',
  highlight: 'extraordinary.',
  description: 'An immersive WordPress dealership concept with cinematic 3D, refined inventory discovery, and a governed service-workshop foundation.',
  contact_label: 'Enquiry info',
  contact_path: '/contact/',
  accent: 'gold'
})
// All palettes are static Tailwind utility names; no generated CSS or style tags.
const brandPalettes = {
  gold: {
    notice: 'bg-[#dfbd82]', logo: 'text-[#dbbc88]', highlight: 'text-[#dcbc85]',
    eyebrow: 'text-[#dcbc85]', primary: 'bg-[#dfbd82] text-[#11232b] hover:bg-[#f2d8a9]',
    border: 'border-[#dfbd82]/70', muted: 'text-[#e6c691]',
  },
  ice: {
    notice: 'bg-[#b6ddeb]', logo: 'text-[#b6ddeb]', highlight: 'text-[#b6ddeb]',
    eyebrow: 'text-[#b6ddeb]', primary: 'bg-[#b6ddeb] text-[#11232b] hover:bg-[#d1eefa]',
    border: 'border-[#b6ddeb]/70', muted: 'text-[#d1eefa]',
  },
  copper: {
    notice: 'bg-[#dca87c]', logo: 'text-[#dca87c]', highlight: 'text-[#dca87c]',
    eyebrow: 'text-[#dca87c]', primary: 'bg-[#dca87c] text-[#11232b] hover:bg-[#f1c7a4]',
    border: 'border-[#dca87c]/70', muted: 'text-[#f1c7a4]',
  },
}
function getBrandSettings() {
  try {
    const raw = document.getElementById('empire-yard-brand-settings')?.textContent
    const settings = raw ? JSON.parse(raw) : {}
    const brand = { ...brandDefaults }
    // The image base is supplied only by this WordPress child theme and must
    // remain on the current installation. Never trust external admin URLs.
    const assetBase = new URL(settings.editorial_assets_base || '/wp-content/themes/empire-yard-atelier/assets/editorial/', location.href)
    brand.editorialAssetsBase = (assetBase.origin === location.origin &&
      assetBase.pathname.endsWith('/assets/editorial/') &&
      !assetBase.search && !assetBase.hash) ? assetBase.href
      : '/wp-content/themes/empire-yard-atelier/assets/editorial/'
    brand.editorialMedia = {}
    for (const index of [1, 2, 3]) {
      const proposed = settings.editorial_media_urls?.[index]
      if (typeof proposed === 'string' && proposed.length < 550) {
        const url = new URL(proposed, location.href)
        if (url.origin === location.origin && url.pathname.includes('/wp-content/uploads/') &&
            !url.search && !url.hash && !url.pathname.includes('..')) {
          brand.editorialMedia[index] = url.href
        }
      }
    }

    for (const key of ['name', 'strapline', 'eyebrow', 'headline', 'highlight',
      'description', 'contact_label']) {
      if (typeof settings[key] === 'string' && settings[key].trim()) {
        brand[key] = settings[key].slice(0, 320)
      }
    }
    if (typeof settings.contact_path === 'string' &&
      /^\/(?:[a-z0-9-]+\/){1,4}$/.test(settings.contact_path)) {
      brand.contact_path = settings.contact_path
    }
    if (Object.prototype.hasOwnProperty.call(brandPalettes, settings.accent)) {
      brand.accent = settings.accent
    }
    return brand
  } catch {
    return { ...brandDefaults, editorialAssetsBase:
      '/wp-content/themes/empire-yard-atelier/assets/editorial/',
      editorialMedia: {} }
  }
}
function Button({ children, href, primary = false, palette = brandPalettes.gold }) {
  return <a href={href} className={(primary
    ? palette.primary
    : 'border border-white/30 bg-white/5 text-white hover:bg-white/10'
  ) + ' inline-flex min-h-12 items-center justify-center gap-3 rounded-md px-6 py-3 text-xs font-extrabold uppercase tracking-[.11em] no-underline transition-colors focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-[#eecb87]'}>
    {children}<ArrowUpRight aria-hidden="true" className="h-4 w-4" />
  </a>
}
const features = [
  { num: '01', icon: Compass, title: 'Discovery, refined.', copy: 'Fictional showroom inventory with clear filters and a responsive presentation. Real stock feeds need client authorisation.' },
  { num: '02', icon: ScanLine, title: 'Details worth exploring.', copy: 'Honest model specifications and image spaces without fabricated availability, reviews or pricing claims.' },
  { num: '03', icon: CalendarDays, title: 'A smarter workshop.', copy: 'The private workbench uses database-backed slot protection. Customer booking remains disabled.' }
]
const photographicReferences = [
  {
    num: '01', name: 'The art of the silhouette',
    detail: 'Sculpture, proportion and deliberate light',
    filename: 'studio-red.webp',
    alt: 'Real editorial photograph of a red performance coupe in a dark photography studio; not a vehicle offered by this demo',
    photographer: 'Moses Malik Roldan',
    source: 'https://unsplash.com/photos/a-red-sports-car-parked-in-a-dark-studio-bZRqT3tvryk',
    width: 1600, height: 1066,
  },
  {
    num: '02', name: 'Precision in profile',
    detail: 'A cleaner way to reveal form',
    filename: 'studio-silver.webp',
    alt: 'Real editorial photograph of a silver sports coupe in profile against a dark studio backdrop; not current dealership stock',
    photographer: 'Đào Hiếu',
    source: 'https://unsplash.com/photos/a-sleek-white-sports-car-against-a-dark-background-S5ogDe0Uzp0',
    width: 1600, height: 900,
  },
  {
    num: '03', name: 'An eye for detail',
    detail: 'Materials, texture and finish',
    filename: 'studio-detail.webp',
    alt: 'Real editorial close-up photograph of a vintage car grille and headlight; not a car for sale',
    photographer: 'Serge Kutuzov',
    source: 'https://unsplash.com/photos/black-car-macro-shot-TNybYN-LqJo',
    width: 1500, height: 930,
  },
]
function App() {
  const reduce = !!useReducedMotion()
  const [menu, setMenu] = useState(false)
  // On small screens the hero must never begin visually blank while a slow
  // device hydrates React. Desktop retains the optional entrance treatment.
  const reveal = reduce || window.matchMedia('(max-width: 640px)').matches
    ? false : { opacity: 0, y: 22 }
  const brand = getBrandSettings()
  const palette = brandPalettes[brand.accent] || brandPalettes.gold
  return <div data-react-showroom="true" data-brand-accent={brand.accent} className="min-h-screen bg-[#f5f2eb] font-sans text-[#0b1e28] antialiased">
    <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-white focus:p-3 focus:text-black">Skip to main content</a>
    <div className={palette.notice + " px-4 py-2 text-center text-[9px] font-black uppercase tracking-[.2em] text-[#17303b] sm:text-[10px]"}>
      <span className="inline-flex items-center gap-2"><ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Fictional design preview — no live dealership, prices or bookings</span>
    </div>
    <header className="relative z-30 border-b border-white/10 bg-[#091923] text-white">
      <nav aria-label="Primary navigation" className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-4 px-5 py-5 md:px-10 lg:py-6">
        <a href="/" className="inline-flex items-center gap-3 no-underline" aria-label={brand.name + " concept home"}>
          <span className="flex h-10 w-10 items-center justify-center rounded-full border border-[#ddb982]/65 text-[#ddb982]"><CarFront className="h-6 w-6" strokeWidth={1.3}/></span>
          <span className="text-[15px] font-black tracking-[.18em] text-white">{brand.name.toUpperCase()}<span className={"mt-0.5 block text-[8px] tracking-[.32em] " + palette.logo}>{brand.strapline.toUpperCase()}</span></span>
        </a>
        <button aria-label={menu ? 'Close navigation' : 'Open navigation'} aria-expanded={menu} onClick={() => setMenu(!menu)} className="rounded border border-white/30 px-3 py-2 text-[11px] uppercase tracking-widest text-white md:hidden">{menu ? 'Close' : 'Menu'}</button>
        <div className={(menu ? 'flex' : 'hidden') + ' w-full flex-col gap-5 md:flex md:w-auto md:flex-row md:items-center md:gap-9'}>
          {[['The studio','#studio'],['The collection','#collection'],['Experience','#experience'],['Inventory','/demo-stock/']].map(([label,href])=>
            <a key={label} href={href} className="text-[11px] font-bold uppercase tracking-[.14em] text-[#d4e0e3] no-underline hover:text-[#dfbd82]">{label}</a>
          )}
          <a href={brand.contact_path} className="inline-flex min-h-10 items-center justify-center gap-2 rounded border border-white/30 px-4 py-2 text-[10px] font-black uppercase tracking-[.12em] text-[#e6c691] no-underline hover:bg-white/10">{brand.contact_label} <ArrowUpRight className="h-4 w-4" /></a>
        </div>
      </nav>
    </header>
    <main id="main">
      <section id="studio" aria-labelledby="studio-title" className="relative isolate overflow-hidden bg-[#091923] text-white">
        <AnimatedGrid reduce={reduce}/>
        <div className="pointer-events-none absolute -left-60 top-[-150px] h-[600px] w-[600px] rounded-full bg-[#22505a]/35 blur-[135px]" />
        <div className="relative mx-auto grid max-w-[1320px] items-center gap-12 px-5 pb-10 pt-16 md:px-10 lg:min-h-[720px] lg:grid-cols-[.91fr_1.09fr] lg:gap-7 lg:pb-20 lg:pt-20">
          <div className="relative z-10 max-w-[610px]">
            <motion.p initial={reveal} animate={{opacity:1,y:0}} transition={{delay:.05}} className={"mb-6 inline-flex items-center gap-3 text-[10px] font-black uppercase tracking-[.27em] " + palette.eyebrow}><span className="h-px w-8 bg-current" /> {brand.eyebrow}</motion.p>
            <motion.h1 id="studio-title" initial={reveal} animate={{opacity:1,y:0}} transition={{duration:.7,delay:.12}} className="max-w-[11ch] font-serif text-[clamp(3.4rem,6vw,5.6rem)] leading-[.92] tracking-[-.068em] text-[#fffdf7]">{brand.headline} <em className={"font-normal " + palette.highlight}>{brand.highlight}</em></motion.h1>
            <motion.p initial={reveal} animate={{opacity:1,y:0}} transition={{delay:.22}} className="mb-8 mt-7 max-w-[50ch] text-[15px] leading-[1.85] text-[#bacbd2] sm:text-base">{brand.description}</motion.p>
            <motion.div initial={reveal} animate={{opacity:1,y:0}} transition={{delay:.3}} className="flex flex-wrap gap-3"><Button primary palette={palette} href="/demo-stock/">Explore fictional stock</Button><Button href="#experience">Discover the concept</Button></motion.div>
            <div className="mt-10 flex flex-wrap items-center gap-5 border-t border-white/15 pt-5 text-[10px] uppercase tracking-[.14em] text-[#aabdc4]"><span className="inline-flex items-center gap-2"><Sparkles className="h-4 w-4 text-[#dcbc85]"/> React + Three.js</span><span>Mobile-first</span><span>WordPress native</span></div>
          </div>
          <motion.div initial={reveal === false ? false : {opacity:0,x:28}} animate={{opacity:1,x:0}} transition={{duration:.9,delay:.1}} className="relative z-10">
            <Hero3D reduce={reduce}/><p className="mt-3 text-center text-[10px] font-semibold uppercase tracking-[.15em] text-[#899da5]">Illustrative 3D geometry — no real manufacturer design</p>
          </motion.div>
        </div>
        <div className="relative border-t border-white/10 bg-black/20"><div className="mx-auto flex max-w-[1320px] flex-wrap justify-between gap-3 px-5 py-5 text-[10px] font-semibold uppercase tracking-[.18em] text-[#b4c8ce] md:px-10"><span>01 — A digital showroom</span><span>02 — Evidence-led inventory</span><span>03 — Private workshop intelligence</span></div></div>
      </section>
      <section id="experience" className="bg-[#f5f2eb] px-5 py-20 md:px-10 md:py-28">
        <div className="mx-auto max-w-[1240px]">
          <div className="mb-12 grid items-end gap-7 lg:grid-cols-[1.05fr_.95fr]">
            <div><p className="mb-3 text-[11px] font-extrabold uppercase tracking-[.22em] text-[#916d3b]">Luxury in every interaction</p><h2 className="max-w-[15ch] font-serif text-[clamp(2.9rem,5vw,5.1rem)] leading-[1.08] tracking-[-.06em]">Built to make an <em>impression.</em></h2></div>
            <p className="max-w-[55ch] text-base leading-[1.9] text-[#596a71]">A dealership website should feel as considered as the vehicles it presents. This demo connects visual polish to practical administration without pretending a customer has gone live.</p>
          </div>
          <div className="grid gap-4 md:grid-cols-3">{features.map(({num,icon:Icon,title,copy})=><motion.article key={num} whileHover={reduce?undefined:{y:-5}} className="flex min-h-[310px] flex-col rounded-lg border border-[#dce2df] bg-white p-7 shadow-[0_22px_55px_rgba(8,25,35,.035)] sm:p-9">
            <div className="mb-auto flex items-start justify-between"><span className="text-xs font-extrabold tracking-[.24em] text-[#b39462]">{num}</span><Icon className="h-8 w-8 text-[#294f5b]" strokeWidth={1.3}/></div>
            <h3 className="mt-10 font-serif text-3xl tracking-tight">{title}</h3><p className="mt-3 text-sm leading-[1.8] text-[#64757b]">{copy}</p>
          </motion.article>)}</div>
        </div>
      </section>
      <section id="collection" className="bg-[#edece6] px-5 py-20 md:px-10 md:py-28">
        <div className="mx-auto max-w-[1240px]">
          <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
            <div><p className="mb-3 text-[11px] font-extrabold uppercase tracking-[.22em] text-[#916d3b]">The collection</p><h2 className="font-serif text-[clamp(2.9rem,5vw,5rem)] leading-[1.08] tracking-[-.06em]">Explore the possibilities.</h2></div>
            <a href="/demo-stock/" className="inline-flex items-center gap-2 border-b border-[#947a4d] pb-2 text-[11px] font-black uppercase tracking-widest text-[#173b48] no-underline">See demonstrator inventory <ArrowRight className="h-4 w-4"/></a>
          </div>
          <div data-editorial-gallery="true" className="grid gap-4 lg:grid-cols-[1.18fr_.82fr]">
            {photographicReferences.map((item, idx) => {
              const selected = brand.editorialMedia?.[idx + 1]
              const url = selected || brand.editorialAssetsBase + item.filename
              return <figure key={item.num} data-editorial-photo={item.num}
                className={'group relative isolate overflow-hidden rounded-xl bg-[#0b2029] shadow-[0_24px_55px_rgba(9,25,35,.16)] ' +
                  (idx === 0 ? 'min-h-[370px] lg:row-span-2 lg:min-h-[590px]' : 'min-h-[290px] lg:min-h-[287px]')}>
                <img alt={selected
                    ? 'Client-selected editorial automotive reference. Media rights and vehicle claims require independent review.'
                    : item.alt}
                  src={url} width={item.width} height={item.height}
                  loading="lazy" decoding="async"
                  className={'absolute inset-0 h-full w-full object-cover transition-transform duration-700 motion-reduce:transition-none motion-safe:group-hover:scale-[1.035] ' +
                    (idx === 2 ? 'object-[center_25%]' : 'object-center')} />
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-[#06151f]/95 via-[#06151f]/15 to-[#06151f]/40" />
                <figcaption className="relative z-10 flex h-full min-h-[inherit] flex-col justify-between gap-16 p-6 text-white sm:p-8">
                  <div className="flex flex-wrap items-start justify-between gap-3 text-[10px] font-extrabold uppercase tracking-[.19em] text-[#f1d4a6]">
                    <span>Frame {item.num} / photographic direction</span>
                    <span className="rounded-full border border-white/25 bg-black/30 px-3 py-2 text-[9px] text-white/90 backdrop-blur-sm">Editorial only</span>
                  </div>
                  <div>
                    <h3 className={'max-w-[20ch] font-serif leading-[1.1] tracking-[-.04em] ' +
                      (idx === 0 ? 'text-[clamp(2.2rem,4vw,4rem)]' : 'text-[clamp(2rem,3vw,3rem)]')}>{item.name}</h3>
                    <p className="mt-2 text-sm text-slate-200">{item.detail}</p>
                    <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-white/20 pt-4 text-[10px] text-slate-200">
                      <span>Photography reference — not a stock listing</span>
                      {selected ? <span>WordPress Media Library selection</span> :
                        <a href={item.source} target="_blank" rel="noopener noreferrer"
                          className="pointer-events-auto text-[#efce97] underline underline-offset-4 hover:text-white focus-visible:outline-2 focus-visible:outline-white">
                          Photo: {item.photographer} / Unsplash
                        </a>}
                    </div>
                  </div>
                </figcaption>
              </figure>
            })}
          </div>
          <p className="mt-6 max-w-[83ch] text-[11px] leading-6 text-[#607178]">These photographs are visual references, not inventory, customer stock, brand partnerships or claims about our fictional GT. Manufacturer names, trademarks and model rights require independent clearance for a real client deployment.</p>
        </div>
      </section>
      <section className="bg-[#102832] px-5 py-20 text-white md:px-10 md:py-28"><div className="mx-auto flex max-w-[1240px] flex-col items-start justify-between gap-10 rounded-xl border border-[#d4ae75]/35 bg-[radial-gradient(ellipse_at_top_right,#214957_0%,#102832_50%,#091923_100%)] p-8 md:flex-row md:items-center md:p-14">
        <div><p className="mb-4 text-[10px] font-bold uppercase tracking-[.26em] text-[#d6b47d]">A secure commercial foundation</p><h2 className="max-w-[16ch] font-serif text-[clamp(2.7rem,4vw,4.5rem)] leading-[1.1] tracking-[-.05em]">Designed to be extraordinary. Built to be responsible.</h2><p className="mt-5 max-w-[62ch] text-sm leading-[1.9] text-[#b9cbd2]">Private bookings are verified in WordPress and MariaDB staging. Public booking, payments and customer enquiries remain disabled.</p></div>
        <Button primary palette={palette} href={brand.contact_path}>{brand.contact_label}</Button>
      </div></section>
    </main>
    <footer className="border-t border-white/10 bg-[#07151f] px-5 py-12 text-[#b9c9ce] md:px-10"><div className="mx-auto flex max-w-[1240px] flex-col justify-between gap-6 md:flex-row">
      <div><p className="text-sm font-black uppercase tracking-[.2em] text-white">{brand.name}</p><p className="mt-2 max-w-[44ch] text-xs leading-7">Fictional WordPress + React showroom made for internal Empire AI capability testing.</p></div>
      <div className="text-xs leading-7 md:text-right"><p>No real vehicles, sales offers, reservations or customer data.</p><p>Client identity, privacy and commercial terms remain pending.</p></div>
    </div></footer>
  </div>
}
const mount = document.getElementById('empire-yard-react-root')
if (mount) createRoot(mount).render(<App/>)

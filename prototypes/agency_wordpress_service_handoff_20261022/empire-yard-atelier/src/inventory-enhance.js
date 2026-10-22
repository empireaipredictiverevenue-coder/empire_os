/* Tailwind-only DOM enhancement for the existing public read-only WP shortcode.
 * No forms or bookings are submitted by this script. */
(function () {
  const root = document.querySelector('.empire-yard-inventory')
  if (!root || root.dataset.yardStyled === 'true') return
  root.dataset.yardStyled = 'true'
  const apply = (el, classnames) => el && el.classList.add(...classnames.split(' '))
  apply(root, 'mt-6 w-full max-w-6xl text-[#102a37]')
  apply(root.querySelector(':scope > p'), 'mb-6 rounded-lg border border-[#d6bd91] bg-[#fff9ed] px-5 py-3 text-sm font-semibold leading-relaxed text-[#7b5b2f]')
  const form = root.querySelector(':scope > form')
  apply(form, 'mb-9 grid grid-cols-1 gap-4 rounded-xl border border-[#d7dedb] bg-white p-5 shadow-sm md:grid-cols-[1fr_1fr_auto] md:items-end')
  for (const label of root.querySelectorAll('form label')) {
    apply(label, 'flex flex-col gap-2 text-[11px] font-bold uppercase tracking-widest text-[#49606b]')
    apply(label.querySelector('input'), 'w-full min-h-12 rounded-md border border-[#c1d0d0] bg-[#fbfcfa] px-3 py-2 text-base font-medium normal-case tracking-normal text-[#102a37]')
  }
  apply(form?.querySelector('button'), 'min-h-12 rounded-md border-0 bg-[#102b36] px-5 py-3 text-xs font-extrabold uppercase tracking-widest text-white hover:bg-[#244d5a] focus-visible:outline-3 focus-visible:outline-[#d7b57a]')
  for (const article of root.querySelectorAll(':scope > article')) {
    apply(article, 'mb-8 flex max-w-md flex-col overflow-hidden rounded-xl border border-[#d5dedb] bg-white shadow-[0_15px_45px_rgba(14,45,56,.08)]')
    apply(article.querySelector('img'), 'order-1 aspect-[16/10] h-auto w-full object-cover bg-[#d0d6d3]')
    const title = article.querySelector('h3')
    apply(title, 'order-2 mx-6 mt-5 mb-1 font-serif text-2xl leading-tight tracking-tight')
    apply(title?.querySelector('a'), 'text-[#122e39] no-underline hover:text-[#ad8042]')
    for (const p of article.querySelectorAll('p')) apply(p, 'order-3 mx-6 mb-6 mt-2 text-sm leading-7 text-[#5c7079]')
  }
  for (const article of root.querySelectorAll('.empire-yard-detail')) {
    apply(article, 'overflow-hidden rounded-xl border border-[#d5dedb] bg-white p-5 shadow-sm sm:p-8')
    apply(article.querySelector('img'), 'mb-6 aspect-video w-full rounded-lg object-cover')
    apply(article.querySelector('h2'), 'my-5 font-serif text-3xl')
  }
})()

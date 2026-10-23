/* Native WordPress media editor. Runs only in Appearance > Showroom Branding.
 * No remote assets, no extra API, no credentials, no framework.
 */
(() => {
  'use strict'
  const setImage = (index, id, thumbnail) => {
    const input = document.getElementById('empire_yard_media_' + index)
    const preview = document.querySelector('[data-media-preview="' + index + '"]')
    if (!input || !preview) return
    input.value = String(id || 0)
    preview.replaceChildren()
    if (id && thumbnail) {
      const image = document.createElement('img')
      image.src = thumbnail
      image.alt = 'Selected WordPress editorial image'
      image.style.maxWidth = '150px'
      image.style.height = 'auto'
      image.style.marginTop = '8px'
      preview.appendChild(image)
    }
  }
  document.addEventListener('click', event => {
    const choose = event.target.closest('.empire-yard-choose-media')
    const remove = event.target.closest('.empire-yard-remove-media')
    if (!choose && !remove) return
    const index = (choose || remove).dataset.mediaIndex
    if (!/^[123]$/.test(index)) return
    if (remove) {
      setImage(index, 0, '')
      return
    }
    if (!window.wp?.media) return
    const frame = window.wp.media({
      title: 'Choose licensed editorial photography',
      button: { text: 'Use selected image' },
      library: { type: 'image' },
      multiple: false,
    })
    frame.on('select', () => {
      const selected = frame.state().get('selection').first()?.toJSON()
      if (!Number.isSafeInteger(selected?.id) || selected.id < 1) return
      const thumbnail = selected.sizes?.thumbnail?.url || selected.url
      const url = new URL(thumbnail, location.href)
      if (url.origin !== location.origin) return
      setImage(index, selected.id, url.href)
    })
    frame.open()
  })
})()

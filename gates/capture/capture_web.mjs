// Web evidence capture for the frontend gates. Input: a JSON job on argv[2]; output: JSON results on stdout.
// For each capture × size: DOM, computed styles of the named elements, what the whole page measures
// (fonts, text sizes, corner radii, gradients, open dialogs), ARIA snapshot, screenshot.
import { chromium } from 'playwright-core'
import fs from 'node:fs'
import path from 'node:path'

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

// What the page as rendered measures, for the taste measures (gatelib/taste.py). Runs in the page.
// Only elements with a box are counted. Text inside code, pre, kbd and samp is counted apart.
const pageFacts = () => {
  const name = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
    (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '')
  const add = (o, k, n, e) => { (o[k] || (o[k] = { count: 0, example: name(e) })).count += n }
  const clear = c => c === 'transparent' || /,\s*0\)$/.test(c)
  const facts = { fonts: {}, code_fonts: {}, text_px: {}, radii: {}, gradients: [], dialogs_open: [] }
  for (const e of document.body.querySelectorAll('*')) {
    const box = e.getBoundingClientRect(), cs = getComputedStyle(e)
    if (!box.width || !box.height || cs.visibility === 'hidden' || cs.display === 'none') continue
    let chars = 0
    for (const n of e.childNodes) if (n.nodeType === 3) chars += n.textContent.trim().length
    if (chars) {
      const family = cs.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '')
      if (e.closest('code, pre, kbd, samp')) add(facts.code_fonts, family, chars, e)
      else { add(facts.fonts, family, chars, e); add(facts.text_px, cs.fontSize, chars, e) }
    }
    const drawn = cs.borderTopWidth !== '0px' || !clear(cs.backgroundColor) || cs.backgroundImage !== 'none' ||
      cs.boxShadow !== 'none' || cs.overflow !== 'visible'
    if (drawn) {
      const half = Math.min(box.width, box.height) / 2
      for (const r of new Set([cs.borderTopLeftRadius, cs.borderTopRightRadius, cs.borderBottomRightRadius, cs.borderBottomLeftRadius])) {
        const px = parseFloat(r)   // "6px", "50%", "6px 8px" (elliptical: its first radius)
        if (!px) continue
        add(facts.radii, r.includes('%') ? (px >= 50 ? 'round' : r) : px >= half ? 'round' : `${Math.round(px * 100) / 100}px`, 1, e)
      }
    }
    if (cs.backgroundImage.includes('gradient(') && facts.gradients.length < 20) facts.gradients.push(name(e))
    if (e.matches('dialog[open], [role="dialog"], [role="alertdialog"]')) facts.dialogs_open.push(name(e))
  }
  return facts
}
const results = []
const browser = await chromium.launch({ executablePath: job.chrome, headless: true })
try {
  for (const cap of job.captures) {
    for (const size of job.sizes) {
      const stem = `${cap.id}@${size.name}`
      const entry = { id: cap.id, row: cap.row, state: cap.state, size: size.name, width: size.width,
                      height: size.height, url: job.base_url + (cap.url || ''), files: {}, ok: true }
      const ctx = await browser.newContext({ viewport: { width: size.width, height: size.height } })
      const page = await ctx.newPage()
      try {
        await page.goto(entry.url, { waitUntil: 'load', timeout: 30000 })
        for (const s of cap.steps || []) {
          if (s.action === 'click') await page.click(s.selector)
          else if (s.action === 'fill') await page.fill(s.selector, s.value)
          else if (s.action === 'press') await page.press(s.selector, s.key)
          else if (s.action === 'setInputFiles') await page.setInputFiles(s.selector, s.file)
          else if (s.action === 'waitFor') await page.waitForSelector(s.selector, { timeout: 15000 })
          else if (s.action === 'wait') await page.waitForTimeout(s.ms)
          else if (s.action === 'goto') await page.goto(job.base_url + s.url)
          else throw new Error(`unknown action ${s.action}`)
        }
        const write = (suffix, data) => {
          const f = `${stem}.${suffix}`
          fs.writeFileSync(path.join(job.out_dir, f), data)
          entry.files[suffix] = f
        }
        write('dom.html', await page.content())
        const st = cap.styles || {}
        const styles = st.selector
          ? await page.$$eval(st.selector, (els, props) => els.map(e => {
              const cs = getComputedStyle(e)
              return Object.fromEntries(props.map(p => [p, cs.getPropertyValue(p)]))
            }), st.properties || [])
          : []
        write('styles.json', JSON.stringify({ selector: st.selector || null, elements: styles }, null, 2))
        write('page.json', JSON.stringify(await page.evaluate(pageFacts), null, 2))
        write('aria.yml', await page.locator('body').ariaSnapshot())
        await page.screenshot({ path: path.join(job.out_dir, `${stem}.png`), fullPage: true })
        entry.files['png'] = `${stem}.png`
      } catch (e) {
        entry.ok = false
        entry.error = String(e.message || e).split('\n')[0]
        try {  // what the page showed when it failed: a demo's "before" is often a step that cannot run yet
          await page.screenshot({ path: path.join(job.out_dir, `${stem}.png`), fullPage: true })
          entry.files['png'] = `${stem}.png`
        } catch {}
      }
      results.push(entry)
      await ctx.close()
    }
  }
} finally {
  await browser.close()
}
process.stdout.write(JSON.stringify(results))

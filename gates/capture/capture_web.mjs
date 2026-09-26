// Web evidence capture for the frontend gates. Input: a JSON job on argv[2]; output: JSON results on stdout.
// For each capture × size: DOM, computed styles of the named elements, ARIA snapshot, screenshot.
import { chromium } from 'playwright-core'
import fs from 'node:fs'
import path from 'node:path'

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
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
        write('aria.yml', await page.locator('body').ariaSnapshot())
        await page.screenshot({ path: path.join(job.out_dir, `${stem}.png`), fullPage: true })
        entry.files['png'] = `${stem}.png`
      } catch (e) {
        entry.ok = false
        entry.error = String(e.message || e).split('\n')[0]
      }
      results.push(entry)
      await ctx.close()
    }
  }
} finally {
  await browser.close()
}
process.stdout.write(JSON.stringify(results))

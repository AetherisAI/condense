/**
 * Best-effort first-page thumbnail for an uploaded file — generated entirely in the browser,
 * before/independent of upload, so it never touches the ingest pipeline. Returns a small JPEG
 * data URL (or null → the caller falls back to a type-chip). Heavy renderers are dynamically
 * imported, so pdf.js / JSZip land in their own lazy chunks, not the main bundle.
 *
 *  - images          → scaled down on a canvas
 *  - PDF             → pdf.js renders page 1 to a canvas
 *  - docx/pptx/xlsx  → the optional embedded OOXML preview (docProps/thumbnail.*), if present
 *  - anything else   → null
 */

const THUMB_W = 160 // render width in px; the list downsizes it with CSS

function extOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

async function imageThumbnail(file: File): Promise<string | null> {
  const url = URL.createObjectURL(file)
  try {
    const img = await loadImage(url)
    const scale = Math.min(1, THUMB_W / img.width)
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(img.width * scale))
    canvas.height = Math.max(1, Math.round(img.height * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.72)
  } finally {
    URL.revokeObjectURL(url)
  }
}

async function pdfThumbnail(file: File): Promise<string | null> {
  const pdfjs = await import('pdfjs-dist')
  // Point pdf.js at its worker as a lazily-loaded URL chunk (the Vite way).
  pdfjs.GlobalWorkerOptions.workerSrc = (
    await import('pdfjs-dist/build/pdf.worker.mjs?url')
  ).default
  const data = await file.arrayBuffer()
  const pdf = await pdfjs.getDocument({ data }).promise
  const page = await pdf.getPage(1)
  const scale = THUMB_W / page.getViewport({ scale: 1 }).width
  const viewport = page.getViewport({ scale })
  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil(viewport.width)
  canvas.height = Math.ceil(viewport.height)
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  await page.render({ canvas, canvasContext: ctx, viewport }).promise
  return canvas.toDataURL('image/jpeg', 0.72)
}

async function officeThumbnail(file: File): Promise<string | null> {
  const JSZip = (await import('jszip')).default
  const zip = await JSZip.loadAsync(await file.arrayBuffer())
  // OOXML may store a preview picture here (common in PowerPoint, optional in Word/Excel).
  const entry =
    zip.file('docProps/thumbnail.jpeg') ??
    zip.file('docProps/thumbnail.jpg') ??
    zip.file('docProps/thumbnail.png')
  if (!entry) return null
  const mime = entry.name.toLowerCase().endsWith('.png') ? 'image/png' : 'image/jpeg'
  const b64 = await entry.async('base64')
  return `data:${mime};base64,${b64}`
}

/** Resolve a thumbnail data URL for ``file``, or null if we can't make one cheaply. */
export async function makeThumbnail(file: File): Promise<string | null> {
  try {
    const ext = extOf(file.name)
    if (file.type.startsWith('image/')) return await imageThumbnail(file)
    if (ext === 'pdf' || file.type === 'application/pdf') return await pdfThumbnail(file)
    if (ext === 'docx' || ext === 'pptx' || ext === 'xlsx') return await officeThumbnail(file)
    return null
  } catch {
    return null // any failure → caller shows the type-chip instead
  }
}

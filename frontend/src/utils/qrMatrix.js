import { BarcodeFormat, QRCodeWriter } from '@zxing/library'

export function buildQrMatrix(text) {
  try {
    const writer = new QRCodeWriter()
    const matrix = writer.encode(String(text || ''), BarcodeFormat.QR_CODE, 0, 0, new Map())
    const width = matrix.getWidth()
    const height = matrix.getHeight()
    const rows = []
    for (let y = 0; y < height; y += 1) {
      const cols = []
      for (let x = 0; x < width; x += 1) {
        cols.push(Boolean(matrix.get(x, y)))
      }
      rows.push(cols)
    }
    return { size: width, rows }
  } catch {
    return null
  }
}


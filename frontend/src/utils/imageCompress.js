/**
 * Kompres file gambar ke JPEG/WebP base64 data URL di browser
 * agar ukuran unggahan tetap ringan (maks ~1280px, jauh di bawah batas 5 MB server).
 */
export async function compressImageToDataUrl(file, options = {}) {
  const maxDimension = Number(options.maxDimension || 1280);
  const quality = Number(options.quality || 0.84);
  const mimeType = options.mimeType || 'image/jpeg';

  if (!file || typeof file.type !== 'string' || !file.type.startsWith('image/')) {
    throw new Error('Pilih file gambar yang valid (JPG, PNG, atau WEBP).');
  }

  // Untuk file PNG QRIS kecil (< 400 KB), pertahankan ketajaman piksel asli
  if (options.preserveSharpQr && file.size <= 450 * 1024 && file.type === 'image/png') {
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Gagal membaca file gambar.'));
      reader.readAsDataURL(file);
    });
  }

  const objectUrl = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Gagal memuat gambar yang dipilih.'));
      image.src = objectUrl;
    });

    const srcW = img.naturalWidth || img.width || 1;
    const srcH = img.naturalHeight || img.height || 1;
    const scale = Math.min(1, maxDimension / Math.max(srcW, srcH));
    const targetW = Math.max(1, Math.round(srcW * scale));
    const targetH = Math.max(1, Math.round(srcH * scale));

    const canvas = document.createElement('canvas');
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      throw new Error('Browser tidak mendukung pemrosesan gambar.');
    }

    // Beri latar putih agar PNG transparan tidak menjadi hitam saat diekspor ke JPEG
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, targetW, targetH);
    ctx.drawImage(img, 0, 0, targetW, targetH);

    const outType = mimeType === 'image/png' ? 'image/png' : 'image/jpeg';
    const dataUrl = canvas.toDataURL(outType, outType === 'image/png' ? undefined : quality);
    if (!dataUrl || !dataUrl.startsWith('data:image/')) {
      throw new Error('Gagal mengompresi gambar.');
    }
    return dataUrl;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}


import * as pdfjsLib from 'pdfjs-dist';

let isWorkerConfigured = false;

export function configurePdfWorker(): void {
  if (isWorkerConfigured) return;
  try {
    if (typeof window !== 'undefined' && !pdfjsLib.GlobalWorkerOptions.workerSrc) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
        'pdfjs-dist/build/pdf.worker.min.mjs',
        import.meta.url
      ).toString();
    }
    isWorkerConfigured = true;
  } catch {
    // In headless test environments where import.meta.url or Worker is unsupported
  }
}

export { pdfjsLib };


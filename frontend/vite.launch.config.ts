import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// A completely separate build. The controlled mail pilot keeps its existing entry.
export default defineConfig({
  root: 'launch',
  plugins: [react(), tailwindcss()],
  build: { outDir: '../dist-launch', emptyOutDir: true },
});

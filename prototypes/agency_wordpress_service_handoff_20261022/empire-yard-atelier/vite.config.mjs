import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    sourcemap: false,
    lib: {
      entry: 'src/main.jsx',
      name: 'EmpireYardAtelier',
      formats: ['iife'],
      fileName: () => 'yard.js',
      cssFileName: 'yard'
    },
    rollupOptions: {
      output: { assetFileNames: 'yard.[ext]' }
    }
  }
})

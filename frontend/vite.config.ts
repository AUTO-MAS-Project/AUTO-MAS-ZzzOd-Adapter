import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  publicDir: false,
  plugins: [
    vue(),
    {
      name: 'zzzod-panel-classic-script',
      generateBundle: {
        order: 'post',
        handler(_options, bundle) {
          // Opaque-origin panels cannot load modules from the host asset server.
          for (const output of Object.values(bundle)) {
            if (
              output.type === 'chunk' &&
              (output.imports.length || output.dynamicImports.length || output.exports.length)
            ) {
              this.error('The panel runtime must be a standalone classic script')
            }
            if (output.type === 'asset' && output.fileName.endsWith('.html')) {
              output.source = String(output.source)
                .replaceAll(' type="module"', ' defer')
                .replaceAll(' crossorigin', '')
            }
          }
        },
      },
    },
  ],
  build: {
    outDir: '../src/zzzod_adapter/ui',
    emptyOutDir: false,
    assetsInlineLimit: 0,
    modulePreload: false,
    rolldownOptions: {
      input: { script: 'script.html', user: 'user.html' },
      output: {
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
})

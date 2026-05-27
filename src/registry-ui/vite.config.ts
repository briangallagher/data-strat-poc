import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});

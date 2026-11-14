import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

// Relative base so the build works at https://<user>.github.io/Makani/ and locally.
export default defineConfig({
  base: './',
  plugins: [svelte()],
})

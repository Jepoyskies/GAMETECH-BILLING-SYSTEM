// import { defineConfig } from "vite";
// import react from "@vitejs/plugin-react";

// export default defineConfig({
//   plugins: [react()],
//   build: {
//     rollupOptions: {
//       output: {
//         manualChunks: {
//           vendor: ["react", "react-dom", "react-router-dom"],
//           recharts: ["recharts"],
//           leaflet: ["leaflet", "react-leaflet"],
//         },
//       },
//     },
//   },
//   server: {
//     host: true,
//     port: parseInt(process.env.VITE_PORT || "5501", 10),
//     proxy: {
//       "/api": {
//         target: "http://127.0.0.1:5502",
//         changeOrigin: true,
//       },
//       "/socket.io": {
//         target: "http://127.0.0.1:5502",
//         changeOrigin: true,
//         ws: true,
//       },
//     },
//   },
// });

// DEVELOPMENT (not used by pm2 only for bulding production (npm run build))
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "react-router-dom"],
          recharts: ["recharts"],
          leaflet: ["leaflet", "react-leaflet"],
        },
      },
    },
  },
  server: {
    host: true,
    port: parseInt(process.env.VITE_PORT || "5504", 10),
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5503",
        changeOrigin: true,
      },
      "/socket.io": {
        target: "http://127.0.0.1:5503",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
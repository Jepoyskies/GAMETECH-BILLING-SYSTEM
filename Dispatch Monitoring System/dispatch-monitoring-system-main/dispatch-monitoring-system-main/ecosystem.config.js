module.exports = {
  apps: [
    {
      name: "dispatch-backend",
      cwd: "./backend",
      script: "./dist/src/index.js",
      instances: 1,
      exec_mode: "fork",
      env: {
        NODE_ENV: "production",
      },
      error_file: "../logs/backend-error.log",
      out_file: "../logs/backend-out.log",
      time: true,
      max_memory_restart: "512M",
      max_restarts: 15,
      restart_delay: 3000,
    },
  ],
};

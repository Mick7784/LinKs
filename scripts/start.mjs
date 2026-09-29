import { spawn } from "node:child_process";
import { createVideoServer } from "./video-api.mjs";

const server = createVideoServer();
let nginx;
let stopping = false;
function stop(code) {
  if (stopping) return;
  stopping = true;
  server.close();
  nginx?.kill("SIGTERM");
  const deadline = setTimeout(() => { nginx?.kill("SIGKILL"); process.exit(code); }, 5000);
  deadline.unref();
  if (!nginx) process.exit(code);
  else nginx.once("exit", () => process.exit(code));
}
server.on("error", () => stop(1));
server.listen(3002, "127.0.0.1", () => {
  nginx = spawn("nginx", ["-g", "daemon off;"], { stdio: "inherit" });
  nginx.on("error", () => { server.close(); process.exit(1); });
  nginx.on("exit", code => { if (!stopping) { server.close(); process.exit(code || 1); } });
});
process.on("SIGTERM", () => stop(0));
process.on("SIGINT", () => stop(0));

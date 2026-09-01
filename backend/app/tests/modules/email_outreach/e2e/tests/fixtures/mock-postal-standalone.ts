/**
 * Entry point run as a detached child process by global-setup.ts.
 * Playwright's globalSetup script itself exits after returning, which
 * would kill any HTTP server created in-process along with it - this
 * file keeps the mock server alive independently for the whole test
 * run. Writes its assigned port to stdout as the first line so the
 * parent can capture it.
 */
import { MockPostalServer } from "./mock-postal-server";

async function main() {
  const server = new MockPostalServer();
  const port = await server.start();
  // eslint-disable-next-line no-console
  console.log(`PORT=${port}`);

  process.on("SIGTERM", async () => {
    await server.stop();
    process.exit(0);
  });
  process.on("SIGINT", async () => {
    await server.stop();
    process.exit(0);
  });
}

main();

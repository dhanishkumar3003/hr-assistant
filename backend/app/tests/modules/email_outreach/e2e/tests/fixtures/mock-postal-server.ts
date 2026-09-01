import http from "node:http";

export interface CapturedSend {
  to: string[];
  from: string;
  sender: string;
  subject: string;
  plain_body: string;
  html_body: string;
  reply_to?: string;
  receivedAt: number;
}

/**
 * Minimal stand-in for the real Postal API (see
 * backend/app/modules/email_outreach/services/postal_backend.py) -
 * accepts the exact payload shape PostalBackend.send() posts and
 * always returns Postal's success response shape, so /email/send
 * transitions to Sent for real without any email leaving the machine.
 * Captures every send so tests can assert on recipient/subject/body/
 * reply-to (see prompt section 14).
 */
export class MockPostalServer {
  private server: http.Server;
  private captured: CapturedSend[] = [];
  public port = 0;

  constructor() {
    this.server = http.createServer((req, res) => {
      // Inspection endpoints - Playwright's globalSetup runs in a
      // separate process from test workers, so tests can't share this
      // class's in-memory instance directly. They query it over HTTP
      // instead, same as the backend under test does for /send.
      if (req.method === "GET" && req.url === "/__captured") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify(this.captured));
        return;
      }
      if (req.method === "POST" && req.url === "/__clear") {
        this.captured = [];
        res.writeHead(200).end();
        return;
      }

      if (req.method !== "POST") {
        res.writeHead(404).end();
        return;
      }
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", () => {
        try {
          const payload = JSON.parse(body);
          this.captured.push({ ...payload, receivedAt: Date.now() });
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(
            JSON.stringify({
              status: "success",
              time: Date.now() / 1000,
              flags: {},
              data: { message_id: `mock-${Date.now()}@e2e.test`, messages: {} },
            })
          );
        } catch (err) {
          res.writeHead(400).end(String(err));
        }
      });
    });
  }

  async start(): Promise<number> {
    await new Promise<void>((resolve) => {
      // Bind 0.0.0.0 so the Docker container (via host.docker.internal)
      // can reach this from outside the host's loopback interface.
      this.server.listen(0, "0.0.0.0", resolve);
    });
    const address = this.server.address();
    if (address && typeof address === "object") {
      this.port = address.port;
    }
    return this.port;
  }

  async stop(): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      this.server.close((err) => (err ? reject(err) : resolve()));
    });
  }

  getCaptured(): CapturedSend[] {
    return this.captured;
  }

  getLastSendTo(recipient: string): CapturedSend | undefined {
    return [...this.captured].reverse().find((c) => c.to.includes(recipient));
  }

  clear(): void {
    this.captured = [];
  }
}

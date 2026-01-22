import { render, screen } from "@testing-library/react";
import App from "../App";

const buildResponse = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("App", () => {
  const mailPayload = {
    user_id: "test-user",
    mail: {
      user: {
        userId: "test",
        username: "Test User",
        email: "test@example.com",
        avatar: "https://picsum.photos/100/100?random=1",
      },
      emails: [
        {
          id: "e1",
          threadId: "t1",
          from: { name: "Alice", email: "alice@example.com", avatar: "" },
          to: [{ name: "Test User", email: "test@example.com" }],
          cc: [],
          bcc: [],
          subject: "Welcome to the demo",
          body: "Hello there",
          snippet: "Hello there",
          timestamp: "2024-01-01T00:00:00Z",
          read: false,
          starred: false,
          important: false,
          labels: [],
          category: "primary",
          folder: "inbox",
          attachments: [],
        },
      ],
      labels: [{ id: "l1", name: "Work", color: "#ef4444" }],
      drafts: [],
    },
  };

  beforeEach(() => {
    global.fetch = vi.fn(async () => buildResponse(mailPayload));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the mailbox layout", async () => {
    render(<App />);
    expect(await screen.findByText("Compose")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search mail")).toBeInTheDocument();
  });

  it("shows inbox emails from the backend", async () => {
    render(<App />);
    expect(await screen.findByText("Welcome to the demo")).toBeInTheDocument();
  });
});

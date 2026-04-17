import { render, screen } from "@testing-library/react";
import { EmailBody } from "./ThreadView";

describe("EmailBody", () => {
  it("renders plain text bodies without collapsing lines", () => {
    const { container } = render(<EmailBody body={"Line 1\nLine 2"} bodyFormat="text" />);

    expect(screen.getByText(/Line 1/)).toBeInTheDocument();
    expect(screen.queryByTitle("email-body")).not.toBeInTheDocument();
    expect(container.querySelector(".whitespace-pre-wrap")).toBeInTheDocument();
  });

  it("treats angle-bracket email addresses as plain text", () => {
    render(<EmailBody body={"Alice <alice@example.com>\nFollow up"} />);

    expect(screen.getByText(/alice@example\.com/)).toBeInTheDocument();
    expect(screen.queryByTitle("email-body")).not.toBeInTheDocument();
  });

  it("renders HTML bodies inside the iframe path", () => {
    render(<EmailBody body="<div>Hello<br>world</div>" />);

    const iframe = screen.getByTitle("email-body");
    expect(iframe).toBeInTheDocument();
    expect(iframe.getAttribute("srcdoc")).toContain("Hello");
  });
});

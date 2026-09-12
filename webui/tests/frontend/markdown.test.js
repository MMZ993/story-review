import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

import { renderMarkdown, renderStoryPreview } from "../../static/markdown.js";

// Carried over from the cv-agent source project (D16-3): the renderer must
// never trust model HTML and must repair incomplete fences for display.
describe("renderMarkdown", () => {
  it("renders an unfinished code fence without permitting model HTML", () => {
    const document = new JSDOM("<div id=message></div>").window.document;
    const message = document.querySelector("#message");

    renderMarkdown(message, "```python\nprint('<script>alert(1)</script>')", false);

    expect(message.querySelector("pre code")?.textContent).toContain("<script>alert(1)</script>");
    expect(message.querySelector("script")).toBeNull();
  });

  it("renders story plain-text lines as separate Markdown paragraphs", () => {
    const document = new JSDOM("<div id=preview></div>").window.document;
    const preview = document.querySelector("#preview");

    renderStoryPreview(preview, "Context: first paragraph\n\nScope: second paragraph");

    expect([...preview.querySelectorAll("p")].map((paragraph) => paragraph.textContent)).toEqual([
      "Context: first paragraph",
      "Scope: second paragraph",
    ]);
  });

  it("formats completed Markdown while removing raw HTML and images", () => {
    const document = new JSDOM("<div id=message></div>").window.document;
    const message = document.querySelector("#message");

    renderMarkdown(
      message,
      "## Background\n\n[Report](https://example.test) [Unsafe](javascript:alert(1))\n\n<img src=x onerror=alert(1)><script>alert(1)</script>",
      true,
    );

    expect(message.querySelector("h2")?.textContent).toBe("Background");
    expect(message.querySelector("a")?.getAttribute("href")).toBe("https://example.test");
    expect(message.querySelectorAll("a")[1]?.hasAttribute("href")).toBe(false);
    expect(message.querySelector("img, script")).toBeNull();
  });
});

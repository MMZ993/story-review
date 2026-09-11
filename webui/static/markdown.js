import createDOMPurify from "dompurify";
import { Marked, Renderer } from "marked";
import remend from "remend";

const ALLOWED_TAGS = [
  "a",
  "blockquote",
  "br",
  "code",
  "del",
  "em",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "hr",
  "li",
  "ol",
  "p",
  "pre",
  "strong",
  "table",
  "tbody",
  "td",
  "th",
  "thead",
  "tr",
  "ul",
];
const ALLOWED_ATTR = ["class", "href", "title"];
const renderer = new Renderer();
renderer.html = () => "";
const parser = new Marked({ breaks: true, gfm: true, renderer });

/**
 * Render model Markdown into one assistant message without trusting its HTML.
 *
 * Inputs: an assistant message element, accumulated raw Markdown, and final-stream state.
 * Output: no return value.
 * Side effects: replaces the element's children with sanitized rendered markup.
 * Errors: propagates parser or DOM errors.
 * Constraint: raw model HTML and images are always excluded; incomplete Markdown is repaired only for display.
 */
export function renderMarkdown(element, source, isFinal) {
  const displaySource = isFinal ? source : remend(source);
  const rendered = parser.parse(displaySource);
  const purifier = createDOMPurify(element.ownerDocument.defaultView);
  const safeHtml = purifier.sanitize(rendered, {
    ALLOWED_ATTR,
    ALLOWED_TAGS,
    FORBID_TAGS: ["img"],
  });

  element.innerHTML = safeHtml;
}

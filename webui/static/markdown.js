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

/**
 * Render a StoryDetail plain-text field as readable Markdown paragraphs.
 *
 * Input: one plain-text story field whose source paragraphs are newline-separated.
 * Output: no return value.
 * Side effects: replaces `element` children through the sanitized Markdown renderer.
 * Errors: propagates parser or DOM errors.
 * Constraint: this preserves source paragraph boundaries without interpreting or
 * reconstructing the ADO HTML formatting stripped by story preparation.
 */
export function renderStoryPreview(element, source) {
  const paragraphMarkdown = source
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n\n");
  renderMarkdown(element, paragraphMarkdown, true);
}

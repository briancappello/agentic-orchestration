/** The agent's Markdown as safe HTML. The agent repeats what it reads, so its output is untrusted. */
import DOMPurify from "dompurify";
import { Marked } from "marked";

const marked = new Marked({ gfm: true, breaks: false, async: false });

let hooked = false;
function hookLinks() {
  if (hooked) return;
  hooked = true;
  // Links open outside the workbench and cannot reach back into it.
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A") {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });
}

export function renderMarkdown(text: string): string {
  hookLinks();
  const html = (marked.parse(text) as string).trim();
  return DOMPurify.sanitize(html, { FORBID_TAGS: ["style", "form", "input", "img"], FORBID_ATTR: ["style"] });
}

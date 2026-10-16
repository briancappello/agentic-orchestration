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
  // A table scrolls sideways in its own box instead of crushing its columns.
  const html = (marked.parse(text) as string).trim()
    .replaceAll("<table>", '<div class="table-scroll"><table>').replaceAll("</table>", "</table></div>");
  return DOMPurify.sanitize(html, { FORBID_TAGS: ["style", "form", "input", "img"], FORBID_ATTR: ["style"] });
}

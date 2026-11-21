import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { build } from "vite";

// A classic script works in file:// pages, where browsers block module imports.
const entry = fileURLToPath(new URL("../src/paperKeyphrase.ts", import.meta.url));
const destination = new URL("../../web/paper-labels.js", import.meta.url);
const result = await build({
  configFile: false, publicDir: false, logLevel: "error",
  build: {
    lib: { entry, name: "CosMatterPaperLabels", formats: ["iife"] },
    target: "es2022", minify: false, write: false,
  },
});
const bundle = Array.isArray(result) ? result[0] : result;
const content = "// Generated from frontend/src/paperKeyphrase.ts by frontend/scripts/build-offline-paper-labels.mjs.\n"
  + bundle.output[0].code;
if (process.argv.includes("--check")) {
  if ((await readFile(destination, "utf8")).replaceAll("\r\n", "\n") !== content.replaceAll("\r\n", "\n")) {
    throw new Error("Offline paper labels are stale. Run node frontend/scripts/build-offline-paper-labels.mjs.");
  }
} else {
  await writeFile(destination, content);
}

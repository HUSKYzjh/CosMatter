/** Chinese-first UI dictionary. Provider and product names remain untranslated. */
const TEXT: Record<string, string> = {
  Discover: "\u53d1\u73b0", Workflow: "\u5de5\u4f5c\u6d41", Graph: "\u56fe\u8c31", Reading: "\u9605\u8bfb", Horizon: "\u62d3\u5c55",
  "Mission scope": "\u4efb\u52a1\u8303\u56f4", Papers: "\u8bba\u6587", "Accepted evidence": "\u5df2\u6279\u51c6\u8bc1\u636e", "Reference metadata": "\u53c2\u8003\u5143\u6570\u636e", "Structure / collections": "\u7ed3\u6784\u4e0e\u96c6\u5408",
  "Discovery route": "\u53d1\u73b0\u8def\u7ebf", "Evidence provenance": "\u8bc1\u636e\u6eaf\u6e90", "Bibliographic links": "\u4e66\u76ee\u5173\u8054", "Related-title suggestions": "\u76f8\u5173\u9898\u540d\u5efa\u8bae", "Document / collection links": "\u6587\u732e\u4e0e\u96c6\u5408\u5173\u8054",
  "Research question": "\u7814\u7a76\u95ee\u9898", "Update discovery": "\u66f4\u65b0\u53d1\u73b0\u53f0", "Launch API mission": "\u542f\u52a8 API \u4efb\u52a1", "Draft plan with DeepSeek": "\u4f7f\u7528 DeepSeek \u8d77\u8349\u8ba1\u5212", "Approve reviewed plan": "\u6279\u51c6\u590d\u6838\u8ba1\u5212",
  "Light": "\u6d45\u8272", "Dark": "\u6df1\u8272", "Eye care": "\u62a4\u773c", "Material": "\u6750\u6599", "Property": "\u6027\u8d28", Scope: "\u8303\u56f4", "All objects": "\u5168\u90e8\u5bf9\u8c61",
  "Research workflow": "\u7814\u7a76\u5de5\u4f5c\u6d41", "Evidence navigation route": "\u8bc1\u636e\u5bfc\u822a\u8def\u7ebf", "Paper reading desk": "\u8bba\u6587\u9605\u8bfb\u53f0", "Research extension": "\u7814\u7a76\u62d3\u5c55",
  "Reading task": "\u9605\u8bfb\u4efb\u52a1", "Evidence leads": "\u8bc1\u636e\u7ebf\u7d22", "Review notes": "\u590d\u6838\u5907\u6ce8", "Approved evidence": "\u5df2\u6279\u51c6\u8bc1\u636e",
  "Current mission": "\u5f53\u524d\u4efb\u52a1", "Condition gaps": "\u6761\u4ef6\u7f3a\u53e3", "Report status": "\u62a5\u544a\u72b6\u6001", available: "\u53ef\u7528", "not released": "\u672a\u53d1\u5e03",
  "Card view": "\u5361\u7247\u89c6\u56fe", "Relationship graph": "\u5173\u7cfb\u56fe\u8c31", "Topic clusters": "\u4e3b\u9898\u7c07", "Node types": "\u8282\u70b9\u7c7b\u578b", "Relation types": "\u5173\u7cfb\u7c7b\u578b", All: "\u5168\u90e8", Fit: "\u9002\u914d", Focus: "\u805a\u7126",
  "Research scope": "\u7814\u7a76\u8303\u56f4", "Search visible map": "\u68c0\u7d22\u53ef\u89c1\u56fe\u8c31", "titles or sources": "\u9898\u540d\u6216\u6765\u6e90", "Open in graph": "\u5728\u56fe\u8c31\u4e2d\u6253\u5f00", "Related titles": "\u76f8\u5173\u9898\u540d", "Trust boundary": "\u53ef\u4fe1\u8fb9\u754c", "Metadata source": "\u5143\u6570\u636e\u6765\u6e90", "Publication year": "\u53d1\u8868\u5e74\u4efd", "Content access": "\u5185\u5bb9\u8bbf\u95ee",
};

export function zh(en: string, fallback = "\u4efb\u52a1\u4fe1\u606f"): string { return TEXT[en] ?? fallback; }

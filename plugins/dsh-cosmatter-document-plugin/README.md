# CosMatter document plugin for DeepSeek Harness

This bundle submits and polls metadata-only MinerU extraction tasks through the local CosMatter backend. It requires one already retrieved candidate with either an upstream `is_content_accessible=true` declaration or a current hash-only Sciverse content-access confirmation created by the explicit local review command, a complete human `include_for_fulltext` screening decision, and exactly these authorizations:

`mission_scoped_egress_consent`, `mineru_file_consent`, `private_content_to_mineru`.

It does not upload local files, list files, read a filesystem, fetch parser output, expose a source URL, return full text, create a Source Map, create content-access confirmations, or accept evidence. Those remain separately reviewed local CosMatter operations.

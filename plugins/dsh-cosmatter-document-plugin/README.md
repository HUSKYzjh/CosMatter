# CosMatter document plugin for DeepSeek Harness

This bundle submits and polls metadata-only MinerU extraction tasks through the local CosMatter backend. It requires one already retrieved candidate with either an upstream `is_content_accessible=true` declaration or a current hash-only Sciverse content-access confirmation created by the explicit local review command, a complete human `include_for_fulltext` screening decision, and exactly these authorizations:

`mission_scoped_egress_consent`, `mineru_file_consent`, `private_content_to_mineru`.

Both tools return task metadata and `workbench_url`. Open it on the machine running CosMatter to focus that candidate. The workbench uses its local phase, screening, and parse records to choose between the paper inspector and the reader. Parser output and evidence review stay in the CosMatter workbench and its private local workflows.

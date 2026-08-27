import json
import tempfile
import unittest
from pathlib import Path
from cosmatter.local_library import LocalLibraryError, candidates_from_zotero_export

class LocalLibraryTests(unittest.TestCase):
    def test_ranks_metadata_without_exporting_private_fields(self):
        items=[{"key":"BFO1","title":"BiFeO3 thin films under epitaxial strain","date":"2023-06-01","DOI":"10.1000/a","tags":[{"tag":"ferroelectric"}],"abstractNote":"private abstract","attachments":[{"path":"C:/private/a.pdf"}],"notes":["private note"]},{"key":"BFO2","title":"BiFeO3 magnetic order","date":"2022","tags":["magnetism"]},{"key":"DUP","title":"Duplicate","DOI":"10.1000/a","tags":["BiFeO3"]}]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"zotero.json";path.write_text(json.dumps(items),encoding="utf-8")
            candidates=candidates_from_zotero_export(path,"BiFeO3 ferroelectric",10)
        self.assertEqual([item.document_id for item in candidates],["zotero:BFO1","zotero:BFO2"])
        self.assertEqual(candidates[0].publication_year,2023)
        self.assertEqual(candidates[0].doi,"10.1000/a")
        self.assertFalse(candidates[0].is_content_accessible)
        blob=json.dumps([item.to_dict() for item in candidates])
        self.assertNotIn("private abstract",blob);self.assertNotIn("private/a.pdf",blob);self.assertNotIn("private note",blob)
    def test_accepts_wrapped_items_and_rejects_unsearchable_query(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"zotero.json";path.write_text(json.dumps({"items":[{"title":"BiFeO3 overview","date":"2021"}]}),encoding="utf-8")
            self.assertEqual(len(candidates_from_zotero_export(path,"BiFeO3",1)),1)
            with self.assertRaises(LocalLibraryError): candidates_from_zotero_export(path,"***",1)
if __name__=="__main__": unittest.main()

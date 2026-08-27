"""Safe metadata-only local Zotero retrieval."""

from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from .models import PaperCandidate, normalized_doi_or_none

class LocalLibraryError(ValueError):
    pass

_TOKEN=re.compile(r"[a-z0-9][a-z0-9+._-]*",re.I)
_YEAR=re.compile(r"(?:^|\D)((?:19|20)\d{2})(?:\D|$)")

def candidates_from_zotero_export(path: Path, query: str, top_k: int) -> tuple[PaperCandidate,...]:
    terms=_tokens(query)
    if not terms or not 1<=top_k<=250:
        raise LocalLibraryError("query must contain searchable terms and top_k must be between 1 and 250")
    try:
        raw=json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LocalLibraryError("local Zotero export does not exist") from error
    except json.JSONDecodeError as error:
        raise LocalLibraryError("local Zotero export is not valid JSON") from error
    items=raw if isinstance(raw,list) else raw.get("items") if isinstance(raw,dict) else None
    return candidates_from_zotero_items(items, query, top_k)


def candidates_from_zotero_items(items: object, query: str, top_k: int) -> tuple[PaperCandidate, ...]:
    """Rank already-loaded Zotero metadata; used by frozen retrieval benchmarks."""
    terms=_tokens(query)
    if not terms or not 1<=top_k<=250:
        raise LocalLibraryError("query must contain searchable terms and top_k must be between 1 and 250")
    if not isinstance(items,list) or not all(isinstance(item,dict) for item in items):
        raise LocalLibraryError("local Zotero export must be an array or an object with an items array")
    ranked=[]; seen=set()
    for order,item in enumerate(items):
        title=_text(item.get("title"))
        if not title: continue
        identity=_identity(item,title)
        if identity in seen: continue
        score=_score(terms,_searchable(item,title))
        if not score: continue
        seen.add(identity)
        key=_text(item.get("key")) or _stable_key(item,title)
        year=_YEAR.search(_text(item.get("date")))
        candidate=PaperCandidate(document_id=f"zotero:{key}",title=title[:500],query=query,source="Local Zotero metadata",publication_year=int(year.group(1)) if year else None,locator_hint="metadata:title,tags",is_content_accessible=False,doi=normalized_doi_or_none(_text(item.get("DOI")) or _text(item.get("doi"))))
        ranked.append((score,order,title.casefold(),candidate))
    ranked.sort(key=lambda row:(-row[0],row[1],row[2]))
    return tuple(row[3] for row in ranked[:top_k])

def _tokens(value: str)->tuple[str,...]:
    return tuple(dict.fromkeys(term.casefold() for term in _TOKEN.findall(value)))

def _text(value: object)->str:
    return value.strip() if isinstance(value,str) else ""

def _searchable(item: dict[str,Any],title:str)->str:
    tags=item.get("tags",[])
    values=[]
    if isinstance(tags,list):
        for tag in tags:
            if isinstance(tag,str): values.append(tag)
            elif isinstance(tag,dict) and _text(tag.get("tag")): values.append(_text(tag.get("tag")))
    return " ".join([title,*values])

def _score(terms:tuple[str,...],metadata:str)->float:
    found=set(_tokens(metadata))
    return sum(term in found for term in terms)/len(terms)

def _identity(item:dict[str,Any],title:str)->str:
    doi=normalized_doi_or_none(_text(item.get("DOI")) or _text(item.get("doi")))
    return "doi:"+doi if doi else "title:"+title.casefold()

def _stable_key(item:dict[str,Any],title:str)->str:
    doi=normalized_doi_or_none(_text(item.get("DOI")) or _text(item.get("doi")))
    return hashlib.sha256((doi if doi else title.casefold()).encode("utf-8")).hexdigest()[:16]

# Reviewed unit normalization

CosMatter treats unit normalization as an auditable review action, not an LLM
inference. A material fact retains its reported value and unit, and may also
contain a reviewer-entered normalized value and normalized unit. If both pairs
are numeric and their units belong to a supported dimension, the local
validator checks the conversion before the fact can be recorded.

## Supported deterministic dimensions

- length: m, cm, mm, micrometre, nm, pm, angstrom, bohr;
- temperature: K and degrees Celsius;
- pressure: Pa, kPa, MPa, GPa, bar;
- energy: eV, meV, keV, J;
- polarization: C/m2 and microC/cm2;
- electric field: V/m, kV/cm, MV/cm;
- strain: percent and fraction;
- magnetization: A/m, kA/m, MA/m, emu/cm3;
- frequency: Hz, kHz, MHz, GHz; and
- density: kg/m3 and g/cm3.

Unicode is normalized conservatively before lookup: `micro` sign variants,
`angstrom`, degree-Celsius notation, superscript 2, whitespace, and caret
notation are accepted. The source document is never rewritten: the original
value/unit stay in the material-fact artifact, and every fact remains linked to
its reviewed source-map locator and quote hash.

## Boundaries

The validator does not derive a quantity from a field name, parse a number out
of prose, choose a preferred unit, or convert an unsupported unit. In those
cases it retains the reviewer-provided fields without a guessed conversion.
It rejects only a numeric pair that is demonstrably inconsistent or belongs to
different supported dimensions. This prevents a UI or fusion step from silently
turning a unit typo into a material-science conclusion.

材料事实表单会在浏览器中对同一组已支持单位的有限数值对做一次即时一致性预检，以便在提交前发现明显的换算笔误。该预检不认识未知单位、不处理文本量，也不能绕过本机服务的同一规则复核或人工来源审核。

`fuse-material-facts` groups the reviewed normalized values only when the
reviewer supplied a normalized unit. It still treats observations under
different qualifiers as not directly comparable. The unit check therefore
improves comparability but does not establish causality or resolve a literature
contradiction.

## Regression verification

The offline test suite covers exact conversion, incompatible dimensions,
incorrect numeric pairs, source-map-bound fact recording, and common
materials-science representations including micrometre, angstrom, Celsius,
strain, magnetization, frequency, and density. Run:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_unit_normalization.py" -v
```

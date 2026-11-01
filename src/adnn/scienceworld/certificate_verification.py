"""Certificate verification: proof obligations, mechanical source scans and simulator tests.

Phase 4G (docs/23 §4, ADR-0004 C1-C4). A precondition checker returning
``precondition_met`` is **not** a proven certificate. A claim is
``verified_source_relative`` only when every proof obligation is discharged:

- O1 the invariant is stated precisely, with horizon and restoration definition;
- O2 every occurrence of the protected identifier is classified mechanically and no
  write can undo the invariant;
- O3 the owning property object is never reassigned inside a method body;
- O4 reflection is limited to type tags (no field mutation by reflection);
- O5 the audited action space equals the action files in ``actions/``;
- O6 the invariant holds in tests on the pinned simulator;
- O7 a bounded counterexample search on the simulator finds no violation;
- O8 replacement / regrowth: no runtime constructor can recreate the protected object.

Any failed obligation with a counterexample -> ``rejected``; any other failed or open
obligation -> ``provisional``. "Source-relative" means relative to the pinned source
text and our harness's API surface (``HARNESS_API``); it is still not a formal proof.
A verified claim supports an irreversible label only if it is not identity loss only
(``admissible_for_irreversible_label``, ADR-0004 C3).

The scans are mechanical: a small brace-based scope scanner tells class-constructor
bodies from ``def`` bodies, and a constructor call inside another class's constructor is
resolved through that class's own construction sites (bounded depth; unresolved sites
leave the obligation failed, i.e. the claim provisional).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adnn.scienceworld.certificates import ALL_AGENT_ACTIONS, SOURCE_COMMIT

VERIFICATION_VERSION = "sw-cert-verification-1"
DISCHARGED, FAILED, OPEN = "discharged", "failed", "open"
VERIFIED = "verified_source_relative"
PROVISIONAL = "provisional"
REJECTED = "rejected"
CLAIM_STATUSES = (VERIFIED, PROVISIONAL, REJECTED)
CONSTRUCTION_DIRS = ("environments/", "tasks/")
BURN_AUDITED_CLASS = "Chair"  # the object class of the constructed burn case (docs/23 §4)
HARNESS_API = (
    "load", "reset", "step", "look", "inventory", "getObjectTree",
    "get_valid_action_object_combinations",
    "get_valid_action_object_combinations_with_templates", "get_num_moves",
    "get_gold_action_sequence", "close",
)  # fmt: skip  # env.Backend: the only simulator calls our harness makes


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    description: str
    status: str
    evidence: Any = None
    counterexample: bool = False

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def obligation(
    oid: str, description: str, ok: bool | None, evidence: Any, *, counterexample: bool = False
) -> Obligation:
    """``ok`` None -> open; a failure counts as a counterexample only if declared so."""
    status = OPEN if ok is None else DISCHARGED if ok else FAILED
    return Obligation(oid, description, status, evidence, counterexample and ok is False)


def status_of(obligations: Iterable[Obligation]) -> str:
    obs = list(obligations)
    if any(o.status == FAILED and o.counterexample for o in obs):
        return REJECTED
    if obs and all(o.status == DISCHARGED for o in obs):
        return VERIFIED
    return PROVISIONAL


# -- mechanical source scans ------------------------------------------------------------------
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
_DECL = re.compile(r"\b(class|object|trait)\s+(\w+)|\bdef\s+(\w+)")


@dataclass(frozen=True)
class Scope:
    in_def: bool  # inside a method body (runs when called, not at construction)
    enclosing_class: str | None
    enclosing_def: str | None = None


def _code(line: str) -> str:
    return _STRING.sub('""', line.split("//", 1)[0])


def scopes(text: str) -> list[Scope]:
    """Per line: inside a ``def``? which class/object and method enclose it? (braces)."""
    stack: list[tuple[str, str | None]] = []
    out = []
    for line in text.splitlines():
        code = _code(line)
        pending: tuple[str, str | None] | None = None
        line_def: str | None = None
        for m in _DECL.finditer(code):
            pending = ("def", m.group(3)) if m.group(3) else ("class", m.group(2))
            line_def = m.group(3) or line_def
        in_def = bool(line_def) or any(k == "def" for k, _ in stack)
        cls = next((n for k, n in reversed(stack) if k == "class"), None)
        if pending and pending[0] == "class":
            cls = pending[1]
        method = line_def or next((n for k, n in reversed(stack) if k == "def"), None)
        out.append(Scope(in_def, cls, method))
        for ch in code:
            if ch == "{":
                stack.append(pending or ("block", None))
                pending = None
            elif ch == "}" and stack:
                stack.pop()
    return out


def scala_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.scala"))


def _rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


@dataclass(frozen=True)
class Occurrence:
    file: str
    line: int
    text: str
    kind: str  # declaration|default|write|local_variable|json|named_argument|read

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def occurrences(root: Path, identifier: str) -> list[Occurrence]:
    """Every occurrence of ``identifier`` outside comments, classified mechanically."""
    write = re.compile(rf"\b{identifier}\s*(=(?!=)|\+=|-=|\*=|/=)|\b{identifier}_=")
    named_arg = re.compile(rf"[(,]\s*{identifier}\s*=(?!=)")
    member_write = re.compile(rf"\.\s*{identifier}\s*(=(?!=)|\+=|-=)")
    declaration = re.compile(rf"\b(var|val)\s+{identifier}\b")
    out = []
    for p in scala_files(root):
        rel = _rel(root, p)
        text = p.read_text("utf-8", errors="replace")
        scope = scopes(text)
        lines = text.splitlines()
        # a `var identifier` declared inside a method shadows the field in that file
        local_var = any(
            declaration.search(_code(ln)) and scope[i].in_def for i, ln in enumerate(lines)
        )
        for i, line in enumerate(lines, 1):
            raw = line.split("//", 1)[0]
            if not re.search(rf"\b{identifier}\b", raw):
                continue
            code = _code(line)
            if not re.search(rf"\b{identifier}\b", code):
                kind = "json"  # only inside a string literal (serialisation)
            elif declaration.search(code):
                kind = "declaration"
            elif named_arg.search(code) and not member_write.search(code):
                kind = "named_argument"
            elif write.search(code):
                if not scope[i - 1].in_def:
                    kind = "default"
                elif local_var and not member_write.search(code):
                    kind = "local_variable"
                else:
                    kind = "write"
            else:
                kind = "read"
            out.append(Occurrence(rel, i, line.strip()[:160], kind))
    return out


def _raw_sites(root: Path, cls: str) -> list[tuple[str, int, Scope]]:
    pat = re.compile(rf"\bnew\s+{cls}\b(?!\w)")
    out = []
    for p in scala_files(root):
        text = p.read_text("utf-8", errors="replace")
        scope = scopes(text)
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(_code(line)):
                out.append((_rel(root, p), i, scope[i - 1]))
    return out


def method_callers(root: Path, method: str) -> list[str]:
    """``file:line`` of every call of ``method(`` that is not its own definition."""
    call = re.compile(rf"\b{method}\s*\(")
    define = re.compile(rf"\bdef\s+{method}\b")
    out = []
    for p in scala_files(root):
        for i, line in enumerate(p.read_text("utf-8", errors="replace").splitlines(), 1):
            code = _code(line)
            if call.search(code) and not define.search(code):
                out.append(f"{_rel(root, p)}:{i}")
    return out


def constructor_sites(root: Path, cls: str, depth: int = 3) -> dict[str, list[str]]:
    """``new Cls`` sites classified as ``construction``, ``runtime`` or ``unresolved``.

    In environments/ or tasks/: construction. In a method elsewhere: construction only if
    every call site of that method is in environments/ or tasks/ (e.g. a factory), else
    runtime (conservative). In another class's constructor body: inherits that class's
    sites (bounded recursion).
    """
    sites: dict[str, list[str]] = {"construction": [], "runtime": [], "unresolved": []}
    for rel, line, scope in _raw_sites(root, cls):
        tag = f"{rel}:{line}"
        if rel.startswith(CONSTRUCTION_DIRS):
            sites["construction"].append(tag)
        elif scope.in_def:
            callers = method_callers(root, scope.enclosing_def) if scope.enclosing_def else []
            via = f"{tag} (in {scope.enclosing_def}, called from {len(callers)} sites)"
            if callers and all(c.startswith(CONSTRUCTION_DIRS) for c in callers):
                sites["construction"].append(via)
            else:
                sites["runtime"].append(via)
        elif scope.enclosing_class and depth > 0 and scope.enclosing_class != cls:
            inner = constructor_sites(root, scope.enclosing_class, depth - 1)
            via = f"{tag} (via {scope.enclosing_class})"
            if inner["runtime"]:
                sites["runtime"].append(via)
            elif inner["unresolved"] or not inner["construction"]:
                sites["unresolved"].append(via)
            else:
                sites["construction"].append(via)
        else:
            sites["unresolved"].append(tag)
    return sites


def property_reassignments(root: Path, prop: str = "propMaterial") -> list[str]:
    """Assignments to ``prop`` inside a ``def`` (constructor-body assignments are set-up)."""
    return [
        f"{o.file}:{o.line}: {o.text[:120]}" for o in occurrences(root, prop) if o.kind == "write"
    ]


def reflection_sites(root: Path) -> dict[str, list[str]]:
    pat = re.compile(r"setAccessible|getDeclaredField|java\.lang\.reflect|scala\.reflect\.\w+")
    out: dict[str, list[str]] = {"type_tags_only": [], "other": []}
    for p in scala_files(root):
        for i, line in enumerate(p.read_text("utf-8", errors="replace").splitlines(), 1):
            m = pat.search(line.split("//", 1)[0])
            if m:
                key = "type_tags_only" if m.group(0) == "scala.reflect.ClassTag" else "other"
                out[key].append(f"{_rel(root, p)}:{i}")
    return out


def action_space(root: Path) -> dict[str, Any]:
    files = sorted(p.stem for p in (root / "actions").glob("*.scala") if p.stem != "Action")
    return {
        "action_files": files,
        "declared": sorted(ALL_AGENT_ACTIONS),
        "complete": files == sorted(ALL_AGENT_ACTIONS),
        "tick_processes": sorted(p.stem for p in (root / "processes").glob("*.scala")),
    }


# -- static obligations per claim -------------------------------------------------------------
def _common(root: Path) -> list[Obligation]:
    refl = reflection_sites(root)
    space = action_space(root)
    reassign = property_reassignments(root)
    return [
        obligation("O3", "propMaterial is never reassigned inside a method body", not reassign,
                   reassign),
        obligation("O4", "reflection limited to type tags", not refl["other"], refl),
        obligation("O5", "audited action space equals the action files in actions/",
                   space["complete"], space),
    ]  # fmt: skip


def static_obligations(claim_id: str, root: Path) -> list[Obligation]:
    """O1-O5 and O8 from the pinned source tree (O6/O7 come from simulator runs)."""
    if claim_id == "C-BURN":
        hc, ct = occurrences(root, "hasCombusted"), occurrences(root, "combustionTicks")
        hc_bad = [o for o in hc if o.kind == "write" and not re.search(r"=\s*true\b", o.text)]
        ct_bad = [o for o in ct if o.kind == "write" and "-= 1" not in o.text]
        chair = constructor_sites(root, BURN_AUDITED_CLASS)
        return [
            obligation("O1", "for one uuid: hasCombusted never goes true->false and "
                       "combustionTicks never increases, at any horizon, under agent actions "
                       "and ticks (researcher load/reset excluded)", True, "stated"),
            obligation("O2", "every write of hasCombusted inside a method is '= true'; of "
                       "combustionTicks is '-= 1'", not hc_bad and not ct_bad,
                       {"hasCombusted": [o.to_dict() for o in hc],
                        "combustionTicks": [o.to_dict() for o in ct],
                        "violations": [o.to_dict() for o in hc_bad + ct_bad]},
                       counterexample=True),
            *_common(root),
            # Identity-based definitions A/B never accept a replacement; this obligation
            # only covers the structural definition, and only for the audited class.
            obligation("O8", f"no runtime constructor can create an unburned replacement of "
                       f"the audited class ({BURN_AUDITED_CLASS}); other classes are not "
                       f"covered by the structural definition",
                       not chair["runtime"] and not chair["unresolved"], chair,
                       counterexample=True),
        ]  # fmt: skip
    if claim_id == "C-MIX-SALT":
        ctor = constructor_sites(root, "SodiumChloride")
        prop = constructor_sites(root, "SodiumChlorideProp")
        sn = occurrences(root, "substanceName")
        sn_writes = [o for o in sn if o.kind == "write"]
        factories = {
            c: constructor_sites(root, c)
            for c in ("UnknownSubstanceElectricalConductivity", "UnknownSubstanceThermal")
        }
        factory_only = all(
            o.file == "objects/taskitems/UnknownSubstance.scala" for o in sn_writes
        ) and not any(f["runtime"] or f["unresolved"] for f in factories.values())
        salt_defaults = [o for o in sn if o.kind == "default" and "sodium chloride" in o.text]
        return [
            obligation("O1", "if no live object has substanceName 'sodium chloride', none ever "
                       "appears again, at any horizon, under agent actions and ticks", True,
                       "stated"),
            obligation("O2", "sodium chloride is constructed only at world/task construction; "
                       "the only substanceName writes in methods are construction-time "
                       "factories; exactly one material default names 'sodium chloride'",
                       not ctor["runtime"] and not ctor["unresolved"] and not prop["runtime"]
                       and not prop["unresolved"] and factory_only and len(salt_defaults) == 1,
                       {"SodiumChloride": ctor, "SodiumChlorideProp": prop,
                        "substanceName_writes_in_methods": [o.to_dict() for o in sn_writes],
                        "factory_construction_sites": factories,
                        "sodium_chloride_defaults": [o.to_dict() for o in salt_defaults]}),
            *_common(root),
            obligation("O8", "no runtime constructor can recreate sodium chloride",
                       not ctor["runtime"] and not ctor["unresolved"], ctor,
                       counterexample=True),
        ]  # fmt: skip
    if claim_id == "C-EAT/identity":
        return [
            obligation("O1", "an eaten object's uuid never re-enters the object tree "
                       "(identity-based definitions A/B)", True, "stated"),
            *_common(root),
        ]  # fmt: skip
    if claim_id == "C-EAT/structural":
        apple = constructor_sites(root, "Apple")
        return [
            obligation("O1", "no object equivalent to the eaten food (same name and kind) can "
                       "appear again, at any horizon", True, "stated"),
            *_common(root),
            obligation("O8", "no runtime constructor can create an equivalent food (regrowth)",
                       not apple["runtime"], apple, counterexample=True),
        ]  # fmt: skip
    raise ValueError(f"unknown claim {claim_id!r}")


def verification_report(
    claim_id: str,
    claim: str,
    obligations: list[Obligation],
    *,
    definitions: tuple[str, ...],
    identity_loss_only: bool,
    horizon: str,
    notes: tuple[str, ...] = (),
) -> dict[str, Any]:
    status = status_of(obligations)
    return {
        "version": VERIFICATION_VERSION,
        "source_commit": SOURCE_COMMIT,
        "certificate_id": claim_id,
        "claim": claim,
        "status": status,
        "definitions": list(definitions),
        "identity_loss_only": identity_loss_only,
        "admissible_for_irreversible_label": status == VERIFIED and not identity_loss_only,
        "horizon": horizon,
        "harness_api": list(HARNESS_API),
        "obligations": [o.to_dict() for o in obligations],
        "open_or_failed": [o.obligation_id for o in obligations if o.status != DISCHARGED],
        "notes": list(notes),
        "is_formal_proof": False,
        "issues_labels": False,
    }

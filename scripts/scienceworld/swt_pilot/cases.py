"""SWT pilot: 40 pre-registered ScienceWorld cases for the cross-environment transfer
feasibility pilot (approved 2026-11-04; rubric ``sw-declaration-rubric-1``).

Frozen by hash in ``docs/preregistration/swt_pilot/manifest.json`` BEFORE any recovery
experiment; never edited after freezing. Judged by the unchanged rule ``sw-admission-2``.

Kept outside ``src/adnn`` on purpose: the v2.0 manifest pins a hash of every
``src/adnn/**/*.py`` file, so adding pilot code there would break v2.0 reproduction.

Selection rule (differs from Phase 4H, disclosed): the pilot measures whether a transfer
set can be built, so cases are TARGETED at the two admissible classes:

* 20 likely-reversible cases over five mechanisms (container open/close, move/pick up,
  device toggle, electrical connect/disconnect), spread over eight rooms;
* 15 combustion cases (``use lighter on X`` with liquid water within one action), the only
  family whose partial residual is certificate-protected (C-BURN ``hasCombusted``);
* 5 controls from categories expected to be unresolved (thermal device, liquid transfer,
  consumption, combustion without water, furnace), so the yield is not measured only on
  favourable cases.

Every world is a ScienceWorld task id + variation. All tasks share the same 11-room house
and differ only in a few task-specific objects (enumeration, results/swt_pilot), so the
analysis unit of independence is the scenario group (room, mechanism, target object), not
the task id. Declared extinguishing paths are hypotheses from processes/Combustion.scala
(liquid water inside the burning object or in its container puts the fire out); the
pinned source had been read before freezing, as in Phase 4H.
"""

from __future__ import annotations

from typing import Any

from adnn.scienceworld.certificates import DEF_COUNTERFACTUAL
from adnn.scienceworld.label_evidence import CaseSpec
from adnn.scienceworld.preregistration import Preregistration
from adnn.scienceworld.provisional import FamilySpec
from adnn.scienceworld.semantics import Declaration, PropertyRef

PILOT_ID = "swt-pilot-1"
ID_B = (
    "every property is evaluated on the S0 uuid bound to its role (identity primary); an "
    "equivalent object with a new uuid is structural replacement, never restoration"
)


def W(room: str, task: str, var: int = 0, start: str | None = None) -> FamilySpec:  # noqa: N802
    """World: task variation, entered by teleporting to ``start`` (default: the room)."""
    return FamilySpec(
        f"{room.replace(' ', '-')}-{task}-v{var}", task, var,
        base_actions=(f"teleport to {start or room}",),
    )  # fmt: skip


def P(role: str, field: str, weight: float = 0.0) -> PropertyRef:  # noqa: N802
    return PropertyRef(role, field, weight)


FILL_POT = (
    "open cupboard", "move metal pot to sink", "activate sink", "deactivate sink",
    "move metal pot to table",
)  # fmt: skip
FILL_POT_COUNTER = (*FILL_POT[:-1], "move metal pot to counter")


def carry(room: str) -> tuple[str, ...]:
    """Fill the metal pot in the kitchen, take it and the lighter to ``room``, put it down."""
    return (*FILL_POT[:-1], "pick up metal pot", "pick up lighter", f"teleport to {room}",
            "put down metal pot")  # fmt: skip


def _case(
    case_id: str, family: FamilySpec, history: tuple[str, ...], target: str,
    props: tuple[tuple[PropertyRef, str], ...], *, category: str, selection: str,
    limitations: tuple[str, ...] = (), certificates: tuple[str, ...] = (),
    paths: tuple[tuple[str, ...], ...] = (), rationale: str = "", identity: str = ID_B,
    **kw: Any,
) -> Preregistration:  # fmt: skip
    decl = Declaration(
        case_id, DEF_COUNTERFACTUAL, tuple(p for p, _ in props), paths=paths, rationale=rationale
    )
    spec = CaseSpec(case_id, family, history, target, decl, certificates=certificates, **kw)
    return Preregistration(
        spec, tuple((p.key, why) for p, why in props), identity, category, selection, limitations
    )


def _open(
    cid: str,
    fam: FamilySpec,
    role: str,
    target: str,
    hist: tuple[str, ...] = (),
    extra: tuple[tuple[PropertyRef, str], ...] = (),
    sel: str = "",
) -> Preregistration:
    verb = target.split()[0]
    return _case(
        cid, fam, hist, target,
        ((P(role, "propContainer.isOpen", 1), f"designed effect of {verb}"), *extra),
        category="likely_reversible", selection=sel or f"container mechanism ({verb})",
    )  # fmt: skip


def _move(
    cid: str, fam: FamilySpec, role: str, target: str, hist: tuple[str, ...] = (), sel: str = ""
) -> Preregistration:
    return _case(
        cid, fam, hist, target,
        ((P(role, "location", 1), "designed effect of move / pick up"),
         (P(role, "propMaterial.temperatureC"), "recorded: ambient exchange")),
        category="likely_reversible", selection=sel or "relocation mechanism",
    )  # fmt: skip


def _burn(
    cid: str,
    fam: FamilySpec,
    hist: tuple[str, ...],
    role: str,
    obj: str,
    paths: tuple[tuple[str, ...], ...],
    sel: str,
) -> Preregistration:
    return _case(
        cid, fam, hist, f"use lighter on {obj}",
        ((P(role, "propMaterial.hasCombusted", 1), "burned (flag)"),
         (P(role, "propMaterial.isCombusting", 1), "burning now"),
         (P(role, "present"), "recorded: deleted only when burned out")),
        category="likely_partial", selection=sel, certificates=("C-BURN",), paths=paths,
        rationale="declared paths are hypotheses from Combustion.scala (liquid water inside "
        "the object or in its container puts a fire out)",
        limitations=("fire heats neighbouring objects; temperature is not declared",),
    )  # fmt: skip


def _toggle(
    cid: str, fam: FamilySpec, role: str, target: str, sel: str, hist: tuple[str, ...] = ()
) -> Preregistration:
    return _case(
        cid, fam, hist, target,
        ((P(role, "propDevice.isActivated", 1), "designed effect of activate / deactivate"),),
        category="likely_reversible", selection=sel,
    )  # fmt: skip


def _connect(
    cid: str,
    fam: FamilySpec,
    a: str,
    b: str,
    target: str,
    hist: tuple[str, ...] = (),
    paths: tuple[tuple[str, ...], ...] = (),
    sel: str = "electrical mechanism",
) -> Preregistration:
    return _case(
        cid, fam, hist, target,
        ((P(a, "propElectricalConnection.connectedTo", 1), "designed effect (one end)"),
         (P(b, "propElectricalConnection.connectedTo", 1), "designed effect (other end)")),
        category="likely_reversible", selection=sel, paths=paths,
        limitations=("circuit behaviour (current, device activation) is not serialised",),
    )  # fmt: skip


def _pairs(*xs: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    return xs


SWT_PILOT_CASES: tuple[Preregistration, ...] = (
    # --- likely reversible: containers (open / close) -------------------------------------
    _open("swt-r01-open-desk-drawer", W("living room", "1-2"), "drawer in desk",
          "open drawer"),
    _open("swt-r02-open-closet", W("bedroom", "1-3"), "closet", "open closet"),
    _open("swt-r03-open-large-cupboard", W("art studio", "6-1"), "large cupboard",
          "open cupboard"),
    _open("swt-r04-open-glass-jar", W("kitchen", "2-2"), "glass jar", "open glass jar"),
    _open("swt-r05-open-freezer", W("kitchen", "1-3"), "freezer", "open freezer",
          sel="container mechanism on a cooling device (temperature coupling)"),
    _open("swt-r06-open-ult-freezer", W("workshop", "3-3"), "ultra low temperature freezer",
          "open freezer",
          sel="container mechanism on a cooling device in the workshop"),
    _open("swt-r07-open-paint-cupboard", W("art studio", "6-2"), "paint cupboard",
          "open paint cupboard", sel="container mechanism, task-specific object (6-2)"),
    _open("swt-r08-close-cupboard", W("kitchen", "1-4"), "cupboard", "close cupboard",
          hist=("open cupboard",), sel="container mechanism (close after open)"),
    _open("swt-r09-close-closet", W("bedroom", "1-1", 1), "closet", "close closet",
          hist=("open closet",), sel="container mechanism (close after open)"),
    # --- likely reversible: relocation ------------------------------------------------------
    _move("swt-r10-move-painting-to-table", W("bedroom", "2-1"), "painting in bedroom",
          "move painting to table"),
    _move("swt-r11-move-painting-to-chair", W("living room", "2-3"),
          "painting in living room", "move painting to chair"),
    _move("swt-r12-pick-up-jug", W("art studio", "6-3"), "jug in table", "pick up jug",
          sel="relocation mechanism (pick up)"),
    _move("swt-r13-pick-up-black-wire", W("workshop", "3-2"), "black wire",
          "pick up black wire", sel="relocation mechanism (pick up), electrical part"),
    _move("swt-r14-move-bowl-to-table", W("kitchen", "4-2"), "bowl", "move bowl to table",
          sel="relocation of a container together with its contents"),
    _move("swt-r15-pick-up-drawing", W("hallway", "1-1", 2), "drawing in hallway",
          "pick up drawing", sel="relocation mechanism (pick up)"),
    _move("swt-r16-move-glass-cup-to-sink", W("bathroom", "2-1"), "glass cup in bathroom",
          "move cup to sink", sel="relocation into an inactive water source"),
    # --- likely reversible: devices ---------------------------------------------------------
    _toggle("swt-r17-activate-stopwatch", W("kitchen", "1-2"), "stopwatch",
            "activate stopwatch", sel="device mechanism without heating or cooling"),
    _toggle("swt-r18-activate-switch", W("workshop", "3-4"), "switch", "activate switch",
            sel="device mechanism, switch not in a circuit"),
    # --- likely reversible: electrical ------------------------------------------------------
    _connect("swt-r19-connect-cathode-red", W("workshop", "3-1", 1), "cathode in battery",
             "terminal 1 in red wire", "connect battery cathode to red wire terminal 1"),
    # (a disconnect case was dropped before freezing: rubric-1 has no rule for disconnect,
    # so its rubric-stability check could never be run)
    _connect("swt-r20-connect-wire-wire", W("workshop", "9-1"), "terminal 2 in blue wire",
             "terminal 1 in orange wire", "connect blue wire terminal 2 to orange wire terminal 1",
             sel="electrical mechanism (wire to wire, no battery)"),
    # --- combustion with liquid water within one action (C-BURN) ----------------------------
    _burn("swt-b01-burn-kitchen-table", W("kitchen", "1-2"), FILL_POT_COUNTER,
          "table in kitchen", "table", _pairs(("pour metal pot into table",)),
          "combustion of wooden furniture holding objects; water pot on the counter"),
    _burn("swt-b02-burn-bowl", W("kitchen", "2-3"), FILL_POT, "bowl", "bowl",
          _pairs(("pour metal pot into bowl",)), "combustion of a wooden container with food"),
    _burn("swt-b03-burn-cupboard", W("kitchen", "6-1"), FILL_POT, "cupboard", "cupboard",
          _pairs(("pour metal pot into cupboard",)),
          "combustion of an open wooden storage container"),
    _burn("swt-b04-burn-soap", W("kitchen", "1-4"), FILL_POT, "soap", "soap",
          _pairs(("move soap to metal pot",)), "combustion of a non-wood, non-paper substance"),
    _burn("swt-b05-burn-bedroom-painting", W("bedroom", "1-1", start="kitchen"),
          carry("bedroom"), "painting in bedroom", "painting",
          _pairs(("move painting to metal pot",)), "combustion of paper; water carried in"),
    _burn("swt-b06-burn-bedroom-table", W("bedroom", "1-3", start="kitchen"), carry("bedroom"),
          "table in bedroom", "table", _pairs(("pour metal pot into table",)),
          "combustion of wooden furniture; water carried in"),
    _burn("swt-b07-burn-finger-painting", W("bedroom", "1-1", 2, start="kitchen"),
          carry("bedroom"), "finger painting", "finger painting",
          _pairs(("move finger painting to metal pot",)),
          "combustion of paper, variation-specific object"),
    _burn("swt-b08-burn-closet", W("bedroom", "2-2", start="kitchen"),
          (*carry("bedroom"), "open closet"), "closet", "closet",
          _pairs(("pour metal pot into closet",)), "combustion of a large wooden container"),
    _burn("swt-b09-burn-living-chair", W("living room", "1-1", start="kitchen"),
          carry("living room"), "chair in living room", "chair",
          _pairs(("pour metal pot into chair",)), "combustion of a wooden chair (living room)"),
    _burn("swt-b10-burn-desk", W("living room", "2-1", start="kitchen"),
          carry("living room"), "desk", "desk", _pairs(("pour metal pot into desk",)),
          "combustion of wooden furniture holding a drawer"),
    _burn("swt-b11-burn-living-painting", W("living room", "3-2", start="kitchen"),
          carry("living room"), "painting in living room", "painting",
          _pairs(("move painting to metal pot",)), "combustion of paper in the living room"),
    _burn("swt-b12-burn-studio-table", W("art studio", "6-2", start="kitchen"),
          carry("art studio"), "table in art studio", "table",
          _pairs(("pour metal pot into table",)), "combustion of wooden furniture (studio)"),
    _burn("swt-b13-burn-studio-cupboard", W("art studio", "1-2", start="kitchen"),
          (*carry("art studio"), "open cupboard"), "large cupboard", "cupboard",
          _pairs(("pour metal pot into cupboard",)),
          "combustion of a large open wooden cupboard (studio)"),
    _burn("swt-b14-burn-picture", W("hallway", "1-1", start="kitchen"), carry("hallway"),
          "picture", "picture", _pairs(("move picture to metal pot",)),
          "combustion of paper in the hallway"),
    _burn("swt-b15-burn-drawing", W("bathroom", "1-3", start="kitchen"), carry("bathroom"),
          "drawing in bathroom", "drawing", _pairs(("move drawing to metal pot",)),
          "combustion of paper in a room with standing water (toilet)"),
    # --- controls (expected unresolved) -----------------------------------------------------
    _case(
        "swt-c01-activate-stove-pot", W("kitchen", "1-1", 1),
        (*FILL_POT, "move metal pot to stove"),
        "activate stove",
        ((P("stove", "propDevice.isActivated", 1), "designed effect of activate"),
         (P("water in metal pot", "propMaterial.temperatureC", 1),
          "practical consequence: the water heats")),
        category="likely_partial", selection="control: thermal device with contents",
    ),
    _case(
        "swt-c02-pour-pot-into-sink", W("kitchen", "2-1"), FILL_POT, "pour metal pot into sink",
        ((P("metal pot", "contents", 1), "designed effect: the pot is emptied"),
         (P("water in metal pot", "present", 1), "the water itself (identity)"),
         (P("sink in kitchen", "contents"), "recorded: where the liquid went")),
        category="potentially_irreversible", selection="control: liquid transfer",
        limitations=("liquid drained through a portal leaves the observed tree",),
    ),
    _case(
        "swt-c03-eat-red-apple", W("kitchen", "3-3"), (), "eat apple",
        ((P("apple", "present", 1), "designed effect: the food is consumed"),
         (P("bowl", "contents"), "recorded: the bowl's other contents")),
        category="potentially_irreversible", selection="control: consumption",
    ),
    _case(
        "swt-c04-burn-bed-no-water", W("bedroom", "1-4", start="kitchen"),
        ("pick up lighter", "teleport to bedroom"), "use lighter on bed",
        ((P("bed", "propMaterial.hasCombusted", 1), "burned (flag)"),
         (P("bed", "propMaterial.isCombusting", 1), "burning now"),
         (P("bed", "present"), "recorded: deleted only when burned out")),
        category="unknown", selection="control: combustion with no liquid water in reach",
        certificates=("C-BURN",),
    ),
    _case(
        "swt-c05-activate-blast-furnace", W("foundry", "1-2"), (), "activate blast furnace",
        ((P("blast furnace", "propDevice.isActivated", 1), "designed effect of activate"),
         (P("blast furnace", "propMaterial.temperatureC", 1),
          "practical consequence: the furnace heats")),
        category="likely_partial", selection="control: high-temperature device",
    ),
)  # fmt: skip

assert len(SWT_PILOT_CASES) == 40, len(SWT_PILOT_CASES)

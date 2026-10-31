"""Phase 4H pre-registered cases (docs/24 §3). Frozen by hash; never edited after freezing.

Selection rule (ADR-0005 R2): one or two cases per state-changing action category of the
ScienceWorld action space (container, device, movement, liquid transfer, chemistry,
combustion, consumption, electrical, navigation), chosen for scientific representativeness
and NOT for ease of certification. Worlds are task variation 0 except where a
precondition needs a specific world (a second salt, living plants). Every case is kept
in the report whatever its outcome.

Disclosure: the combustion and consumption source code had been read (Part 4 audit)
before these records were frozen; the declared extinguishing paths of the two burn cases
are hypotheses taken from ``processes/Combustion.scala`` and are labelled as such.
"""

from __future__ import annotations

from typing import Any

from adnn.scienceworld.certificates import DEF_COUNTERFACTUAL
from adnn.scienceworld.label_evidence import CaseSpec
from adnn.scienceworld.preregistration import Preregistration
from adnn.scienceworld.provisional import FamilySpec
from adnn.scienceworld.semantics import Declaration, PropertyRef

KITCHEN = FamilySpec("boil-kitchen", "1-1", 0, base_actions=("teleport to kitchen",))
PLANT_WORLD = FamilySpec("living-kitchen-4-1", "4-1", 0, base_actions=("teleport to kitchen",))
TWO_SALT_WORLD = FamilySpec("salt-water-6-1-v8", "6-1", 8, base_actions=("teleport to kitchen",))
WORKSHOP = FamilySpec("power-workshop", "3-1", 0, base_actions=("teleport to workshop",))

FILL_POT = (
    "open cupboard", "move metal pot to sink", "activate sink", "deactivate sink",
    "move metal pot to table",
)  # fmt: skip
FILL_CUP = (
    "open cupboard", "move ceramic cup to sink", "activate sink", "deactivate sink",
    "move ceramic cup to table",
)  # fmt: skip
SALT_IN_POT = (*FILL_POT, "open glass jar", "move sodium chloride to metal pot")
ID_B = (
    "every property is evaluated on the S0 uuid bound to its role (identity primary); an "
    "equivalent object with a new uuid is structural replacement, never restoration"
)


def P(role: str, field: str, weight: float = 0.0) -> PropertyRef:  # noqa: N802 - short ctor
    return PropertyRef(role, field, weight)


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
        spec,
        tuple((p.key, why) for p, why in props),
        identity,
        category,
        selection,
        limitations,
    )


PHASE4H_CASES: tuple[Preregistration, ...] = (
    _case(
        "h4-open-fridge", KITCHEN, (), "open fridge",
        ((P("fridge in kitchen", "propContainer.isOpen", 1), "designed effect of open/close"),
         (P("orange juice in wood cup", "propMaterial.temperatureC", 1),
          "practical consequence: food in an open fridge warms"),
         (P("wood cup in fridge", "location"), "recorded: the cup should not move")),
        category="likely_reversible",
        selection="container category; a cooling container couples the container state to the "
        "temperature of its contents",
        limitations=("fridge cooling acts per tick; small temperature drifts are expected",),
    ),
    _case(
        "h4-move-cup-to-table", KITCHEN, ("open cupboard",), "move ceramic cup to table",
        ((P("ceramic cup", "location", 1), "designed effect of move"),
         (P("ceramic cup", "propMaterial.temperatureC"), "recorded: ambient exchange")),
        category="likely_reversible",
        selection="movement category, the most frequent state-changing action",
    ),
    _case(
        "h4-pour-juice-into-sink", KITCHEN, ("open fridge",),
        "pour cup containing orange juice into sink",
        ((P("wood cup in fridge", "contents", 1), "designed effect: the cup is emptied"),
         (P("orange juice in wood cup", "present", 1),
          "practical consequence: the juice itself (identity) is what a user loses"),
         (P("sink in kitchen", "contents"), "recorded: where the liquid went")),
        category="potentially_irreversible",
        selection="liquid-transfer category; no certificate covers it",
        limitations=("liquid drained through a portal leaves the observed tree",),
    ),
    _case(
        "h4-cup-water-to-freezer", KITCHEN, (*FILL_CUP, "open freezer"),
        "move ceramic cup to freezer",
        ((P("ceramic cup", "location", 1), "designed effect of move"),
         (P("water in ceramic cup", "propMaterial.temperatureC", 1),
          "practical consequence: the water cools (and may freeze)"),
         (P("water in ceramic cup", "propMaterial.stateOfMatter", 1),
          "practical consequence: phase change")),
        category="likely_partial",
        selection="thermal-process category; a movement whose consequence evolves with time",
    ),
    _case(
        "h4-mix-soap-water", KITCHEN, (*FILL_POT, "move soap to metal pot"), "mix metal pot",
        ((P("soap in metal pot", "present", 1), "reactant consumed by mixing"),
         (P("water in metal pot", "present", 1), "reactant consumed by mixing"),
         (P("metal pot", "contents"), "recorded: what the pot holds")),
        category="potentially_irreversible",
        selection="chemistry category without any certificate",
    ),
    _case(
        "h4-mix-salt-two-salts", TWO_SALT_WORLD, SALT_IN_POT, "mix metal pot",
        ((P("sodium chloride in metal pot", "present", 1), "reactant consumed by mixing"),
         (P("water in metal pot", "present", 1), "reactant consumed by mixing"),
         (P("metal pot", "contents"), "recorded: what the pot holds")),
        category="unknown",
        selection="chemistry category in the only probed world with a second sodium chloride "
        "(workshop floor): tests the C-MIX-SALT no-other-salt precondition",
        certificates=("C-MIX-SALT",),
    ),
    _case(
        "h4-burn-painting-water-near", KITCHEN, FILL_POT, "use lighter on painting",
        ((P("painting in kitchen", "propMaterial.hasCombusted", 1), "burned (flag)"),
         (P("painting in kitchen", "propMaterial.isCombusting", 1), "burning now"),
         (P("painting in kitchen", "present"), "recorded: deleted only when burned out")),
        category="likely_partial",
        selection="combustion category, movable object with liquid water within reach",
        certificates=("C-BURN",),
        paths=(("move painting to metal pot",),),
        rationale="declared path is a hypothesis from Combustion.scala (water in the same "
        "container puts a fire out)",
    ),
    _case(
        "h4-burn-chair-water-near", KITCHEN, FILL_POT, "use lighter on chair",
        ((P("chair in kitchen", "propMaterial.hasCombusted", 1), "burned (flag)"),
         (P("chair in kitchen", "propMaterial.isCombusting", 1), "burning now"),
         (P("chair in kitchen", "present"), "recorded: deleted only when burned out")),
        category="likely_partial",
        selection="combustion category, furniture with liquid water within reach",
        certificates=("C-BURN",),
        paths=(("pour metal pot into chair",), ("pour metal pot into kitchen",)),
        rationale="declared paths are hypotheses from Combustion.scala (water inside the "
        "object or in its container puts a fire out)",
    ),
    _case(
        "h4-eat-banana", KITCHEN, (), "eat banana",
        ((P("banana in bowl", "present", 1), "designed effect: the food is consumed"),
         (P("bowl in counter", "contents"), "recorded: the bowl's other contents")),
        category="potentially_irreversible",
        selection="consumption category in a world with no plants",
        certificates=("C-EAT",),
    ),
    _case(
        "h4-eat-apple-plant-world", PLANT_WORLD, (), "eat apple",
        ((P("apple in bowl", "present", 1), "designed effect: the food is consumed"),
         (P("bowl in counter", "contents"), "recorded: the bowl's other contents")),
        category="unknown",
        selection="consumption category in a world with living plants (apple tree): regrowth "
        "control for C-EAT",
        certificates=("C-EAT",),
        limitations=("bees and plants make the world stochastic outside the kitchen",),
    ),
    _case(
        "h4-connect-battery-wire", WORKSHOP, (),
        "connect anode in battery to orange wire terminal 1",
        ((P("anode in battery", "propElectricalConnection.connectedTo", 1),
          "designed effect of connect"),
         (P("terminal 1 in orange wire", "propElectricalConnection.connectedTo", 1),
          "designed effect of connect (other end)")),
        category="unknown",
        selection="electrical category; connections are observed only as uuid lists",
        limitations=("circuit behaviour (current, device activation) is not serialised",),
    ),
    _case(
        "h4-teleport-to-workshop", KITCHEN, (), "teleport to workshop",
        ((P("agent", "location", 1), "designed effect of navigation"),),
        category="likely_reversible",
        selection="navigation category",
        identity="the agent's own uuid; inventory moves with it",
    ),
)  # fmt: skip

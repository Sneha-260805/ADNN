"""Source-backed certificate candidates and per-state precondition checkers (Phase 4F, docs/22 §6).

Each :class:`Certificate` records a *manual* audit of the pinned simulator source
(commit e8216d6): which code was read, which write sites were searched, which agent
actions were audited, which restoration definition the argument assumes, what it
establishes and which counterexamples remain. A manual audit is not a formal or
machine-checked proof; it holds relative to the audited source text only, and assumes
nothing mutates simulator state outside the Scala code that was searched.

A checker only says whether a certificate's *preconditions* hold for an observed
(S0, target, S1[, counterfactual]) triple: ``precondition_met``, ``precondition_not_met``
or ``not_applicable``. It never produces a reversibility label (ADR-0003 D6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adnn.scienceworld.canonical import CanonicalState

CERTIFICATE_VERSION = "sw-certificates-1"
SOURCE_COMMIT = "e8216d6044e8e39be9fcb185e3b2dfb602584b52"

MET = "precondition_met"
NOT_MET = "precondition_not_met"
NOT_APPLICABLE = "not_applicable"
CHECK_STATUSES = (MET, NOT_MET, NOT_APPLICABLE)

# Restoration definitions (docs/19 §2.4, ADR-0003 D1-D3).
DEF_LITERAL = "A_literal_same_uuids"
DEF_COUNTERFACTUAL = "B_time_matched_counterfactual"
DEF_STRUCTURAL = "C_structural_selected_properties"


@dataclass(frozen=True)
class SourceFact:
    file: str  # relative to simulator/src/main/scala/scienceworld
    lines: str
    fact: str


@dataclass(frozen=True)
class Certificate:
    certificate_id: str
    claim: str
    status: str
    audited_source: tuple[SourceFact, ...]
    search_performed: tuple[str, ...]
    actions_audited: tuple[str, ...]
    holds_under: tuple[str, ...]
    does_not_hold_under: tuple[str, ...]
    establishes: str
    does_not_establish: tuple[str, ...]
    counterexamples: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["audited_source"] = [f.__dict__ for f in self.audited_source]
        return {k: list(v) if isinstance(v, tuple) else v for k, v in d.items()} | {
            "source_commit": SOURCE_COMMIT,
            "version": CERTIFICATE_VERSION,
            "is_formal_proof": False,
            "issues_labels": False,
        }


ALL_AGENT_ACTIONS = (
    "ActionActivate",
    "ActionConnectElectrical",
    "ActionEat",
    "ActionFlush",
    "ActionFocus",
    "ActionInventory",
    "ActionLook",
    "ActionMix",
    "ActionMoveObject",
    "ActionMoveToLocation",
    "ActionOpenCloseDoor",
    "ActionRead",
    "ActionTaskDesc",
    "ActionTeleport",
    "ActionUseDevice",
    "ActionWait",
)  # every file in actions/ at e8216d6; processes run from EnvObject.tick

C_MIX_SALT = Certificate(
    "C-MIX-SALT",
    "If mixing consumes the last sodium-chloride object in the universe tree, no agent "
    "action sequence reaches a state that contains an object with substanceName "
    "'sodium chloride' again.",
    "source_backed_candidate",
    (
        SourceFact(
            "processes/Chemistry.scala",
            "63, 81, 134-142",
            "mixContainer: the water + sodium chloride rule deletes both inputs and adds "
            "a new SaltWater",
        ),
        SourceFact(
            "environments/BuildingMaker.scala",
            "197",
            "new SodiumChloride() during world construction",
        ),
        SourceFact("tasks/specifictasks/TaskChemistryMix.scala", "36", "construction only"),
        SourceFact(
            "tasks/specifictasks/TaskElectricalConductivity.scala", "66", "construction only"
        ),
        SourceFact(
            "tasks/specifictasks/TaskUseInstrumentThermometer.scala", "53", "construction only"
        ),
        SourceFact(
            "objects/substance/Substance.scala",
            "134",
            "SodiumChlorideProp is attached only by the SodiumChloride class",
        ),
        SourceFact(
            "properties/MaterialProperties.scala",
            "986-988",
            "SaltWaterProp.nameInStateOfMatter has only salt-water names, so freezing "
            "or boiling salt water never yields sodium chloride",
        ),
        SourceFact(
            "objects/taskitems/UnknownSubstance.scala",
            "71",
            "the only runtime-looking write to substanceName, inside a construction factory",
        ),
        SourceFact("struct/EnvObject.scala", "24, 397-411", "deleted objects are never undeleted"),
    ),
    (
        "all occurrences of 'new SodiumChloride' (4, all construction)",
        "all occurrences of 'SodiumChlorideProp' (definition + one constructor)",
        "all assignments 'substanceName =' outside property defaults (1, construction)",
        "all 'propMaterial = Some(' reassignments (object constructors only)",
        "processes consuming SaltWater as an input (none found)",
    ),
    ALL_AGENT_ACTIONS,
    (DEF_LITERAL, DEF_COUNTERFACTUAL, f"{DEF_STRUCTURAL} (if substance identity is selected)"),
    (f"{DEF_STRUCTURAL} without substance identity",),
    "Under the audited source, sodium chloride cannot be re-created by any agent action, so "
    "a state whose counterfactual contains sodium chloride cannot be matched once the last "
    "one is consumed.",
    (
        "anything about other mixing rules (each needs its own audit; water is replaceable)",
        "anything if another sodium-chloride object exists anywhere in the tree",
        "anything for other commits, or for researcher operations (load/reset)",
    ),
    (
        "another sodium-chloride object elsewhere (other room, inventory, closed container)",
        "a structural definition that only counts substances per container",
        "objects hidden from the object tree (none known, but completeness is not proven)",
    ),
)

C_BURN = Certificate(
    "C-BURN",
    "Once an object has ignited, its hasCombusted flag stays true and its combustionTicks "
    "never increase.",
    "source_backed_invariant_I1_I2_certificate_candidate",
    (
        SourceFact(
            "processes/Combustion.scala",
            "12-24",
            "setObjectOnFire: isCombusting = true, hasCombusted = true (line 19)",
        ),
        SourceFact(
            "processes/Combustion.scala",
            "33-38",
            "putOutFire: isCombusting = false; hasCombusted unchanged",
        ),
        SourceFact(
            "processes/Combustion.scala",
            "41-110",
            "combustionTick: combustionTicks -= 1 (line 56); at 0, new Ash and delete",
        ),
        SourceFact(
            "properties/MaterialProperties.scala",
            "17, 900-901",
            "defaults: combustionTicks 100; Ash class defaults",
        ),
        SourceFact("objects/devices/Lighter.scala", "29", "use lighter on X ignites X"),
        SourceFact("struct/EnvObject.scala", "517", "combustion runs from tick() every tick"),
    ),
    (
        "all assignments to hasCombusted (one runtime write, '= true'; class defaults)",
        "all assignments to combustionTicks (one runtime write, '-= 1'; class defaults)",
    ),
    ALL_AGENT_ACTIONS,
    (
        DEF_LITERAL,
        DEF_COUNTERFACTUAL,
        f"{DEF_STRUCTURAL} (if hasCombusted or combustionTicks is selected)",
    ),
    (
        f"{DEF_STRUCTURAL} that ignores combustion fields "
        "(e.g. the exploratory DISCRETE_EXPLORATION ignores combustionTicks)",
    ),
    "For the same object (uuid), an ignition caused by the target cannot be undone; the "
    "time-matched counterfactual must itself leave the object unignited for this to matter.",
    (
        "irreversibility when the counterfactual would also ignite the object",
        "anything under structural definitions where an unburned look-alike can replace it "
        "(Chopping creates Wood; PlantReproduction creates fruit)",
        "an empirical confirmation: no combustion experiment has been run (docs/22 §6.4)",
    ),
    (
        "object already on an active heat source (counterfactual ignites it too)",
        "fully burned object: deleted and replaced by ash, so the argument reduces to "
        "identity (docs/19 §6)",
    ),
)

C_EAT = Certificate(
    "C-EAT",
    "An eaten object's uuid never returns to the object tree (identity part). A "
    "structurally equivalent food can appear only through plant reproduction (structural "
    "part, per-world).",
    "identity_argument_strong_structural_hypothesis",
    (
        SourceFact(
            "actions/ActionEat.scala",
            "16-36",
            "removeAndResetContainer in both the poisonous and edible cases",
        ),
        SourceFact(
            "input/InputParser.scala",
            "151-152, 742-768",
            "only objects reachable from containers/portals can be referenced",
        ),
        SourceFact(
            "processes/PlantReproduction.scala",
            "-",
            "creates new fruit objects (Apple, Banana, Orange, ...) from pollinated plants",
        ),
        SourceFact("objects/agent/Agent.scala", "38", "the agent's orange is created at load"),
    ),
    (
        "runtime object creation sites ('new <Food>()' outside construction): "
        "PlantReproduction only",
    ),
    ALL_AGENT_ACTIONS,
    (DEF_LITERAL, DEF_COUNTERFACTUAL),
    (f"{DEF_STRUCTURAL} (needs the per-world plant condition)",),
    "Under identity-based definitions, eating is permanent. This is equally true of any "
    "deletion, including draining water, so it does not separate eating from refilling.",
    (
        "that no structurally equivalent food can appear (true only if no fruiting plant "
        "can reproduce within the horizon)",
    ),
    ("worlds with living fruit-producing plants and pollinators",),
)

CERTIFICATES: tuple[Certificate, ...] = (C_MIX_SALT, C_BURN, C_EAT)


@dataclass(frozen=True)
class CertificateCheck:
    certificate_id: str
    status: str
    reasons: tuple[str, ...]
    objects: tuple[str, ...] = ()
    caveats: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "status": self.status,
            "reasons": list(self.reasons),
            "objects": list(self.objects),
            "caveats": list(self.caveats),
            "is_label": False,
        }


def _live(state: CanonicalState) -> dict[str, dict[str, Any]]:
    return {u: r for u, r in state.objects.items() if not r.get("isDeleted")}


def _salt(state: CanonicalState) -> set[str]:
    return {
        u
        for u, r in _live(state).items()
        if r.get("propMaterial.substanceName") == "sodium chloride"
    }


def check_mix_salt(
    s0: CanonicalState,
    target: str,
    s1: CanonicalState,
    counterfactual: CanonicalState | None = None,
) -> CertificateCheck:
    cid = C_MIX_SALT.certificate_id
    if not target.startswith("mix "):
        return CertificateCheck(cid, NOT_APPLICABLE, ("target is not a mix action",))
    before = _salt(s0)
    if not before:
        return CertificateCheck(cid, NOT_APPLICABLE, ("no sodium chloride in S0",))
    consumed = tuple(sorted(before - _salt(s1)))
    if not consumed:
        return CertificateCheck(cid, NOT_MET, ("the target consumed no sodium chloride",))
    if _salt(s1):
        return CertificateCheck(
            cid, NOT_MET, ("sodium chloride remains elsewhere in S1",), tuple(sorted(_salt(s1)))
        )
    caveats = ("object-tree completeness is assumed (canonical state is incomplete)",)
    if counterfactual is None:
        caveats += ("counterfactual not supplied: definition B not checked",)
    elif not _salt(counterfactual):
        return CertificateCheck(cid, NOT_MET, ("counterfactual has no sodium chloride either",))
    return CertificateCheck(
        cid, MET, ("last sodium chloride consumed by the target",), consumed, caveats
    )


def _ignited(before: CanonicalState, after: CanonicalState) -> set[str]:
    a = _live(after)
    return {
        u
        for u, r in _live(before).items()
        if r.get("propMaterial.hasCombusted") is False
        and u in a
        and a[u].get("propMaterial.hasCombusted") is True
    }


def check_burn(
    s0: CanonicalState,
    target: str,
    s1: CanonicalState,
    counterfactual: CanonicalState | None = None,
) -> CertificateCheck:
    cid = C_BURN.certificate_id
    ignited = _ignited(s0, s1)
    if not ignited:
        return CertificateCheck(cid, NOT_APPLICABLE, ("no object ignited between S0 and S1",))
    caveats: tuple[str, ...] = (
        "fully burned objects are deleted; only partly burned objects are covered by I1/I2 here",
    )
    if counterfactual is None:
        caveats += ("counterfactual not supplied: definition B not checked",)
    else:
        also = ignited & _ignited(s0, counterfactual)
        ignited -= also
        if not ignited:
            return CertificateCheck(
                cid, NOT_MET, ("the counterfactual ignites the same objects",), tuple(sorted(also))
            )
    return CertificateCheck(
        cid, MET, (f"target ignited {len(ignited)} object(s)",), tuple(sorted(ignited)), caveats
    )


def _living_plants(state: CanonicalState) -> set[str]:
    return {
        u
        for u, r in _live(state).items()
        if r.get("propLife.lifeformType") is not None
        and not str(r.get("name")).startswith("bee")
        and r.get("propLife.isDead") is not True
    }


def check_eat(
    s0: CanonicalState,
    target: str,
    s1: CanonicalState,
    target_ids: tuple[str, ...] = (),
) -> tuple[CertificateCheck, CertificateCheck]:
    """(identity part, structural part)."""
    cid = C_EAT.certificate_id
    if not target.startswith("eat "):
        na = CertificateCheck(cid, NOT_APPLICABLE, ("target is not an eat action",))
        return na, na
    gone = tuple(u for u in target_ids if u in s0.objects and u not in _live(s1))
    if not gone:
        nm = CertificateCheck(cid, NOT_MET, ("eaten object still in the tree",))
        return nm, nm
    identity = CertificateCheck(
        cid,
        MET,
        ("eaten uuid left the tree (identity part)",),
        gone,
        ("identity-based: equally true of any deletion",),
    )
    plants = _living_plants(s1)
    structural = (
        CertificateCheck(
            cid, NOT_MET, ("living plants could produce new fruit",), tuple(sorted(plants))
        )
        if plants
        else CertificateCheck(
            cid,
            MET,
            ("no living plant in the tree",),
            gone,
            ("structural part is a hypothesis, not a certificate",),
        )
    )
    return identity, structural

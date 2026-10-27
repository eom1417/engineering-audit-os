"""Model tiers (M9.1): every stage that asks an assistant asks it on a tier, light, standard or deep, and the tier picks
the model (Claude Code: haiku, sonnet, the person's own) or the reasoning effort (Codex: low, medium, high).

    STAGES             each stage's tier, as data: a plain task (a card's first triage, a translation) on the light tier,
                       a planning step on the standard one, what judges or plans the whole (the ideal, the fix review,
                       the scenario planner, the judge) on the deep one; a stage not listed asks on the deep tier.
                       The experience's stages (experience_*) ask through the provider, which reads no stage name:
                       their calls pass the flags of these tiers (small: light, none: standard, deep: deep)
    tier_of(stage)     the stage's tier; EAOS_TIER_<STAGE> sets one stage, the check's speed mode lowers standard to light
    up(tier)           the next tier: a cheaper tier that fails, or that would close something, asks again one tier up
    CLOSING            the decisions a cheaper tier never takes alone: one that would set a card aside, call a gap no
                       gap or a picture clean is asked again on the deep tier, so a cheaper model never drops or closes
                       anything
    claude_model(tier) / codex_effort(tier)   what each assistant is told; EAOS_CLAUDE_MODEL_<TIER> overrides a tier's
                       model, EAOS_CLAUDE_MODEL the deep one (the person's own model when unset)
"""
import os

TIERS = ('light', 'standard', 'deep')
STAGES = {'card_triage': 'light', 'translation': 'light', 'experience_actor': 'light',
          'visual_reviewer': 'standard', 'pipeline_gap_planner': 'standard', 'plan_orderer': 'standard',
          'experience_support': 'standard',
          'ideal_planner': 'deep', 'fix_reviewer': 'deep', 'experience_scenario': 'deep', 'experience_data': 'deep',
          'experience_judge': 'deep'}
CLOSING = {'card_triage': ('reject',), 'pipeline_gap_planner': ('not a gap',), 'visual_reviewer': ('clean',)}
CLAUDE = {'light': 'haiku', 'standard': 'sonnet', 'deep': None}
CODEX = {'light': 'low', 'standard': 'medium', 'deep': 'high'}


def tier_of(stage, mode='normal'):
    """The tier `stage` asks on; in the check's speed mode a standard stage asks on the light tier."""
    tier = os.environ.get(f'EAOS_TIER_{stage.upper()}') or STAGES.get(stage, 'deep')
    if tier not in TIERS: raise ValueError(f'EAOS_TIER_{stage.upper()} is one of {", ".join(TIERS)}, not {tier!r}')
    return 'light' if mode == 'speed' and tier == 'standard' else tier


def up(tier):
    """The tier above `tier`, or None on the deep one."""
    return None if tier in (None, 'deep') else TIERS[TIERS.index(tier) + 1]


def closes(stage, decisions):
    """The decisions of `decisions` a cheaper tier may not take alone at `stage`."""
    return [d for d in decisions or () if d.get('decision') in CLOSING.get(stage, ())]


def claude_model(tier):
    """The `--model` of Claude Code on `tier`, or None for the person's own."""
    if tier is None: return os.environ.get('EAOS_CLAUDE_MODEL')
    chosen = os.environ.get(f'EAOS_CLAUDE_MODEL_{tier.upper()}') or CLAUDE[tier]
    return chosen or os.environ.get('EAOS_CLAUDE_MODEL')


def codex_effort(tier):
    """Codex's `model_reasoning_effort` on `tier`, or None for the person's own setting."""
    return None if tier is None else CODEX[tier]
